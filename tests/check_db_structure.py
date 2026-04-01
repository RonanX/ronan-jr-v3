"""Check database structure."""
import asyncio
import aiosqlite

DATABASE_PATH = "database/ronan.db"


async def check_structure():
    """Check what tables and columns exist."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Check test character
        async with db.execute("""
            SELECT name, current_stars, max_stars, temp_stars, hp, max_hp
            FROM characters WHERE name = 'test'
        """) as cursor:
            row = await cursor.fetchone()
            if row:
                print(f"[INFO] Test character:")
                print(f"  Name: {row[0]}")
                print(f"  Current Stars: {row[1]}")
                print(f"  Max Stars: {row[2]}")
                print(f"  Temp Stars: {row[3]}")
                print(f"  HP: {row[4]}/{row[5]}")
            else:
                print("[ERROR] Test character not found")


if __name__ == "__main__":
    asyncio.run(check_structure())
