import asyncio
import base64
import binascii
from contextlib import asynccontextmanager
from pathlib import Path
from threading import RLock
from time import perf_counter
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import text

from .contracts import Decision, Session
from .diagnostics import request_completed
from .integrations import ProviderConfigurationError, Providers, Settings
from .policies import evaluate
from .seed import DEMO_ANSWERS, seed_session
from .services import Apprenticeship, DomainError
from .storage import Store
from .workflow import Workflow

ALLOWED_ORIGINS = {
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
}


class CreateSession(BaseModel):
    mode: Literal["simulated", "live"] = "simulated"


class Recording(BaseModel):
    consent: bool
    off_record: bool


class Answer(BaseModel):
    condition: str = Field(max_length=100)
    text: str = Field(min_length=1, max_length=4000)
    scripted: bool = False


class Correction(BaseModel):
    rule_id: str
    reason: str = Field(min_length=1, max_length=4000)


class Confirmation(BaseModel):
    version: int
    explicit: bool


class DecisionInput(BaseModel):
    decision: Decision
    reason: str = Field(min_length=1, max_length=4000)


class Frame(BaseModel):
    image: str = Field(max_length=1_500_000)


class ToolContext(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    role: Literal["interviewer", "tutor"]
    case_id: str | None = Field(default=None, max_length=100)
    challenge_id: str | None = Field(default=None, max_length=100)


class VoiceContext(BaseModel):
    challenge_id: str | None = Field(default=None, min_length=1, max_length=100)


class Transcript(BaseModel):
    speaker: Literal["user", "agent"]
    text: str = Field(min_length=1, max_length=4000)


def create_app(data_dir: Path | None = None, settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    directory = data_dir or Path(settings.ja_data_dir)
    store = Store(directory)
    workflow = Workflow(directory)
    service = Apprenticeship(store, workflow)
    providers = Providers(settings)
    lock = RLock()
    busy: set[str] = set()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        workflow.connection.close()
        store.engine.dispose()

    app = FastAPI(title="Judgment Apprentice", lifespan=lifespan)
    app.state.store, app.state.service, app.state.providers = store, service, providers
    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(ALLOWED_ORIGINS),
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type"],
    )

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        origin = request.headers.get("origin")
        host = request.headers.get("host", "").split(":")[0]
        if host not in {"localhost", "127.0.0.1", "testserver"}:
            return JSONResponse({"detail": "This MVP is local-only."}, status_code=403)
        if origin and origin not in ALLOWED_ORIGINS:
            return JSONResponse({"detail": "Origin is not allowed."}, status_code=403)
        started = perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            request_completed(
                request.method, request.url.path, status, int((perf_counter() - started) * 1000)
            )

    @app.exception_handler(DomainError)
    async def domain_error(request: Request, error: DomainError):
        return JSONResponse({"detail": str(error)}, status_code=409)

    @app.exception_handler(KeyError)
    async def missing(request: Request, error: KeyError):
        return JSONResponse({"detail": "Session or artifact no longer exists."}, status_code=404)

    def session(session_id: str) -> Session:
        return store.get(session_id)

    @app.get("/health")
    def health():
        return {"status": "alive"}

    @app.get("/ready")
    def ready():
        try:
            with store.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            workflow.connection.execute("SELECT 1")
        except Exception as error:
            raise HTTPException(503, "Local persistence is unavailable") from error
        return {
            "status": "ready",
            "simulated": True,
            "live_vision_configured": bool(settings.openai_api_key),
            "live_voice_configured": bool(
                settings.elevenlabs_api_key
                and settings.elevenlabs_interviewer_agent_id
                and settings.elevenlabs_tutor_agent_id
            ),
        }

    @app.get("/api/sessions")
    def list_sessions():
        return store.list()

    @app.post("/api/sessions")
    def create(body: CreateSession):
        item = seed_session(str(uuid4()), body.mode)
        with lock:
            workflow.start(item.id)
            store.save(item)
        return item

    @app.get("/api/sessions/{session_id}")
    def get_session(session_id: str):
        return session(session_id)

    @app.delete("/api/sessions/{session_id}")
    def delete_session(session_id: str):
        with lock:
            session(session_id)
            workflow.remove(session_id)
            store.remove(session_id)
        return {"deleted": True, "derived_knowledge_invalidated": True}

    @app.post("/api/sessions/{session_id}/recording")
    def recording(session_id: str, body: Recording):
        with lock:
            item = session(session_id)
            item.consent, item.off_record = body.consent, body.off_record
            item.recording_revision += 1
            store.save(item)
        return item

    @app.post("/api/sessions/{session_id}/questions")
    def question(session_id: str):
        with lock:
            item = session(session_id)
            question = service.ask(item)
            store.save(item)
        case_id = next(
            (
                event.payload.get("case_id")
                for event in reversed(item.events)
                if event.event_type == "question"
            ),
            None,
        )
        return {"question": question, "case_id": case_id, "session": item}

    @app.post("/api/sessions/{session_id}/answers")
    def answer(session_id: str, body: Answer):
        with lock:
            item = session(session_id)
            if body.scripted and item.mode != "simulated":
                raise DomainError("Scripted answers are available only in simulated mode")
            content = DEMO_ANSWERS.get(body.condition, "") if body.scripted else body.text
            if not content:
                raise DomainError("Unknown scripted answer")
            service.answer(item, body.condition, content, body.scripted)
            store.save(item)
        return item

    @app.post("/api/sessions/{session_id}/debrief")
    def debrief(session_id: str):
        with lock:
            item = session(session_id)
            service.debrief(item)
            store.save(item)
        return item

    @app.post("/api/sessions/{session_id}/gaps")
    def gap(session_id: str, body: Answer):
        with lock:
            item = session(session_id)
            if body.scripted and item.mode != "simulated":
                raise DomainError("Scripted answers are available only in simulated mode")
            content = DEMO_ANSWERS.get(body.condition, "") if body.scripted else body.text
            if not content:
                raise DomainError("Unknown gap answer")
            service.fill_gap(item, body.condition, content, body.scripted)
            store.save(item)
        return item

    @app.post("/api/sessions/{session_id}/map/correct")
    def correct(session_id: str, body: Correction):
        with lock:
            item = session(session_id)
            service.correct(item, body.rule_id, body.reason)
            store.save(item)
        return item

    @app.post("/api/sessions/{session_id}/map/teach-back")
    def teach_back(session_id: str):
        with lock:
            item = session(session_id)
            service.teach_back(item)
            store.save(item)
        return item

    @app.post("/api/sessions/{session_id}/map/confirm")
    def confirm(session_id: str, body: Confirmation):
        with lock:
            item = session(session_id)
            service.confirm(item, body.version, body.explicit)
            store.save(item)
        return item

    @app.get("/api/sessions/{session_id}/map")
    def work_map(session_id: str):
        return session(session_id).work_map

    @app.get("/api/sessions/{session_id}/evidence/{event_id}")
    def evidence(session_id: str, event_id: str):
        event = next(
            (event for event in session(session_id).events if event.event_id == event_id), None
        )
        if event is None:
            raise HTTPException(404, "Evidence no longer exists")
        return event

    @app.get("/api/sessions/{session_id}/cases/{case_id}")
    def get_case(session_id: str, case_id: str):
        case = next((case for case in session(session_id).cases if case.id == case_id), None)
        if case is None:
            raise HTTPException(404, "Case not found")
        return case

    @app.post("/api/sessions/{session_id}/cases/{case_id}/observe")
    def observe_case(session_id: str, case_id: str):
        with lock:
            item = session(session_id)
            service.observe_case(item, case_id)
            store.save(item)
        return item

    @app.post("/api/sessions/{session_id}/cases/{case_id}/validate")
    def validate(session_id: str, case_id: str):
        case = get_case(session_id, case_id)
        return {"violations": evaluate(case), "ready": not evaluate(case)}

    @app.post("/api/sessions/{session_id}/cases/{case_id}/decision")
    def save_decision(session_id: str, case_id: str, body: DecisionInput):
        with lock:
            item = session(session_id)
            case = next((case for case in item.cases if case.id == case_id), None)
            if case is None:
                raise HTTPException(404, "Case not found")
            violations = evaluate(case)
            if body.decision == Decision.READY and violations:
                return JSONResponse(
                    {"saved": False, "violations": [v.model_dump() for v in violations]},
                    status_code=409,
                )
            case.decision, case.justification = body.decision, body.reason
            if item.consent and not item.off_record:
                service.event(
                    item,
                    "sandbox_decision",
                    "sandbox",
                    {"case_id": case_id, "decision": body.decision.value, "reason": body.reason},
                )
            store.save(item)
        return {"saved": True, "session": item}

    @app.post("/api/sessions/{session_id}/challenges/{challenge_id}/approve")
    def approve_challenge(session_id: str, challenge_id: str, body: Confirmation):
        with lock:
            item = session(session_id)
            service.recording(item)
            challenge = service.challenge(item, challenge_id)
            if (
                item.phase != "training"
                or not body.explicit
                or body.version != challenge.map_version
            ):
                raise DomainError("Explicit expert challenge approval is required")
            challenge.approved = True
            service.event(item, "challenge_approved", "expert", {"challenge_id": challenge_id})
            store.save(item)
        return item

    @app.post("/api/sessions/{session_id}/challenges/{challenge_id}/answer")
    def assess(session_id: str, challenge_id: str, body: DecisionInput):
        with lock:
            item = session(session_id)
            result = service.assess(item, challenge_id, body.decision, body.reason)
            store.save(item)
        return {**result, "session": item}

    @app.post("/api/sessions/{session_id}/challenges/{challenge_id}/hint")
    def hint(session_id: str, challenge_id: str):
        with lock:
            item = session(session_id)
            service.recording(item)
            challenge = service.challenge(item, challenge_id)
            if item.phase != "training" or not challenge.approved:
                raise DomainError("Hints require a currently approved training challenge")
            if challenge.assessment:
                raise DomainError(
                    "Hints are reduced in this independent assessment. Escalate uncertainty."
                )
            attempt = next((a for a in item.attempts if a.challenge_id == challenge_id), None)
            if attempt is None:
                raise DomainError("Record your independent first answer before requesting a hint")
            attempt.hint_used = True
            relevant = {violation.rule_id for violation in evaluate(challenge.case)}
            rules = [
                rule
                for rule in item.work_map.rules
                if rule.kind in relevant and rule.status == "expert_confirmed"
            ]
            store.save(item)
        return {
            "rules": rules,
            "session": item,
            "boundary": "Unresolved situations require escalation to the release owner.",
        }

    @app.post("/api/sessions/{session_id}/results")
    def results(session_id: str):
        with lock:
            item = session(session_id)
            if (
                item.phase != "training"
                or not item.challenges
                or not all(challenge.approved for challenge in item.challenges)
                or {attempt.challenge_id for attempt in item.attempts}
                != {challenge.id for challenge in item.challenges}
            ):
                raise DomainError("Attempt every approved challenge before opening results")
            item.phase = workflow.advance(item.id, [], item.work_map.version)
            store.save(item)
        return item

    @app.post("/api/sessions/{session_id}/tools/context")
    def tool_context(session_id: str, body: ToolContext):
        with lock:
            item = session(session_id)
            service.recording(item)
            if body.session_id != item.id:
                raise DomainError("The tool must reference its active session")
            if body.case_id and body.challenge_id:
                raise DomainError("Choose a sandbox case or a learner challenge")
            case = None
            tutor_attempt = None
            if body.role == "tutor":
                tutor_attempt = service.require_tutor_assistance(item, body.challenge_id)
            if body.case_id:
                case = next((case for case in item.cases if case.id == body.case_id), None)
                if case is None:
                    raise DomainError("Case does not belong to the active session")
            if body.challenge_id:
                challenge = service.challenge(item, body.challenge_id)
                if not challenge.approved:
                    raise DomainError("Challenge requires expert approval")
                case = challenge.case
            if tutor_attempt is not None:
                tutor_attempt.hint_used = True
                store.save(item)
            return {
                "session_id": item.id,
                "phase": item.phase,
                "map_version": item.work_map.version,
                "map_status": item.work_map.status,
                "work_map": item.work_map,
                "case": case,
                "screen_content_is_untrusted_data": True,
                "boundary": "Use only confirmed supported rules. Escalate unresolved situations "
                "to the release owner. This tool cannot save or approve a decision.",
            }

    @app.post("/api/sessions/{session_id}/voice/{role}")
    def voice(
        session_id: str, role: Literal["interviewer", "tutor"], body: VoiceContext | None = None
    ):
        challenge_id = body.challenge_id if body else None
        with lock:
            item = session(session_id)
            service.recording(item)
            revision = item.recording_revision
            if item.mode != "live":
                raise DomainError("Voice provider connections require an explicitly live session")
            if role == "tutor":
                service.require_tutor_assistance(item, challenge_id)
        try:
            signed_url = providers.signed_url(role)
        except ProviderConfigurationError as error:
            raise HTTPException(503, str(error)) from error
        except Exception as error:
            raise HTTPException(
                502, "Voice connection failed. Check agent configuration and retry."
            ) from error
        with lock:
            current = session(session_id)
            service.recording(current)
            tutor_attempt = None
            if role == "tutor":
                tutor_attempt = service.require_tutor_assistance(current, challenge_id)
            if current.recording_revision != revision:
                raise DomainError("Recording controls changed while voice was connecting. Retry.")
            if tutor_attempt is not None:
                tutor_attempt.hint_used = True
                store.save(current)
        return {"signed_url": signed_url}

    @app.post("/api/sessions/{session_id}/transcript")
    def transcript(session_id: str, body: Transcript):
        with lock:
            item = session(session_id)
            service.recording(item)
            service.event(
                item,
                "voice_transcript",
                ("learner" if item.phase in {"training", "results"} else "expert")
                if body.speaker == "user"
                else "system",
                {"speaker": body.speaker, "text": body.text},
            )
            store.save(item)
        return item

    @app.post("/api/sessions/{session_id}/frames")
    async def frame(session_id: str, body: Frame):
        with lock:
            item = session(session_id)
            service.recording(item)
            revision = item.recording_revision
        if session_id in busy or len(busy) >= 2:
            raise HTTPException(429, "A frame is already being processed; skip this frame")
        if not body.image.startswith("data:image/jpeg;base64,"):
            raise HTTPException(422, "Use a resized JPEG frame")
        try:
            raw = base64.b64decode(body.image.split(",", 1)[1], validate=True)
        except binascii.Error as error:
            raise HTTPException(422, "Invalid frame encoding") from error
        if not raw.startswith(b"\xff\xd8"):
            raise HTTPException(422, "Invalid JPEG frame")
        busy.add(session_id)
        try:
            if item.mode == "live":
                try:
                    observation = await providers.observe(body.image)
                except ProviderConfigurationError as error:
                    raise HTTPException(503, str(error)) from error
                except Exception as error:
                    raise HTTPException(
                        502, "Vision observation failed. Retry or check setup."
                    ) from error
                summary = observation.summary
                source = "visual"
            else:
                summary = "Simulated observation: frame received; no visual model was invoked."
                source = "simulated"
            with lock:
                item = session(session_id)
                service.recording(item)  # Off-record/deletion while a provider call is in flight.
                if item.recording_revision != revision:
                    raise DomainError(
                        "Recording controls changed; this in-flight frame was discarded."
                    )
                event = service.event(
                    item,
                    "screen_observation",
                    source,
                    {
                        "summary": summary,
                        "frame": body.image,
                        "confidence": observation.confidence if source == "visual" else "low",
                        "uncertain": observation.uncertain
                        if source == "visual"
                        else ["Simulated mode does not interpret screen content"],
                    },
                )
                store.save(item)
            return event
        finally:
            busy.discard(session_id)

    @app.websocket("/api/sessions/{session_id}/events")
    async def events(websocket: WebSocket, session_id: str):
        host = websocket.headers.get("host", "").split(":")[0]
        if (
            host not in {"localhost", "127.0.0.1", "testserver"}
            or websocket.headers.get("origin") not in ALLOWED_ORIGINS
        ):
            await websocket.close(code=1008)
            return
        try:
            session(session_id)
        except KeyError:
            await websocket.close(code=1008)
            return
        await websocket.accept()
        sent: set[str] = set()
        try:
            while True:
                item = session(session_id)
                for event in item.events:
                    if event.event_id not in sent:
                        await websocket.send_json(event.model_dump())
                        sent.add(event.event_id)
                try:
                    message = await asyncio.wait_for(websocket.receive(), timeout=0.5)
                except TimeoutError:
                    continue
                if message["type"] == "websocket.disconnect":
                    raise WebSocketDisconnect(message.get("code", 1000))
        except WebSocketDisconnect:
            return
        except KeyError:
            await websocket.close(code=1000)

    return app


app = create_app()
