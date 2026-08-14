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
    """Result from rolling a save (d6 pool or legacy d20)."""
    success: bool
    roll: int  # For d20 legacy, or highest die for d6
    modifier: int
    total: int
    dc: int
    outcome: str = "fail"  # "clean_success", "success_with_cost", or "fail"
    all_dice: List[int] = None  # For d6 pools
    kept_dice: List[int] = None  # For d6 pools

    def __post_init__(self):
        if self.all_dice is None:
            self.all_dice = []
        if self.kept_dice is None:
            self.kept_dice = []


def get_save_tier_thresholds(tier: int) -> dict:
    """
    Map save tier to d6 pool thresholds.

    Saves use keep-lowest mechanic (inherently harder/defensive).

    Args:
        tier: 1 (easy), 2 (medium), or 3 (hard)

    Returns:
        dict with 'clean', 'cost', 'fail' thresholds and 'label'
    """
    tiers = {
        1: {"clean": 5, "cost": 3, "fail": 2, "label": "Easy"},
        2: {"clean": 7, "cost": 5, "fail": 4, "label": "Medium"},
        3: {"clean": 9, "cost": 7, "fail": 6, "label": "Hard"}
    }
    if tier not in tiers:
        raise ValueError(f"Save tier must be 1, 2, or 3, got {tier}")
    return tiers[tier]


def get_skill_tier_thresholds(tier: int) -> dict:
    """
    Map skill tier to d6 pool thresholds.

    Skills use keep-highest mechanic (inherently easier/offensive).

    Args:
        tier: 1 (easy), 2 (medium), or 3 (hard)

    Returns:
        dict with 'clean', 'cost', 'fail' thresholds and 'label'
    """
    tiers = {
        1: {"clean": 5, "cost": 3, "fail": 2, "label": "Easy"},
        2: {"clean": 7, "cost": 5, "fail": 4, "label": "Medium"},
        3: {"clean": 9, "cost": 7, "fail": 6, "label": "Hard"}
    }
    if tier not in tiers:
        raise ValueError(f"Skill tier must be 1, 2, or 3, got {tier}")
    return tiers[tier]


def get_save_dc_from_tier(tier: int) -> dict:
    """
    LEGACY: Map save tier to d20 DC thresholds.
    Kept for backwards compatibility.
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


def roll_d6_save(stat_modifier: int, save_modifier: int, tier: int) -> SaveResult:
    """
    Roll a d6 pool save with keep-lowest mechanic.

    Base: 2d6kl1 (keep lowest - saves are defensive/harder)
    Modified by: stat_modifier and save_modifier (advantage/disadvantage)

    Args:
        stat_modifier: stat bonus converted to advantage/disadvantage (-2 to +2 typical)
        save_modifier: modifier from effects (positive = advantage, negative = disadvantage)
        tier: difficulty tier (1, 2, or 3)

    Returns:
        SaveResult with d6 pool details
    """
    # Calculate total modifier (advantage/disadvantage stacks)
    total_modifier = stat_modifier + save_modifier

    # Base is 2 dice, modified by advantage/disadvantage
    num_dice = max(2, 2 + total_modifier)

    # Roll all dice
    all_dice = [random.randint(1, 6) for _ in range(num_dice)]

    # Keep lowest 1 die (saves are defensive)
    kept_die = min(all_dice)
    kept_dice = [kept_die]

    # Get tier thresholds
    tier_data = get_save_tier_thresholds(tier)

    # Determine outcome
    if kept_die >= tier_data["clean"]:
        success = True
        outcome = "clean_success"
    elif kept_die >= tier_data["cost"]:
        success = True
        outcome = "success_with_cost"
    else:
        success = False
        outcome = "fail"

    return SaveResult(
        success=success,
        roll=kept_die,
        modifier=total_modifier,
        total=kept_die,  # For d6 saves, total = kept die
        dc=tier_data["clean"],
        outcome=outcome,
        all_dice=all_dice,
        kept_dice=kept_dice
    )


def roll_d6_skill(stat_modifier: int, proficiency: int, skill_modifier: int, tier: int) -> SaveResult:
    """
    Roll a d6 pool skill check with keep-highest mechanic.

    Base: 2d6k1 (keep highest - skills are offensive/easier)
    Modified by: stat_modifier, proficiency, and skill_modifier (advantage/disadvantage)

    Args:
        stat_modifier: stat bonus converted to advantage/disadvantage (-2 to +2 typical)
        proficiency: proficiency bonus as advantage dice (+0 to +2)
        skill_modifier: modifier from effects (positive = advantage, negative = disadvantage)
        tier: difficulty tier (1, 2, or 3)

    Returns:
        SaveResult with d6 pool details (reusing SaveResult for consistency)
    """
    # Calculate total modifier (advantage/disadvantage stacks)
    total_modifier = stat_modifier + proficiency + skill_modifier

    # Base is 2 dice, modified by advantage/disadvantage
    num_dice = max(2, 2 + total_modifier)

    # Roll all dice
    all_dice = [random.randint(1, 6) for _ in range(num_dice)]

    # Keep highest 1 die (skills are offensive)
    kept_die = max(all_dice)
    kept_dice = [kept_die]

    # Get tier thresholds
    tier_data = get_skill_tier_thresholds(tier)

    # Determine outcome
    if kept_die >= tier_data["clean"]:
        success = True
        outcome = "clean_success"
    elif kept_die >= tier_data["cost"]:
        success = True
        outcome = "success_with_cost"
    else:
        success = False
        outcome = "fail"

    return SaveResult(
        success=success,
        roll=kept_die,
        modifier=total_modifier,
        total=kept_die,  # For d6 skills, total = kept die
        dc=tier_data["clean"],
        outcome=outcome,
        all_dice=all_dice,
        kept_dice=kept_dice
    )
