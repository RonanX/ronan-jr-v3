import aiosqlite
import asyncio
import json

async def verify():
    db = await aiosqlite.connect('database/ronan.db')

    print("=== CHARACTERS ===")
    async with db.execute("SELECT name, hp, max_hp, mp, max_mp, ac, base_stats FROM characters WHERE name IN ('Alicia', 'Hinobi')") as c:
        rows = await c.fetchall()
        for r in rows:
            stats = json.loads(r[6])
            print(f"{r[0]}: HP {r[1]}/{r[2]}, MP {r[3]}/{r[4]}, AC {r[5]}")
            print(f"  Stats: str {stats['str']}, dex {stats['dex']}, con {stats['con']}, int {stats['int']}, wis {stats['wis']}, cha {stats['cha']}")

    print("\n=== FORMS ===")
    async with db.execute("SELECT character_name, form_name, ac, transformation_cost FROM forms WHERE character_name = 'Hinobi'") as c:
        rows = await c.fetchall()
        for r in rows:
            print(f"Hinobi - {r[1]}: AC {r[2]}, Cost: {r[3]}")

    print("\n=== MOVE COUNTS ===")
    async with db.execute("""
        SELECT character_name, form_name, COUNT(*)
        FROM movesets
        WHERE character_name IN ('Alicia', 'Hinobi')
        GROUP BY character_name, form_name
    """) as c:
        rows = await c.fetchall()
        for r in rows:
            print(f"{r[0]} ({r[1]}): {r[2]} moves")

    print("\n=== SAMPLE MOVES ===")
    async with db.execute("""
        SELECT character_name, form_name, move_name, category, stat, damage, mp_cost
        FROM movesets
        WHERE character_name IN ('Alicia', 'Hinobi')
        ORDER BY character_name, form_name, category
        LIMIT 10
    """) as c:
        rows = await c.fetchall()
        for r in rows:
            print(f"{r[0]} ({r[1]}) - {r[2]}: {r[3]}, {r[4]}, dmg {r[5]}, mp {r[6]}")

    await db.close()

asyncio.run(verify())
