"""
Add threshold_damage and threshold_dc columns to characters table.

These columns support the damage threshold system where characters
must make CON saves when taking damage above their threshold.
"""

import asyncio
import aiosqlite

DATABASE_PATH = 'database/ronan.db'


async def add_threshold_columns():
    """Add threshold_damage and threshold_dc columns to characters table if they don't exist."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Check current schema
        async with db.execute("PRAGMA table_info(characters)") as cursor:
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]

        changes_made = False

        # Add threshold_damage column if missing
        if "threshold_damage" not in column_names:
            await db.execute("ALTER TABLE characters ADD COLUMN threshold_damage INTEGER DEFAULT NULL")
            print("[SUCCESS] Added threshold_damage column to characters table")
            changes_made = True
        else:
            print("[INFO] threshold_damage column already exists")

        # Add threshold_dc column if missing
        if "threshold_dc" not in column_names:
            await db.execute("ALTER TABLE characters ADD COLUMN threshold_dc INTEGER DEFAULT NULL")
            print("[SUCCESS] Added threshold_dc column to characters table")
            changes_made = True
        else:
            print("[INFO] threshold_dc column already exists")

        if changes_made:
            await db.commit()
            print("\n[OK] Database schema updated successfully!")
        else:
            print("\n[INFO] No changes needed - schema is up to date")


if __name__ == "__main__":
    asyncio.run(add_threshold_columns())
