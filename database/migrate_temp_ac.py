"""
Migration to add temp_mp, ac_modifier, and ac_modifier_source columns to characters table
"""

import asyncio
import aiosqlite

DATABASE_PATH = 'database/ronan.db'

async def migrate():
    """Add temp_mp, ac_modifier, and ac_modifier_source columns to characters table"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Check existing columns
        async with db.execute("PRAGMA table_info(characters)") as cursor:
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]

        # Add temp_mp if not exists
        if "temp_mp" not in column_names:
            print("[MIGRATION] Adding temp_mp column...")
            await db.execute("ALTER TABLE characters ADD COLUMN temp_mp INTEGER DEFAULT 0")
            await db.execute("UPDATE characters SET temp_mp = 0 WHERE temp_mp IS NULL")
            print("[OK] temp_mp column added")
        else:
            print("[INFO] temp_mp column already exists")

        # Add ac_modifier if not exists
        if "ac_modifier" not in column_names:
            print("[MIGRATION] Adding ac_modifier column...")
            await db.execute("ALTER TABLE characters ADD COLUMN ac_modifier INTEGER DEFAULT 0")
            await db.execute("UPDATE characters SET ac_modifier = 0 WHERE ac_modifier IS NULL")
            print("[OK] ac_modifier column added")
        else:
            print("[INFO] ac_modifier column already exists")

        # Add ac_modifier_source if not exists
        if "ac_modifier_source" not in column_names:
            print("[MIGRATION] Adding ac_modifier_source column...")
            await db.execute("ALTER TABLE characters ADD COLUMN ac_modifier_source TEXT DEFAULT ''")
            await db.execute("UPDATE characters SET ac_modifier_source = '' WHERE ac_modifier_source IS NULL")
            print("[OK] ac_modifier_source column added")
        else:
            print("[INFO] ac_modifier_source column already exists")

        await db.commit()
        print("\nMigration complete!")

if __name__ == "__main__":
    asyncio.run(migrate())
