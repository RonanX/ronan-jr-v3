"""
Comprehensive tests for unified dice pool system.
Tests both attack and save mechanics using the same dice pool.
"""

import sys
sys.path.insert(0, 'D:/Games/Campaigns/ronan-jr-v3')

from utils.dice import roll_dice_pool, check_result


def test_dice_pool_basic():
    """Test basic dice pool with no modifiers."""
    highest, dice, crit = roll_dice_pool(rating=3, modifier=0)
    assert len(dice) == 3, f"Expected 3 dice, got {len(dice)}"
    assert 1 <= highest <= 6, f"Highest die out of range: {highest}"
    assert isinstance(crit, bool), "Crit should be boolean"
    print(f"[OK] [TEST] Basic dice pool: {dice}, highest={highest}, crit={crit}")


def test_dice_pool_with_positive_modifier():
    """Test dice pool with positive modifier."""
    highest, dice, crit = roll_dice_pool(rating=3, modifier=2)
    assert len(dice) == 5, f"Expected 5 dice (3+2), got {len(dice)}"
    print(f"[OK] [TEST] Dice pool with +2 modifier: {dice}, highest={highest}")


def test_dice_pool_with_negative_modifier():
    """Test dice pool with negative modifier."""
    highest, dice, crit = roll_dice_pool(rating=3, modifier=-2)
    assert len(dice) == 1, f"Expected 1 die (3-2=1), got {len(dice)}"
    print(f"[OK] [TEST] Dice pool with -2 modifier: {dice}, highest={highest}")


def test_dice_pool_minimum():
    """Test dice pool always rolls at least 1 die."""
    highest, dice, crit = roll_dice_pool(rating=0, modifier=-5)
    assert len(dice) == 1, f"Expected minimum 1 die, got {len(dice)}"
    print(f"[OK] [TEST] Minimum 1 die with rating=0, modifier=-5: {dice}")


def test_dice_pool_advantage():
    """Test advantage mechanic using modifier system."""
    highest, dice, crit = roll_dice_pool(rating=3, modifier=1)  # +1 advantage
    assert len(dice) == 4, f"Expected 4 dice (3+1 for advantage), got {len(dice)}"
    print(f"[OK] [TEST] Advantage (+1 modifier): rolled {dice}, highest={highest}")


def test_dice_pool_disadvantage():
    """Test disadvantage mechanic using modifier system."""
    highest, dice, crit = roll_dice_pool(rating=3, modifier=-1)  # -1 disadvantage
    assert len(dice) == 2, f"Expected 2 dice (3-1 for disadvantage), got {len(dice)}"
    print(f"[OK] [TEST] Disadvantage (-1 modifier): rolled {dice}, highest={highest}")


def test_check_result_easy_dc():
    """Test easy DC thresholds (10-12)."""
    assert check_result(6, 10) == "clean_hit"
    assert check_result(5, 10) == "clean_hit"
    assert check_result(4, 10) == "clean_hit"
    assert check_result(3, 10) == "hit_with_cost"
    assert check_result(2, 10) == "miss"
    assert check_result(1, 10) == "miss"
    print("[OK] [TEST] Easy DC (10-12) thresholds: 4-6 clean, 3 cost, 1-2 miss")


def test_check_result_medium_dc():
    """Test medium DC thresholds (13-15)."""
    assert check_result(6, 13) == "clean_hit"
    assert check_result(5, 13) == "clean_hit"
    assert check_result(4, 13) == "hit_with_cost"
    assert check_result(3, 13) == "miss"
    assert check_result(2, 13) == "miss"
    assert check_result(1, 13) == "miss"
    print("[OK] [TEST] Medium DC (13-15) thresholds: 5-6 clean, 4 cost, 1-3 miss")


def test_check_result_hard_dc():
    """Test hard DC thresholds (16-18)."""
    assert check_result(6, 16) == "clean_hit"
    assert check_result(5, 16) == "hit_with_cost"
    assert check_result(4, 16) == "miss"
    assert check_result(3, 16) == "miss"
    assert check_result(2, 16) == "miss"
    assert check_result(1, 16) == "miss"
    print("[OK] [TEST] Hard DC (16-18) thresholds: 6 clean, 5 cost, 1-4 miss")


def test_modifier_stacking():
    """Test that modifiers stack correctly."""
    # +2 attack modifier, -1 incoming modifier = +1 net
    highest, dice, crit = roll_dice_pool(rating=3, modifier=1)
    assert len(dice) == 4, f"Expected 4 dice (3+1), got {len(dice)}"
    print(f"[OK] [TEST] Modifier stacking (3 rating + 1 net modifier): {dice}")


def test_attack_scenario():
    """Test realistic attack scenario."""
    # Attacker: STR 3, +1 attack modifier, -2 incoming modifier = -1 net
    # Result: 3-1=2 dice
    highest, dice, crit = roll_dice_pool(rating=3, modifier=-1)
    assert len(dice) == 2, f"Expected 2 dice, got {len(dice)}"

    # Check vs AC 15 (medium)
    result = check_result(highest, 15)
    assert result in ["clean_hit", "hit_with_cost", "miss"]
    print(f"[OK] [TEST] Attack scenario (3 STR, -1 net mod vs AC 15): rolled {dice}, highest={highest}, result={result}")


def test_save_scenario():
    """Test realistic save scenario."""
    # Character: DEX 4, -1 save modifier from poisoned
    # Result: 4-1=3 dice
    highest, dice, crit = roll_dice_pool(rating=4, modifier=-1)
    assert len(dice) == 3, f"Expected 3 dice, got {len(dice)}"

    # Check vs DC 13 (medium)
    result = check_result(highest, 13)
    assert result in ["clean_hit", "hit_with_cost", "miss"]

    # Check if crit (multiple 6s)
    if crit:
        print(f"[OK] [TEST] Save scenario (4 DEX, -1 save mod vs DC 13): rolled {dice}, highest={highest}, result={result} **CRIT!** (gains advantage next turn)")
    else:
        print(f"[OK] [TEST] Save scenario (4 DEX, -1 save mod vs DC 13): rolled {dice}, highest={highest}, result={result}")


if __name__ == "__main__":
    print("="*60)
    print("UNIFIED DICE POOL SYSTEM TESTS")
    print("="*60)
    print()

    test_dice_pool_basic()
    test_dice_pool_with_positive_modifier()
    test_dice_pool_with_negative_modifier()
    test_dice_pool_minimum()
    test_dice_pool_advantage()
    test_dice_pool_disadvantage()
    print()

    test_check_result_easy_dc()
    test_check_result_medium_dc()
    test_check_result_hard_dc()
    print()

    test_modifier_stacking()
    test_attack_scenario()
    test_save_scenario()

    print()
    print("="*60)
    print("[OK] ALL TESTS PASSED!")
    print("="*60)
