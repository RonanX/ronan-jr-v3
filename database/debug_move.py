import aiosqlite
import asyncio

async def check():
    db = await aiosqlite.connect('database/ronan.db')
    async with db.execute("""
        SELECT category, star_cost, mp_cost, hp_cost, stat, damage,
               hits, targets, save_type, save_dc, save_effect,
               half_on_save, bonus_on_hit, duration, cooldown, uses, description
        FROM movesets
        WHERE character_name = 'Hinobi' AND move_name = 'Storm Drummer'
    """) as cursor:
        row = await cursor.fetchone()
        if row:
            cols = ['category', 'star_cost', 'mp_cost', 'hp_cost', 'stat', 'damage',
                   'hits', 'targets', 'save_type', 'save_dc', 'save_effect',
                   'half_on_save', 'bonus_on_hit', 'duration', 'cooldown', 'uses', 'description']
            for i, col in enumerate(cols):
                print(f"{col:20} = {row[i]!r} ({type(row[i]).__name__})")
    await db.close()

asyncio.run(check())
