"""
Migration: Create movesets table for storing character moves
"""

import aiosqlite
import asyncio

DATABASE_PATH = "database/ronan.db"

async def migrate():
    """Create movesets table if it doesn't exist."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Check if table exists
        async with db.execute("""
            SELECT name FROM sqlite_master WHERE type='table' AND name='movesets'
        """) as cursor:
            exists = await cursor.fetchone()

            if exists:
                print("[INFO] movesets table already exists, skipping migration")
                return

        # Create movesets table
        await db.execute("""
            CREATE TABLE movesets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character_name TEXT NOT NULL,
                form_name TEXT DEFAULT 'base',
                move_name TEXT NOT NULL,
                category TEXT NOT NULL,
                star_cost INTEGER DEFAULT 0,
                mp_cost INTEGER DEFAULT 0,
                hp_cost INTEGER DEFAULT 0,
                stat TEXT,
                damage INTEGER DEFAULT 0,
                hits INTEGER DEFAULT 1,
                targets INTEGER DEFAULT 1,
                save_type TEXT,
                save_dc INTEGER,
                save_effect TEXT,
                half_on_save INTEGER DEFAULT 0,
                bonus_on_hit TEXT,
                duration INTEGER DEFAULT 0,
                cooldown INTEGER DEFAULT 0,
                uses INTEGER,
                description TEXT,
                UNIQUE(character_name, form_name, move_name),
                FOREIGN KEY (character_name) REFERENCES characters(name) ON DELETE CASCADE
            )
        """)

        await db.commit()
        print("[SUCCESS] movesets table created successfully!")

if __name__ == "__main__":
    asyncio.run(migrate())
