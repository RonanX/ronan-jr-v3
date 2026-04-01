"""
Test script for character system
Tests character creation, updates, forms, and database persistence
"""

import asyncio
import json
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

from database.init_db import init_database, get_db


async def test_character_system():
    print("=== CHARACTER SYSTEM TESTS ===\n")

    # Initialize database
    print("--- Initializing Database ---")
    await init_database()
    print("[OK] Database initialized\n")

    # Clean up any existing test data
    db = await get_db()
    await db.execute("DELETE FROM characters WHERE name LIKE 'TestChar%'")
    await db.commit()
    await db.close()

    # Test 1: Create a character
    print("--- Test 1: Create Character ---")
    test_char = {
        "name": "TestChar1",
        "hp": 100,
        "max_hp": 100,
        "mp": 50,
        "max_mp": 50,
        "ac": 13,
        "movement": 30,
        "proficiency": 3,
        "stats": {
            "combat": 3,
            "power": 2,
            "mobility": 4,
            "technique": 2,
            "resilience": 3,
            "focus": 2
        }
    }

    db = await get_db()
    await db.execute(
        """
        INSERT INTO characters
        (name, hp, max_hp, mp, max_mp, ac, movement, proficiency, stats_json, current_form)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'base')
        """,
        (
            test_char["name"],
            test_char["hp"],
            test_char["max_hp"],
            test_char["mp"],
            test_char["max_mp"],
            test_char["ac"],
            test_char["movement"],
            test_char["proficiency"],
            json.dumps(test_char["stats"])
        )
    )
    await db.commit()
    await db.close()

    print(f"[OK] Created character: {test_char['name']}")
    print(f"  HP: {test_char['hp']}/{test_char['max_hp']}")
    print(f"  MP: {test_char['mp']}/{test_char['max_mp']}")
    print(f"  AC: {test_char['ac']}")
    print(f"  Stats: {test_char['stats']}\n")

    # Test 2: Read character back
    print("--- Test 2: Read Character ---")
    db = await get_db()
        async with db.execute(
            "SELECT * FROM characters WHERE name = ?",
            (test_char["name"],)
        ) as cursor:
            row = await cursor.fetchone()

    if row:
        print(f"[OK] Retrieved character: {row[0]}")
        print(f"  HP: {row[1]}/{row[2]}")
        print(f"  MP: {row[3]}/{row[4]}")
        print(f"  AC: {row[5]}")
        print(f"  Movement: {row[6]}ft")
        print(f"  Proficiency: +{row[7]}")
        print(f"  Stats: {json.loads(row[8])}")
        print(f"  Current Form: {row[9]}\n")
    else:
        print("[FAIL] Failed to retrieve character\n")

    # Test 3: Update HP and MP
    print("--- Test 3: Update HP and MP ---")
    db = await get_db()
        await db.execute(
            "UPDATE characters SET hp = ?, mp = ? WHERE name = ?",
            (80, 40, test_char["name"])
        )
        await db.commit()

    db = await get_db()
        async with db.execute(
            "SELECT hp, mp FROM characters WHERE name = ?",
            (test_char["name"],)
        ) as cursor:
            row = await cursor.fetchone()

    print(f"[OK] Updated HP: {row[0]}/100")
    print(f"[OK] Updated MP: {row[1]}/50\n")

    # Test 4: Update a stat
    print("--- Test 4: Update Stats ---")
    db = await get_db()
        async with db.execute(
            "SELECT stats_json FROM characters WHERE name = ?",
            (test_char["name"],)
        ) as cursor:
            row = await cursor.fetchone()

        stats = json.loads(row[0])
        stats["combat"] = 4  # Update combat from 3 to 4

        await db.execute(
            "UPDATE characters SET stats_json = ? WHERE name = ?",
            (json.dumps(stats), test_char["name"])
        )
        await db.commit()

    print(f"[OK] Updated combat stat: 3 -> 4")
    print(f"  New stats: {stats}\n")

    # Test 5: Add a form
    print("--- Test 5: Add Transformation Form ---")
    super_form_stats = {
        "combat": 4,
        "power": 4,
        "mobility": 3,
        "technique": 1,
        "resilience": 2,
        "focus": 1
    }

    db = await get_db()
        await db.execute(
            """
            INSERT INTO forms (character_name, form_name, stats_json)
            VALUES (?, ?, ?)
            """,
            (test_char["name"], "super", json.dumps(super_form_stats))
        )
        await db.commit()

    print(f"[OK] Added 'super' form to {test_char['name']}")
    print(f"  Form stats: {super_form_stats}\n")

    # Test 6: Transform (swap form)
    print("--- Test 6: Transform to Super Form ---")
    db = await get_db()
        # Get current MP
        async with db.execute(
            "SELECT mp FROM characters WHERE name = ?",
            (test_char["name"],)
        ) as cursor:
            current_mp = (await cursor.fetchone())[0]

        # Transform: deduct 10 MP, swap stats, change form
        new_mp = current_mp - 10
        await db.execute(
            "UPDATE characters SET mp = ?, stats_json = ?, current_form = ? WHERE name = ?",
            (new_mp, json.dumps(super_form_stats), "super", test_char["name"])
        )
        await db.commit()

    db = await get_db()
        async with db.execute(
            "SELECT mp, stats_json, current_form FROM characters WHERE name = ?",
            (test_char["name"],)
        ) as cursor:
            row = await cursor.fetchone()

    print(f"[OK] Transformed to 'super' form!")
    print(f"  MP cost: -10 (Now: {row[0]}/50)")
    print(f"  New stats: {json.loads(row[1])}")
    print(f"  Current form: {row[2]}\n")

    # Test 7: Create second character
    print("--- Test 7: Create Second Character ---")
    test_char2 = {
        "name": "TestChar2",
        "hp": 120,
        "max_hp": 120,
        "mp": 30,
        "max_mp": 30,
        "ac": 15,
        "movement": 25,
        "proficiency": 2,
        "stats": {
            "combat": 2,
            "power": 3,
            "mobility": 2,
            "technique": 3,
            "resilience": 4,
            "focus": 2
        }
    }

    db = await get_db()
        await db.execute(
            """
            INSERT INTO characters
            (name, hp, max_hp, mp, max_mp, ac, movement, proficiency, stats_json, current_form)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'base')
            """,
            (
                test_char2["name"],
                test_char2["hp"],
                test_char2["max_hp"],
                test_char2["mp"],
                test_char2["max_mp"],
                test_char2["ac"],
                test_char2["movement"],
                test_char2["proficiency"],
                json.dumps(test_char2["stats"])
            )
        )
        await db.commit()

    print(f"[OK] Created character: {test_char2['name']}")
    print(f"  HP: {test_char2['hp']}/{test_char2['max_hp']}")
    print(f"  AC: {test_char2['ac']}\n")

    # Test 8: List all characters
    print("--- Test 8: List All Characters ---")
    db = await get_db()
        async with db.execute(
            "SELECT name, hp, max_hp, mp, max_mp, ac, current_form FROM characters WHERE name LIKE 'TestChar%'"
        ) as cursor:
            rows = await cursor.fetchall()

    for row in rows:
        print(f"  {row[0]} ({row[6]} form)")
        print(f"    HP: {row[1]}/{row[2]} | MP: {row[3]}/{row[4]} | AC: {row[5]}")

    print()

    # Test 9: Delete a character
    print("--- Test 9: Delete Character ---")
    db = await get_db()
        await db.execute("DELETE FROM characters WHERE name = ?", (test_char["name"],))
        await db.commit()

    db = await get_db()
        async with db.execute(
            "SELECT COUNT(*) FROM characters WHERE name = ?",
            (test_char["name"],)
        ) as cursor:
            count = (await cursor.fetchone())[0]

    if count == 0:
        print(f"[OK] Successfully deleted {test_char['name']}\n")
    else:
        print(f"[FAIL] Failed to delete {test_char['name']}\n")

    # Test 10: Verify persistence (close and reopen DB)
    print("--- Test 10: Verify Persistence ---")
    db = await get_db()
        async with db.execute(
            "SELECT name, hp, ac FROM characters WHERE name = ?",
            (test_char2["name"],)
        ) as cursor:
            row = await cursor.fetchone()

    if row:
        print(f"[OK] Data persisted correctly!")
        print(f"  Character: {row[0]}")
        print(f"  HP: {row[1]}")
        print(f"  AC: {row[2]}\n")
    else:
        print(f"[FAIL] Data not persisted\n")

    # Cleanup
    print("--- Cleanup ---")
    db = await get_db()
        await db.execute("DELETE FROM characters WHERE name LIKE 'TestChar%'")
        await db.commit()
    print("[OK] Test data cleaned up\n")

    print("=== ALL TESTS COMPLETE ===")


if __name__ == "__main__":
    asyncio.run(test_character_system())
