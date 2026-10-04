import json
from pathlib import Path

from sqlalchemy import Column, MetaData, String, Table, Text, create_engine, delete, select

from .contracts import Session


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
        return Session.model_validate_json(body)

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
