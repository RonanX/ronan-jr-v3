"""
Move execution utilities - PROMPT 3
Handles attack, save, and utility move execution
"""

import json
from typing import Tuple, Dict, Any, Optional

# Category emojis for move display
CATEGORY_EMOJIS = {
    "light": "⚡",
    "medium": "⚔️",
    "heavy": "💥",
    "utility": "🛠️"
}


def calculate_multihit_result(outcome: str, total_hits: int) -> int:
    """
    Calculate how many hits land based on outcome.

    Args:
        outcome: "clean_hit", "hit_with_cost", or "miss"
        total_hits: Total number of hits in the move

    Returns:
        Number of hits that land
    """
    if outcome == "clean_hit":
        return total_hits
    elif outcome == "hit_with_cost":
        return (total_hits + 1) // 2  # Round up
    else:  # miss
        return 0


def calculate_save_dc(proficiency: int, mental_stats: Dict[str, int]) -> int:
    """
    Auto-calculate save DC: 8 + proficiency + highest mental stat.

    Args:
        proficiency: Character's proficiency bonus
        mental_stats: Dict with int, wis, cha values

    Returns:
        Calculated DC
    """
    highest_mental = max(
        mental_stats.get("int", 0),
        mental_stats.get("wis", 0),
        mental_stats.get("cha", 0)
    )
    return 8 + proficiency + highest_mental


def calculate_attack_damage(
    base_damage: int,
    effective_stat: int,
    hits_landed: int,
    is_crit: bool
) -> Tuple[int, int]:
    """
    Calculate total damage for an attack move.

    Args:
        base_damage: Move's base damage
        effective_stat: Character's effective stat (base + modifier)
        hits_landed: Number of hits that landed
        is_crit: Whether attack was critical

    Returns:
        (damage_per_hit, total_damage)
    """
    damage_per_hit = base_damage + effective_stat

    if is_crit:
        damage_per_hit *= 2

    total_damage = damage_per_hit * hits_landed

    return damage_per_hit, total_damage


def calculate_save_damage(
    base_damage: int,
    effective_stat: int,
    save_success: bool,
    half_on_save: bool
) -> int:
    """
    Calculate damage for a save-based move.

    Args:
        base_damage: Move's base damage
        effective_stat: Character's effective stat
        save_success: Whether target succeeded on save
        half_on_save: Whether damage is halved on successful save

    Returns:
        Total damage
    """
    total_damage = base_damage + effective_stat

    if save_success and half_on_save:
        total_damage //= 2
    elif save_success and not half_on_save:
        total_damage = 0

    return total_damage


def validate_costs(
    current_stars: int,
    current_mp: int,
    current_hp: int,
    star_cost: int,
    mp_cost: int,
    hp_cost: int
) -> Tuple[bool, Optional[str]]:
    """
    Validate if character has enough resources for move.

    Args:
        current_stars: Character's current stars
        current_mp: Character's current MP
        current_hp: Character's current HP
        star_cost: Move's star cost
        mp_cost: Move's MP cost
        hp_cost: Move's HP cost

    Returns:
        (is_valid, error_message)
    """
    if current_stars < star_cost:
        return False, f"❌ Not enough stars! Need {star_cost}⭐, have {current_stars}⭐"

    if current_mp < mp_cost:
        return False, f"❌ Not enough MP! Need {mp_cost}💙, have {current_mp}💙"

    if current_hp < hp_cost:  # < allows sacrifice moves that drop to exactly 0 HP
        return False, f"❌ Not enough HP! Need {hp_cost}❤️, have {current_hp}❤️"

    return True, None


def create_health_bar(current: int, maximum: int, length: int = 10) -> str:
    """
    Create health bar visualization.

    Args:
        current: Current HP
        maximum: Max HP
        length: Number of blocks (default 10)

    Returns:
        Health bar string with emojis
    """
    if maximum == 0:
        return "⬜" * length

    percentage = current / maximum
    filled_blocks = round(percentage * length)

    filled = "🟩" * filled_blocks
    empty = "⬜" * (length - filled_blocks)

    return filled + empty


def format_move_costs(star_cost: int, mp_cost: int, hp_cost: int) -> str:
    """
    Format move costs for display.

    Args:
        star_cost: Star cost
        mp_cost: MP cost
        hp_cost: HP cost

    Returns:
        Formatted cost string
    """
    costs = []

    if star_cost > 0:
        costs.append(f"{star_cost}⭐")
    if mp_cost > 0:
        costs.append(f"{mp_cost}💙")
    if hp_cost > 0:
        costs.append(f"{hp_cost}❤️")

    return " ".join(costs) if costs else "Free"


def determine_move_type(move_data: Dict[str, Any]) -> str:
    """
    Determine move execution type based on move properties.

    Args:
        move_data: Move dictionary from database

    Returns:
        "attack", "save", or "utility"
    """
    has_damage = move_data.get("damage", 0) > 0
    has_save = move_data.get("save_type") is not None

    if has_save:
        return "save"
    elif has_damage:
        return "attack"
    else:
        return "utility"
