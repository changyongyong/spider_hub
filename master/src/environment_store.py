import json
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator


@dataclass
class EnvironmentRecord:
    worker_id: str
    node_id: str
    env_name: str | None
    status: str
    config: dict[str, Any]
    created_at: str | None = None
    updated_at: str | None = None


class SqliteEnvironmentStore:
    def __init__(self, database_path: str = "data/spider.db") -> None:
        self.database_path = database_path

    @classmethod
    def from_env(cls) -> "SqliteEnvironmentStore":
        return cls(database_path=os.getenv("SPIDER_SQLITE_PATH", "data/spider.db"))

    def initialize(self) -> None:
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS browser_environments (
                    worker_id TEXT PRIMARY KEY,
                    node_id TEXT NOT NULL,
                    env_name TEXT NULL,
                    status TEXT NOT NULL DEFAULT 'stopped',
                    config_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TRIGGER IF NOT EXISTS trg_browser_environments_updated_at
                AFTER UPDATE ON browser_environments
                FOR EACH ROW
                BEGIN
                    UPDATE browser_environments
                    SET updated_at = CURRENT_TIMESTAMP
                    WHERE worker_id = OLD.worker_id;
                END
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_browser_environments_node_id ON browser_environments (node_id)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_browser_environments_status ON browser_environments (status)"
            )

    def list(self) -> list[EnvironmentRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT worker_id, node_id, env_name, status, config_json, created_at, updated_at
                FROM browser_environments
                ORDER BY created_at DESC
                """
            ).fetchall()
            return [self._record(row) for row in rows]

    def get(self, worker_id: str) -> EnvironmentRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT worker_id, node_id, env_name, status, config_json, created_at, updated_at
                FROM browser_environments
                WHERE worker_id = ?
                """,
                (worker_id,),
            ).fetchone()
            return self._record(row) if row else None

    def save(self, record: EnvironmentRecord) -> EnvironmentRecord:
        config_json = json.dumps(record.config, ensure_ascii=False, separators=(",", ":"))
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO browser_environments (worker_id, node_id, env_name, status, config_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(worker_id) DO UPDATE SET
                    node_id = excluded.node_id,
                    env_name = excluded.env_name,
                    status = excluded.status,
                    config_json = excluded.config_json
                """,
                (record.worker_id, record.node_id, record.env_name, record.status, config_json),
            )
        saved = self.get(record.worker_id)
        if not saved:
            raise RuntimeError("environment was not saved")
        return saved

    def set_status(self, worker_id: str, status: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE browser_environments SET status = ? WHERE worker_id = ?",
                (status, worker_id),
            )

    def delete(self, worker_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM browser_environments WHERE worker_id = ?", (worker_id,))

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _record(self, row: sqlite3.Row) -> EnvironmentRecord:
        return EnvironmentRecord(
            worker_id=row["worker_id"],
            node_id=row["node_id"],
            env_name=row["env_name"],
            status=row["status"],
            config=json.loads(row["config_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
