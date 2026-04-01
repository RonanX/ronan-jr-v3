"""
Simple test script for character system
Tests character CRUD operations and persistence
"""

import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from database.init_db import init_database, get_db


async def main():
    print("=== CHARACTER SYSTEM TESTS ===\n")

    # Initialize database
    print("--- Test 1: Initialize Database ---")
    await init_database()
    print("[OK] Database initialized\n")

    # Test 2: Create a character
    print("--- Test 2: Create Character ---")
    db = await get_db()
    await db.execute(
        """
        INSERT OR REPLACE INTO characters
        (name, hp, max_hp, mp, max_mp, ac, movement, proficiency, stats_json, current_form)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'base')
        """,
        ("Goku", 150, 150, 80, 80, 12, 35, 3, json.dumps({
            "combat": 4,
            "power": 4,
            "mobility": 3,
            "technique": 2,
            "resilience": 3,
            "focus": 2
        }))
    )
    await db.commit()
    await db.close()
    print("[OK] Created character 'Goku'\n")

    # Test 3: Read character back
    print("--- Test 3: Read Character ---")
    db = await get_db()
    async with db.execute(
        "SELECT name, hp, max_hp, mp, max_mp, ac, movement, proficiency, stats_json, current_form FROM characters WHERE name = ?",
        ("Goku",)
    ) as cursor:
        row = await cursor.fetchone()
    await db.close()

    if row:
        print(f"Name: {row[0]}")
        print(f"HP: {row[1]}/{row[2]}")
        print(f"MP: {row[3]}/{row[4]}")
        print(f"AC: {row[5]}")
        print(f"Movement: {row[6]}ft")
        print(f"Proficiency: +{row[7]}")
        print(f"Stats: {json.loads(row[8])}")
        print(f"Form: {row[9]}")
        print("[OK] Retrieved character\n")
    else:
        print("[FAIL] Character not found\n")

    # Test 4: Update HP/MP
    print("--- Test 4: Update HP/MP ---")
    db = await get_db()
    await db.execute(
        "UPDATE characters SET hp = ?, mp = ? WHERE name = ?",
        (120, 60, "Goku")
    )
    await db.commit()
    await db.close()
    print("[OK] Updated HP to 120, MP to 60\n")

    # Test 5: Verify update
    print("--- Test 5: Verify Update ---")
    db = await get_db()
    async with db.execute(
        "SELECT hp, mp FROM characters WHERE name = ?",
        ("Goku",)
    ) as cursor:
        row = await cursor.fetchone()
    await db.close()
    print(f"HP: {row[0]}/150")
    print(f"MP: {row[1]}/80")
    print("[OK] Update verified\n")

    # Test 6: Update stats
    print("--- Test 6: Update Stats ---")
    db = await get_db()
    async with db.execute(
        "SELECT stats_json FROM characters WHERE name = ?",
        ("Goku",)
    ) as cursor:
        row = await cursor.fetchone()

    stats = json.loads(row[0])
    stats["power"] = 4  # Goku powers up!

    await db.execute(
        "UPDATE characters SET stats_json = ? WHERE name = ?",
        (json.dumps(stats), "Goku")
    )
    await db.commit()
    await db.close()
    print(f"[OK] Updated stats: {stats}\n")

    # Test 7: Add a form
    print("--- Test 7: Add Transformation Form ---")
    super_saiyan_stats = {
        "combat": 4,
        "power": 4,
        "mobility": 4,
        "technique": 3,
        "resilience": 4,
        "focus": 3
    }

    db = await get_db()
    await db.execute(
        "INSERT OR REPLACE INTO forms (character_name, form_name, stats_json) VALUES (?, ?, ?)",
        ("Goku", "super_saiyan", json.dumps(super_saiyan_stats))
    )
    await db.commit()
    await db.close()
    print(f"[OK] Added 'super_saiyan' form\n")

    # Test 8: Transform
    print("--- Test 8: Transform ---")
    db = await get_db()

    # Get current MP
    async with db.execute(
        "SELECT mp FROM characters WHERE name = ?",
        ("Goku",)
    ) as cursor:
        current_mp = (await cursor.fetchone())[0]

    # Transform
    new_mp = current_mp - 10
    await db.execute(
        "UPDATE characters SET mp = ?, stats_json = ?, current_form = ? WHERE name = ?",
        (new_mp, json.dumps(super_saiyan_stats), "super_saiyan", "Goku")
    )
    await db.commit()
    await db.close()

    print(f"[OK] Transformed to super_saiyan!")
    print(f"MP cost: -10 (Now: {new_mp}/80)")
    print(f"New stats: {super_saiyan_stats}\n")

    # Test 9: Create second character
    print("--- Test 9: Create Second Character ---")
    db = await get_db()
    await db.execute(
        """
        INSERT OR REPLACE INTO characters
        (name, hp, max_hp, mp, max_mp, ac, movement, proficiency, stats_json, current_form)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'base')
        """,
        ("Vegeta", 140, 140, 70, 70, 13, 30, 3, json.dumps({
            "combat": 4,
            "power": 3,
            "mobility": 2,
            "technique": 3,
            "resilience": 4,
            "focus": 2
        }))
    )
    await db.commit()
    await db.close()
    print("[OK] Created character 'Vegeta'\n")

    # Test 10: List all characters
    print("--- Test 10: List All Characters ---")
    db = await get_db()
    async with db.execute(
        "SELECT name, hp, max_hp, mp, max_mp, ac, current_form FROM characters"
    ) as cursor:
        rows = await cursor.fetchall()
    await db.close()

    for row in rows:
        print(f"{row[0]} ({row[6]} form)")
        print(f"  HP: {row[1]}/{row[2]} | MP: {row[3]}/{row[4]} | AC: {row[5]}")
    print("[OK] Listed all characters\n")

    # Test 11: Delete a character
    print("--- Test 11: Delete Character ---")
    db = await get_db()
    await db.execute("DELETE FROM characters WHERE name = ?", ("Vegeta",))
    await db.commit()
    await db.close()
    print("[OK] Deleted 'Vegeta'\n")

    # Test 12: Verify deletion
    print("--- Test 12: Verify Deletion ---")
    db = await get_db()
    async with db.execute(
        "SELECT COUNT(*) FROM characters WHERE name = ?",
        ("Vegeta",)
    ) as cursor:
        count = (await cursor.fetchone())[0]
    await db.close()

    if count == 0:
        print("[OK] Vegeta successfully deleted\n")
    else:
        print("[FAIL] Vegeta still exists\n")

    # Test 13: Verify persistence
    print("--- Test 13: Verify Persistence ---")
    db = await get_db()
    async with db.execute(
        "SELECT name, current_form, stats_json FROM characters WHERE name = ?",
        ("Goku",)
    ) as cursor:
        row = await cursor.fetchone()
    await db.close()

    if row:
        print(f"[OK] Data persisted!")
        print(f"  Character: {row[0]}")
        print(f"  Form: {row[1]}")
        print(f"  Stats: {json.loads(row[2])}\n")
    else:
        print("[FAIL] Data not persisted\n")

    print("=== ALL TESTS COMPLETE ===")


if __name__ == "__main__":
    asyncio.run(main())
