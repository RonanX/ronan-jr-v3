"""
Database migration script
Adds new columns and tables for combat system
"""

import asyncio
import aiosqlite

DATABASE_PATH = "database/ronan.db"


async def migrate():
    """Migrate database to add combat features"""
    print("Starting database migration...")

    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Add current_turn_index column to initiative table if it doesn't exist
        try:
            await db.execute(
                "ALTER TABLE initiative ADD COLUMN current_turn_index INTEGER DEFAULT 0"
            )
            print("[OK] Added current_turn_index column to initiative table")
        except Exception as e:
            if "duplicate column name" in str(e).lower():
                print("[SKIP] current_turn_index column already exists")
            else:
                print(f"[ERROR] Failed to add current_turn_index: {e}")

        # Create combat_state table if it doesn't exist
        try:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS combat_state (
                    character_name TEXT PRIMARY KEY,
                    stars INTEGER DEFAULT 5,
                    effects_json TEXT DEFAULT '[]'
                )
            """)
            print("[OK] Created combat_state table")
        except Exception as e:
            print(f"[ERROR] Failed to create combat_state table: {e}")

        await db.commit()

    print("Migration complete!")


if __name__ == "__main__":
    asyncio.run(migrate())
