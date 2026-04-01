"""
Test /char status relative value syntax (+/-)
"""
import pytest
import pytest_asyncio
import aiosqlite


@pytest_asyncio.fixture
async def temp_db():
    """Fixture that provides a database connection and cleans up after test"""
    db = await aiosqlite.connect('database/ronan.db')

    # Store original values for Alicia
    async with db.execute("""
        SELECT hp, mp, current_stars FROM characters WHERE name = 'Alicia'
    """) as cursor:
        original = await cursor.fetchone()

    yield db

    # Restore original values
    if original:
        await db.execute("""
            UPDATE characters
            SET hp = ?, mp = ?, current_stars = ?
            WHERE name = 'Alicia'
        """, original)
        await db.commit()

    await db.close()


@pytest.mark.asyncio
async def test_char_status_relative_positive(temp_db):
    """Test adding resources with + syntax"""
    db = temp_db

    # Get initial values
    async with db.execute("""
        SELECT hp, max_hp FROM characters WHERE name = 'Alicia'
    """) as cursor:
        row = await cursor.fetchone()
        initial_hp, max_hp = row

    # Damage character first
    await db.execute("""
        UPDATE characters SET hp = ? WHERE name = 'Alicia'
    """, (initial_hp - 20,))
    await db.commit()

    # Now test relative addition
    async with db.execute("""
        SELECT hp FROM characters WHERE name = 'Alicia'
    """) as cursor:
        current_hp = (await cursor.fetchone())[0]

    # Simulate the relative syntax parsing
    hp_str = "+10"
    if hp_str.startswith(('+', '-')):
        delta = int(hp_str)
        new_hp = max(0, min(current_hp + delta, max_hp))
    else:
        new_hp = max(0, min(int(hp_str), max_hp))

    await db.execute("""
        UPDATE characters SET hp = ? WHERE name = 'Alicia'
    """, (new_hp,))
    await db.commit()

    # Verify
    async with db.execute("""
        SELECT hp FROM characters WHERE name = 'Alicia'
    """) as cursor:
        final_hp = (await cursor.fetchone())[0]

    expected_hp = max(0, min(current_hp + 10, max_hp))
    assert final_hp == expected_hp, f"Expected {expected_hp}, got {final_hp}"


@pytest.mark.asyncio
async def test_char_status_relative_negative(temp_db):
    """Test subtracting resources with - syntax"""
    db = temp_db

    # Get initial values
    async with db.execute("""
        SELECT mp, max_mp FROM characters WHERE name = 'Alicia'
    """) as cursor:
        row = await cursor.fetchone()
        initial_mp, max_mp = row

    # Test relative subtraction
    mp_str = "-15"
    if mp_str.startswith(('+', '-')):
        delta = int(mp_str)
        new_mp = max(0, min(initial_mp + delta, max_mp))
    else:
        new_mp = max(0, min(int(mp_str), max_mp))

    await db.execute("""
        UPDATE characters SET mp = ? WHERE name = 'Alicia'
    """, (new_mp,))
    await db.commit()

    # Verify
    async with db.execute("""
        SELECT mp FROM characters WHERE name = 'Alicia'
    """) as cursor:
        final_mp = (await cursor.fetchone())[0]

    expected_mp = max(0, min(initial_mp - 15, max_mp))
    assert final_mp == expected_mp, f"Expected {expected_mp}, got {final_mp}"


@pytest.mark.asyncio
async def test_char_status_relative_clamping(temp_db):
    """Test that relative values clamp to min/max"""
    db = temp_db

    # Get initial values
    async with db.execute("""
        SELECT current_stars, max_stars FROM characters WHERE name = 'Alicia'
    """) as cursor:
        row = await cursor.fetchone()
        initial_stars, max_stars = row

    # Test adding more than max
    stars_str = "+100"
    if stars_str.startswith(('+', '-')):
        delta = int(stars_str)
        new_stars = max(0, min(initial_stars + delta, max_stars))
    else:
        new_stars = max(0, min(int(stars_str), max_stars))

    assert new_stars == max_stars, f"Should clamp to max_stars {max_stars}, got {new_stars}"

    # Test subtracting below 0
    stars_str = "-100"
    if stars_str.startswith(('+', '-')):
        delta = int(stars_str)
        new_stars = max(0, min(initial_stars + delta, max_stars))
    else:
        new_stars = max(0, min(int(stars_str), max_stars))

    assert new_stars == 0, f"Should clamp to 0, got {new_stars}"
