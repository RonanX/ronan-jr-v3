"""
Migrate deployables table to new schema.

OLD schema: name, owner, hp, max_hp, stars, max_stars, duration, owner_name
NEW schema: id, deployable_name, owner_name, hp, max_hp, stars, max_stars,
            available_until_round, created_round, ac, archetype, mp, max_mp
"""

import asyncio
import aiosqlite

DATABASE_PATH = 'database/ronan.db'


async def migrate_deployables():
    """Migrate deployables table to new schema."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Check if table exists
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='deployables'"
        ) as cursor:
            exists = await cursor.fetchone()

        if not exists:
            print("[INFO] Deployables table doesn't exist, creating new one...")
            await create_new_schema(db)
            return

        # Get current schema
        async with db.execute("PRAGMA table_info(deployables)") as cursor:
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]

        print(f"[INFO] Current columns: {column_names}")

        # Check if already migrated
        if "deployable_name" in column_names and "available_until_round" in column_names:
            print("[OK] Deployables table already migrated!")
            return

        # Backup existing data
        print("[INFO] Backing up existing deployables...")
        async with db.execute("SELECT * FROM deployables") as cursor:
            old_data = await cursor.fetchall()

        # Drop old table
        print("[INFO] Dropping old deployables table...")
        await db.execute("DROP TABLE deployables")

        # Create new table
        await create_new_schema(db)

        # Migrate old data if any
        if old_data:
            print(f"[INFO] Migrating {len(old_data)} deployables...")
            for row in old_data:
                # Old schema: name, owner, hp, max_hp, stars, max_stars, duration, owner_name
                # Map to new schema
                name = row[0] if len(row) > 0 else "Unknown"
                owner = row[7] if len(row) > 7 and row[7] else (row[1] if len(row) > 1 else "Unknown")
                hp = row[2] if len(row) > 2 else 10
                max_hp = row[3] if len(row) > 3 else 10
                stars = row[4] if len(row) > 4 else 2
                max_stars = row[5] if len(row) > 5 else 2
                duration = row[6] if len(row) > 6 else None

                # Calculate available_until_round
                if duration and duration > 0:
                    available_until = duration  # Assume current round is 1
                else:
                    available_until = 999999

                await db.execute("""
                    INSERT INTO deployables (
                        deployable_name, owner_name, hp, max_hp, stars, max_stars,
                        available_until_round, created_round, ac, archetype, mp, max_mp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (name, owner, hp, max_hp, stars, max_stars, available_until, 1, 10, "Balanced", 0, 0))

        await db.commit()
        print(f"[OK] Deployables table migrated successfully!")


async def create_new_schema(db):
    """Create deployables table with new schema."""
    await db.execute("""
        CREATE TABLE IF NOT EXISTS deployables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deployable_name TEXT NOT NULL,
            owner_name TEXT NOT NULL,
            hp INTEGER NOT NULL,
            max_hp INTEGER NOT NULL,
            stars INTEGER NOT NULL,
            max_stars INTEGER NOT NULL,
            available_until_round INTEGER NOT NULL,
            created_round INTEGER NOT NULL,
            ac INTEGER DEFAULT 10,
            archetype TEXT DEFAULT 'Balanced',
            mp INTEGER DEFAULT 0,
            max_mp INTEGER DEFAULT 0
        )
    """)
    await db.commit()
    print("[OK] Created new deployables table schema")


if __name__ == "__main__":
    asyncio.run(migrate_deployables())
