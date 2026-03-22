import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STEP_KEYS = [
    "generate_base_image",
    "modify_images",
    "generate_video",
    "modify_video",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProcedureRepository:
    """SQLite-backed persistence for procedures, assets, and step runs."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS procedures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS step_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    procedure_id INTEGER NOT NULL,
                    step_key TEXT NOT NULL,
                    model_id TEXT,
                    params_json TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL,
                    UNIQUE(procedure_id, step_key),
                    FOREIGN KEY(procedure_id) REFERENCES procedures(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS assets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    procedure_id INTEGER NOT NULL,
                    step_key TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    path TEXT NOT NULL,
                    source TEXT NOT NULL,
                    parent_asset_id INTEGER,
                    archived INTEGER NOT NULL DEFAULT 0,
                    meta_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(procedure_id) REFERENCES procedures(id) ON DELETE CASCADE,
                    FOREIGN KEY(parent_asset_id) REFERENCES assets(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS step_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    procedure_id INTEGER NOT NULL,
                    step_key TEXT NOT NULL,
                    model_id TEXT,
                    params_json TEXT NOT NULL DEFAULT '{}',
                    estimated_cost REAL NOT NULL DEFAULT 0,
                    confirmed_at TEXT,
                    status TEXT NOT NULL,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(procedure_id) REFERENCES procedures(id) ON DELETE CASCADE
                );
                """
            )

    @staticmethod
    def _json_load(raw: str | None) -> dict[str, Any]:
        if not raw:
            return {}
        try:
            val = json.loads(raw)
            return val if isinstance(val, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _row_to_procedure(row: sqlite3.Row) -> dict[str, Any]:
        return dict(row)

    def _touch_procedure(self, conn: sqlite3.Connection, procedure_id: int) -> None:
        conn.execute(
            "UPDATE procedures SET updated_at = ? WHERE id = ?",
            (_utc_now(), procedure_id),
        )

    def _ensure_step_configs(self, conn: sqlite3.Connection, procedure_id: int) -> None:
        now = _utc_now()
        for step_key in STEP_KEYS:
            conn.execute(
                """
                INSERT INTO step_configs (procedure_id, step_key, model_id, params_json, updated_at)
                VALUES (?, ?, NULL, '{}', ?)
                ON CONFLICT(procedure_id, step_key) DO NOTHING
                """,
                (procedure_id, step_key, now),
            )

    def create_procedure(self, name: str) -> dict[str, Any]:
        now = _utc_now()
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO procedures (name, status, created_at, updated_at) VALUES (?, 'active', ?, ?)",
                (name, now, now),
            )
            pid = int(cur.lastrowid)
            self._ensure_step_configs(conn, pid)
            row = conn.execute("SELECT * FROM procedures WHERE id = ?", (pid,)).fetchone()
            return self._row_to_procedure(row)

    def list_procedures(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM procedures ORDER BY updated_at DESC, id DESC"
            ).fetchall()
            return [self._row_to_procedure(r) for r in rows]

    def get_procedure(self, procedure_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM procedures WHERE id = ?",
                (procedure_id,),
            ).fetchone()
            return self._row_to_procedure(row) if row else None

    def get_procedure_by_name(self, name: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM procedures WHERE name = ?", (name,)).fetchone()
            return self._row_to_procedure(row) if row else None

    def rename_procedure(self, procedure_id: int, new_name: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE procedures SET name = ?, updated_at = ? WHERE id = ?",
                (new_name, _utc_now(), procedure_id),
            )
            row = conn.execute("SELECT * FROM procedures WHERE id = ?", (procedure_id,)).fetchone()
            return self._row_to_procedure(row) if row else None

    def delete_procedure(self, procedure_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM procedures WHERE id = ?", (procedure_id,))
            return cur.rowcount > 0

    def get_step_config(self, procedure_id: int, step_key: str) -> dict[str, Any]:
        with self._connect() as conn:
            self._ensure_step_configs(conn, procedure_id)
            row = conn.execute(
                """
                SELECT * FROM step_configs
                WHERE procedure_id = ? AND step_key = ?
                """,
                (procedure_id, step_key),
            ).fetchone()
            if not row:
                return {
                    "procedure_id": procedure_id,
                    "step_key": step_key,
                    "model_id": None,
                    "params": {},
                }
            return {
                "procedure_id": row["procedure_id"],
                "step_key": row["step_key"],
                "model_id": row["model_id"],
                "params": self._json_load(row["params_json"]),
                "updated_at": row["updated_at"],
            }

    def list_step_configs(self, procedure_id: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            self._ensure_step_configs(conn, procedure_id)
            rows = conn.execute(
                """
                SELECT * FROM step_configs
                WHERE procedure_id = ?
                ORDER BY id ASC
                """,
                (procedure_id,),
            ).fetchall()
            return [
                {
                    "procedure_id": r["procedure_id"],
                    "step_key": r["step_key"],
                    "model_id": r["model_id"],
                    "params": self._json_load(r["params_json"]),
                    "updated_at": r["updated_at"],
                }
                for r in rows
            ]

    def save_step_config(
        self,
        procedure_id: int,
        step_key: str,
        model_id: str | None,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        now = _utc_now()
        with self._connect() as conn:
            self._ensure_step_configs(conn, procedure_id)
            conn.execute(
                """
                INSERT INTO step_configs (procedure_id, step_key, model_id, params_json, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(procedure_id, step_key) DO UPDATE SET
                    model_id = excluded.model_id,
                    params_json = excluded.params_json,
                    updated_at = excluded.updated_at
                """,
                (procedure_id, step_key, model_id, json.dumps(params or {}), now),
            )
            self._touch_procedure(conn, procedure_id)
        return self.get_step_config(procedure_id, step_key)

    def create_asset(
        self,
        procedure_id: int,
        step_key: str,
        kind: str,
        path: str,
        source: str,
        parent_asset_id: int | None = None,
        archived: bool = False,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = _utc_now()
        meta_json = json.dumps(meta or {})
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO assets
                    (procedure_id, step_key, kind, path, source, parent_asset_id, archived, meta_json, created_at, updated_at)
                VALUES
                    (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    procedure_id,
                    step_key,
                    kind,
                    path,
                    source,
                    parent_asset_id,
                    1 if archived else 0,
                    meta_json,
                    now,
                    now,
                ),
            )
            self._touch_procedure(conn, procedure_id)
            aid = int(cur.lastrowid)
            row = conn.execute("SELECT * FROM assets WHERE id = ?", (aid,)).fetchone()
            return self._row_to_asset(row)

    def _row_to_asset(self, row: sqlite3.Row | None) -> dict[str, Any] | None:
        if not row:
            return None
        out = dict(row)
        out["archived"] = bool(out.get("archived"))
        out["meta"] = self._json_load(out.pop("meta_json", "{}"))
        return out

    def get_asset(self, asset_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone()
            return self._row_to_asset(row)

    def list_assets(
        self,
        procedure_id: int,
        step_key: str | None = None,
        kind: str | None = None,
        archived: bool | None = None,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM assets WHERE procedure_id = ?"
        args: list[Any] = [procedure_id]
        if step_key:
            query += " AND step_key = ?"
            args.append(step_key)
        if kind:
            query += " AND kind = ?"
            args.append(kind)
        if archived is not None:
            query += " AND archived = ?"
            args.append(1 if archived else 0)
        query += " ORDER BY created_at DESC, id DESC"
        with self._connect() as conn:
            rows = conn.execute(query, args).fetchall()
            return [self._row_to_asset(r) for r in rows]

    def set_asset_archived(self, asset_id: int, archived: bool) -> dict[str, Any] | None:
        now = _utc_now()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT procedure_id FROM assets WHERE id = ?",
                (asset_id,),
            ).fetchone()
            if not row:
                return None
            procedure_id = int(row["procedure_id"])
            conn.execute(
                "UPDATE assets SET archived = ?, updated_at = ? WHERE id = ?",
                (1 if archived else 0, now, asset_id),
            )
            self._touch_procedure(conn, procedure_id)
        return self.get_asset(asset_id)

    def delete_asset(self, asset_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone()
            if not row:
                return None
            asset = self._row_to_asset(row)
            conn.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
            self._touch_procedure(conn, int(asset["procedure_id"]))
            return asset

    def update_asset_meta(self, asset_id: int, meta: dict[str, Any]) -> dict[str, Any] | None:
        now = _utc_now()
        with self._connect() as conn:
            row = conn.execute("SELECT procedure_id FROM assets WHERE id = ?", (asset_id,)).fetchone()
            if not row:
                return None
            procedure_id = int(row["procedure_id"])
            conn.execute(
                "UPDATE assets SET meta_json = ?, updated_at = ? WHERE id = ?",
                (json.dumps(meta or {}), now, asset_id),
            )
            self._touch_procedure(conn, procedure_id)
        return self.get_asset(asset_id)

    def create_step_run(
        self,
        procedure_id: int,
        step_key: str,
        model_id: str | None,
        params: dict[str, Any] | None,
        estimated_cost: float,
        status: str,
        error: str | None = None,
        confirmed: bool = False,
    ) -> dict[str, Any]:
        now = _utc_now()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO step_runs
                    (procedure_id, step_key, model_id, params_json, estimated_cost, confirmed_at, status, error, created_at, updated_at)
                VALUES
                    (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    procedure_id,
                    step_key,
                    model_id,
                    json.dumps(params or {}),
                    float(estimated_cost or 0),
                    now if confirmed else None,
                    status,
                    error,
                    now,
                    now,
                ),
            )
            self._touch_procedure(conn, procedure_id)
            rid = int(cur.lastrowid)
            row = conn.execute("SELECT * FROM step_runs WHERE id = ?", (rid,)).fetchone()
            return self._row_to_step_run(row)

    def update_step_run_status(
        self,
        run_id: int,
        status: str,
        error: str | None = None,
    ) -> dict[str, Any] | None:
        now = _utc_now()
        with self._connect() as conn:
            row = conn.execute("SELECT procedure_id FROM step_runs WHERE id = ?", (run_id,)).fetchone()
            if not row:
                return None
            procedure_id = int(row["procedure_id"])
            conn.execute(
                "UPDATE step_runs SET status = ?, error = ?, updated_at = ? WHERE id = ?",
                (status, error, now, run_id),
            )
            self._touch_procedure(conn, procedure_id)
            final = conn.execute("SELECT * FROM step_runs WHERE id = ?", (run_id,)).fetchone()
            return self._row_to_step_run(final)

    def _row_to_step_run(self, row: sqlite3.Row | None) -> dict[str, Any] | None:
        if not row:
            return None
        out = dict(row)
        out["params"] = self._json_load(out.pop("params_json", "{}"))
        return out

    def list_step_runs(self, procedure_id: int, step_key: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM step_runs WHERE procedure_id = ?"
        args: list[Any] = [procedure_id]
        if step_key:
            query += " AND step_key = ?"
            args.append(step_key)
        query += " ORDER BY created_at DESC, id DESC"
        with self._connect() as conn:
            rows = conn.execute(query, args).fetchall()
            return [self._row_to_step_run(r) for r in rows]
