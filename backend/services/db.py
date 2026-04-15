import json
import os
from datetime import datetime, timezone

import aiosqlite


DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "azdo_manager.db")


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS profiles (
                name TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS upload_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                org TEXT NOT NULL,
                project TEXT NOT NULL,
                plan_id INTEGER NOT NULL,
                story_id INTEGER NOT NULL,
                suite_id INTEGER,
                created_count INTEGER NOT NULL,
                linked_count INTEGER NOT NULL,
                failed_count INTEGER NOT NULL,
                status TEXT NOT NULL,
                logs TEXT NOT NULL,
                uploaded_at TEXT NOT NULL
            )
            """
        )
        await db.commit()


async def list_profiles() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT name FROM profiles ORDER BY name") as cursor:
            rows = await cursor.fetchall()
    return [{"name": row["name"]} for row in rows]


async def get_profile(name: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT name, data FROM profiles WHERE name = ?", (name,)) as cursor:
            row = await cursor.fetchone()
    if row is None:
        return None
    return {"name": row["name"], "data": json.loads(row["data"])}


async def save_profile(name: str, config: dict) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    data = dict(config)
    data.pop("pat", None)
    payload = json.dumps(data)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO profiles (name, data, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                data = excluded.data,
                updated_at = excluded.updated_at
            """,
            (name, payload, timestamp, timestamp),
        )
        await db.commit()


async def delete_profile(name: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM profiles WHERE name = ?", (name,))
        await db.commit()
    return cursor.rowcount > 0


async def save_upload_history(
    *,
    org: str,
    project: str,
    plan_id: int,
    story_id: int,
    suite_id: int | None,
    created: int,
    linked: int,
    failed: int,
    status: str,
    logs: list[str],
) -> int:
    uploaded_at = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO upload_history (
                org, project, plan_id, story_id, suite_id,
                created_count, linked_count, failed_count,
                status, logs, uploaded_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                org,
                project,
                plan_id,
                story_id,
                suite_id,
                created,
                linked,
                failed,
                status,
                "\n".join(logs),
                uploaded_at,
            ),
        )
        await db.commit()
    return cursor.lastrowid


async def list_upload_history() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT id, org, project, plan_id, story_id, suite_id,
                   created_count, linked_count, failed_count,
                   status, uploaded_at
            FROM upload_history
            ORDER BY uploaded_at DESC, id DESC
            """
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_upload_history(entry_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM upload_history WHERE id = ?", (entry_id,)) as cursor:
            row = await cursor.fetchone()
    if row is None:
        return None
    return dict(row)


async def delete_upload_history(entry_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM upload_history WHERE id = ?", (entry_id,))
        await db.commit()
    return cursor.rowcount > 0