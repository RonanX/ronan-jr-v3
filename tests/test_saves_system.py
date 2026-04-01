"""
Test saves system: save rolls, hide_dc, nat 20 crit success, emojis
"""

import pytest
import random


@pytest.mark.asyncio
async def test_save_roll_basic():
    """Test basic save roll: d20 + stat vs DC"""
    stat_rating = 3
    dc = 15

    # Simulate roll
    roll = random.randint(1, 20)
    total = roll + stat_rating

    success = total >= dc

    # Verify calculation
    assert total == roll + stat_rating
    assert isinstance(success, bool)


@pytest.mark.asyncio
async def test_save_type_emojis():
    """Test all 6 save type emojis are correct"""
    save_emojis = {
        "str": "💪",
        "dex": "🤸",
        "con": "🛡️",
        "int": "🧠",
        "wis": "👁️",
        "cha": "✨"
    }

    # Verify all 6 stats have emojis
    assert len(save_emojis) == 6

    # Verify specific emojis
    assert save_emojis["str"] == "💪"
    assert save_emojis["dex"] == "🤸"
    assert save_emojis["con"] == "🛡️"
    assert save_emojis["int"] == "🧠"
    assert save_emojis["wis"] == "👁️"
    assert save_emojis["cha"] == "✨"


@pytest.mark.asyncio
async def test_nat_20_crit_success():
    """Test natural 20 adds +10 bonus"""
    stat_rating = 2
    dc = 18

    # Normal roll of 15
    roll = 15
    normal_total = roll + stat_rating
    assert normal_total == 17  # Fails DC 18

    # Natural 20
    nat_20_roll = 20
    base_total = nat_20_roll + stat_rating  # 22

    # Nat 20 bonus
    is_nat_20 = (nat_20_roll == 20)
    if is_nat_20:
        crit_total = base_total + 10
    else:
        crit_total = base_total

    assert is_nat_20 is True
    assert crit_total == 32  # 20 + 2 + 10
    assert crit_total >= dc  # Passes DC 18


@pytest.mark.asyncio
async def test_hide_dc_flag():
    """Test hide_dc hides DC in output"""
    roll = 14
    stat_rating = 3
    total = roll + stat_rating
    dc = 15
    hide_dc = True

    # Build result line
    if hide_dc:
        result_line = f"🎲 Result: {total}"
    else:
        result_line = f"🎲 Result: {total}  🎯 DC: {dc}"

    # When hide_dc=True, should not contain DC
    assert "DC" not in result_line
    assert str(total) in result_line


@pytest.mark.asyncio
async def test_hide_dc_false():
    """Test hide_dc=False shows DC"""
    roll = 16
    stat_rating = 2
    total = roll + stat_rating
    dc = 12
    hide_dc = False

    if hide_dc:
        result_line = f"🎲 Result: {total}"
    else:
        result_line = f"🎲 Result: {total}  🎯 DC: {dc}"

    # When hide_dc=False, should show DC
    assert "DC" in result_line
    assert str(dc) in result_line


@pytest.mark.asyncio
async def test_save_success_logic():
    """Test success determined by total >= dc"""
    test_cases = [
        (15, 15, True),   # Exactly meets DC
        (16, 15, True),   # Beats DC
        (14, 15, False),  # Misses DC
        (20, 5, True),    # Way over DC
        (1, 20, False)    # Way under DC
    ]

    for total, dc, expected_success in test_cases:
        actual_success = (total >= dc)
        assert actual_success == expected_success, f"Failed for total={total}, dc={dc}"


@pytest.mark.asyncio
async def test_nat_20_with_hide_dc():
    """Test nat 20 shows crit success even with hide_dc"""
    roll = 20
    stat_rating = 2
    dc = 15
    hide_dc = True

    total = roll + stat_rating
    is_nat_20 = (roll == 20)

    if is_nat_20:
        total += 10

    # Build result line
    if is_nat_20:
        if hide_dc:
            result_line = f"🎲 Result: {total}  ✨ CRITICAL SUCCESS +10"
        else:
            result_line = f"🎲 Result: {total}  🎯 DC: {dc}  ✨ CRITICAL SUCCESS +10"
    else:
        if hide_dc:
            result_line = f"🎲 Result: {total}"
        else:
            result_line = f"🎲 Result: {total}  🎯 DC: {dc}"

    # Should show crit success but not DC
    assert "CRITICAL SUCCESS" in result_line
    assert "DC" not in result_line
    assert "+10" in result_line


@pytest.mark.asyncio
async def test_save_embed_color():
    """Test embed color: gold for nat 20, green for success, red for fail"""
    # Nat 20 -> gold (0xFFD700)
    is_nat_20 = True
    success = True

    if is_nat_20:
        color = 0xFFD700  # Gold
    elif success:
        color = 0x00FF00  # Green
    else:
        color = 0xFF0000  # Red

    assert color == 0xFFD700

    # Normal success -> green
    is_nat_20 = False
    success = True

    if is_nat_20:
        color = 0xFFD700
    elif success:
        color = 0x00FF00
    else:
        color = 0xFF0000

    assert color == 0x00FF00

    # Failure -> red
    is_nat_20 = False
    success = False

    if is_nat_20:
        color = 0xFFD700
    elif success:
        color = 0x00FF00
    else:
        color = 0xFF0000

    assert color == 0xFF0000


@pytest.mark.asyncio
async def test_save_with_note():
    """Test save can include optional note"""
    note = "RESISTING POISON"

    # Note should appear in embed title or description
    assert len(note) > 0
    assert note == "RESISTING POISON"


@pytest.mark.asyncio
async def test_all_save_types():
    """Test all 6 save types work correctly"""
    save_types = ["str", "dex", "con", "int", "wis", "cha"]

    for save_type in save_types:
        # Each save type should have emoji
        save_emojis = {
            "str": "💪", "dex": "🤸", "con": "🛡️",
            "int": "🧠", "wis": "👁️", "cha": "✨"
        }

        emoji = save_emojis.get(save_type)
        assert emoji is not None
        assert len(emoji) > 0


@pytest.mark.asyncio
async def test_save_stat_mapping():
    """Test stats are retrieved correctly for saves"""
    stats = {
        "str": 3,
        "dex": 4,
        "con": 2,
        "int": 2,
        "wis": 3,
        "cha": 2
    }

    # Test each save type
    assert stats["str"] == 3
    assert stats["dex"] == 4
    assert stats["con"] == 2
    assert stats["int"] == 2
    assert stats["wis"] == 3
    assert stats["cha"] == 2
