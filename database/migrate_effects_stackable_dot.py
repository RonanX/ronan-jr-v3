"""
Migrate effects table for stackable DoT and note field
- Add note column for effect display names
- Change resource_change to TEXT to support flat/dice/percentage formats
- Add dot_value TEXT column to replace dot_damage INTEGER
- Add stackable BOOLEAN column to control stacking behavior
"""

import asyncio
import aiosqlite

DATABASE_PATH = 'database/ronan.db'


async def migrate():
    """Add new columns for stackable DoT system"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Check existing columns
        async with db.execute("PRAGMA table_info(effects)") as cursor:
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]

        # Add note column
        if 'note' not in column_names:
            print("Adding note column...")
            await db.execute("""
                ALTER TABLE effects
                ADD COLUMN note TEXT DEFAULT ''
            """)
            print("[OK] Added note column")
        else:
            print("[SKIP] note column already exists")

        # Add dot_value column (TEXT to support dice/percentage)
        if 'dot_value' not in column_names:
            print("Adding dot_value column...")
            await db.execute("""
                ALTER TABLE effects
                ADD COLUMN dot_value TEXT DEFAULT '0'
            """)
            print("[OK] Added dot_value column")
        else:
            print("[SKIP] dot_value column already exists")

        # Add resource_value column (TEXT to support dice/percentage)
        if 'resource_value' not in column_names:
            print("Adding resource_value column...")
            await db.execute("""
                ALTER TABLE effects
                ADD COLUMN resource_value TEXT DEFAULT '0'
            """)
            print("[OK] Added resource_value column")
        else:
            print("[SKIP] resource_value column already exists")

        # Add stackable column
        if 'stackable' not in column_names:
            print("Adding stackable column...")
            await db.execute("""
                ALTER TABLE effects
                ADD COLUMN stackable INTEGER DEFAULT 0
            """)
            print("[OK] Added stackable column")
        else:
            print("[SKIP] stackable column already exists")

        await db.commit()
        print("[OK] Migration complete")


if __name__ == "__main__":
    asyncio.run(migrate())
