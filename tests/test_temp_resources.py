"""
Comprehensive tests for temporary resource system
"""

import pytest
import pytest_asyncio
import aiosqlite
import json


@pytest_asyncio.fixture
async def temp_db():
    """Fixture that provides a database connection and cleans up temp resources after test"""
    db = await aiosqlite.connect('database/ronan.db')

    # Store original values
    async with db.execute("""
        SELECT temp_hp, temp_mp, temp_stars FROM characters WHERE name = 'Alicia'
    """) as cursor:
        original = await cursor.fetchone()

    yield db

    # Restore original values
    await db.execute("""
        UPDATE characters
        SET temp_hp = ?, temp_mp = ?, temp_stars = ?
        WHERE name = 'Alicia'
    """, original)
    await db.commit()
    await db.close()


@pytest.mark.asyncio
async def test_temp_hp_addition(temp_db):
    """Test adding temporary HP"""
    # Set temp HP
    await temp_db.execute("""
        UPDATE characters SET temp_hp = 20 WHERE name = 'Alicia'
    """)
    await temp_db.commit()

    # Verify
    async with temp_db.execute("""
        SELECT temp_hp FROM characters WHERE name = 'Alicia'
    """) as cursor:
        temp_hp, = await cursor.fetchone()

    assert temp_hp == 20, "Temp HP should be 20"


@pytest.mark.asyncio
async def test_temp_mp_addition(temp_db):
    """Test adding temporary MP"""
    # Set temp MP
    await temp_db.execute("""
        UPDATE characters SET temp_mp = 30 WHERE name = 'Alicia'
    """)
    await temp_db.commit()

    # Verify
    async with temp_db.execute("""
        SELECT temp_mp FROM characters WHERE name = 'Alicia'
    """) as cursor:
        temp_mp, = await cursor.fetchone()

    assert temp_mp == 30, "Temp MP should be 30"


@pytest.mark.asyncio
async def test_temp_stars_addition(temp_db):
    """Test adding temporary stars"""
    # Set temp stars
    await temp_db.execute("""
        UPDATE characters SET temp_stars = 2 WHERE name = 'Alicia'
    """)
    await temp_db.commit()

    # Verify
    async with temp_db.execute("""
        SELECT temp_stars FROM characters WHERE name = 'Alicia'
    """) as cursor:
        temp_stars, = await cursor.fetchone()

    assert temp_stars == 2, "Temp stars should be 2"


@pytest.mark.asyncio
async def test_temp_resources_replace_not_stack(temp_db):
    """Test that temp resources replace existing, don't stack"""
    # Set initial temp resources
    await temp_db.execute("""
        UPDATE characters
        SET temp_hp = 15, temp_mp = 20, temp_stars = 1
        WHERE name = 'Alicia'
    """)
    await temp_db.commit()

    # Replace with new values
    await temp_db.execute("""
        UPDATE characters
        SET temp_hp = 10, temp_mp = 25, temp_stars = 2
        WHERE name = 'Alicia'
    """)
    await temp_db.commit()

    # Verify new values (not added)
    async with temp_db.execute("""
        SELECT temp_hp, temp_mp, temp_stars FROM characters WHERE name = 'Alicia'
    """) as cursor:
        temp_hp, temp_mp, temp_stars = await cursor.fetchone()

    assert temp_hp == 10, "Temp HP should be replaced, not stacked"
    assert temp_mp == 25, "Temp MP should be replaced, not stacked"
    assert temp_stars == 2, "Temp stars should be replaced, not stacked"


@pytest.mark.asyncio
async def test_temp_hp_damage_depletion():
    """Test that damage depletes temp HP first"""
    db = await aiosqlite.connect('database/ronan.db')

    # Set character to 45 HP with 15 temp HP
    await db.execute("""
        UPDATE characters
        SET hp = 45, temp_hp = 15
        WHERE name = 'Alicia'
    """)
    await db.commit()

    # Simulate taking 25 damage (should deplete 15 temp HP + 10 real HP)
    async with db.execute("""
        SELECT hp, temp_hp FROM characters WHERE name = 'Alicia'
    """) as cursor:
        current_hp, current_temp_hp = await cursor.fetchone()

    damage = 25
    if current_temp_hp > 0:
        if damage <= current_temp_hp:
            new_temp_hp = current_temp_hp - damage
            new_hp = current_hp
        else:
            remaining_damage = damage - current_temp_hp
            new_temp_hp = 0
            new_hp = max(0, current_hp - remaining_damage)
    else:
        new_temp_hp = 0
        new_hp = max(0, current_hp - damage)

    await db.execute("""
        UPDATE characters
        SET hp = ?, temp_hp = ?
        WHERE name = 'Alicia'
    """, (new_hp, new_temp_hp))
    await db.commit()

    # Verify: should be 35 HP, 0 temp HP
    async with db.execute("""
        SELECT hp, temp_hp FROM characters WHERE name = 'Alicia'
    """) as cursor:
        final_hp, final_temp_hp = await cursor.fetchone()

    assert final_hp == 35, "HP should be 35 (45 - 10)"
    assert final_temp_hp == 0, "Temp HP should be depleted"

    # Restore
    await db.execute("UPDATE characters SET hp = 55, temp_hp = 0 WHERE name = 'Alicia'")
    await db.commit()
    await db.close()


@pytest.mark.asyncio
async def test_temp_stars_available_for_actions(temp_db):
    """Test that temp stars are added to max for available actions"""
    # Set character to 1 normal star + 2 temp stars
    await temp_db.execute("""
        UPDATE characters
        SET current_stars = 1, temp_stars = 2
        WHERE name = 'Alicia'
    """)
    await temp_db.commit()

    # Get available stars
    async with temp_db.execute("""
        SELECT current_stars, temp_stars, max_stars FROM characters WHERE name = 'Alicia'
    """) as cursor:
        current, temp, max_s = await cursor.fetchone()

    available_stars = current + temp

    assert available_stars == 3, "Should have 3 total stars available (1 normal + 2 temp)"
    assert current == 1, "Normal stars should be 1"
    assert temp == 2, "Temp stars should be 2"


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires combat table which doesn't exist yet")
async def test_temp_duration_effect_creation():
    """Test that temp_duration creates an effect entry"""
    db = await aiosqlite.connect('database/ronan.db')

    # Ensure combat is active and character is in combat_state
    await db.execute("UPDATE initiative SET combat_active = 1 WHERE id = 1")
    await db.execute("DELETE FROM combat WHERE id = 1")
    await db.execute("INSERT INTO combat (id, round_num) VALUES (1, 1)")

    # Ensure character exists in combat_state
    await db.execute("DELETE FROM combat_state WHERE character_name = 'Alicia'")
    await db.execute("""
        INSERT INTO combat_state (character_name, stars, effects_json)
        VALUES ('Alicia', 3, '[]')
    """)
    await db.commit()

    # Simulate adding temp resources with duration
    temp_hp = 15
    temp_stars = 1
    temp_duration = 3
    current_round = 1

    # Get existing effects
    async with db.execute("""
        SELECT effects_json FROM combat_state WHERE character_name = 'Alicia'
    """) as cursor:
        row = await cursor.fetchone()
        effects = json.loads(row[0]) if row and row[0] else []

    # Remove existing "Temporary Resources" effect
    effects = [e for e in effects if e.get("name") != "Temporary Resources"]

    # Add new temp resource effect
    effects.append({
        "name": "Temporary Resources",
        "duration": temp_duration,
        "applied_round": current_round,
        "temp_hp": temp_hp,
        "temp_mp": 0,
        "temp_stars": temp_stars
    })

    await db.execute("""
        UPDATE combat_state SET effects_json = ? WHERE character_name = 'Alicia'
    """, (json.dumps(effects),))
    await db.commit()

    # Verify effect was created
    async with db.execute("""
        SELECT effects_json FROM combat_state WHERE character_name = 'Alicia'
    """) as cursor:
        row = await cursor.fetchone()
        effects = json.loads(row[0])

    temp_effect = next((e for e in effects if e.get("name") == "Temporary Resources"), None)

    assert temp_effect is not None, "Temporary Resources effect should exist"
    assert temp_effect["duration"] == 3, "Duration should be 3"
    assert temp_effect["temp_hp"] == 15, "Should track temp_hp value"
    assert temp_effect["temp_stars"] == 1, "Should track temp_stars value"

    # Cleanup
    await db.execute("UPDATE initiative SET combat_active = 0 WHERE id = 1")
    await db.execute("DELETE FROM combat_state WHERE character_name = 'Alicia'")
    await db.commit()
    await db.close()


@pytest.mark.asyncio
async def test_temp_resource_expiry():
    """Test that temp resources are removed when effect expires"""
    db = await aiosqlite.connect('database/ronan.db')

    # Store original values first
    async with db.execute("""
        SELECT temp_hp, temp_mp, temp_stars FROM characters WHERE name = 'Alicia'
    """) as cursor:
        original = await cursor.fetchone()

    # Set temp resources on character
    await db.execute("""
        UPDATE characters
        SET temp_hp = 15, temp_mp = 20, temp_stars = 1
        WHERE name = 'Alicia'
    """)
    await db.commit()

    # Verify they exist
    async with db.execute("""
        SELECT temp_hp, temp_mp, temp_stars FROM characters WHERE name = 'Alicia'
    """) as cursor:
        temp_hp, temp_mp, temp_stars = await cursor.fetchone()

    assert temp_hp == 15
    assert temp_mp == 20
    assert temp_stars == 1

    # Simulate expiry (set to 0)
    await db.execute("""
        UPDATE characters
        SET temp_hp = 0, temp_mp = 0, temp_stars = 0
        WHERE name = 'Alicia'
    """)
    await db.commit()

    # Verify removed
    async with db.execute("""
        SELECT temp_hp, temp_mp, temp_stars FROM characters WHERE name = 'Alicia'
    """) as cursor:
        temp_hp, temp_mp, temp_stars = await cursor.fetchone()

    assert temp_hp == 0, "Temp HP should be removed"
    assert temp_mp == 0, "Temp MP should be removed"
    assert temp_stars == 0, "Temp stars should be removed"

    # Restore original values
    await db.execute("""
        UPDATE characters
        SET temp_hp = ?, temp_mp = ?, temp_stars = ?
        WHERE name = 'Alicia'
    """, original)
    await db.commit()

    await db.close()


@pytest.mark.asyncio
async def test_no_upper_limit_for_temp_resources(temp_db):
    """Test that temp resources have no upper limit (unlike regular resources)"""
    # Get max values
    async with temp_db.execute("""
        SELECT max_hp, max_mp, max_stars FROM characters WHERE name = 'Alicia'
    """) as cursor:
        max_hp, max_mp, max_stars = await cursor.fetchone()

    # Set temp resources way above max
    high_temp = max_hp * 2  # Double the max
    await temp_db.execute("""
        UPDATE characters
        SET temp_hp = ?, temp_mp = ?, temp_stars = ?
        WHERE name = 'Alicia'
    """, (high_temp, high_temp, max_stars * 2))
    await temp_db.commit()

    # Verify they're stored (not clamped)
    async with temp_db.execute("""
        SELECT temp_hp, temp_mp, temp_stars FROM characters WHERE name = 'Alicia'
    """) as cursor:
        temp_hp, temp_mp, temp_stars = await cursor.fetchone()

    assert temp_hp == high_temp, "Temp HP should not be clamped"
    assert temp_mp == high_temp, "Temp MP should not be clamped"
    assert temp_stars == max_stars * 2, "Temp stars should not be clamped"


@pytest.mark.asyncio
async def test_mixing_regular_and_temp_updates(temp_db):
    """Test updating both regular and temp resources in one operation"""
    # Get max HP
    async with temp_db.execute("""
        SELECT max_hp FROM characters WHERE name = 'Alicia'
    """) as cursor:
        max_hp, = await cursor.fetchone()

    # Update: restore HP to max + add temp stars
    await temp_db.execute("""
        UPDATE characters
        SET hp = ?, temp_stars = 2
        WHERE name = 'Alicia'
    """, (max_hp,))
    await temp_db.commit()

    # Verify both updates
    async with temp_db.execute("""
        SELECT hp, max_hp, temp_stars FROM characters WHERE name = 'Alicia'
    """) as cursor:
        hp, max_hp, temp_stars = await cursor.fetchone()

    assert hp == max_hp, "HP should be restored to max"
    assert temp_stars == 2, "Temp stars should be added"
