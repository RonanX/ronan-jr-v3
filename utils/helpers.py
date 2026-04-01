"""
Helper functions for common operations and validation
"""

import discord
import logging
from typing import Optional, Tuple
from utils.constants import EmbedColors, Emoji, Limits

logger = logging.getLogger(__name__)


async def get_character_or_error(db, character_name: str, interaction: discord.Interaction) -> Optional[dict]:
    """
    Get character data from database or send error message.

    Returns character data dict or None if not found.
    """
    async with db.execute(
        "SELECT name, hp, max_hp, mp, max_mp, ac, movement, proficiency, stats_json, current_form FROM characters WHERE name = ?",
        (character_name,)
    ) as cursor:
        row = await cursor.fetchone()

        if not row:
            await interaction.response.send_message(
                f"{Emoji.ERROR} Character **{character_name}** not found!",
                ephemeral=True
            )
            return None

        return {
            "name": row[0],
            "hp": row[1],
            "max_hp": row[2],
            "mp": row[3],
            "max_mp": row[4],
            "ac": row[5],
            "movement": row[6],
            "proficiency": row[7],
            "stats_json": row[8],
            "current_form": row[9]
        }


async def check_combat_active(db, interaction: discord.Interaction, should_be_active: bool = True) -> bool:
    """
    Check if combat is active/inactive and send error if wrong state.

    Args:
        db: Database connection
        interaction: Discord interaction
        should_be_active: True if combat should be active, False if should be inactive

    Returns:
        True if in correct state, False otherwise
    """
    async with db.execute("SELECT combat_active FROM initiative WHERE id = 1") as cursor:
        row = await cursor.fetchone()
        is_active = row and row[0] == 1

        if should_be_active and not is_active:
            await interaction.response.send_message(
                f"{Emoji.ERROR} No active combat! Use `/init start` first.",
                ephemeral=True
            )
            return False
        elif not should_be_active and is_active:
            await interaction.response.send_message(
                f"{Emoji.WARNING} Combat is already active! Use `/init end` to finish the current combat first.",
                ephemeral=True
            )
            return False

        return True


async def check_stars(db, character_name: str, required: int, interaction: discord.Interaction) -> bool:
    """
    Check if character has enough stars.

    Returns True if enough stars, False otherwise (and sends error message).
    """
    async with db.execute(
        "SELECT stars FROM combat_state WHERE character_name = ?",
        (character_name,)
    ) as cursor:
        row = await cursor.fetchone()

        if not row:
            await interaction.response.send_message(
                f"{Emoji.ERROR} **{character_name}** is not in combat!",
                ephemeral=True
            )
            return False

        current_stars = row[0]

        if current_stars < required:
            await interaction.response.send_message(
                f"{Emoji.ERROR} Not enough stars! Need {required}, have {current_stars}.",
                ephemeral=True
            )
            return False

        return True


async def check_mp(db, character_name: str, required: int, interaction: discord.Interaction) -> bool:
    """
    Check if character has enough MP.

    Returns True if enough MP, False otherwise (and sends error message).
    """
    async with db.execute(
        "SELECT mp FROM characters WHERE name = ?",
        (character_name,)
    ) as cursor:
        row = await cursor.fetchone()

        if not row:
            await interaction.response.send_message(
                f"{Emoji.ERROR} **{character_name}** not found!",
                ephemeral=True
            )
            return False

        current_mp = row[0]

        if current_mp < required:
            await interaction.response.send_message(
                f"{Emoji.ERROR} Not enough MP! Need {required}, have {current_mp}.",
                ephemeral=True
            )
            return False

        return True


def validate_stat_rating(rating: int) -> Tuple[bool, Optional[str]]:
    """
    Validate a single stat rating.

    Returns (is_valid, error_message)
    """
    if rating < Limits.MIN_STAT_RATING or rating > Limits.MAX_STAT_RATING:
        return False, f"Stat ratings must be between {Limits.MIN_STAT_RATING} and {Limits.MAX_STAT_RATING}."
    return True, None


def validate_stat_total(stats: dict) -> Tuple[bool, Optional[str]]:
    """
    Validate total of all stats.

    Returns (is_valid, error_message)
    """
    total = sum(stats.values())
    if total < Limits.MIN_STAT_TOTAL or total > Limits.MAX_STAT_TOTAL:
        return False, f"Total stats must be between {Limits.MIN_STAT_TOTAL} and {Limits.MAX_STAT_TOTAL}. Current total: {total}"
    return True, None


async def confirm_action(bot, interaction: discord.Interaction, prompt: str, timeout: float = 30.0) -> bool:
    """
    Prompt user for confirmation.

    Returns True if confirmed, False if denied or timeout.
    """
    await interaction.followup.send(f"{prompt}\nReply with **yes** to confirm or **no** to cancel.")

    def check(m):
        return m.author == interaction.user and m.channel == interaction.channel

    try:
        msg = await bot.wait_for('message', timeout=timeout, check=check)
        return msg.content.lower() in ['yes', 'y']
    except:
        await interaction.followup.send(f"{Emoji.WARNING} Confirmation timed out. Action cancelled.")
        return False


def create_error_embed(title: str, description: str) -> discord.Embed:
    """Create a standardized error embed."""
    return discord.Embed(
        title=f"{Emoji.ERROR} {title}",
        description=description,
        color=EmbedColors.ERROR
    )


def create_success_embed(title: str, description: str) -> discord.Embed:
    """Create a standardized success embed."""
    return discord.Embed(
        title=f"{Emoji.SUCCESS} {title}",
        description=description,
        color=EmbedColors.SUCCESS
    )


def create_info_embed(title: str, description: str) -> discord.Embed:
    """Create a standardized info embed."""
    return discord.Embed(
        title=title,
        description=description,
        color=EmbedColors.INFO
    )
