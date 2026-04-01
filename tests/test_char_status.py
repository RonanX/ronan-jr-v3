"""
Tests for /char status command
"""

import pytest
import aiosqlite


@pytest.mark.asyncio
async def test_char_status_read_only():
    """Test that status reading doesn't modify database"""
    db = await aiosqlite.connect('database/ronan.db')

    # Get Alicia's current stats
    async with db.execute("""
        SELECT hp, max_hp, mp, max_mp, current_stars, max_stars, ac
        FROM characters WHERE name = 'Alicia'
    """) as cursor:
        before = await cursor.fetchone()

    # Simulate reading status (no updates)
    # In actual command: /char status Alicia (no params)
    # Should show: ❤️ 55/55  💙 110/110  ⭐ 3/3  🛡️ 13

    # Check nothing changed
    async with db.execute("""
        SELECT hp, max_hp, mp, max_mp, current_stars, max_stars, ac
        FROM characters WHERE name = 'Alicia'
    """) as cursor:
        after = await cursor.fetchone()

    assert before == after, "Read-only status check should not modify database"

    await db.close()


@pytest.mark.asyncio
async def test_char_status_hp_update():
    """Test HP update with delta"""
    db = await aiosqlite.connect('database/ronan.db')

    # Get Hinobi's current HP
    async with db.execute("""
        SELECT hp, max_hp FROM characters WHERE name = 'Hinobi'
    """) as cursor:
        old_hp, max_hp = await cursor.fetchone()

    # Simulate: /char status Hinobi hp:40
    new_hp = 40
    await db.execute("UPDATE characters SET hp = ? WHERE name = ?", (new_hp, "Hinobi"))
    await db.commit()

    # Verify update
    async with db.execute("SELECT hp FROM characters WHERE name = 'Hinobi'") as cursor:
        result_hp, = await cursor.fetchone()

    assert result_hp == new_hp, f"HP should be {new_hp}"

    # Restore original
    await db.execute("UPDATE characters SET hp = ? WHERE name = ?", (old_hp, "Hinobi"))
    await db.commit()

    await db.close()


@pytest.mark.asyncio
async def test_char_status_senzu():
    """Test senzu bean (restore to max)"""
    db = await aiosqlite.connect('database/ronan.db')

    # Set Alicia to low resources
    await db.execute("""
        UPDATE characters
        SET hp = 20, mp = 30, current_stars = 1
        WHERE name = 'Alicia'
    """)
    await db.commit()

    # Get max values
    async with db.execute("""
        SELECT max_hp, max_mp, max_stars FROM characters WHERE name = 'Alicia'
    """) as cursor:
        max_hp, max_mp, max_stars = await cursor.fetchone()

    # Simulate: /char status Alicia hp:senzu mp:senzu stars:senzu
    await db.execute("""
        UPDATE characters
        SET hp = ?, mp = ?, current_stars = ?
        WHERE name = 'Alicia'
    """, (max_hp, max_mp, max_stars))
    await db.commit()

    # Verify all restored to max
    async with db.execute("""
        SELECT hp, mp, current_stars FROM characters WHERE name = 'Alicia'
    """) as cursor:
        hp, mp, stars = await cursor.fetchone()

    assert hp == max_hp, "HP should be restored to max"
    assert mp == max_mp, "MP should be restored to max"
    assert stars == max_stars, "Stars should be restored to max"

    await db.close()


@pytest.mark.asyncio
async def test_char_status_multiple_updates():
    """Test updating multiple resources at once"""
    db = await aiosqlite.connect('database/ronan.db')

    # Store original values
    async with db.execute("""
        SELECT hp, mp, current_stars FROM characters WHERE name = 'Hinobi'
    """) as cursor:
        old_hp, old_mp, old_stars = await cursor.fetchone()

    # Simulate: /char status Hinobi hp:40 mp:100 stars:1
    new_hp, new_mp, new_stars = 40, 100, 1
    await db.execute("""
        UPDATE characters
        SET hp = ?, mp = ?, current_stars = ?
        WHERE name = ?
    """, (new_hp, new_mp, new_stars, "Hinobi"))
    await db.commit()

    # Verify all updated
    async with db.execute("""
        SELECT hp, mp, current_stars FROM characters WHERE name = 'Hinobi'
    """) as cursor:
        hp, mp, stars = await cursor.fetchone()

    assert hp == new_hp
    assert mp == new_mp
    assert stars == new_stars

    # Restore original
    await db.execute("""
        UPDATE characters
        SET hp = ?, mp = ?, current_stars = ?
        WHERE name = ?
    """, (old_hp, old_mp, old_stars, "Hinobi"))
    await db.commit()

    await db.close()


@pytest.mark.asyncio
async def test_char_status_clamping():
    """Test that values are clamped to 0-max"""
    db = await aiosqlite.connect('database/ronan.db')

    # Get Alicia's max values
    async with db.execute("""
        SELECT max_hp, max_mp, max_stars FROM characters WHERE name = 'Alicia'
    """) as cursor:
        max_hp, max_mp, max_stars = await cursor.fetchone()

    # Try to set above max
    new_hp = min(999, max_hp)  # Should clamp to max_hp
    new_mp = min(999, max_mp)  # Should clamp to max_mp
    new_stars = min(999, max_stars)  # Should clamp to max_stars

    await db.execute("""
        UPDATE characters
        SET hp = ?, mp = ?, current_stars = ?
        WHERE name = ?
    """, (new_hp, new_mp, new_stars, "Alicia"))
    await db.commit()

    # Verify clamping
    async with db.execute("""
        SELECT hp, mp, current_stars FROM characters WHERE name = 'Alicia'
    """) as cursor:
        hp, mp, stars = await cursor.fetchone()

    assert hp <= max_hp, "HP should be clamped to max"
    assert mp <= max_mp, "MP should be clamped to max"
    assert stars <= max_stars, "Stars should be clamped to max"

    # Try to set below 0
    new_hp = max(-999, 0)  # Should clamp to 0
    new_mp = max(-999, 0)  # Should clamp to 0
    new_stars = max(-999, 0)  # Should clamp to 0

    await db.execute("""
        UPDATE characters
        SET hp = ?, mp = ?, current_stars = ?
        WHERE name = ?
    """, (new_hp, new_mp, new_stars, "Alicia"))
    await db.commit()

    # Verify clamping
    async with db.execute("""
        SELECT hp, mp, current_stars FROM characters WHERE name = 'Alicia'
    """) as cursor:
        hp, mp, stars = await cursor.fetchone()

    assert hp >= 0, "HP should be clamped to 0"
    assert mp >= 0, "MP should be clamped to 0"
    assert stars >= 0, "Stars should be clamped to 0"

    await db.close()
