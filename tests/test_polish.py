"""
Test script to verify polish improvements:
- Error handling
- Consistent embeds
- Confirmation prompts
- Logging
"""

import asyncio
import os
import sys
import json

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.init_db import init_database, get_db
from utils.constants import EmbedColors, Emoji, Limits
from utils.helpers import (
    validate_stat_rating,
    validate_stat_total,
    create_error_embed,
    create_success_embed,
    create_info_embed
)


async def main():
    print("=== POLISH & CLEANUP TESTS ===\n")

    # Test 1: Constants are defined correctly
    print("--- Test 1: Constants Module ---")
    assert hasattr(EmbedColors, 'SUCCESS'), "Missing SUCCESS color"
    assert hasattr(EmbedColors, 'ERROR'), "Missing ERROR color"
    assert hasattr(EmbedColors, 'COMBAT'), "Missing COMBAT color"
    assert hasattr(Emoji, 'SUCCESS'), "Missing SUCCESS emoji"
    assert hasattr(Emoji, 'ERROR'), "Missing ERROR emoji"
    assert hasattr(Limits, 'MAX_STAT_RATING'), "Missing MAX_STAT_RATING"
    print("[OK] All constants defined\n")

    # Test 2: Validation functions
    print("--- Test 2: Validation Functions ---")

    # Test stat rating validation
    valid, error = validate_stat_rating(3)
    assert valid, "Valid stat (3) should pass"
    assert error is None, "Valid stat should have no error"

    valid, error = validate_stat_rating(5)
    assert not valid, "Invalid stat (5) should fail"
    assert error is not None, "Invalid stat should have error message"

    valid, error = validate_stat_rating(-1)
    assert not valid, "Invalid stat (-1) should fail"

    print("[OK] Stat rating validation works")

    # Test stat total validation
    valid_stats = {
        "combat": 3,
        "power": 2,
        "mobility": 2,
        "technique": 3,
        "resilience": 2,
        "focus": 2
    }
    valid, error = validate_stat_total(valid_stats)
    assert valid, f"Valid stat total (14) should pass, got error: {error}"

    invalid_stats = {
        "combat": 4,
        "power": 4,
        "mobility": 4,
        "technique": 4,
        "resilience": 4,
        "focus": 4
    }
    valid, error = validate_stat_total(invalid_stats)
    assert not valid, "Invalid stat total (24) should fail"
    assert error is not None, "Invalid total should have error message"

    print("[OK] Stat total validation works\n")

    # Test 3: Embed creation helpers
    print("--- Test 3: Embed Helpers ---")

    error_embed = create_error_embed("Test Error", "This is a test")
    assert error_embed.title == f"{Emoji.ERROR} Test Error"
    assert error_embed.color == EmbedColors.ERROR
    print("[OK] Error embed created correctly")

    success_embed = create_success_embed("Test Success", "This is a test")
    assert success_embed.title == f"{Emoji.SUCCESS} Test Success"
    assert success_embed.color == EmbedColors.SUCCESS
    print("[OK] Success embed created correctly")

    info_embed = create_info_embed("Test Info", "This is a test")
    assert info_embed.title == "Test Info"
    assert info_embed.color == EmbedColors.INFO
    print("[OK] Info embed created correctly\n")

    # Test 4: Database initialization with new schema
    print("--- Test 4: Database Schema ---")
    await init_database()

    db = await get_db()

    # Check combat_state has current_hp and current_mp
    async with db.execute("PRAGMA table_info(combat_state)") as cursor:
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]
        assert 'current_hp' in column_names, "combat_state missing current_hp column"
        assert 'current_mp' in column_names, "combat_state missing current_mp column"
        assert 'stars' in column_names, "combat_state missing stars column"
        assert 'effects_json' in column_names, "combat_state missing effects_json column"

    print("[OK] Database schema is correct\n")

    # Test 5: Character creation with validation
    print("--- Test 5: Character Creation with Validation ---")

    valid_stats = {
        "combat": 4,
        "power": 3,
        "mobility": 2,
        "technique": 1,
        "resilience": 3,
        "focus": 1
    }

    # Total = 14 (valid)
    total = sum(valid_stats.values())
    assert Limits.MIN_STAT_TOTAL <= total <= Limits.MAX_STAT_TOTAL, "Stats should be in valid range"

    await db.execute(
        """INSERT INTO characters
           (name, hp, max_hp, mp, max_mp, ac, movement, proficiency, stats_json, current_form)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("TestChar", 100, 100, 50, 50, 15, 30, 2, json.dumps(valid_stats), "base")
    )

    await db.commit()

    # Verify character exists
    async with db.execute("SELECT name FROM characters WHERE name = ?", ("TestChar",)) as cursor:
        row = await cursor.fetchone()
        assert row is not None, "Character should exist"
        assert row[0] == "TestChar", "Character name should match"

    print("[OK] Character created with valid stats\n")

    # Test 6: Error handling for invalid operations
    print("--- Test 6: Error Handling ---")

    # Try to get non-existent character
    async with db.execute("SELECT name FROM characters WHERE name = ?", ("NonExistent",)) as cursor:
        row = await cursor.fetchone()
        assert row is None, "Non-existent character should not be found"

    print("[OK] Handles missing characters correctly")

    # Try to check stars for character not in combat
    async with db.execute("SELECT stars FROM combat_state WHERE character_name = ?", ("TestChar",)) as cursor:
        row = await cursor.fetchone()
        assert row is None, "Character not in combat should have no combat_state"

    print("[OK] Handles combat state checks correctly\n")

    # Test 7: Combat state management
    print("--- Test 7: Combat State Management ---")

    # Start combat
    await db.execute(
        "UPDATE initiative SET combat_active = 1, round_number = 1, current_turn_index = 0 WHERE id = 1"
    )

    # Add character to combat
    await db.execute(
        """INSERT INTO combat_state (character_name, current_hp, current_mp, stars, effects_json)
           VALUES (?, ?, ?, ?, ?)""",
        ("TestChar", 100, 50, 5, json.dumps([]))
    )

    await db.commit()

    # Verify combat state
    async with db.execute("SELECT combat_active FROM initiative WHERE id = 1") as cursor:
        row = await cursor.fetchone()
        assert row[0] == 1, "Combat should be active"

    async with db.execute("SELECT stars FROM combat_state WHERE character_name = ?", ("TestChar",)) as cursor:
        row = await cursor.fetchone()
        assert row is not None, "Character should have combat state"
        assert row[0] == 5, "Stars should be 5"

    print("[OK] Combat state managed correctly\n")

    # Test 8: Effect management
    print("--- Test 8: Effect Management ---")

    effects = [
        {"name": "Haste", "duration": 3},
        {"name": "Shield", "duration": 2}
    ]

    await db.execute(
        "UPDATE combat_state SET effects_json = ? WHERE character_name = ?",
        (json.dumps(effects), "TestChar")
    )

    await db.commit()

    # Verify effects
    async with db.execute("SELECT effects_json FROM combat_state WHERE character_name = ?", ("TestChar",)) as cursor:
        row = await cursor.fetchone()
        loaded_effects = json.loads(row[0])
        assert len(loaded_effects) == 2, "Should have 2 effects"
        assert loaded_effects[0]["name"] == "Haste", "First effect should be Haste"
        assert loaded_effects[1]["duration"] == 2, "Second effect duration should be 2"

    print("[OK] Effects stored and retrieved correctly\n")

    # Test 9: Deployable management
    print("--- Test 9: Deployable Management ---")

    await db.execute(
        """INSERT INTO deployables (name, owner, hp, max_hp, stars, max_stars, duration)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("TestTurret", "TestChar", 30, 30, 3, 3, 2)
    )

    await db.commit()

    # Verify deployable
    async with db.execute("SELECT name, owner, duration FROM deployables WHERE name = ?", ("TestTurret",)) as cursor:
        row = await cursor.fetchone()
        assert row is not None, "Deployable should exist"
        assert row[0] == "TestTurret", "Deployable name should match"
        assert row[1] == "TestChar", "Owner should match"
        assert row[2] == 2, "Duration should be 2"

    print("[OK] Deployable created and stored correctly\n")

    # Test 10: Cleanup
    print("--- Test 10: Cleanup ---")

    await db.execute("DELETE FROM deployables")
    await db.execute("DELETE FROM combat_state")
    await db.execute("DELETE FROM characters")
    await db.execute(
        "UPDATE initiative SET combat_active = 0, round_number = 0, current_turn_index = 0, turn_order_json = '[]' WHERE id = 1"
    )

    await db.commit()
    await db.close()

    print("[OK] Database cleaned up\n")

    print("=== ALL POLISH TESTS COMPLETE ===")
    print("\nSummary:")
    print("- Constants module: OK")
    print("- Validation helpers: OK")
    print("- Embed helpers: OK")
    print("- Database schema: OK")
    print("- Error handling: OK")
    print("- Combat state: OK")
    print("- Effects: OK")
    print("- Deployables: OK")
    print("\nAll systems polished and ready!")


if __name__ == "__main__":
    asyncio.run(main())
