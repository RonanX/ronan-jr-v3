"""
Real integration tests for database operations - NO MOCKS
Uses actual SQLite database with WAL mode enabled
"""

import asyncio
import aiosqlite
import json
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.init_db import init_database
from utils.effects import apply_effect, remove_effect, get_active_effects, get_preset_effect


TEST_DB_PATH = "test_ronan.db"


async def setup_test_db():
    """Create a real test database with actual schema"""
    # Delete old test DB if exists
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

    # Create connection and initialize schema
    db = await aiosqlite.connect(TEST_DB_PATH)

    # Enable WAL mode
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")

    # Initialize schema by running the actual init_db tables
    # (We can't call init_database() directly as it uses a different path)
    # So we'll copy the schema creation

    # Characters table
    await db.execute("""
        CREATE TABLE IF NOT EXISTS characters (
            name TEXT PRIMARY KEY,
            hp INTEGER NOT NULL,
            max_hp INTEGER NOT NULL,
            mp INTEGER NOT NULL,
            max_mp INTEGER NOT NULL,
            ac INTEGER NOT NULL,
            movement INTEGER DEFAULT 30,
            proficiency INTEGER DEFAULT 2,
            stats_json TEXT NOT NULL,
            current_form TEXT DEFAULT 'base',
            base_stats_json TEXT,
            base_stats TEXT,
            stat_modifiers TEXT,
            roll_modifiers TEXT,
            max_stars INTEGER DEFAULT 3,
            current_stars INTEGER,
            temp_hp INTEGER DEFAULT 0,
            temp_mp INTEGER DEFAULT 0,
            temp_stars INTEGER DEFAULT 0,
            ac_modifier INTEGER DEFAULT 0,
            ac_modifier_source TEXT,
            threshold_damage INTEGER,
            threshold_dc INTEGER,
            hidden_resources INTEGER DEFAULT 0,
            squishy INTEGER DEFAULT 0,
            tier TEXT,
            grunt INTEGER DEFAULT 0
        )
    """)

    # Effects table
    await db.execute("""
        CREATE TABLE IF NOT EXISTS effects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_name TEXT NOT NULL,
            effect_name TEXT NOT NULL,
            emoji TEXT,
            available_until_round INTEGER,
            contributions TEXT,
            dot_damage INTEGER DEFAULT 0,
            dot_type TEXT,
            dot_value TEXT DEFAULT '0',
            resource_type TEXT DEFAULT 'hp',
            resource_change INTEGER DEFAULT 0,
            resource_value TEXT DEFAULT '0',
            stackable INTEGER DEFAULT 0,
            note TEXT DEFAULT '',
            FOREIGN KEY (character_name) REFERENCES characters(name) ON DELETE CASCADE
        )
    """)

    await db.commit()
    return db


async def cleanup_test_db(db):
    """Close connection and delete test database"""
    await db.close()
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    # Also remove WAL files
    for ext in ['-wal', '-shm']:
        wal_file = TEST_DB_PATH + ext
        if os.path.exists(wal_file):
            os.remove(wal_file)


async def create_test_character(db, name="TestChar"):
    """Insert a real test character with proper JSON fields"""
    base_stats = json.dumps({"str": 3, "dex": 2, "con": 3, "int": 1, "wis": 2, "cha": 1})
    stat_mods = json.dumps({"str": 0, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0})
    roll_mods = json.dumps({"attack_modifier": 0, "save_modifier": 0, "incoming_modifier": 0})

    await db.execute("""
        INSERT INTO characters (
            name, hp, max_hp, mp, max_mp, ac, proficiency,
            stats_json, base_stats, stat_modifiers, roll_modifiers
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (name, 50, 50, 30, 30, 13, 3, base_stats, base_stats, stat_mods, roll_mods))

    await db.commit()


async def test_apply_effect_with_native_json():
    """Test that apply_effect correctly uses native JSON updates"""
    print("\n=== TEST: Apply Effect with Native JSON Updates ===")

    db = await setup_test_db()

    try:
        # Create test character
        await create_test_character(db, "Alice")

        # Verify initial state
        async with db.execute("SELECT stat_modifiers, roll_modifiers, ac_modifier FROM characters WHERE name = 'Alice'") as cursor:
            row = await cursor.fetchone()
            initial_stat_mods = json.loads(row[0])
            initial_roll_mods = json.loads(row[1])
            initial_ac_mod = row[2]

        print(f"Initial stat_modifiers: {initial_stat_mods}")
        print(f"Initial roll_modifiers: {initial_roll_mods}")
        print(f"Initial ac_modifier: {initial_ac_mod}")

        assert initial_stat_mods['str'] == 0, "Initial str should be 0"
        assert initial_roll_mods['attack_modifier'] == 0, "Initial attack_modifier should be 0"
        assert initial_ac_mod == 0, "Initial ac_modifier should be 0"

        # Apply an effect that modifies stats
        effect_data = get_preset_effect("advantage", duration=5)
        effect_data['contributions']['stat_modifiers'] = {'str': 2, 'dex': 1}
        effect_data['contributions']['ac_modifier'] = 3

        await apply_effect("Alice", effect_data, db)

        # Verify effect was applied using native JSON
        async with db.execute("SELECT stat_modifiers, roll_modifiers, ac_modifier FROM characters WHERE name = 'Alice'") as cursor:
            row = await cursor.fetchone()
            updated_stat_mods = json.loads(row[0])
            updated_roll_mods = json.loads(row[1])
            updated_ac_mod = row[2]

        print(f"Updated stat_modifiers: {updated_stat_mods}")
        print(f"Updated roll_modifiers: {updated_roll_mods}")
        print(f"Updated ac_modifier: {updated_ac_mod}")

        # Verify changes
        assert updated_stat_mods['str'] == 2, f"Expected str=2, got {updated_stat_mods['str']}"
        assert updated_stat_mods['dex'] == 1, f"Expected dex=1, got {updated_stat_mods['dex']}"
        assert updated_roll_mods['attack_modifier'] == 1, f"Expected attack_modifier=1 (from advantage), got {updated_roll_mods['attack_modifier']}"
        assert updated_ac_mod == 3, f"Expected ac_modifier=3, got {updated_ac_mod}"

        # Verify effect was inserted
        effects = await get_active_effects("Alice", db)
        assert len(effects) == 1, f"Expected 1 effect, got {len(effects)}"
        assert effects[0]['name'] == 'advantage', f"Expected 'advantage', got {effects[0]['name']}"

        print("[PASS] Effect applied correctly using native JSON updates")

    finally:
        await cleanup_test_db(db)


async def test_remove_effect_with_native_json():
    """Test that remove_effect correctly uses native JSON updates to subtract"""
    print("\n=== TEST: Remove Effect with Native JSON Updates ===")

    db = await setup_test_db()

    try:
        # Create test character
        await create_test_character(db, "Bob")

        # Apply effect
        effect_data = get_preset_effect("marked", duration=3)
        effect_data['contributions']['stat_modifiers'] = {'con': 2}
        effect_data['contributions']['ac_modifier'] = -1

        await apply_effect("Bob", effect_data, db)

        # Verify effect applied
        async with db.execute("SELECT stat_modifiers, ac_modifier FROM characters WHERE name = 'Bob'") as cursor:
            row = await cursor.fetchone()
            stat_mods = json.loads(row[0])
            ac_mod = row[1]

        print(f"After apply - stat_modifiers: {stat_mods}, ac_modifier: {ac_mod}")
        assert stat_mods['con'] == 2, "CON should be +2 after apply"
        assert ac_mod == -1, "AC modifier should be -1 after apply"

        # Get effect ID
        effects = await get_active_effects("Bob", db)
        effect_id = effects[0]['id']

        # Remove effect
        await remove_effect("Bob", effect_id, db)

        # Verify effect was removed using native JSON
        async with db.execute("SELECT stat_modifiers, roll_modifiers, ac_modifier FROM characters WHERE name = 'Bob'") as cursor:
            row = await cursor.fetchone()
            final_stat_mods = json.loads(row[0])
            final_roll_mods = json.loads(row[1])
            final_ac_mod = row[2]

        print(f"After remove - stat_modifiers: {final_stat_mods}, ac_modifier: {final_ac_mod}")

        # Should be back to 0
        assert final_stat_mods['con'] == 0, f"Expected con=0 after removal, got {final_stat_mods['con']}"
        assert final_roll_mods['incoming_modifier'] == 0, f"Expected incoming_modifier=0 after removal, got {final_roll_mods['incoming_modifier']}"
        assert final_ac_mod == 0, f"Expected ac_modifier=0 after removal, got {final_ac_mod}"

        # Verify effect was deleted
        effects_after = await get_active_effects("Bob", db)
        assert len(effects_after) == 0, f"Expected 0 effects after removal, got {len(effects_after)}"

        print("[PASS] Effect removed correctly using native JSON updates")

    finally:
        await cleanup_test_db(db)


async def test_multiple_effects_stacking():
    """Test that multiple effects correctly stack using atomic JSON operations"""
    print("\n=== TEST: Multiple Effects Stacking ===")

    db = await setup_test_db()

    try:
        # Create test character
        await create_test_character(db, "Charlie")

        # Apply multiple effects to same stat
        effect1 = get_preset_effect("advantage", duration=5)
        effect1['contributions']['stat_modifiers'] = {'str': 3}

        effect2 = get_preset_effect("advantage", duration=5)
        effect2['contributions']['stat_modifiers'] = {'str': 2, 'dex': 1}

        # Apply both
        await apply_effect("Charlie", effect1, db)
        await apply_effect("Charlie", effect2, db)

        # Verify stacking
        async with db.execute("SELECT stat_modifiers FROM characters WHERE name = 'Charlie'") as cursor:
            row = await cursor.fetchone()
            stat_mods = json.loads(row[0])

        print(f"After stacking - stat_modifiers: {stat_mods}")
        assert stat_mods['str'] == 5, f"Expected str=5 (3+2), got {stat_mods['str']}"
        assert stat_mods['dex'] == 1, f"Expected dex=1, got {stat_mods['dex']}"

        print("[PASS] Multiple effects stacked correctly")

    finally:
        await cleanup_test_db(db)


async def run_all_tests():
    """Run all integration tests"""
    print("Starting Real Database Integration Tests...")
    print("=" * 60)

    try:
        await test_apply_effect_with_native_json()
        await test_remove_effect_with_native_json()
        await test_multiple_effects_stacking()

        print("\n" + "=" * 60)
        print("[SUCCESS] ALL TESTS PASSED")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n[FAIL] TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
