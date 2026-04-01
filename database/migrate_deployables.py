"""
Migration: Create deployables and deployable_moves tables
"""

import aiosqlite
import asyncio

DATABASE_PATH = "database/ronan.db"

async def migrate():
    """Create deployables and deployable_moves tables if they don't exist."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Check if deployables table exists
        async with db.execute("""
            SELECT name FROM sqlite_master WHERE type='table' AND name='deployables'
        """) as cursor:
            exists = await cursor.fetchone()

            if exists:
                print("[INFO] deployables table already exists, skipping creation")
            else:
                # Create deployables table
                await db.execute("""
                    CREATE TABLE deployables (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        owner_name TEXT NOT NULL,
                        deployable_name TEXT NOT NULL,
                        hp INTEGER NOT NULL,
                        max_hp INTEGER NOT NULL,
                        stars INTEGER NOT NULL,
                        max_stars INTEGER NOT NULL,
                        available_until_round INTEGER NOT NULL,
                        created_round INTEGER NOT NULL,
                        FOREIGN KEY (owner_name) REFERENCES characters(name) ON DELETE CASCADE
                    )
                """)
                print("[SUCCESS] deployables table created successfully!")

        # Check if deployable_moves table exists
        async with db.execute("""
            SELECT name FROM sqlite_master WHERE type='table' AND name='deployable_moves'
        """) as cursor:
            exists = await cursor.fetchone()

            if exists:
                print("[INFO] deployable_moves table already exists, skipping creation")
            else:
                # Create deployable_moves table
                await db.execute("""
                    CREATE TABLE deployable_moves (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        deployable_id INTEGER NOT NULL,
                        move_name TEXT NOT NULL,
                        category TEXT NOT NULL,
                        star_cost INTEGER DEFAULT 0,
                        stat TEXT,
                        damage INTEGER DEFAULT 0,
                        hits INTEGER DEFAULT 1,
                        save_type TEXT,
                        save_dc INTEGER,
                        save_effect TEXT,
                        half_on_save INTEGER DEFAULT 0,
                        bonus_on_hit TEXT,
                        description TEXT,
                        FOREIGN KEY (deployable_id) REFERENCES deployables(id) ON DELETE CASCADE
                    )
                """)
                print("[SUCCESS] deployable_moves table created successfully!")

        await db.commit()

if __name__ == "__main__":
    asyncio.run(migrate())
