import pytest
from utils.dice import roll_dice_pool, check_result


class TestDicePoolBasics:
    """Test basic dice pool rolling mechanics."""

    def test_stat_0_rolls_minimum_1d6(self):
        """Stat 0 should roll 1d6 minimum."""
        highest, all_dice, is_crit = roll_dice_pool(rating=0, modifier=0)
        assert len(all_dice) == 1
        assert 1 <= highest <= 6

    def test_negative_modifier_caps_at_1d6(self):
        """Negative modifiers should cap at 1d6."""
        highest, all_dice, is_crit = roll_dice_pool(rating=3, modifier=-5)
        assert len(all_dice) == 1
        assert 1 <= highest <= 6

    def test_normal_pool_size(self):
        """Normal stat + modifier should create correct pool size."""
        highest, all_dice, is_crit = roll_dice_pool(rating=2, modifier=1)
        assert len(all_dice) == 3
        assert all(1 <= die <= 6 for die in all_dice)


class TestAdvantageDisadvantage:
    """Test advantage and disadvantage mechanics using modifier system."""

    def test_advantage_adds_dice_to_pool(self):
        """Advantage should add +1 die to pool per stack."""
        highest, all_dice, is_crit = roll_dice_pool(rating=2, modifier=1)  # +1 advantage
        # Should roll 3 dice (2 base + 1 advantage)
        assert len(all_dice) == 3

    def test_disadvantage_removes_dice_from_pool(self):
        """Disadvantage should remove 1 die from pool per stack."""
        highest, all_dice, is_crit = roll_dice_pool(rating=3, modifier=-1)  # -1 disadvantage
        # Should roll 2 dice (3 base - 1 disadvantage)
        assert len(all_dice) == 2

    def test_advantage_and_disadvantage_cancel(self):
        """Advantage and disadvantage should cancel net against each other."""
        highest, all_dice, is_crit = roll_dice_pool(rating=2, modifier=0)  # +2 adv, -2 disadv = 0
        # Should roll 2 dice (base rating, modifiers cancel)
        assert len(all_dice) == 2

    def test_stacking_advantage(self):
        """Multiple stacks of advantage should add multiple dice."""
        highest, all_dice, is_crit = roll_dice_pool(rating=2, modifier=2)  # +2 advantage
        # Should roll 4 dice (2 base + 2 advantage)
        assert len(all_dice) == 4


class TestCriticalHits:
    """Test critical hit detection."""

    def test_crit_requires_multiple_6s_in_kept_dice(self):
        """Crit should only trigger with multiple 6s in KEPT dice."""
        # This is probabilistic, so we'll test the logic exists
        # by running many rolls and checking at least some crits occur
        crit_count = 0
        for _ in range(1000):
            _, all_dice, is_crit = roll_dice_pool(rating=3, modifier=0)
            if is_crit:
                # If crit, verify multiple 6s in kept dice
                assert all_dice.count(6) >= 2
                crit_count += 1
        # With 3d6, we should see at least a few crits in 1000 rolls
        assert crit_count > 0

    def test_single_6_is_not_crit(self):
        """A single 6 should not be a crit."""
        # We can't force specific rolls, but we can verify the logic
        # by checking that crits require multiple 6s
        for _ in range(100):
            _, all_dice, is_crit = roll_dice_pool(rating=2, modifier=0)
            if all_dice.count(6) < 2:
                assert not is_crit


class TestCheckResult:
    """Test AC check result logic using tier system."""

    @pytest.mark.parametrize("highest,ac,expected", [
        # AC 10-12 tier: 4-6 clean, 3 cost, 1-2 miss
        (6, 10, "clean_hit"),
        (5, 10, "clean_hit"),
        (4, 10, "clean_hit"),
        (3, 10, "hit_with_cost"),
        (2, 10, "miss"),
        (1, 10, "miss"),
        # AC 13-15 tier: 5-6 clean, 4 cost, 1-3 miss
        (6, 13, "clean_hit"),
        (5, 13, "clean_hit"),
        (4, 13, "hit_with_cost"),
        (3, 13, "miss"),
        (2, 13, "miss"),
        # AC 16-18 tier: 6 clean, 5 cost, 1-4 miss
        (6, 16, "clean_hit"),
        (5, 16, "hit_with_cost"),
        (4, 16, "miss"),
    ])
    def test_check_result_thresholds(self, highest, ac, expected):
        """Test AC check thresholds using tier system."""
        assert check_result(highest, ac) == expected

    def test_tier_boundaries(self):
        """Test that tier boundaries work correctly."""
        # AC 12 should use easy tier
        assert check_result(4, 12) == "clean_hit"
        assert check_result(3, 12) == "hit_with_cost"

        # AC 13 should use medium tier
        assert check_result(5, 13) == "clean_hit"
        assert check_result(4, 13) == "hit_with_cost"

        # AC 16 should use hard tier
        assert check_result(6, 16) == "clean_hit"
        assert check_result(5, 16) == "hit_with_cost"
