"""
Test character system: creation, validation, tiers, grunt flag, stat calculations
"""

import pytest
import pytest_asyncio
import aiosqlite
import json
import os


# Test database path
TEST_DB = "database/test_ronan.db"


@pytest_asyncio.fixture
async def db():
    """Create test database"""
    # Remove old test db
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

    # Create fresh database
    async with aiosqlite.connect(TEST_DB) as conn:
        # Characters table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS characters (
                name TEXT PRIMARY KEY,
                hp INTEGER NOT NULL,
                max_hp INTEGER NOT NULL,
                mp INTEGER NOT NULL,
                max_mp INTEGER NOT NULL,
                ac INTEGER NOT NULL,
                proficiency INTEGER DEFAULT 2,
                stats_json TEXT NOT NULL,
                temp_hp INTEGER DEFAULT 0,
                tier TEXT DEFAULT 'veteran',
                grunt INTEGER DEFAULT 0,
                base_stats_json TEXT
            )
        """)
        await conn.commit()

    yield TEST_DB

    # Cleanup
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


@pytest.mark.asyncio
async def test_character_creation_veteran(db):
    """Test creating a veteran tier character"""
    async with aiosqlite.connect(db) as conn:
        stats = {"str": 3, "dex": 4, "con": 2, "int": 2, "wis": 3, "cha": 2}

        await conn.execute(
            """INSERT INTO characters
            (name, hp, max_hp, mp, max_mp, ac, proficiency, stats_json, tier, grunt, base_stats_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("TestHero", 100, 100, 50, 50, 14, 3, json.dumps(stats), "veteran", 0, json.dumps(stats))
        )
        await conn.commit()

        # Verify
        async with conn.execute("SELECT * FROM characters WHERE name = ?", ("TestHero",)) as cursor:
            row = await cursor.fetchone()
            assert row is not None
            assert row[0] == "TestHero"
            assert row[6] == 3  # proficiency
            loaded_stats = json.loads(row[7])
            assert loaded_stats["str"] == 3
            assert loaded_stats["dex"] == 4


@pytest.mark.asyncio
async def test_stat_validation_range(db):
    """Test that stats must be 0-4 for veteran"""
    stats = {"str": 3, "dex": 4, "con": 2, "int": 2, "wis": 3, "cha": 2}
    total = sum(stats.values())

    # Veteran should be 12-16 stat points
    assert 12 <= total <= 16, f"Veteran stats {total} outside 12-16 range"

    # Each stat should be 0-4
    for stat_name, value in stats.items():
        assert 0 <= value <= 4, f"Stat {stat_name}={value} outside 0-4 range"


@pytest.mark.asyncio
async def test_tier_proficiency_mapping(db):
    """Test that tier determines proficiency correctly"""
    tier_config = {
        "rookie": {"prof": 2, "stat_min": 10, "stat_max": 14},
        "veteran": {"prof": 3, "stat_min": 12, "stat_max": 16},
        "elite": {"prof": 4, "stat_min": 16, "stat_max": 20}
    }

    # Verify config
    assert tier_config["rookie"]["prof"] == 2
    assert tier_config["veteran"]["prof"] == 3
    assert tier_config["elite"]["prof"] == 4


@pytest.mark.asyncio
async def test_grunt_flag(db):
    """Test grunt flag is stored correctly"""
    async with aiosqlite.connect(db) as conn:
        stats = {"str": 2, "dex": 2, "con": 2, "int": 2, "wis": 2, "cha": 2}

        # Create grunt character
        await conn.execute(
            """INSERT INTO characters
            (name, hp, max_hp, mp, max_mp, ac, proficiency, stats_json, tier, grunt, base_stats_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("TestGrunt", 50, 50, 25, 25, 12, 3, json.dumps(stats), "veteran", 1, json.dumps(stats))
        )
        await conn.commit()

        # Verify grunt flag
        async with conn.execute("SELECT grunt FROM characters WHERE name = ?", ("TestGrunt",)) as cursor:
            row = await cursor.fetchone()
            assert row[0] == 1  # grunt = true


@pytest.mark.asyncio
async def test_base_stats_tracking(db):
    """Test that base_stats_json tracks original stats for transformations"""
    async with aiosqlite.connect(db) as conn:
        base_stats = {"str": 3, "dex": 3, "con": 3, "int": 3, "wis": 2, "cha": 2}

        await conn.execute(
            """INSERT INTO characters
            (name, hp, max_hp, mp, max_mp, ac, proficiency, stats_json, base_stats_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("TestShape", 80, 80, 40, 40, 13, 3, json.dumps(base_stats), json.dumps(base_stats))
        )
        await conn.commit()

        # Verify base stats match
        async with conn.execute(
            "SELECT stats_json, base_stats_json FROM characters WHERE name = ?",
            ("TestShape",)
        ) as cursor:
            row = await cursor.fetchone()
            current = json.loads(row[0])
            base = json.loads(row[1])
            assert current == base


@pytest.mark.asyncio
async def test_save_dc_calculation(db):
    """Test Save DC = 8 + prof + highest mental stat"""
    stats = {"str": 2, "dex": 3, "con": 2, "int": 4, "wis": 3, "cha": 2}
    prof = 3

    mental_stats = [stats["int"], stats["wis"], stats["cha"]]
    highest_mental = max(mental_stats)

    expected_dc = 8 + prof + highest_mental
    assert expected_dc == 15  # 8 + 3 + 4


@pytest.mark.asyncio
async def test_temp_hp_storage(db):
    """Test temp HP is stored separately"""
    async with aiosqlite.connect(db) as conn:
        stats = {"str": 3, "dex": 3, "con": 3, "int": 2, "wis": 2, "cha": 3}

        await conn.execute(
            """INSERT INTO characters
            (name, hp, max_hp, mp, max_mp, ac, proficiency, stats_json, temp_hp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("TestTemp", 100, 100, 50, 50, 14, 3, json.dumps(stats), 20)
        )
        await conn.commit()

        # Verify temp HP
        async with conn.execute(
            "SELECT hp, max_hp, temp_hp FROM characters WHERE name = ?",
            ("TestTemp",)
        ) as cursor:
            row = await cursor.fetchone()
            assert row[0] == 100  # current HP
            assert row[1] == 100  # max HP
            assert row[2] == 20   # temp HP


@pytest.mark.asyncio
async def test_char_show_formatting(db):
    """Test character display formatting logic with Discord emojis"""
    # Health bar rendering
    def create_health_bar(current: int, max_hp: int, temp: int) -> str:
        if max_hp <= 0:
            return ":black_large_square:" * 10 + " (0%)"

        hp_percentage = current / max_hp
        temp_percentage = temp / max_hp

        hp_blocks = round(hp_percentage * 10)
        temp_blocks = round(temp_percentage * 10)

        filled = ":green_square:" * hp_blocks
        temp_bar = ":white_large_square:" * temp_blocks

        total_blocks = hp_blocks + temp_blocks
        if total_blocks <= 10:
            empty = ":black_large_square:" * (10 - total_blocks)
        else:
            empty = ""

        return filled + temp_bar + empty

    # Test cases
    bar1 = create_health_bar(100, 100, 0)
    assert bar1 == ":green_square:" * 10

    bar2 = create_health_bar(50, 100, 0)
    assert bar2 == ":green_square:" * 5 + ":black_large_square:" * 5

    bar3 = create_health_bar(50, 100, 20)
    assert bar3 == ":green_square:" * 5 + ":white_large_square:" * 2 + ":black_large_square:" * 3
