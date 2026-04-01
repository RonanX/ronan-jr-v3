"""
Test suite for refactored effects system
Tests stackable DoT, advantage/disadvantage with +1/-1, value formats, and edge cases
"""

import asyncio
import aiosqlite
import json
from utils.effects import apply_effect, get_active_effects, expire_effects
from utils.value_parser import parse_value

DATABASE_PATH = 'database/ronan.db'


async def test_advantage_disadvantage_stacking():
    """Test that advantage/disadvantage use +1/-1 and stack properly"""
    print("=== Test: Advantage/Disadvantage Stacking ===\n")

    test_char = "test"

    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Clear effects and reset modifiers
        await db.execute("DELETE FROM effects WHERE character_name = ?", (test_char,))
        zero_mods = json.dumps({"attack_modifier": 0, "save_modifier": 0, "incoming_modifier": 0})
        await db.execute("UPDATE characters SET roll_modifiers = ? WHERE name = ?", (zero_mods, test_char))
        await db.commit()

    # Apply first advantage (+1)
    advantage1 = {
        "name": "advantage",
        "emoji": "⬆️",
        "available_until_round": 10,
        "contributions": {"roll_modifiers": {"attack_modifier": 1}},
        "stackable": True
    }
    await apply_effect(test_char, advantage1)

    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT roll_modifiers FROM characters WHERE name = ?", (test_char,)) as cursor:
            row = await cursor.fetchone()
            mods = json.loads(row[0])
            assert mods['attack_modifier'] == 1, f"Expected 1, got {mods['attack_modifier']}"
            print(f"[OK] First advantage: attack_modifier = {mods['attack_modifier']}")

    # Apply second advantage (should stack to +2)
    await apply_effect(test_char, advantage1)

    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT roll_modifiers FROM characters WHERE name = ?", (test_char,)) as cursor:
            row = await cursor.fetchone()
            mods = json.loads(row[0])
            assert mods['attack_modifier'] == 2, f"Expected 2, got {mods['attack_modifier']}"
            print(f"[OK] Second advantage stacked: attack_modifier = {mods['attack_modifier']}")

    # Apply disadvantage (-1, should result in net +1)
    disadvantage1 = {
        "name": "disadvantage",
        "emoji": "⬇️",
        "available_until_round": 10,
        "contributions": {"roll_modifiers": {"attack_modifier": -1}},
        "stackable": True
    }
    await apply_effect(test_char, disadvantage1)

    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT roll_modifiers FROM characters WHERE name = ?", (test_char,)) as cursor:
            row = await cursor.fetchone()
            mods = json.loads(row[0])
            assert mods['attack_modifier'] == 1, f"Expected 1, got {mods['attack_modifier']}"
            print(f"[OK] Disadvantage applied: attack_modifier = {mods['attack_modifier']} (2 advantage - 1 disadvantage)\n")

    # Cleanup
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM effects WHERE character_name = ?", (test_char,))
        await db.execute("UPDATE characters SET roll_modifiers = ? WHERE name = ?", (zero_mods, test_char))
        await db.commit()


async def test_stackable_dot():
    """Test that DoT effects stack correctly with different values"""
    print("=== Test: Stackable DoT ===\n")

    test_char = "test"

    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM effects WHERE character_name = ?", (test_char,))
        await db.commit()

    # Apply first DoT (fire)
    dot_fire = {
        "name": "dot",
        "emoji": "🩸",
        "available_until_round": 10,
        "contributions": {},
        "dot_value": "5",
        "stackable": True,
        "note": "fire"
    }
    await apply_effect(test_char, dot_fire)

    # Apply second DoT (bleed)
    dot_bleed = {
        "name": "dot",
        "emoji": "🩸",
        "available_until_round": 10,
        "contributions": {},
        "dot_value": "3",
        "stackable": True,
        "note": "bleed"
    }
    await apply_effect(test_char, dot_bleed)

    effects = await get_active_effects(test_char)
    assert len(effects) == 2, f"Expected 2 DoT stacks, got {len(effects)}"
    print(f"[OK] Two DoT instances created: {[(e['dot_value'], e['note']) for e in effects]}\n")

    # Cleanup
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM effects WHERE character_name = ?", (test_char,))
        await db.commit()


async def test_value_formats():
    """Test flat, dice, and percentage value formats"""
    print("=== Test: Value Format Parsing ===\n")

    # Test flat
    flat_val = parse_value("5", max_value=100)
    assert flat_val == 5, f"Flat: Expected 5, got {flat_val}"
    print(f"[OK] Flat value: '5' = {flat_val}")

    # Test dice (deterministic test - just check it doesn't error)
    dice_val = parse_value("1d4", max_value=100)
    assert 1 <= dice_val <= 4, f"Dice: Expected 1-4, got {dice_val}"
    print(f"[OK] Dice value: '1d4' = {dice_val}")

    # Test percentage
    pct_val = parse_value("10%", max_value=100)
    assert pct_val == 10, f"Percentage: Expected 10, got {pct_val}"
    print(f"[OK] Percentage value: '10%' of 100 = {pct_val}")

    # Test percentage with minimum 1
    pct_small = parse_value("1%", max_value=50)
    assert pct_small == 1, f"Percentage min: Expected 1, got {pct_small}"
    print(f"[OK] Percentage minimum: '1%' of 50 = {pct_small}")

    # Edge case: 0 max HP
    pct_zero = parse_value("10%", max_value=0)
    assert pct_zero == 0, f"Percentage zero max: Expected 0, got {pct_zero}"
    print(f"[OK] Percentage with 0 max: '10%' of 0 = {pct_zero}\n")


async def test_stacked_expiry():
    """Test that DoT stacks expire independently"""
    print("=== Test: Independent Stack Expiry ===\n")

    test_char = "test"

    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM effects WHERE character_name = ?", (test_char,))
        await db.commit()

    # Apply DoT expiring at round 3
    dot1 = {
        "name": "dot",
        "emoji": "🩸",
        "available_until_round": 3,
        "contributions": {},
        "dot_value": "5",
        "stackable": True,
        "note": "early"
    }
    await apply_effect(test_char, dot1)

    # Apply DoT expiring at round 5
    dot2 = {
        "name": "dot",
        "emoji": "🩸",
        "available_until_round": 5,
        "contributions": {},
        "dot_value": "3",
        "stackable": True,
        "note": "late"
    }
    await apply_effect(test_char, dot2)

    effects = await get_active_effects(test_char)
    assert len(effects) == 2, f"Expected 2 stacks, got {len(effects)}"
    print(f"[OK] Both stacks active: {[(e['note'], e['available_until_round']) for e in effects]}")

    # Expire effects at round 3
    async with aiosqlite.connect(DATABASE_PATH) as db:
        expired = await expire_effects(test_char, 3, db=db)

    print(f"[OK] Expired at round 3: {[(eid, name) for eid, name in expired]}")

    effects_after = await get_active_effects(test_char)
    assert len(effects_after) == 1, f"Expected 1 remaining stack, got {len(effects_after)}"
    assert effects_after[0]['note'] == 'late', f"Expected 'late' stack to remain"
    print(f"[OK] Remaining stack: {effects_after[0]['note']}\n")

    # Cleanup
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM effects WHERE character_name = ?", (test_char,))
        await db.commit()


async def test_non_stackable_resource_effects():
    """Test that resource effects (HP/MP) are non-stackable"""
    print("=== Test: Non-Stackable Resource Effects ===\n")

    test_char = "test"

    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM effects WHERE character_name = ?", (test_char,))
        await db.commit()

    # Apply mana regen
    regen1 = {
        "name": "mana_regen",
        "emoji": "💙",
        "available_until_round": 10,
        "contributions": {},
        "resource_type": "mp",
        "resource_value": "3",
        "stackable": False
    }
    await apply_effect(test_char, regen1)

    effects = await get_active_effects(test_char)
    assert len(effects) == 1, f"Expected 1 effect, got {len(effects)}"
    assert effects[0]['resource_value'] == "3", f"Expected value '3', got {effects[0]['resource_value']}"
    print(f"[OK] First mana_regen applied: value = {effects[0]['resource_value']}")

    # Reapply with different value (should refresh, not stack)
    regen2 = {
        "name": "mana_regen",
        "emoji": "💙",
        "available_until_round": 12,
        "contributions": {},
        "resource_type": "mp",
        "resource_value": "5",
        "stackable": False
    }
    await apply_effect(test_char, regen2)

    effects_after = await get_active_effects(test_char)
    assert len(effects_after) == 1, f"Expected 1 effect (refreshed), got {len(effects_after)}"
    assert effects_after[0]['resource_value'] == "5", f"Expected updated value '5', got {effects_after[0]['resource_value']}"
    print(f"[OK] Mana_regen refreshed: value updated to {effects_after[0]['resource_value']}\n")

    # Cleanup
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM effects WHERE character_name = ?", (test_char,))
        await db.commit()


async def test_edge_cases():
    """Test edge cases like invalid formats and boundary conditions"""
    print("=== Test: Edge Cases ===\n")

    # Invalid dice format
    try:
        parse_value("1d", max_value=100)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        print(f"[OK] Invalid dice format rejected: {e}")

    # Invalid format
    try:
        parse_value("abc", max_value=100)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        print(f"[OK] Invalid format rejected: {e}")

    # Negative value
    neg_val = parse_value("-5", max_value=100)
    assert neg_val == -5, f"Expected -5, got {neg_val}"
    print(f"[OK] Negative value: '-5' = {neg_val}")

    print()


async def main():
    """Run all tests"""
    try:
        await test_advantage_disadvantage_stacking()
        await test_stackable_dot()
        await test_value_formats()
        await test_stacked_expiry()
        await test_non_stackable_resource_effects()
        await test_edge_cases()

        print("\n[OK] All tests passed!")
    except AssertionError as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
