"""
Migration: Add current_stars column to characters table
"""

import aiosqlite
import asyncio

DATABASE_PATH = "database/ronan.db"

async def migrate():
    """Add current_stars column if it doesn't exist."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Check if column exists
        async with db.execute("PRAGMA table_info(characters)") as cursor:
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]

            if 'current_stars' in column_names:
                print("[INFO] current_stars column already exists, skipping migration")
                return

        # Add current_stars column, default to max_stars value
        print("[INFO] Adding current_stars column...")
        await db.execute("""
            ALTER TABLE characters
            ADD COLUMN current_stars INTEGER DEFAULT 5
        """)

        # Update existing characters to set current_stars = max_stars
        await db.execute("""
            UPDATE characters
            SET current_stars = max_stars
        """)

        await db.commit()
        print("[SUCCESS] current_stars column added successfully!")

if __name__ == "__main__":
    asyncio.run(migrate())
