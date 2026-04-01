"""Add squishy column to characters table."""
import asyncio
import aiosqlite

DATABASE_PATH = r"d:\Games\Campaigns\ronan-jr-v3\database\ronan.db"


async def add_squishy_column():
    """Add squishy boolean column to characters table."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Check if column already exists
        async with db.execute("PRAGMA table_info(characters)") as cursor:
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]

        if "squishy" in column_names:
            print("[OK] squishy column already exists!")
            return

        print("[INFO] Adding squishy column to characters table...")
        await db.execute("""
            ALTER TABLE characters
            ADD COLUMN squishy INTEGER DEFAULT 0
        """)
        await db.commit()
        print("[OK] Successfully added squishy column (default False)")


if __name__ == "__main__":
    asyncio.run(add_squishy_column())
