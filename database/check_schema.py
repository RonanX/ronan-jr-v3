import aiosqlite
import asyncio

async def check():
    db = await aiosqlite.connect('database/ronan.db')
    async with db.execute('PRAGMA table_info(characters)') as c:
        cols = await c.fetchall()
        for r in cols:
            print(f"{r[1]:25} {r[2]:10} NULL={r[3]} DEFAULT={r[4]}")
    await db.close()

asyncio.run(check())
