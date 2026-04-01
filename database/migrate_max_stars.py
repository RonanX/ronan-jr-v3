"""
Migration: Add max_stars column to characters table
Default to 5 for all existing characters
"""

import asyncio
import aiosqlite

DATABASE_PATH = "database/ronan.db"


async def migrate():
    """Add max_stars column to characters table"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Check if column already exists
        async with db.execute("PRAGMA table_info(characters)") as cursor:
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]

            if "max_stars" in column_names:
                print("[INFO] max_stars column already exists, skipping migration")
                return

        # Add max_stars column with default value of 5
        print("[MIGRATION] Adding max_stars column to characters table...")
        await db.execute("""
            ALTER TABLE characters
            ADD COLUMN max_stars INTEGER DEFAULT 5
        """)

        # Set existing characters to max_stars=5
        await db.execute("UPDATE characters SET max_stars = 5 WHERE max_stars IS NULL")

        await db.commit()
        print("[OK] max_stars column added successfully")
        print("[OK] All existing characters set to max_stars=5")


if __name__ == "__main__":
    asyncio.run(migrate())
    print("\nMigration complete!")
