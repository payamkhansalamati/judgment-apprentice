import asyncio
import base64
import binascii
from contextlib import asynccontextmanager
from pathlib import Path
from secrets import compare_digest, token_urlsafe
from threading import RLock
from time import perf_counter
from typing import Literal
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import text

from .contracts import CorrectionExtraction, Decision, Session, StructuredCorrection
from .diagnostics import request_completed
from .integrations import ProviderConfigurationError, Providers, Settings
from .knowledge import proposal, simulated_extraction
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


class ProposedCorrection(Correction):
    structured: StructuredCorrection | None = None


class ApplyCorrection(BaseModel):
    explicit: bool


class QuestionCue(BaseModel):
    condition: str | None = None
    case_id: str | None = None


class TrainingVersion(BaseModel):
    version: int
    seed: int = Field(default=17, ge=0, le=1_000_000)


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
    public_origin = (settings.ja_public_origin or settings.render_external_url).rstrip("/")
    if settings.ja_public_demo and (
        urlsplit(public_origin).scheme not in {"http", "https"}
        or not urlsplit(public_origin).hostname
    ):
        raise ValueError("Public demo requires JA_PUBLIC_ORIGIN or RENDER_EXTERNAL_URL")
    allowed_origins = {public_origin} if settings.ja_public_demo else ALLOWED_ORIGINS
    allowed_hosts = {"localhost", "127.0.0.1", "testserver"}
    if settings.ja_public_demo:
        allowed_hosts.add(urlsplit(public_origin).hostname)
    # Ownership is intentionally ephemeral, just like the hosted demo data.
    visitor_sessions: dict[str, str] = {}
    visitor_cookie = "ja-demo-visitor"
    frontend = Path(settings.ja_frontend_dir).resolve() if settings.ja_frontend_dir else None
    if frontend is not None and not (frontend / "index.html").is_file():
        raise ValueError("JA_FRONTEND_DIR must contain a compiled frontend index.html")
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
        allow_origins=sorted(allowed_origins),
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type"],
    )

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        origin = request.headers.get("origin")
        host = request.headers.get("host", "").split(":")[0]
        if host not in allowed_hosts:
            return JSONResponse({"detail": "This MVP is local-only."}, status_code=403)
        if origin and origin not in allowed_origins:
            return JSONResponse({"detail": "Origin is not allowed."}, status_code=403)
        if settings.ja_public_demo:
            parts = request.url.path.strip("/").split("/")
            if parts == ["api", "sessions"] and request.method == "GET":
                return JSONResponse({"detail": "Session listing is disabled in public demo."}, 403)
            if parts[:2] == ["api", "sessions"] and len(parts) >= 3:
                owner = visitor_sessions.get(parts[2])
                visitor = request.cookies.get(visitor_cookie, "")
                if not owner or not compare_digest(owner.encode(), visitor.encode()):
                    return JSONResponse({"detail": "Session or artifact no longer exists."}, 404)
                if len(parts) >= 4 and parts[3] in {"voice", "tools", "transcript", "frames"}:
                    return JSONResponse(
                        {"detail": "Live providers and real capture are disabled in public demo."},
                        403,
                    )
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

    @app.get("/api/config")
    def configuration():
        return {"public_demo": settings.ja_public_demo}

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
            "live_vision_configured": not settings.ja_public_demo and bool(settings.openai_api_key),
            "live_voice_configured": not settings.ja_public_demo
            and bool(
                settings.elevenlabs_api_key
                and settings.elevenlabs_interviewer_agent_id
                and settings.elevenlabs_tutor_agent_id
            ),
        }

    @app.get("/api/sessions")
    def list_sessions():
        return store.list()

    @app.post("/api/sessions")
    def create(body: CreateSession, request: Request, response: Response):
        if settings.ja_public_demo and body.mode != "simulated":
            raise HTTPException(403, "Only the simulated journey is enabled in public demo.")
        item = seed_session(str(uuid4()), body.mode)
        with lock:
            workflow.start(item.id)
            store.save(item)
            if settings.ja_public_demo:
                visitor = request.cookies.get(visitor_cookie, "")
                if visitor not in visitor_sessions.values():
                    visitor = token_urlsafe(32)
                visitor_sessions[item.id] = visitor
                response.set_cookie(
                    visitor_cookie,
                    visitor,
                    httponly=True,
                    secure=urlsplit(public_origin).scheme == "https",
                    samesite="strict",
                    max_age=86400,
                )
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
            visitor_sessions.pop(session_id, None)
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
    def question(session_id: str, body: QuestionCue | None = None):
        with lock:
            item = session(session_id)
            question = service.ask(
                item, body.condition if body else None, body.case_id if body else None
            )
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

    @app.post("/api/sessions/{session_id}/map/corrections/propose")
    async def propose_correction(session_id: str, body: ProposedCorrection):
        with lock:
            item = session(session_id)
            service.recording(item)
            rule = next((rule for rule in item.work_map.rules if rule.id == body.rule_id), None)
            if rule is None or not body.reason.strip():
                raise DomainError("A supported rule and exact expert words are required")
            rule = rule.model_copy(deep=True)
            version, revision, mode = item.work_map.version, item.recording_revision, item.mode
        if body.structured is not None:
            extraction = CorrectionExtraction(
                status="ready",
                message="Explicit structured edit; review the diff.",
                clarification=None,
                **body.structured.model_dump(),
            )
            extraction_mode = "structured"
        elif mode == "simulated":
            extraction = simulated_extraction(body.reason)
            extraction_mode = "simulated"
        else:
            try:
                extraction = await providers.extract_correction(body.reason, rule.model_dump())
            except ProviderConfigurationError as error:
                raise HTTPException(503, str(error)) from error
            except Exception as error:
                raise HTTPException(
                    502, "Correction extraction failed. Retry or use structured editing."
                ) from error
            extraction_mode = "live"
        with lock:
            current = session(session_id)
            service.recording(current)
            current_rule = next(rule for rule in current.work_map.rules if rule.id == body.rule_id)
            if (
                current.recording_revision != revision
                or current.work_map.version != version
                or current_rule != rule
            ):
                raise DomainError("Recording or knowledge changed during extraction; review again")
            event = service.event(
                current,
                "correction_proposed",
                "expert",
                {
                    "condition": body.rule_id,
                    "text": body.reason,
                    "extraction_mode": extraction_mode,
                },
            )
            suggestion = proposal(
                rule, version, body.reason, extraction_mode, event.event_id, extraction
            )
            current.correction_proposals.append(suggestion)
            store.save(current)
        return {"proposal": suggestion, "session": current}

    @app.post("/api/sessions/{session_id}/map/corrections/{proposal_id}/apply")
    def apply_correction(session_id: str, proposal_id: str, body: ApplyCorrection):
        with lock:
            item = session(session_id)
            service.recording(item)
            suggestion = next(
                (value for value in item.correction_proposals if value.id == proposal_id), None
            )
            if (
                suggestion is None
                or not body.explicit
                or suggestion.status != "ready"
                or suggestion.proposed_rule is None
            ):
                raise DomainError("A ready proposal and explicit review approval are required")
            current_rule = next(
                rule for rule in item.work_map.rules if rule.id == suggestion.rule_id
            )
            if (
                suggestion.map_version != item.work_map.version
                or current_rule != suggestion.before_rule
            ):
                raise DomainError("This correction is stale; propose and review it again")
            service.draft_revision(item)
            revised = suggestion.proposed_rule.model_copy(deep=True)
            evidence = next(
                event for event in item.events if event.event_id == suggestion.evidence_id
            )
            revised.evidence_ids.append(evidence.event_id)
            revised.evidence_timestamps[evidence.event_id] = evidence.timestamp
            item.work_map.rules = [
                revised if rule.id == revised.id else rule for rule in item.work_map.rules
            ]
            suggestion.status = "applied"
            service.event(
                item,
                "correction_applied",
                "expert",
                {"proposal_id": proposal_id, "version": item.work_map.version},
            )
            store.save(item)
        return item

    @app.post("/api/sessions/{session_id}/training/start")
    def start_training(session_id: str, body: TrainingVersion):
        with lock:
            item = session(session_id)
            service.recording(item)
            service.generate_challenges(item, body.version, body.seed)
            service.event(
                item, "training_selected", "expert", {"version": body.version, "seed": body.seed}
            )
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
            artifact = service.approved_map(item, challenge.map_version)
            relevant = {violation.rule_id for violation in evaluate(challenge.case, artifact.rules)}
            rules = [
                rule
                for rule in artifact.rules
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
            active = [
                challenge
                for challenge in item.challenges
                if challenge.batch_id == item.training_batch_id
            ]
            if (
                item.phase != "training"
                or not active
                or not all(challenge.approved for challenge in active)
                or not {challenge.id for challenge in active}.issubset(
                    {attempt.challenge_id for attempt in item.attempts}
                )
            ):
                raise DomainError("Attempt every approved challenge before opening results")
            checkpoint = workflow.graph.get_state(workflow.config(item.id)).values
            item.phase = (
                workflow.advance(item.id, [], item.training_map_version)
                if checkpoint.get("phase") == "training"
                else "results"
            )
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
            artifact = service.approved_map(item) if body.role == "tutor" else item.work_map
            return {
                "session_id": item.id,
                "phase": item.phase,
                "map_version": artifact.version,
                "map_status": artifact.status,
                "work_map": artifact,
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
        if host not in allowed_hosts or websocket.headers.get("origin") not in allowed_origins:
            await websocket.close(code=1008)
            return
        if settings.ja_public_demo:
            owner = visitor_sessions.get(session_id)
            visitor = websocket.cookies.get(visitor_cookie, "")
            if not owner or not compare_digest(owner.encode(), visitor.encode()):
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

    if frontend is not None:
        app.mount("/assets", StaticFiles(directory=frontend / "assets"), name="assets")

        @app.middleware("http")
        async def frontend_page(request: Request, call_next):
            response = await call_next(request)
            path = request.url.path.lstrip("/")
            if (
                response.status_code != 404
                or request.method not in {"GET", "HEAD"}
                or path == "api"
                or path.startswith(("api/", "assets/"))
            ):
                return response
            target = (frontend / path).resolve()
            if not target.is_relative_to(frontend):
                return response
            if target.is_file():
                return FileResponse(target, headers={"Cache-Control": "no-cache"})
            if Path(path).suffix:
                return response
            return FileResponse(frontend / "index.html", headers={"Cache-Control": "no-cache"})

    return app


app = create_app()
