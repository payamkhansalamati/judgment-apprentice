import json
from pathlib import Path

from sqlalchemy import Column, MetaData, String, Table, Text, create_engine, delete, select

from .contracts import Decision, Session


class Store:
    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{directory / 'app.sqlite'}", hide_parameters=True)
        metadata = MetaData()
        self.sessions = Table(
            "sessions",
            metadata,
            Column("id", String, primary_key=True),
            Column("body", Text, nullable=False),
        )
        metadata.create_all(self.engine)

    def save(self, session: Session) -> None:
        with self.engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA secure_delete=ON")
            connection.execute(delete(self.sessions).where(self.sessions.c.id == session.id))
            connection.execute(
                self.sessions.insert().values(id=session.id, body=session.model_dump_json())
            )

    def get(self, session_id: str) -> Session:
        with self.engine.connect() as connection:
            body = connection.execute(
                select(self.sessions.c.body).where(self.sessions.c.id == session_id)
            ).scalar_one_or_none()
        if body is None:
            raise KeyError(session_id)
        item = Session.model_validate_json(body)
        raw = json.loads(body)
        if "approved_maps" not in raw and item.work_map.status == "approved":
            item.approved_maps = [item.work_map.model_copy(deep=True)]
        if "map_review_ready" not in raw:
            item.map_review_ready = item.phase == "awaiting_confirmation"
        if "training_batch_id" not in raw and item.challenges:
            from .policies import evaluate

            item.training_map_version = item.challenges[0].map_version
            item.training_batch_id = f"legacy-v{item.training_map_version}"
            for challenge in item.challenges:
                challenge.batch_id = item.training_batch_id
                challenge.template_id = "legacy-fixed-seed"
                challenge.expected_violations = [v.rule_id for v in evaluate(challenge.case)]
                challenge.accepted_decisions = [Decision.HOLD, Decision.ESCALATE]
                challenge.source_rule_id = challenge.expected_violations[0]
                challenge.source_evidence_ids = [
                    e
                    for rule in item.work_map.rules
                    if rule.kind in challenge.expected_violations
                    for e in rule.evidence_ids
                ]
        return item

    def list(self) -> list[dict[str, str]]:
        with self.engine.connect() as connection:
            bodies = connection.execute(select(self.sessions.c.body)).scalars().all()
        return [
            {"id": item["id"], "title": item["title"], "phase": item["phase"]}
            for body in bodies
            if (item := json.loads(body))
        ]

    def remove(self, session_id: str) -> None:
        with self.engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA secure_delete=ON")
            connection.execute(delete(self.sessions).where(self.sessions.c.id == session_id))
