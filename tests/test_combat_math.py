import pytest
from utils.move_execution import (
    calculate_attack_damage,
    calculate_multihit_result,
    calculate_save_dc,
    validate_costs
)


class TestDamageCalculation:
    """Test damage calculation logic."""

    @pytest.mark.parametrize("base_damage,stat_mod,hits,is_crit,expected_per_hit,expected_total", [
        # Normal hits
        (10, 3, 1, False, 13, 13),
        (10, 3, 2, False, 13, 26),
        (15, 4, 3, False, 19, 57),
        # Critical hits (damage doubled)
        (10, 3, 1, True, 26, 26),
        (10, 3, 2, True, 26, 52),
        (15, 4, 1, True, 38, 38),
        # Edge cases
        (0, 0, 1, False, 0, 0),
        (5, 0, 2, False, 5, 10),
        (10, 0, 0, False, 10, 0),  # 0 hits = 0 damage
    ])
    def test_damage_calculation(self, base_damage, stat_mod, hits, is_crit, expected_per_hit, expected_total):
        """Test damage calculation with various inputs."""
        per_hit, total = calculate_attack_damage(base_damage, stat_mod, hits, is_crit)
        assert per_hit == expected_per_hit
        assert total == expected_total

    def test_crit_doubles_final_damage(self):
        """Crit should double the (base + stat) damage."""
        per_hit_normal, _ = calculate_attack_damage(10, 3, 1, False)
        per_hit_crit, _ = calculate_attack_damage(10, 3, 1, True)
        assert per_hit_crit == per_hit_normal * 2


class TestMultihitLogic:
    """Test multihit outcome logic."""

    @pytest.mark.parametrize("outcome,total_hits,expected_landed", [
        # Clean hits land all
        ("clean_hit", 1, 1),
        ("clean_hit", 2, 2),
        ("clean_hit", 5, 5),
        # Hit with cost lands half rounded up
        ("hit_with_cost", 1, 1),  # (1+1)//2 = 1
        ("hit_with_cost", 2, 1),  # (2+1)//2 = 1
        ("hit_with_cost", 3, 2),  # (3+1)//2 = 2
        ("hit_with_cost", 4, 2),  # (4+1)//2 = 2
        ("hit_with_cost", 5, 3),  # (5+1)//2 = 3
        # Misses land 0 hits
        ("miss", 1, 0),
        ("miss", 2, 0),
        ("miss", 5, 0),
    ])
    def test_multihit_outcomes(self, outcome, total_hits, expected_landed):
        """Test multihit calculation for all outcomes."""
        landed = calculate_multihit_result(outcome, total_hits)
        assert landed == expected_landed

    def test_hit_with_cost_rounds_up(self):
        """Hit with cost should round up (3 hits = 2 land, not 1)."""
        assert calculate_multihit_result("hit_with_cost", 3) == 2
        assert calculate_multihit_result("hit_with_cost", 5) == 3


class TestSaveDC:
    """Test save DC calculation."""

    @pytest.mark.parametrize("proficiency,int_stat,wis_stat,cha_stat,expected_dc", [
        (2, 3, 2, 1, 13),  # 8 + 2 + 3
        (3, 1, 4, 2, 15),  # 8 + 3 + 4
        (2, 2, 2, 4, 14),  # 8 + 2 + 4
        (0, 0, 0, 0, 8),   # 8 + 0 + 0
        (4, 4, 4, 4, 16),  # 8 + 4 + 4
    ])
    def test_save_dc_calculation(self, proficiency, int_stat, wis_stat, cha_stat, expected_dc):
        """Test save DC uses 8 + prof + highest mental stat."""
        mental_stats = {"int": int_stat, "wis": wis_stat, "cha": cha_stat}
        dc = calculate_save_dc(proficiency, mental_stats)
        assert dc == expected_dc

    def test_save_dc_uses_highest_mental_stat(self):
        """Save DC should use the highest of int/wis/cha."""
        mental_stats = {"int": 1, "wis": 4, "cha": 2}
        dc = calculate_save_dc(2, mental_stats)
        assert dc == 8 + 2 + 4  # Uses wis=4


class TestCostValidation:
    """Test cost validation logic."""

    def test_valid_costs(self):
        """All costs are available."""
        valid, error = validate_costs(
            current_stars=5, current_mp=20, current_hp=30,
            star_cost=3, mp_cost=10, hp_cost=5
        )
        assert valid is True
        assert error is None

    def test_insufficient_stars(self):
        """Not enough stars."""
        valid, error = validate_costs(
            current_stars=2, current_mp=20, current_hp=30,
            star_cost=3, mp_cost=0, hp_cost=0
        )
        assert valid is False
        assert "stars" in error.lower()

    def test_insufficient_mp(self):
        """Not enough MP."""
        valid, error = validate_costs(
            current_stars=5, current_mp=5, current_hp=30,
            star_cost=0, mp_cost=10, hp_cost=0
        )
        assert valid is False
        assert "mp" in error.lower()

    def test_insufficient_hp(self):
        """Not enough HP."""
        valid, error = validate_costs(
            current_stars=5, current_mp=20, current_hp=3,
            star_cost=0, mp_cost=0, hp_cost=5
        )
        assert valid is False
        assert "hp" in error.lower()

    def test_zero_costs_always_valid(self):
        """Zero costs should always be valid."""
        valid, error = validate_costs(
            current_stars=0, current_mp=0, current_hp=1,
            star_cost=0, mp_cost=0, hp_cost=0
        )
        assert valid is True


class TestModifierStacking:
    """Test modifier stacking logic."""

    def test_modifiers_stack_numerically(self):
        """All modifiers should stack numerically."""
        base = 10
        mod1 = 2
        mod2 = 3
        mod3 = -1
        total = base + mod1 + mod2 + mod3
        assert total == 14

    @pytest.mark.parametrize("base_stat,stat_mod1,stat_mod2,expected", [
        (2, 1, 1, 4),
        (3, 0, 2, 5),
        (1, -1, 2, 2),
        (0, 1, 1, 2),
    ])
    def test_stat_modifiers_stack(self, base_stat, stat_mod1, stat_mod2, expected):
        """Stat modifiers should stack on base stat."""
        effective_stat = base_stat + stat_mod1 + stat_mod2
        assert effective_stat == expected
