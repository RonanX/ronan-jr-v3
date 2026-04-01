"""
Tests for /move info command
"""

import pytest
import aiosqlite


@pytest.mark.asyncio
async def test_move_info_data_integrity():
    """Test that move data is stored and retrieved correctly"""
    db = await aiosqlite.connect('database/ronan.db')

    # Test Storm Drummer (was failing with column mismatch)
    async with db.execute("""
        SELECT category, star_cost, mp_cost, hp_cost, stat, damage,
               hits, targets, save_type, save_dc, save_effect,
               half_on_save, bonus_on_hit, duration, cooldown, uses, description
        FROM movesets
        WHERE character_name = 'Hinobi' AND move_name = 'Storm Drummer'
    """) as cursor:
        row = await cursor.fetchone()

    assert row is not None, "Storm Drummer move not found"

    (category, star_cost, mp_cost, hp_cost, stat, damage,
     hits, targets, save_type, save_dc, save_effect,
     half_on_save, bonus_on_hit, duration, cooldown, uses, description) = row

    # Verify types and values
    assert category == 'medium'
    assert isinstance(star_cost, int) and star_cost == 0
    assert isinstance(mp_cost, int) and mp_cost == 10
    assert isinstance(hp_cost, int) and hp_cost == 0
    assert stat == 'dex'
    assert isinstance(damage, int) and damage == 3
    assert isinstance(hits, int) and hits == 4
    assert isinstance(targets, int) and targets == 1  # Was incorrectly a string
    assert save_type is None
    assert save_dc is None
    assert save_effect is None
    assert isinstance(half_on_save, int) and half_on_save == 0
    assert bonus_on_hit == "Clean hit: stun until your next turn"  # Was in wrong column
    assert isinstance(duration, int) and duration == 0
    assert isinstance(cooldown, int) and cooldown == 0
    assert uses is None

    await db.close()


@pytest.mark.asyncio
async def test_move_info_type_conversions():
    """Test that all numeric fields can be safely converted to int"""
    db = await aiosqlite.connect('database/ronan.db')

    # Get a sample of moves
    async with db.execute("""
        SELECT category, star_cost, mp_cost, hp_cost, stat, damage,
               hits, targets, save_type, save_dc, save_effect,
               half_on_save, bonus_on_hit, duration, cooldown, uses, description
        FROM movesets
        LIMIT 20
    """) as cursor:
        rows = await cursor.fetchall()

    for row in rows:
        (category, star_cost, mp_cost, hp_cost, stat, damage,
         hits, targets, save_type, save_dc, save_effect,
         half_on_save, bonus_on_hit, duration, cooldown, uses, description) = row

        # These should always be convertible to int (or None)
        assert star_cost is None or isinstance(int(star_cost), int)
        assert mp_cost is None or isinstance(int(mp_cost), int)
        assert hp_cost is None or isinstance(int(hp_cost), int)
        assert damage is None or isinstance(int(damage), int)
        assert hits is None or isinstance(int(hits), int)
        assert targets is None or isinstance(int(targets), int)  # Critical test
        assert save_dc is None or isinstance(int(save_dc), int)
        assert half_on_save is None or isinstance(int(half_on_save), int)
        assert duration is None or isinstance(int(duration), int)
        assert cooldown is None or isinstance(int(cooldown), int)
        assert uses is None or isinstance(int(uses), int)

        # These should be strings or None
        assert category is None or isinstance(category, str)
        assert stat is None or isinstance(stat, str)
        assert save_type is None or isinstance(save_type, str)
        assert save_effect is None or isinstance(save_effect, str)
        assert bonus_on_hit is None or isinstance(bonus_on_hit, str)
        assert description is None or isinstance(description, str)

    await db.close()


@pytest.mark.asyncio
async def test_alicia_moves_integrity():
    """Test Alicia's moves are correctly stored"""
    db = await aiosqlite.connect('database/ronan.db')

    async with db.execute("""
        SELECT move_name, category, star_cost, targets, bonus_on_hit
        FROM movesets
        WHERE character_name = 'Alicia'
        ORDER BY category, move_name
    """) as cursor:
        moves = await cursor.fetchall()

    assert len(moves) == 16, "Alicia should have 16 moves"

    # Check that all moves have valid data
    for move in moves:
        move_name, category, star_cost, targets, bonus_on_hit = move
        assert isinstance(move_name, str)
        assert category in ['light', 'medium', 'heavy', 'utility']
        assert isinstance(star_cost, int)
        assert targets is None or isinstance(targets, int)  # Should be int, not string
        assert bonus_on_hit is None or isinstance(bonus_on_hit, str)

    await db.close()
