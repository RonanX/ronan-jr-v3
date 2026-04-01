import asyncio
import aiosqlite

async def check_schema():
    async with aiosqlite.connect('database/ronan.db') as db:
        async with db.execute("PRAGMA table_info(deployables)") as cursor:
            columns = await cursor.fetchall()
            print("Deployables table columns:")
            for col in columns:
                print(f"  {col[1]} ({col[2]})")

asyncio.run(check_schema())
