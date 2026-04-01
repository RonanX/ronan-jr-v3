"""
Migrate effects table to add resource_type and resource_change columns
This allows effects to modify HP, MP, etc. in addition to dealing damage
"""

import asyncio
import aiosqlite

DATABASE_PATH = 'database/ronan.db'


async def migrate():
    """Add resource_type and resource_change columns to effects table"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Check if columns already exist
        async with db.execute("PRAGMA table_info(effects)") as cursor:
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]

        if 'resource_type' not in column_names:
            print("Adding resource_type column...")
            await db.execute("""
                ALTER TABLE effects
                ADD COLUMN resource_type TEXT DEFAULT 'hp'
            """)
            print("[OK] Added resource_type column")
        else:
            print("[SKIP] resource_type column already exists")

        if 'resource_change' not in column_names:
            print("Adding resource_change column...")
            await db.execute("""
                ALTER TABLE effects
                ADD COLUMN resource_change INTEGER DEFAULT 0
            """)
            print("[OK] Added resource_change column")
        else:
            print("[SKIP] resource_change column already exists")

        await db.commit()
        print("[OK] Migration complete")


if __name__ == "__main__":
    asyncio.run(migrate())
