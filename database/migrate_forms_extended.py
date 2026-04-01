"""
Migration: Add transformation properties to forms table
"""

import aiosqlite
import asyncio

DATABASE_PATH = "database/ronan.db"

async def migrate():
    """Add transformation properties to forms table."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Get existing columns
        async with db.execute("PRAGMA table_info(forms)") as cursor:
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]

        # Add new columns if they don't exist
        if "ac" not in column_names:
            await db.execute("ALTER TABLE forms ADD COLUMN ac INTEGER DEFAULT 10")
            print("[SUCCESS] Added ac column to forms")

        if "transformation_cost" not in column_names:
            await db.execute("ALTER TABLE forms ADD COLUMN transformation_cost TEXT DEFAULT ''")
            print("[SUCCESS] Added transformation_cost column to forms")

        if "duration" not in column_names:
            await db.execute("ALTER TABLE forms ADD COLUMN duration INTEGER")
            print("[SUCCESS] Added duration column to forms")

        if "cancellable" not in column_names:
            await db.execute("ALTER TABLE forms ADD COLUMN cancellable INTEGER DEFAULT 1")
            print("[SUCCESS] Added cancellable column to forms")

        if "dot_damage" not in column_names:
            await db.execute("ALTER TABLE forms ADD COLUMN dot_damage INTEGER DEFAULT 0")
            print("[SUCCESS] Added dot_damage column to forms")

        if "dot_type" not in column_names:
            await db.execute("ALTER TABLE forms ADD COLUMN dot_type TEXT DEFAULT ''")
            print("[SUCCESS] Added dot_type column to forms")

        await db.commit()
        print("[INFO] Forms table migration complete")

if __name__ == "__main__":
    asyncio.run(migrate())
