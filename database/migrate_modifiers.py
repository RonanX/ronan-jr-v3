"""
Migration to add modifier tracking columns to characters table.
Supports unified dice pool system with attack/save/incoming modifiers.
"""

import asyncio
import aiosqlite
import json

DATABASE_PATH = 'database/ronan.db'

async def migrate():
    """Add modifier columns to characters table."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Check existing columns
        async with db.execute("PRAGMA table_info(characters)") as cursor:
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]

        # Add base_stats column
        if "base_stats" not in column_names:
            print("[MIGRATION] Adding base_stats column...")
            await db.execute("ALTER TABLE characters ADD COLUMN base_stats TEXT")

            # Initialize base_stats for existing characters (copy from stats_json)
            async with db.execute("SELECT name, stats_json FROM characters WHERE base_stats IS NULL") as cursor:
                rows = await cursor.fetchall()
                for name, stats_json in rows:
                    await db.execute("UPDATE characters SET base_stats = ? WHERE name = ?", (stats_json, name))
                    print(f"[OK] Initialized base_stats for {name}")

            print("[OK] base_stats column added")
        else:
            print("[INFO] base_stats column already exists")

        # Add stat_modifiers column
        if "stat_modifiers" not in column_names:
            print("[MIGRATION] Adding stat_modifiers column...")
            await db.execute("ALTER TABLE characters ADD COLUMN stat_modifiers TEXT")

            empty_stat_mods = json.dumps({"str": 0, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0})
            await db.execute("UPDATE characters SET stat_modifiers = ? WHERE stat_modifiers IS NULL", (empty_stat_mods,))

            print("[OK] stat_modifiers column added")
        else:
            print("[INFO] stat_modifiers column already exists")

        # Add roll_modifiers column
        if "roll_modifiers" not in column_names:
            print("[MIGRATION] Adding roll_modifiers column...")
            await db.execute("ALTER TABLE characters ADD COLUMN roll_modifiers TEXT")

            empty_roll_mods = json.dumps({"attack_modifier": 0, "save_modifier": 0, "incoming_modifier": 0})
            await db.execute("UPDATE characters SET roll_modifiers = ? WHERE roll_modifiers IS NULL", (empty_roll_mods,))

            print("[OK] roll_modifiers column added")
        else:
            print("[INFO] roll_modifiers column already exists")

        await db.commit()
        print("\n[OK] Migration complete!")

if __name__ == "__main__":
    asyncio.run(migrate())
