"""
Test harness for damage type system and effect updates.
Tests vulnerable/resistant modifiers on direct damage and DoT.
"""

import asyncio
import aiosqlite
import json
from utils.effects import apply_effect, get_preset_effect, get_active_effects
from utils.move_execution import apply_damage_type_modifiers


async def test_damage_type_system():
    """Test damage type modifiers with vulnerable/resistant effects"""
    print("=" * 60)
    print("DAMAGE TYPE SYSTEM TEST")
    print("=" * 60)

    async with aiosqlite.connect('database/ronan.db') as db:
        test_char = "test1"

        # Clean up any existing effects
        await db.execute("DELETE FROM effects WHERE character_name = ?", (test_char,))
        await db.commit()

        # Test 1: Baseline damage (no modifiers)
        print("\n[TEST 1] Baseline damage - no modifiers")
        damage, modifier_text = await apply_damage_type_modifiers(10, "fire", test_char, db)
        print(f"  Input: 10 fire damage")
        print(f"  Output: {damage} damage {modifier_text}")
        assert damage == 10, f"Expected 10, got {damage}"
        assert modifier_text == "", f"Expected no modifier text, got '{modifier_text}'"
        print("  >> PASS")

        # Test 2: Vulnerable to fire
        print("\n[TEST 2] Vulnerable to fire (2x damage)")
        vuln_effect = get_preset_effect("vulnerable", duration=5, note="fire")
        await apply_effect(test_char, vuln_effect, db)
        damage, modifier_text = await apply_damage_type_modifiers(10, "fire", test_char, db)
        print(f"  Input: 10 fire damage")
        print(f"  Output: {damage} damage {modifier_text}")
        assert damage == 20, f"Expected 20, got {damage}"
        assert "x2" in modifier_text and "fire" in modifier_text, f"Expected x2 fire modifier, got '{modifier_text}'"
        print("  >> PASS")

        # Test 3: Vulnerable doesn't affect other damage types
        print("\n[TEST 3] Vulnerable to fire, but taking cold damage (no effect)")
        damage, modifier_text = await apply_damage_type_modifiers(10, "cold", test_char, db)
        print(f"  Input: 10 cold damage (still vulnerable to fire)")
        print(f"  Output: {damage} damage {modifier_text}")
        assert damage == 10, f"Expected 10, got {damage}"
        assert modifier_text == "", f"Expected no modifier, got '{modifier_text}'"
        print("  >> PASS")

        # Clean up
        await db.execute("DELETE FROM effects WHERE character_name = ?", (test_char,))
        await db.commit()

        # Test 4: Resistant to cold
        print("\n[TEST 4] Resistant to cold (0.5x damage)")
        resist_effect = get_preset_effect("resistant", duration=5, note="cold")
        await apply_effect(test_char, resist_effect, db)
        damage, modifier_text = await apply_damage_type_modifiers(10, "cold", test_char, db)
        print(f"  Input: 10 cold damage")
        print(f"  Output: {damage} damage {modifier_text}")
        assert damage == 5, f"Expected 5, got {damage}"
        assert "x0.5" in modifier_text and "cold" in modifier_text, f"Expected x0.5 cold modifier, got '{modifier_text}'"
        print("  >> PASS")

        # Clean up
        await db.execute("DELETE FROM effects WHERE character_name = ?", (test_char,))
        await db.commit()

        print("\n" + "=" * 60)
        print(">> ALL DAMAGE TYPE TESTS PASSED")
        print("=" * 60)


async def test_dot_damage_types():
    """Test DoT effects with damage types"""
    print("\n" + "=" * 60)
    print("DOT DAMAGE TYPE TEST")
    print("=" * 60)

    async with aiosqlite.connect('database/ronan.db') as db:
        test_char = "test1"

        # Clean up
        await db.execute("DELETE FROM effects WHERE character_name = ?", (test_char,))
        await db.commit()

        # Test 1: Apply fire DoT
        print("\n[TEST 1] Apply fire DoT effect")
        fire_dot = get_preset_effect("dot", duration=3, dot_value="5", damage_type="fire", note="burning")
        await apply_effect(test_char, fire_dot, db)

        # Check it was stored correctly
        async with db.execute("""
            SELECT dot_value, damage_type, note FROM effects
            WHERE character_name = ? AND effect_name = 'dot'
        """, (test_char,)) as cursor:
            row = await cursor.fetchone()
            assert row, "DoT effect not found"
            dot_value, damage_type, note = row
            print(f"  Stored: dot_value={dot_value}, damage_type={damage_type}, note={note}")
            assert dot_value == "5", f"Expected '5', got '{dot_value}'"
            assert damage_type == "fire", f"Expected 'fire', got '{damage_type}'"
            assert note == "burning", f"Expected 'burning', got '{note}'"
        print("  >> PASS")

        # Test 2: Apply poison DoT (should default to poison type)
        print("\n[TEST 2] Apply poisoned effect (default poison type)")
        poison_effect = get_preset_effect("poisoned", duration=3)
        await apply_effect(test_char, poison_effect, db)

        async with db.execute("""
            SELECT dot_value, damage_type FROM effects
            WHERE character_name = ? AND effect_name = 'poisoned'
        """, (test_char,)) as cursor:
            row = await cursor.fetchone()
            assert row, "Poisoned effect not found"
            dot_value, damage_type = row
            print(f"  Stored: dot_value={dot_value}, damage_type={damage_type}")
            assert damage_type == "poison", f"Expected 'poison', got '{damage_type}'"
        print("  >> PASS")

        # Clean up
        await db.execute("DELETE FROM effects WHERE character_name = ?", (test_char,))
        await db.commit()

        print("\n" + "=" * 60)
        print(">> ALL DOT DAMAGE TYPE TESTS PASSED")
        print("=" * 60)


async def test_effect_presets():
    """Test new effect presets (weakened, slowed, exposed, etc.)"""
    print("\n" + "=" * 60)
    print("EFFECT PRESET TEST")
    print("=" * 60)

    async with aiosqlite.connect('database/ronan.db') as db:
        test_char = "test1"

        # Clean up
        await db.execute("DELETE FROM effects WHERE character_name = ?", (test_char,))
        await db.execute("""
            UPDATE characters
            SET stat_modifiers = ?, roll_modifiers = ?
            WHERE name = ?
        """, (
            json.dumps({"str": 0, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0}),
            json.dumps({"attack_modifier": 0, "save_modifier": 0, "incoming_modifier": 0}),
            test_char
        ))
        await db.commit()

        # Get base stats
        async with db.execute("SELECT base_stats FROM characters WHERE name = ?", (test_char,)) as cursor:
            row = await cursor.fetchone()
            base_stats = json.loads(row[0])
            base_str = base_stats["str"]
            print(f"\nBase STR: {base_str}")

        # Test 1: Weakened (halves STR)
        print("\n[TEST 1] Apply weakened effect (halves STR)")
        weakened = get_preset_effect("weakened", duration=3)
        await apply_effect(test_char, weakened, db)

        async with db.execute("SELECT stat_modifiers FROM characters WHERE name = ?", (test_char,)) as cursor:
            row = await cursor.fetchone()
            stat_mods = json.loads(row[0])
            print(f"  Stat modifiers after weakened: {stat_mods}")
            expected_mod = (base_str // 2) - base_str
            assert stat_mods["str"] == expected_mod, f"Expected STR modifier {expected_mod}, got {stat_mods['str']}"
        print("  >> PASS")

        # Clean up
        await db.execute("DELETE FROM effects WHERE character_name = ?", (test_char,))
        await db.execute("""
            UPDATE characters
            SET stat_modifiers = ?, roll_modifiers = ?
            WHERE name = ?
        """, (
            json.dumps({"str": 0, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0}),
            json.dumps({"attack_modifier": 0, "save_modifier": 0, "incoming_modifier": 0}),
            test_char
        ))
        await db.commit()

        # Test 2: Exposed (incoming_modifier +2)
        print("\n[TEST 2] Apply exposed effect (incoming_modifier +2)")
        exposed = get_preset_effect("exposed", duration=2)
        await apply_effect(test_char, exposed, db)

        async with db.execute("SELECT roll_modifiers FROM characters WHERE name = ?", (test_char,)) as cursor:
            row = await cursor.fetchone()
            roll_mods = json.loads(row[0])
            print(f"  Roll modifiers after exposed: {roll_mods}")
            assert roll_mods.get("incoming_modifier", 0) == 2, f"Expected incoming_modifier 2, got {roll_mods.get('incoming_modifier')}"
        print("  >> PASS")

        # Clean up
        await db.execute("DELETE FROM effects WHERE character_name = ?", (test_char,))
        await db.commit()

        # Test 3: Frightened (attack_modifier -2)
        print("\n[TEST 3] Apply frightened effect (attack_modifier -2)")
        frightened = get_preset_effect("frightened", duration=2, note="of the dragon")
        await apply_effect(test_char, frightened, db)

        async with db.execute("SELECT note FROM effects WHERE character_name = ? AND effect_name = 'frightened'", (test_char,)) as cursor:
            row = await cursor.fetchone()
            note = row[0] if row else None

        async with db.execute("SELECT roll_modifiers FROM characters WHERE name = ?", (test_char,)) as cursor:
            row = await cursor.fetchone()
            roll_mods = json.loads(row[0])
            print(f"  Roll modifiers after frightened: {roll_mods}")
            print(f"  Note: {note}")
            assert roll_mods.get("attack_modifier", 0) == -2, f"Expected attack_modifier -2, got {roll_mods.get('attack_modifier')}"
            assert note == "of the dragon", f"Expected note 'of the dragon', got '{note}'"
        print("  >> PASS")

        # Clean up
        await db.execute("DELETE FROM effects WHERE character_name = ?", (test_char,))
        await db.commit()

        print("\n" + "=" * 60)
        print(">> ALL EFFECT PRESET TESTS PASSED")
        print("=" * 60)


async def main():
    """Run all tests"""
    print("\n>> STARTING DAMAGE SYSTEM TEST SUITE\n")

    try:
        await test_damage_type_system()
        await test_dot_damage_types()
        await test_effect_presets()

        print("\n" + "=" * 60)
        print(">> ALL TESTS PASSED!")
        print("=" * 60 + "\n")

    except AssertionError as e:
        print(f"\n>> TEST FAILED: {e}\n")
        raise
    except Exception as e:
        print(f"\n>> ERROR: {e}\n")
        raise


if __name__ == "__main__":
    asyncio.run(main())
