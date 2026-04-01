"""
Migration to create effects table with contribution tracking.
Supports clean effect application/removal with modifier contributions.
"""

import asyncio
import aiosqlite

DATABASE_PATH = 'database/ronan.db'

async def migrate():
    """Create effects table if it doesn't exist."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS effects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character_name TEXT NOT NULL,
                effect_name TEXT NOT NULL,
                emoji TEXT,
                available_until_round INTEGER,
                contributions TEXT,
                dot_damage INTEGER DEFAULT 0,
                dot_type TEXT,
                FOREIGN KEY (character_name) REFERENCES characters(name) ON DELETE CASCADE
            )
        """)

        await db.commit()
        print("[OK] Effects table created")

if __name__ == "__main__":
    asyncio.run(migrate())
