"""
Test harness to verify effect modifiers work correctly
"""

import asyncio
import aiosqlite
import json
from utils.effects import apply_effect, get_active_effects

DATABASE_PATH = 'database/ronan.db'


async def test_roll_modifiers():
    """Test that roll modifiers are properly stored and retrieved"""
    print("=== Testing Roll Modifiers ===\n")

    test_char = "test"

    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Check if character exists
        async with db.execute("SELECT name FROM characters WHERE name = ?", (test_char,)) as cursor:
            if not await cursor.fetchone():
                print(f"[ERROR] Character '{test_char}' not found in database!")
                print("Please create a test character first")
                return

        # Clear existing effects
        await db.execute("DELETE FROM effects WHERE character_name = ?", (test_char,))
        await db.commit()

    # Test 1: Apply advantage effect
    print("Test 1: Applying advantage effect...")
    advantage_effect = {
        "name": "advantage",
        "emoji": "⬆️",
        "available_until_round": 10,
        "contributions": {"roll_modifiers": {"attack_modifier": 999}},
        "dot_damage": 0,
        "dot_type": "",
        "resource_type": "hp",
        "resource_change": 0
    }
    await apply_effect(test_char, advantage_effect)

    # Verify it was applied
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("""
            SELECT stat_modifiers, roll_modifiers, ac_modifier
            FROM characters WHERE name = ?
        """, (test_char,)) as cursor:
            row = await cursor.fetchone()
            roll_mods = json.loads(row[1])
            print(f"Roll modifiers after advantage: {roll_mods}")
            print(f"attack_modifier = {roll_mods.get('attack_modifier', 0)}")

            if roll_mods.get('attack_modifier', 0) == 999:
                print("[OK] Advantage applied correctly!\n")
            else:
                print(f"[ERROR] Expected attack_modifier=999, got {roll_mods.get('attack_modifier', 0)}\n")

    # Test 2: Apply disadvantage effect (should stack)
    print("Test 2: Applying disadvantage effect...")
    disadvantage_effect = {
        "name": "disadvantage",
        "emoji": "⬇️",
        "available_until_round": 10,
        "contributions": {"roll_modifiers": {"attack_modifier": -999}},
        "dot_damage": 0,
        "dot_type": "",
        "resource_type": "hp",
        "resource_change": 0
    }
    await apply_effect(test_char, disadvantage_effect)

    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("""
            SELECT roll_modifiers FROM characters WHERE name = ?
        """, (test_char,)) as cursor:
            row = await cursor.fetchone()
            roll_mods = json.loads(row[0])
            print(f"Roll modifiers after disadvantage: {roll_mods}")
            print(f"attack_modifier = {roll_mods.get('attack_modifier', 0)}")

            # Should be 999 + (-999) = 0
            if roll_mods.get('attack_modifier', 0) == 0:
                print("[OK] Disadvantage stacked correctly (advantage + disadvantage = 0)!\n")
            else:
                print(f"[ERROR] Expected attack_modifier=0, got {roll_mods.get('attack_modifier', 0)}\n")

    # Test 3: Get active effects
    print("Test 3: Retrieving active effects...")
    active = await get_active_effects(test_char)
    print(f"Active effects: {[e['name'] for e in active]}")
    print(f"Total effects: {len(active)}")

    if len(active) == 2:
        print("[OK] Both effects are active!\n")
    else:
        print(f"[ERROR] Expected 2 effects, found {len(active)}\n")

    # Cleanup
    print("Cleaning up...")
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM effects WHERE character_name = ?", (test_char,))
        # Reset modifiers to zero
        zero_roll_mods = json.dumps({"attack_modifier": 0, "save_modifier": 0, "incoming_modifier": 0})
        await db.execute("""
            UPDATE characters
            SET roll_modifiers = ?
            WHERE name = ?
        """, (zero_roll_mods, test_char))
        await db.commit()
    print("[OK] Cleanup complete\n")


async def test_resource_effects():
    """Test that resource change effects work correctly"""
    print("=== Testing Resource Change Effects ===\n")

    test_char = "test"

    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Get current HP/MP
        async with db.execute("""
            SELECT hp, max_hp, mp, max_mp FROM characters WHERE name = ?
        """, (test_char,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                print(f"[ERROR] Character '{test_char}' not found!")
                return

            initial_hp, max_hp, initial_mp, max_mp = row
            print(f"Initial state: HP={initial_hp}/{max_hp}, MP={initial_mp}/{max_mp}\n")

        # Clear effects
        await db.execute("DELETE FROM effects WHERE character_name = ?", (test_char,))
        await db.commit()

    # Test 1: Apply burning (HP damage)
    print("Test 1: Applying burning effect...")
    burning_effect = {
        "name": "burning",
        "emoji": "🔥",
        "available_until_round": 10,
        "contributions": {},
        "dot_damage": 5,
        "dot_type": "fire",
        "resource_type": "hp",
        "resource_change": -5
    }
    await apply_effect(test_char, burning_effect)
    print("[OK] Burning effect applied\n")

    # Test 2: Apply mana regen (MP restore)
    print("Test 2: Applying mana regen effect...")
    mana_regen_effect = {
        "name": "mana_regen",
        "emoji": "💙",
        "available_until_round": 10,
        "contributions": {},
        "dot_damage": 0,
        "dot_type": "",
        "resource_type": "mp",
        "resource_change": 3
    }
    await apply_effect(test_char, mana_regen_effect)
    print("[OK] Mana regen effect applied\n")

    # Get active effects
    active = await get_active_effects(test_char)
    print(f"Active effects: {[(e['name'], e.get('resource_change', 0), e.get('resource_type', 'hp')) for e in active]}")

    for effect in active:
        print(f"  - {effect['name']}: {effect.get('resource_change', 0)} {effect.get('resource_type', 'hp')}/turn")

    # Cleanup
    print("\nCleaning up...")
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM effects WHERE character_name = ?", (test_char,))
        await db.commit()
    print("[OK] Cleanup complete\n")


async def main():
    """Run all tests"""
    try:
        await test_roll_modifiers()
        await test_resource_effects()
        print("\n[OK] All tests completed!")
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
