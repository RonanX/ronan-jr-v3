"""
Migration: Add temp_stars column to characters table
"""

import aiosqlite
import asyncio

DATABASE_PATH = "database/ronan.db"

async def migrate():
    """Add temp_stars column if it doesn't exist."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Check if column exists
        async with db.execute("PRAGMA table_info(characters)") as cursor:
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]

            if 'temp_stars' in column_names:
                print("[INFO] temp_stars column already exists, skipping migration")
                return

        # Add temp_stars column
        print("[INFO] Adding temp_stars column...")
        await db.execute("""
            ALTER TABLE characters
            ADD COLUMN temp_stars INTEGER DEFAULT 0
        """)

        await db.commit()
        print("[SUCCESS] temp_stars column added successfully!")

if __name__ == "__main__":
    asyncio.run(migrate())
