import aiosqlite
from typing import Optional
import logging

logger = logging.getLogger(__name__)

DATABASE_FILE = "verified_users.db"


async def init_database():
    """Initialize the database and create tables."""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS verified_users (
                discord_id INTEGER PRIMARY KEY,
                s21_login TEXT NOT NULL UNIQUE,
                coalition TEXT,
                verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()
        logger.info("Database initialized")


async def add_verified_user(
    discord_id: int,
    s21_login: str,
    coalition: Optional[str] = None
) -> bool:
    """Add a verified user to the database."""
    try:
        async with aiosqlite.connect(DATABASE_FILE) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO verified_users (discord_id, s21_login, coalition)
                VALUES (?, ?, ?)
                """,
                (discord_id, s21_login, coalition)
            )
            await db.commit()
            return True
    except Exception as e:
        logger.error(f"Failed to add verified user: {e}")
        return False


async def get_user_by_discord_id(discord_id: int) -> Optional[dict]:
    """Get verified user by Discord ID."""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM verified_users WHERE discord_id = ?",
            (discord_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None


async def get_user_by_s21_login(s21_login: str) -> Optional[dict]:
    """Get verified user by School 21 login."""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM verified_users WHERE s21_login = ?",
            (s21_login,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None


async def is_login_taken(s21_login: str) -> bool:
    """Check if a School 21 login is already linked to another Discord account."""
    user = await get_user_by_s21_login(s21_login)
    return user is not None


async def remove_user(discord_id: int) -> bool:
    """Remove a verified user from the database."""
    try:
        async with aiosqlite.connect(DATABASE_FILE) as db:
            await db.execute(
                "DELETE FROM verified_users WHERE discord_id = ?",
                (discord_id,)
            )
            await db.commit()
            return True
    except Exception as e:
        logger.error(f"Failed to remove user: {e}")
        return False
