"""
Miscellaneous commands - /roll and other utility commands
"""

import discord
from discord import app_commands
from discord.ext import commands
import re
import random
import ast
import operator
import aiosqlite
import json
import logging

logger = logging.getLogger(__name__)
DATABASE_PATH = "database/ronan.db"


def safe_eval(expression: str) -> float:
    """
    Safely evaluate a mathematical expression using AST.
    Supports: +, -, *, /, //, %, **, parentheses
    """
    # Define allowed operations
    allowed_ops = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
    }

    def eval_node(node):
        if isinstance(node, ast.Constant):  # Python 3.8+
            return node.value
        elif isinstance(node, ast.Num):  # Python 3.7 compat
            return node.n
        elif isinstance(node, ast.BinOp):
            left = eval_node(node.left)
            right = eval_node(node.right)
            op = allowed_ops.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported operation: {type(node.op).__name__}")
            return op(left, right)
        elif isinstance(node, ast.UnaryOp):
            operand = eval_node(node.operand)
            op = allowed_ops.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported unary operation: {type(node.op).__name__}")
            return op(operand)
        else:
            raise ValueError(f"Unsupported expression: {type(node).__name__}")

    try:
        tree = ast.parse(expression, mode='eval')
        result = eval_node(tree.body)
        return result
    except Exception as e:
        raise ValueError(f"Invalid expression: {e}")


async def get_character_stats(character_name: str) -> dict:
    """
    Fetch character stats from the database (case-insensitive).
    Returns a dict with stat names (lowercase) mapped to their modifier values.
    Stats are stored directly as modifiers (1-5 range), no conversion needed.
    Returns None if character not found.
    """
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute(
                "SELECT stats_json, stat_modifiers FROM characters WHERE LOWER(name) = LOWER(?)",
                (character_name,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None

                # Parse base stats
                stats_json = json.loads(row[0]) if row[0] else {}
                stat_modifiers = json.loads(row[1]) if row[1] else {}

                # Combine base stats with modifiers to get final stat values
                # Stats are already modifiers (0-4 range), just add effect modifiers
                final_stats = {}
                for stat, value in stats_json.items():
                    modifier = stat_modifiers.get(stat, 0)
                    final_stats[stat.lower()] = value + modifier

                return final_stats
    except Exception as e:
        logger.error(f"Error fetching stats for {character_name}: {e}")
        return None


async def get_all_character_names() -> list:
    """Fetch all character names for autocomplete."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute("SELECT name FROM characters ORDER BY name") as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]
    except Exception as e:
        logger.error(f"Error fetching character names: {e}")
        return []


def parse_stat_references(expression: str, character_stats: dict | None) -> tuple:
    """
    Parse stat references like +str, -dex, (str), etc. and replace with actual values.
    Returns: (modified_expression, list of substitutions made)
    Example: "2d20+str-dex" with str=3, dex=2 -> "2d20+3-2", [("str", 3), ("dex", -2)]
    Example: "(str)d6" with str=3 -> "3d6", [("str", 3)]

    If character_stats is None, stats default to 0.
    """
    # If no character stats provided, use empty dict (all stats = 0)
    if character_stats is None:
        character_stats = {}

    substitutions = []

    # Pattern 1: Parenthesized stats like (str), (dex)
    paren_pattern = r'\((str|dex|con|int|wis|cha)\)'

    def replace_paren_stat(match):
        stat_name = match.group(1).lower()
        stat_value = character_stats.get(stat_name, 0)
        substitutions.append((stat_name.upper(), stat_value))
        return str(stat_value)

    # Pattern 2: +/- stats like +str, -dex
    sign_pattern = r'([+\-])(str|dex|con|int|wis|cha)'

    def replace_sign_stat(match):
        sign = match.group(1)
        stat_name = match.group(2).lower()
        stat_value = character_stats.get(stat_name, 0)

        # Track what we substituted
        actual_value = stat_value if sign == '+' else -stat_value
        substitutions.append((stat_name.upper(), actual_value))

        # Return the numeric value with proper sign
        if sign == '+':
            return f"+{stat_value}"
        else:
            return f"-{stat_value}"

    # Apply both patterns
    modified = re.sub(paren_pattern, replace_paren_stat, expression, flags=re.IGNORECASE)
    modified = re.sub(sign_pattern, replace_sign_stat, modified, flags=re.IGNORECASE)

    return modified, substitutions


def roll_dice(notation: str) -> tuple:
    """
    Roll dice from standard notation (e.g., 2d6, 1d20+3, d20).
    Supports shorthand: "d20" becomes "1d20"
    Supports keep notation: "3d6k2" (keep highest 2), "3d6kl1" (keep lowest 1)
    Returns: (rolls_list, notation_for_display)
    Each roll in rolls_list is (dice_notation, all_rolls, kept_rolls)
    """
    # First, handle shorthand notation: d20 -> 1d20
    notation = re.sub(r'\bd(\d+)', r'1d\1', notation)

    # Match patterns like 2d6, 1d20, 3d8k2 (keep highest), 4d6kl3 (keep lowest)
    dice_pattern = r'(\d+)d(\d+)(?:k(l?)(\d+))?'

    def roll_replace(match):
        count = int(match.group(1))
        sides = int(match.group(2))
        keep_modifier = match.group(3)  # 'l' for lowest, empty for highest
        keep_count = int(match.group(4)) if match.group(4) else None

        if count > 100 or sides > 10000:
            raise ValueError("Dice count or sides too large")

        # Roll all dice
        all_rolls = [random.randint(1, sides) for _ in range(count)]

        # Determine which dice to keep
        if keep_count is not None:
            if keep_count > count:
                raise ValueError(f"Cannot keep {keep_count} dice from {count}d{sides}")

            # Sort rolls to determine which to keep
            sorted_rolls = sorted(all_rolls, reverse=(keep_modifier != 'l'))
            kept_rolls = sorted_rolls[:keep_count]

            # Build notation display
            if keep_modifier == 'l':
                dice_notation = f"{count}d{sides}kl{keep_count}"
            else:
                dice_notation = f"{count}d{sides}k{keep_count}"
        else:
            # No keep modifier, keep all dice
            kept_rolls = all_rolls
            dice_notation = f"{count}d{sides}"

        # Store rolls for display (all_rolls, kept_rolls)
        if not hasattr(roll_replace, 'all_rolls'):
            roll_replace.all_rolls = []
        roll_replace.all_rolls.append((dice_notation, all_rolls, kept_rolls))

        # Replace with sum of kept dice for calculation
        return str(sum(kept_rolls))

    # Reset rolls storage
    roll_replace.all_rolls = []

    # Replace all dice notation with their sums
    expression = re.sub(dice_pattern, roll_replace, notation)

    return roll_replace.all_rolls, expression


class MiscCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def character_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for character names."""
        names = await get_all_character_names()
        # Filter based on what user has typed
        filtered = [name for name in names if current.lower() in name.lower()]
        # Return up to 25 choices (Discord limit)
        return [app_commands.Choice(name=name, value=name) for name in filtered[:25]]

    @app_commands.command(name="roll", description="Roll dice (d20+str, 2d6+4, etc.)")
    @app_commands.describe(
        query="Dice notation with optional stats (d20+str, 2d6-dex, 4d6+3)",
        character="Character name for stat lookups",
        note="Optional label for the roll"
    )
    @app_commands.autocomplete(character=character_autocomplete)
    async def roll_dice_command(
        self,
        interaction: discord.Interaction,
        query: str,
        character: str = None,
        note: str = None
    ):
        """Generic dice rolling command with stat support"""
        try:
            original_query = query.strip()
            character_stats = None
            substitutions = []

            # Check if query contains stat references
            has_stat_refs = bool(re.search(r'([+\-])(str|dex|con|int|wis|cha)|\((str|dex|con|int|wis|cha)\)', query, re.IGNORECASE))

            # Fetch character stats if provided or if query has stat references
            if character or has_stat_refs:
                if character:
                    character_stats = await get_character_stats(character)
                    if character_stats is None:
                        logger.warning(f"Character '{character}' not found for roll, using 0 for stats")
                        character_stats = {}
                else:
                    # Query has stat refs but no character provided - use 0 for all stats
                    character_stats = {}

                # Parse stat references
                query, substitutions = parse_stat_references(query, character_stats)

            # Roll dice and get expression
            dice_rolls, expression = roll_dice(query)

            if not dice_rolls:
                await interaction.response.send_message(
                    "❌ No valid dice notation found (e.g., d20, 2d6, 1d8+3)",
                    ephemeral=True
                )
                return

            # Evaluate the expression safely
            result = safe_eval(expression)
            final_result = round(result)

            # Build compact embed
            embed = discord.Embed(color=0x5865F2)  # Blurple color

            # Build the main roll display line
            rolls_display_parts = []
            for dice_notation, all_rolls, kept_rolls in dice_rolls:
                if len(all_rolls) == len(kept_rolls):
                    # No drops, show normally
                    if len(kept_rolls) == 1:
                        rolls_display_parts.append(str(kept_rolls[0]))
                    else:
                        rolls_str = ", ".join(map(str, kept_rolls))
                        rolls_display_parts.append(f"({rolls_str})")
                else:
                    # Some dice were dropped, show with strikethrough for dropped, bold for kept
                    kept_set = set()
                    kept_temp = kept_rolls.copy()
                    for i, roll in enumerate(all_rolls):
                        if roll in kept_temp:
                            kept_set.add(i)
                            kept_temp.remove(roll)

                    roll_parts = []
                    for i, roll in enumerate(all_rolls):
                        if i in kept_set:
                            roll_parts.append(f"**{roll}**")
                        else:
                            roll_parts.append(f"~~{roll}~~")

                    rolls_str = ", ".join(roll_parts)
                    rolls_display_parts.append(f"({rolls_str})")

            rolls_display = " + ".join(rolls_display_parts)

            # Build description with note if present
            # Format: [note:] query → rolls [+stat] → result
            parts = []

            if note:
                parts.append(f"**{note}:**")

            parts.append(f"`{original_query}`")
            parts.append("→")
            parts.append(rolls_display)

            # Add stat bonuses if any
            if substitutions:
                stat_parts = []
                for name, val in substitutions:
                    if val >= 0:
                        stat_parts.append(f"**+{val}** {name}")
                    else:
                        stat_parts.append(f"**{val}** {name}")
                parts.append(" ".join(stat_parts))

            parts.append("→")
            parts.append(f"**{final_result}**")

            embed.description = " ".join(parts)

            # Send ephemeral confirmation, then post to channel
            await interaction.response.send_message("✓ Rolled", ephemeral=True, delete_after=2)
            await interaction.channel.send(embed=embed)

            logger.info(f"[ROLL] {interaction.user.name} rolled {original_query} = {final_result}")

        except ValueError as e:
            await interaction.response.send_message(
                f"❌ Invalid dice notation: {str(e)}",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error in roll command: {e}")
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="contest", description="Head-to-head roll contest between two participants")
    @app_commands.describe(
        roll1="First roll (d20+str, 2d6, etc.)",
        roll2="Second roll (d20+dex, 2d6, etc.)",
        note1="Label for first roll",
        note2="Label for second roll",
        character1="Character name for first roll's stat lookups",
        character2="Character name for second roll's stat lookups"
    )
    @app_commands.autocomplete(character1=character_autocomplete, character2=character_autocomplete)
    async def contest_command(
        self,
        interaction: discord.Interaction,
        roll1: str,
        roll2: str,
        note1: str = None,
        note2: str = None,
        character1: str = None,
        character2: str = None
    ):
        """Contest command for head-to-head rolls"""
        try:
            # Process Roll 1
            original_query1 = roll1.strip()
            stats1 = None
            subs1 = []

            has_stat_refs1 = bool(re.search(r'([+\-])(str|dex|con|int|wis|cha)|\((str|dex|con|int|wis|cha)\)', roll1, re.IGNORECASE))

            if character1 or has_stat_refs1:
                if character1:
                    stats1 = await get_character_stats(character1)
                    if stats1 is None:
                        logger.warning(f"Character '{character1}' not found, using 0 for stats")
                        stats1 = {}
                else:
                    stats1 = {}

                roll1, subs1 = parse_stat_references(roll1, stats1)

            dice_rolls1, expression1 = roll_dice(roll1)
            if not dice_rolls1:
                await interaction.response.send_message(
                    f"❌ Invalid dice notation in roll1: {original_query1}",
                    ephemeral=True
                )
                return

            result1 = round(safe_eval(expression1))

            # Process Roll 2
            original_query2 = roll2.strip()
            stats2 = None
            subs2 = []

            has_stat_refs2 = bool(re.search(r'([+\-])(str|dex|con|int|wis|cha)|\((str|dex|con|int|wis|cha)\)', roll2, re.IGNORECASE))

            if character2 or has_stat_refs2:
                if character2:
                    stats2 = await get_character_stats(character2)
                    if stats2 is None:
                        logger.warning(f"Character '{character2}' not found, using 0 for stats")
                        stats2 = {}
                else:
                    stats2 = {}

                roll2, subs2 = parse_stat_references(roll2, stats2)

            dice_rolls2, expression2 = roll_dice(roll2)
            if not dice_rolls2:
                await interaction.response.send_message(
                    f"❌ Invalid dice notation in roll2: {original_query2}",
                    ephemeral=True
                )
                return

            result2 = round(safe_eval(expression2))

            # Determine winner
            if result1 > result2:
                winner_indicator = "🏆"
                loser_indicator = ""
                color = 0x57F287  # Green
            elif result2 > result1:
                winner_indicator = ""
                loser_indicator = "🏆"
                color = 0xED4245  # Red
            else:
                winner_indicator = "🤝"
                loser_indicator = "🤝"
                color = 0xFEE75C  # Yellow

            # Build rolls display
            def format_rolls(dice_rolls):
                parts = []
                for dice_notation, all_rolls, kept_rolls in dice_rolls:
                    if len(all_rolls) == len(kept_rolls):
                        # No drops, show normally
                        if len(kept_rolls) == 1:
                            parts.append(str(kept_rolls[0]))
                        else:
                            rolls_str = ", ".join(map(str, kept_rolls))
                            parts.append(f"({rolls_str})")
                    else:
                        # Some dice were dropped, show with strikethrough for dropped, bold for kept
                        kept_set = set()
                        kept_temp = kept_rolls.copy()
                        for i, roll in enumerate(all_rolls):
                            if roll in kept_temp:
                                kept_set.add(i)
                                kept_temp.remove(roll)

                        roll_parts = []
                        for i, roll in enumerate(all_rolls):
                            if i in kept_set:
                                roll_parts.append(f"**{roll}**")
                            else:
                                roll_parts.append(f"~~{roll}~~")

                        rolls_str = ", ".join(roll_parts)
                        parts.append(f"({rolls_str})")
                return " + ".join(parts)

            rolls_display1 = format_rolls(dice_rolls1)
            rolls_display2 = format_rolls(dice_rolls2)

            # Build embed
            embed = discord.Embed(color=color)

            # Build left side (Roll 1)
            # Format: [note:] query → rolls [+stat] → result trophy
            left_parts = []
            if note1:
                left_parts.append(f"**{note1}:**")
            left_parts.append(f"`{original_query1}`")
            left_parts.append("→")
            left_parts.append(rolls_display1)

            if subs1:
                stat_parts = []
                for n, v in subs1:
                    if v >= 0:
                        stat_parts.append(f"**+{v}** {n}")
                    else:
                        stat_parts.append(f"**{v}** {n}")
                left_parts.append(" ".join(stat_parts))

            left_parts.append("→")
            left_parts.append(f"**{result1}** {winner_indicator}")

            # Build right side (Roll 2)
            right_parts = []
            if note2:
                right_parts.append(f"**{note2}:**")
            right_parts.append(f"`{original_query2}`")
            right_parts.append("→")
            right_parts.append(rolls_display2)

            if subs2:
                stat_parts = []
                for n, v in subs2:
                    if v >= 0:
                        stat_parts.append(f"**+{v}** {n}")
                    else:
                        stat_parts.append(f"**{v}** {n}")
                right_parts.append(" ".join(stat_parts))

            right_parts.append("→")
            right_parts.append(f"**{result2}** {loser_indicator}")

            # Combine with VS divider
            left_text = " ".join(left_parts)
            right_text = " ".join(right_parts)

            embed.description = f"{left_text}\n**vs**\n{right_text}"

            # Send ephemeral confirmation, then post to channel
            await interaction.response.send_message("✓ Contest rolled", ephemeral=True, delete_after=2)
            await interaction.channel.send(embed=embed)

            logger.info(f"[CONTEST] {interaction.user.name}: {result1} vs {result2}")

        except ValueError as e:
            await interaction.response.send_message(
                f"❌ Invalid dice notation: {str(e)}",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error in contest command: {e}")
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(MiscCommands(bot))
