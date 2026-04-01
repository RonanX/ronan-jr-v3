"""
Unified dice pool system for attacks AND saves.

Both use the same mechanic:
- Roll Xd6 where X = stat rating + modifier
- Keep highest die
- Compare to target AC/DC

Supports advantage/disadvantage and critical successes.
"""

import random
from typing import List, Tuple, Literal
from dataclasses import dataclass


@dataclass
class DicePoolResult:
    """Result from rolling a dice pool (attacks or saves)."""
    highest_die: int
    all_dice: List[int]
    kept_dice: List[int]
    is_crit: bool
    had_advantage: bool = False
    had_disadvantage: bool = False


def roll_dice_pool(rating: int, modifier: int = 0) -> Tuple[int, List[int], bool]:
    """
    Roll dice pool for attacks or saves.

    Advantage/disadvantage are handled through the modifier parameter:
    - Each stack of advantage adds +1 to modifier (roll 1 more die)
    - Each stack of disadvantage adds -1 to modifier (roll 1 fewer die)
    - They cancel out net against each other

    Args:
        rating: base stat rating (0-4)
        modifier: roll modifier from effects, advantage, disadvantage, etc. (can be negative)

    Returns:
        (highest_die, all_dice, is_crit)
    """
    # Calculate total dice (minimum 1)
    total_dice = max(1, rating + modifier)

    # Roll all dice
    dice = [random.randint(1, 6) for _ in range(total_dice)]

    # Get highest die
    highest = max(dice) if dice else 0

    # Check for crit (multiple 6s)
    is_crit = dice.count(6) > 1

    return highest, dice, is_crit


def check_result(highest_die: int, target_ac_tier: int) -> Literal["clean_hit", "hit_with_cost", "miss"]:
    """
    Check attack result against AC tier.

    Tier 1 (easy): 4-6 clean, 3 cost, 1-2 miss
    Tier 2 (medium): 5-6 clean, 4 cost, 1-3 miss
    Tier 3 (hard): 6 clean, 5 cost, 1-4 miss

    Args:
        highest_die: Highest die rolled (1-6)
        target_ac_tier: Target AC tier (1, 2, or 3)

    Returns:
        "clean_hit", "hit_with_cost", or "miss"
    """
    if target_ac_tier == 1:
        # Tier 1 (easy)
        if highest_die >= 4:
            return "clean_hit"
        elif highest_die == 3:
            return "hit_with_cost"
        else:
            return "miss"
    elif target_ac_tier == 2:
        # Tier 2 (medium)
        if highest_die >= 5:
            return "clean_hit"
        elif highest_die == 4:
            return "hit_with_cost"
        else:
            return "miss"
    elif target_ac_tier == 3:
        # Tier 3 (hard)
        if highest_die == 6:
            return "clean_hit"
        elif highest_die == 5:
            return "hit_with_cost"
        else:
            return "miss"
    else:
        raise ValueError(f"AC tier must be 1, 2, or 3, got {target_ac_tier}")


@dataclass
class SaveResult:
    """Result from rolling a d20 save."""
    success: bool
    roll: int
    modifier: int
    total: int
    dc: int
    outcome: str = "fail"  # "clean_success", "success_with_cost", or "fail"


def get_save_dc_from_tier(tier: int) -> dict:
    """
    Map save tier to d20 DC thresholds.

    Args:
        tier: 1 (easy), 2 (medium), or 3 (hard)

    Returns:
        dict with 'clean', 'cost', and 'fail' thresholds
    """
    tiers = {
        1: {"clean": 10, "cost": 7, "fail": 6, "label": "Easy"},
        2: {"clean": 14, "cost": 11, "fail": 10, "label": "Medium"},
        3: {"clean": 18, "cost": 15, "fail": 14, "label": "Hard"}
    }
    if tier not in tiers:
        raise ValueError(f"Save tier must be 1, 2, or 3, got {tier}")
    return tiers[tier]


def roll_save(stat_rating: int, proficiency: int, save_modifier: int, dc_or_tier, use_tier: bool = False) -> SaveResult:
    """
    Roll a d20 save with stat + proficiency + save_modifier vs DC.

    Advantage/disadvantage on saves:
    - If save_modifier is positive (advantage stacks), roll (1 + save_modifier) d20s and keep highest
    - If save_modifier is negative (disadvantage stacks), roll (1 + abs(save_modifier)) d20s and keep lowest
    - They cancel out net against each other

    Args:
        stat_rating: base stat rating (0-4)
        proficiency: proficiency bonus (+2/+3/+4)
        save_modifier: modifier from effects (positive = advantage stacks, negative = disadvantage stacks)
        dc_or_tier: difficulty class (int) or tier (1/2/3) if use_tier=True
        use_tier: if True, interpret dc_or_tier as a tier and use 3-tier system

    Returns:
        SaveResult with roll details, success status, and outcome
    """
    if stat_rating < 0 or stat_rating > 4:
        raise ValueError(f"Stat rating must be 0-4, got {stat_rating}")

    # Calculate number of d20s to roll
    if save_modifier > 0:
        # Advantage: roll (1 + advantage stacks) d20s, keep highest
        num_dice = 1 + save_modifier
        rolls = [random.randint(1, 20) for _ in range(num_dice)]
        roll = max(rolls)
    elif save_modifier < 0:
        # Disadvantage: roll (1 + disadvantage stacks) d20s, keep lowest
        num_dice = 1 + abs(save_modifier)
        rolls = [random.randint(1, 20) for _ in range(num_dice)]
        roll = min(rolls)
    else:
        # No advantage or disadvantage
        roll = random.randint(1, 20)

    total = roll + stat_rating + proficiency

    # Determine success and outcome
    if use_tier:
        tier_data = get_save_dc_from_tier(dc_or_tier)
        if total >= tier_data["clean"]:
            success = True
            outcome = "clean_success"
        elif total >= tier_data["cost"]:
            success = True
            outcome = "success_with_cost"
        else:
            success = False
            outcome = "fail"
        dc = tier_data["clean"]  # Store clean threshold as DC for display
    else:
        dc = dc_or_tier
        success = total >= dc
        outcome = "clean_success" if success else "fail"

    return SaveResult(success=success, roll=roll, modifier=stat_rating + proficiency, total=total, dc=dc, outcome=outcome)
