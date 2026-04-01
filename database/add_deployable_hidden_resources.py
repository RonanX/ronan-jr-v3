"""Add hidden_resources column to deployables table."""
import asyncio
import aiosqlite

DATABASE_PATH = r"d:\Games\Campaigns\ronan-jr-v3\database\ronan.db"


async def add_hidden_resources_to_deployables():
    """Add hidden_resources boolean column to deployables table."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Check if column already exists
        async with db.execute("PRAGMA table_info(deployables)") as cursor:
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]

        if "hidden_resources" in column_names:
            print("[OK] hidden_resources column already exists in deployables!")
            return

        print("[INFO] Adding hidden_resources column to deployables table...")
        await db.execute("""
            ALTER TABLE deployables
            ADD COLUMN hidden_resources INTEGER DEFAULT 0
        """)
        await db.commit()
        print("[OK] Successfully added hidden_resources column to deployables (default False)")


if __name__ == "__main__":
    asyncio.run(add_hidden_resources_to_deployables())
