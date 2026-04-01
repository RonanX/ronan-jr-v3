import asyncio
import aiosqlite

async def check_tables():
    async with aiosqlite.connect('database/ronan.db') as db:
        async with db.execute("SELECT name FROM sqlite_master WHERE type='table'") as cursor:
            tables = await cursor.fetchall()
            print("Tables in database:")
            for table in tables:
                print(f"  - {table[0]}")

asyncio.run(check_tables())
