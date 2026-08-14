"""
Combat and initiative commands
"""

import discord
from discord import app_commands
from discord.ext import commands
import json
import random
import logging
import os
import asyncio
from pathlib import Path
import aiosqlite
from utils.autocomplete import character_autocomplete, character_and_deployable_autocomplete
from typing import Optional

logger = logging.getLogger(__name__)


def create_health_bar(current_hp: int, max_hp: int, temp_hp: int) -> str:
    """Create visual health bar with temp HP using Discord emojis (5 blocks)"""
    if max_hp <= 0:
        return ":black_large_square:" * 5 + " (0%)"

    # Calculate percentages (5 blocks max)
    hp_percentage = (current_hp / max_hp)
    temp_percentage = (temp_hp / max_hp)

    # Calculate blocks
    hp_blocks = round(hp_percentage * 5)
    temp_blocks = round(temp_percentage * 5)

    # Build the bar with Discord emojis
    filled = ":green_square:" * hp_blocks  # Actual HP
    temp = ":white_large_square:" * temp_blocks  # Temp HP

    # Calculate empty blocks (only if no overflow)
    total_blocks = hp_blocks + temp_blocks
    if total_blocks <= 5:
        empty_blocks = 5 - total_blocks
        empty = ":black_large_square:" * empty_blocks
    else:
        empty = ""  # Overflow, no empty blocks

    bar = filled + temp + empty

    # Calculate percentages for display
    hp_percent = int(hp_percentage * 100)
    temp_percent = int(temp_percentage * 100)

    if temp_hp > 0:
        return f"{bar} ({hp_percent}% + {temp_percent}% temp)"
    else:
        return f"{bar} ({hp_percent}%)"


# Autocomplete functions now imported from utils.autocomplete


class CombatCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.autosave_enabled = False

    init_group = app_commands.Group(name="init", description="Initiative and combat tracking")

    @init_group.command(name="start", description="Start a new combat encounter")
    @app_commands.describe(
        characters="Optional: comma-separated character names to auto-add to initiative"
    )
    async def start_combat(self, interaction: discord.Interaction, characters: str = None):
        """Start combat and reset initiative"""
        print(f"[CMD] {interaction.user.name} used /init start with params: characters={characters}")
        try:
            async with aiosqlite.connect('database/ronan.db') as db:
                # Check if combat is already active
                async with db.execute("SELECT combat_active FROM initiative WHERE id = 1") as cursor:
                    row = await cursor.fetchone()
                    if row and row[0] == 1:
                        print(f"[ERROR] Combat is already active")
                        await interaction.response.send_message(
                            "⚠️ Combat is already active! Use `/init end` to finish the current combat first.",
                            ephemeral=True
                        )
                        return

                # Start new combat (round 1, not 0)
                await db.execute(
                    "UPDATE initiative SET combat_active = 1, round_number = 1, current_turn_index = 0, turn_order_json = '[]' WHERE id = 1"
                )

                # Clear combat state
                await db.execute("DELETE FROM combat_state")
                await db.commit()

            # If characters provided, auto-add them
            turn_order = []
            if characters:
                char_list = [c.strip() for c in characters.split(',')]

                async with aiosqlite.connect('database/ronan.db') as db:
                    for char_name in char_list:
                        # Get character's dexterity rating
                        async with db.execute(
                            "SELECT stats_json FROM characters WHERE name = ?",
                            (char_name,)
                        ) as cursor:
                            char_row = await cursor.fetchone()
                            if not char_row:
                                continue  # Skip invalid characters

                        stats = json.loads(char_row[0])
                        dexterity = stats.get("dex", 0)

                        # Roll initiative: 1d20 + dexterity
                        roll = random.randint(1, 20)
                        initiative = roll + dexterity

                        # Add to turn order
                        turn_order.append({
                            "name": char_name,
                            "initiative": initiative,
                            "roll": roll,
                            "dexterity": dexterity
                        })

                    # Sort by initiative (highest first), then by dexterity on ties
                    turn_order.sort(key=lambda x: (x["initiative"], x["dexterity"]), reverse=True)

                    # Save turn order
                    await db.execute(
                        "UPDATE initiative SET turn_order_json = ? WHERE id = 1",
                        (json.dumps(turn_order),)
                    )

                    # Add to combat state with 5 stars
                    for char_entry in turn_order:
                        await db.execute(
                            "INSERT OR REPLACE INTO combat_state (character_name, stars, effects_json) VALUES (?, 5, '[]')",
                            (char_entry["name"],)
                        )

                    await db.commit()

            print(f"[OK] Combat started with {len(turn_order)} characters")

            # Trigger autosave (background task)
            self._autosave()

            embed = discord.Embed(
                title="⚔️ Combat Started!",
                description="Round 1 begins!" if turn_order else "Use `/init add [character]` to add combatants to initiative.",
                color=discord.Color.red()
            )

            if turn_order:
                order_text = "\n".join([
                    f"{i+1}. **{entry['name']}** ({entry['initiative']}) - Rolled {entry['roll']} + {entry['dexterity']} (DEX)"
                    for i, entry in enumerate(turn_order)
                ])
                embed.add_field(name="Turn Order", value=order_text, inline=False)

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error(f"Error starting combat: {e}", exc_info=True)
            print(f"[ERROR] /init start failed: {str(e)}")
            await interaction.response.send_message(
                f"❌ Error starting combat: {str(e)}",
                ephemeral=True
            )

    @init_group.command(name="add", description="Add a character to initiative")
    @app_commands.describe(character="Character name")
    @app_commands.autocomplete(character=character_autocomplete)
    async def add_to_initiative(self, interaction: discord.Interaction, character: str):
        """Add character to initiative with 1d20 + mobility roll"""
        print(f"[CMD] {interaction.user.name} used /init add with params: character={character}")
        try:
            async with aiosqlite.connect('database/ronan.db') as db:
                # Check if combat is active
                async with db.execute("SELECT combat_active, turn_order_json FROM initiative WHERE id = 1") as cursor:
                    row = await cursor.fetchone()
                    if not row or row[0] == 0:
                        print(f"[ERROR] No active combat")
                        await interaction.response.send_message(
                            "❌ No active combat! Use `/init start` first.",
                            ephemeral=True
                        )
                        return
                    turn_order = json.loads(row[1])

                # Get character's dexterity rating
                async with db.execute(
                    "SELECT stats_json FROM characters WHERE name = ?",
                    (character,)
                ) as cursor:
                    char_row = await cursor.fetchone()
                    if not char_row:
                        print(f"[ERROR] Character '{character}' not found")
                        await interaction.followup.send(
                            f"❌ Character '{character}' not found!",
                            ephemeral=True
                        )
                        return

                stats = json.loads(char_row[0])
                dexterity = stats.get("dex", 0)

                # Roll initiative: 1d20 + dexterity
                roll = random.randint(1, 20)
                initiative = roll + dexterity

                # Check if character already in initiative
                if any(entry["name"] == character for entry in turn_order):
                    print(f"[ERROR] {character} is already in initiative")
                    await interaction.response.send_message(
                        f"❌ {character} is already in initiative!",
                        ephemeral=True
                    )
                    return

                # Add to turn order
                turn_order.append({
                    "name": character,
                    "initiative": initiative,
                    "roll": roll,
                    "dexterity": dexterity
                })

                # Sort by initiative (highest first), then by dexterity on ties
                turn_order.sort(key=lambda x: (x["initiative"], x["dexterity"]), reverse=True)

                # Save turn order
                await db.execute(
                    "UPDATE initiative SET turn_order_json = ? WHERE id = 1",
                    (json.dumps(turn_order),)
                )

                # Add to combat state with 5 stars
                await db.execute(
                    "INSERT OR REPLACE INTO combat_state (character_name, stars, effects_json) VALUES (?, 5, '[]')",
                    (character,)
                )
                await db.commit()

            print(f"[OK] Added {character} to initiative with roll {initiative}")

            # Trigger autosave (background task)
            self._autosave()

            embed = discord.Embed(
                title=f"🎲 {character} joins the battle!",
                description=f"**Initiative Roll:** {roll} + {dexterity} (DEX) = **{initiative}**",
                color=discord.Color.green()
            )

            # Show current turn order
            order_text = "\n".join([
                f"{i+1}. **{entry['name']}** ({entry['initiative']})"
                for i, entry in enumerate(turn_order)
            ])
            embed.add_field(name="Turn Order", value=order_text, inline=False)

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error(f"Error adding to initiative: {e}", exc_info=True)
            print(f"[ERROR] /init add failed: {str(e)}")
            await interaction.response.send_message(
                f"❌ Error adding to initiative: {str(e)}",
                ephemeral=True
            )

    @init_group.command(name="show", description="Display current turn order")
    async def show_initiative(self, interaction: discord.Interaction):
        """Display turn order and combat state"""
        print(f"[CMD] {interaction.user.name} used /init show")
        try:
            async with aiosqlite.connect('database/ronan.db') as db:
                async with db.execute(
                    "SELECT combat_active, round_number, current_turn_index, turn_order_json FROM initiative WHERE id = 1"
                ) as cursor:
                    row = await cursor.fetchone()

                if not row or row[0] == 0:
                    print(f"[ERROR] No active combat")
                    await interaction.response.send_message(
                        "❌ No active combat!",
                        ephemeral=True
                    )
                    return

                combat_active, round_num, current_idx, turn_order_json = row
                turn_order = json.loads(turn_order_json)

                if not turn_order:
                    print(f"[ERROR] No combatants in initiative")
                    await interaction.response.send_message(
                        "⚠️ No combatants in initiative! Use `/init add [character]` to add combatants.",
                        ephemeral=True
                    )
                    return

            embed = discord.Embed(
                title="⚔️ Initiative Tracker",
                description=f"**Round {round_num}**",
                color=discord.Color.blue()
            )

            # Build turn order display with health bars
            async with aiosqlite.connect('database/ronan.db') as db:
                order_lines = []
                for i, entry in enumerate(turn_order):
                    marker = "➤" if i == current_idx else " "
                    char_name = entry['name']

                    # Get HP data for health bar
                    async with db.execute(
                        "SELECT hp, max_hp, temp_hp FROM characters WHERE name = ?",
                        (char_name,)
                    ) as cursor:
                        hp_row = await cursor.fetchone()

                    if hp_row:
                        hp, max_hp, temp_hp = hp_row
                        hp_display = f"{hp}/{max_hp}"
                        if temp_hp > 0:
                            hp_display += f" [+{temp_hp}]"
                        health_bar = create_health_bar(hp, max_hp, temp_hp)
                        order_lines.append(f"{marker} {i+1}. **{char_name}** ({entry['initiative']}) - {hp_display}\n     {health_bar}")
                    else:
                        order_lines.append(f"{marker} {i+1}. **{char_name}** ({entry['initiative']})")

            embed.add_field(
                name="Turn Order",
                value="\n".join(order_lines),
                inline=False
            )

            if turn_order and round_num >= 1:
                current_char = turn_order[current_idx]["name"]
                embed.set_footer(text=f"Current Turn: {current_char}")

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error(f"Error showing initiative: {e}", exc_info=True)
            print(f"[ERROR] /init show failed: {str(e)}")
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    @init_group.command(name="next", description="Advance to the next turn")
    async def next_turn(self, interaction: discord.Interaction):
        """Advance turn, refresh stars, decrement effects"""
        print(f"[CMD] {interaction.user.name} used /init next")
        try:
            async with aiosqlite.connect('database/ronan.db') as db:
                async with db.execute(
                    "SELECT combat_active, round_number, current_turn_index, turn_order_json FROM initiative WHERE id = 1"
                ) as cursor:
                    row = await cursor.fetchone()

                if not row or row[0] == 0:
                    print(f"[ERROR] No active combat")
                    await interaction.response.send_message(
                        "❌ No active combat!",
                        ephemeral=True
                    )
                    return

                combat_active, round_num, current_idx, turn_order_json = row
                turn_order = json.loads(turn_order_json)

                if not turn_order:
                    print(f"[ERROR] No combatants in initiative")
                    await interaction.response.send_message(
                        "❌ No combatants in initiative!",
                        ephemeral=True
                    )
                    return

                # Advance turn
                current_idx += 1
                if current_idx >= len(turn_order):
                    current_idx = 0
                    round_num += 1

                current_char_name = turn_order[current_idx]["name"]

                # Get character's max_stars and temp_stars
                async with db.execute(
                    "SELECT max_stars, temp_stars, current_stars FROM characters WHERE name = ?",
                    (current_char_name,)
                ) as cursor:
                    stars_row = await cursor.fetchone()
                    max_stars = stars_row[0] if stars_row and stars_row[0] is not None else 5
                    temp_stars = stars_row[1] if stars_row and stars_row[1] is not None else 0
                    old_current_stars = stars_row[2] if stars_row and stars_row[2] is not None else max_stars

                # ====== CRITICAL ORDER OF OPERATIONS ======
                # Star regeneration MUST happen BEFORE effect expiration
                # This ensures stunned effects block regen for exactly 1 turn

                # STEP 1: Check if character is stunned (BEFORE effects expire)
                is_stunned = False
                async with db.execute(
                    "SELECT id FROM effects WHERE character_name = ? AND effect_name = 'stunned'",
                    (current_char_name,)
                ) as cursor:
                    if await cursor.fetchone():
                        is_stunned = True
                        print(f"[STUNNED] {current_char_name} is stunned - no star regeneration")

                # STEP 2: Refresh stars (BEFORE effects expire)
                # If stunned, stars stay at 0; otherwise regenerate to max
                stars_to_set = 0 if is_stunned else max_stars
                await db.execute(
                    "UPDATE combat_state SET stars = ? WHERE character_name = ?",
                    (stars_to_set, current_char_name)
                )
                await db.execute(
                    "UPDATE characters SET current_stars = ? WHERE name = ?",
                    (stars_to_set, current_char_name)
                )

                # Refresh deployable stars for this owner (skip if deployables table doesn't exist)
                try:
                    await db.execute(
                        "UPDATE deployables SET stars = max_stars WHERE owner_name = ?",
                        (current_char_name,)
                    )
                except Exception:
                    pass  # Deployables table doesn't exist yet

                # STEP 3: NOW expire effects (AFTER star regen check)
                # This ensures a 1-round stun blocks exactly 1 turn of regen
                from utils.effects import expire_effects, get_active_effects

                expired = await expire_effects(current_char_name, round_num, db=db)
                expired_names = [name for _, name in expired]

                # Check for expired deployables
                expired_deployables = []
                try:
                    async with db.execute(
                        "SELECT deployable_name FROM deployables WHERE available_until_round <= ?",
                        (round_num,)
                    ) as cursor:
                        expired_deployables = await cursor.fetchall()
                except Exception:
                    pass  # Deployables table doesn't exist yet

                # Remove expired deployables
                if expired_deployables:
                    await db.execute(
                        "DELETE FROM deployables WHERE available_until_round <= ?",
                        (round_num,)
                    )

                expired_dep_names = [dep[0] for dep in expired_deployables]

                # Check for expired transformations
                transformation_expired = False
                async with db.execute("""
                    SELECT effect_name FROM effects
                    WHERE character_name = ? AND effect_name LIKE '%_transformation'
                          AND available_until_round <= ?
                """, (current_char_name, round_num)) as cursor:
                    expired_transform = await cursor.fetchone()
                    if expired_transform:
                        transformation_expired = True

                        # Revert to base form
                        zero_mods = json.dumps({"str": 0, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0})

                        # Get base AC
                        async with db.execute(
                            "SELECT base_stats FROM characters WHERE name = ?",
                            (current_char_name,)
                        ) as cursor2:
                            base_row = await cursor2.fetchone()
                            # Use default AC of 10 as fallback
                            base_ac = 10

                        await db.execute("""
                            UPDATE characters
                            SET current_form = 'base', stat_modifiers = ?
                            WHERE name = ?
                        """, (zero_mods, current_char_name))

                # Get active effects and process DoT/resource changes
                active_effects = await get_active_effects(current_char_name, db=db)

                # Get character's max HP/MP for percentage calculations
                async with db.execute("""
                    SELECT max_hp, max_mp FROM characters WHERE name = ?
                """, (current_char_name,)) as cursor:
                    max_row = await cursor.fetchone()
                    max_hp_for_calc = max_row[0] if max_row else 0
                    max_mp_for_calc = max_row[1] if max_row else 0

                from utils.value_parser import parse_value

                # Process DoT effects (stackable - each instance applies separately)
                dot_effects = [e for e in active_effects if e.get('dot_value', '0') != '0']
                dot_damage_applied = []  # Track for display

                for effect in dot_effects:
                    try:
                        dot_value_str = effect.get('dot_value', '0')
                        damage = parse_value(dot_value_str, max_hp_for_calc)

                        if damage > 0:
                            # Apply DoT damage to HP
                            await db.execute("""
                                UPDATE characters
                                SET hp = MAX(0, hp - ?)
                                WHERE name = ?
                            """, (damage, current_char_name))

                            note = effect.get('note', '')
                            dot_damage_applied.append((damage, note))
                            print(f"[EFFECT] DoT ({note}) dealt {damage} damage to {current_char_name}")
                    except ValueError as e:
                        print(f"[WARN] Failed to parse DoT value '{dot_value_str}': {e}")

                # Process resource effects (non-stackable - HP/MP drain/regen)
                resource_effects = [e for e in active_effects if e.get('resource_value', '0') != '0']
                resource_changes_applied = []  # Track for display

                for effect in resource_effects:
                    try:
                        resource_value_str = effect.get('resource_value', '0')
                        resource_type = effect.get('resource_type', 'hp')

                        # Parse value with appropriate max for percentages
                        if resource_type == 'mp':
                            change = parse_value(resource_value_str, max_mp_for_calc)
                        else:
                            change = parse_value(resource_value_str, max_hp_for_calc)

                        if change != 0:
                            if resource_type == 'hp':
                                # Apply HP change
                                await db.execute("""
                                    UPDATE characters
                                    SET hp = MAX(0, MIN(max_hp, hp + ?))
                                    WHERE name = ?
                                """, (change, current_char_name))
                                resource_changes_applied.append((effect['name'], 'hp', change, effect.get('note', '')))
                                print(f"[EFFECT] {effect['name']} changed {current_char_name}'s HP by {change}")

                            elif resource_type == 'mp':
                                # Apply MP change
                                await db.execute("""
                                    UPDATE characters
                                    SET mp = MAX(0, MIN(max_mp, mp + ?))
                                    WHERE name = ?
                                """, (change, current_char_name))
                                resource_changes_applied.append((effect['name'], 'mp', change, effect.get('note', '')))
                                print(f"[EFFECT] {effect['name']} changed {current_char_name}'s MP by {change}")
                    except ValueError as e:
                        print(f"[WARN] Failed to parse resource value '{resource_value_str}': {e}")

                # Old combat_state effects (for backward compatibility during transition)
                async with db.execute(
                    "SELECT effects_json FROM combat_state WHERE character_name = ?",
                    (current_char_name,)
                ) as cursor:
                    effects_row = await cursor.fetchone()
                effects_json = json.loads(effects_row[0]) if effects_row and effects_row[0] else []

                # Decrement old-style effect durations and handle temp resource expiry
                updated_effects = []
                old_expired = []
                temp_resources_expired = False

                for effect in effects_json:
                    effect["duration"] -= 1
                    if effect["duration"] > 0:
                        updated_effects.append(effect)
                    else:
                        old_expired.append(effect["name"])
                        # Check if this is the Temporary Resources effect
                        if effect.get("name") == "Temporary Resources":
                            temp_resources_expired = True
                            # Remove temp resources
                            await db.execute("""
                                UPDATE characters
                                SET temp_hp = 0, temp_mp = 0, temp_stars = 0
                                WHERE name = ?
                            """, (current_char_name,))

                # Save updated old-style effects
                await db.execute(
                    "UPDATE combat_state SET effects_json = ? WHERE character_name = ?",
                    (json.dumps(updated_effects), current_char_name)
                )

                # Update initiative tracker
                await db.execute(
                    "UPDATE initiative SET round_number = ?, current_turn_index = ? WHERE id = 1",
                    (round_num, current_idx)
                )

                # Get character stats for display
                async with db.execute(
                    "SELECT hp, max_hp, temp_hp, mp, max_mp, temp_mp, temp_stars FROM characters WHERE name = ?",
                    (current_char_name,)
                ) as cursor:
                    char_data = await cursor.fetchone()

                # Get active effects for this character
                async with db.execute("""
                    SELECT effect_name, note, available_until_round
                    FROM effects
                    WHERE character_name = ? AND available_until_round >= ?
                    ORDER BY available_until_round, effect_name
                """, (current_char_name, round_num)) as cursor:
                    active_effects = await cursor.fetchall()

                await db.commit()

            print(f"[OK] Advanced to round {round_num}, {current_char_name}'s turn")

            # Trigger autosave (background task)
            self._autosave()

            # Build embed with horizontal format in description
            # Defer ephemeral to prevent "user used command" bloat
            await interaction.response.defer(ephemeral=True)

            # Build description with round number and active effects
            description_parts = [f"**Round {round_num}**"]

            if active_effects:
                effect_strs = []
                for effect_name, note, expires_at in active_effects:
                    effect_display = f"{effect_name}"
                    if note:
                        effect_display += f" ({note})"
                    effect_display += f" [→ R{expires_at}]"
                    effect_strs.append(effect_display)
                description_parts.append("**Active Effects:**")
                description_parts.extend([f"• {e}" for e in effect_strs])

            embed = discord.Embed(
                title=f"🎯 {current_char_name}'s Turn!",
                description="\n".join(description_parts),
                color=discord.Color.gold()
            )

            if char_data:
                hp, max_hp, temp_hp, mp, max_mp, temp_mp, new_temp_stars = char_data
                temp_hp = temp_hp or 0
                temp_mp = temp_mp or 0
                new_temp_stars = new_temp_stars or 0

                # Build horizontal status line
                status_parts = []

                # HP with temp
                hp_str = f"❤️ {hp}/{max_hp}"
                if temp_hp > 0:
                    hp_str += f" (+{temp_hp} temp)"
                status_parts.append(hp_str)

                # MP with temp
                mp_str = f"💙 {mp}/{max_mp}"
                if temp_mp > 0:
                    mp_str += f" (+{temp_mp} temp)"
                status_parts.append(mp_str)

                # Stars with temp
                stars_str = f"⭐ {max_stars}/{max_stars}"
                if new_temp_stars > 0:
                    stars_str += f" (+{new_temp_stars} temp)"
                status_parts.append(stars_str)

                status_line = "  ".join(status_parts)
                embed.add_field(name="Resources", value=status_line, inline=False)

                # Notifications
                notifications = []

                # Star refresh
                if max_stars + new_temp_stars > old_current_stars + temp_stars:
                    notifications.append(f"⭐ stars refreshed ({old_current_stars} → {max_stars}" + (f" + {new_temp_stars} temp)" if new_temp_stars > 0 else ")"))

                # Temp resource expiry
                if temp_resources_expired:
                    notifications.append("⏱️ temp resources expired")

                # DoT effects (show each stack)
                if dot_damage_applied:
                    for damage, note in dot_damage_applied:
                        note_text = f" ({note})" if note else ""
                        notifications.append(f"🩸 DoT{note_text}: -{damage} HP")

                # Resource change effects (HP/MP drain/regen)
                if resource_changes_applied:
                    for effect_name, res_type, change, note in resource_changes_applied:
                        note_text = f" ({note})" if note else ""
                        display_name = f"{effect_name}{note_text}"

                        if res_type == 'hp':
                            if change < 0:
                                notifications.append(f"💚 {display_name}: -{abs(change)} HP")
                            else:
                                notifications.append(f"💚 {display_name}: +{change} HP")
                        elif res_type == 'mp':
                            if change < 0:
                                notifications.append(f"💙 {display_name}: -{abs(change)} MP")
                            else:
                                notifications.append(f"💙 {display_name}: +{change} MP")

                # Expired effects
                all_expired = list(set(expired_names + old_expired))
                if all_expired:
                    notifications.append(f"⏱️ {', '.join(all_expired)} expire" if len(all_expired) > 1 else f"⏱️ {all_expired[0]} expires")

                # Transformation expiry
                if transformation_expired:
                    notifications.append(f"🔄 transformation ended, reverted to base form")

                # Expired deployables
                if expired_dep_names:
                    notifications.append(f"🎭 {', '.join(expired_dep_names)} removed")

                if notifications:
                    embed.add_field(name="Effects", value="\n".join(notifications), inline=False)

                # Delete ephemeral thinking message, send fresh visible message
                await interaction.delete_original_response()
                await interaction.channel.send(embed=embed)
            else:
                embed.add_field(name="⚠️", value="No character data", inline=False)
                # Delete ephemeral thinking message, send fresh visible message
                await interaction.delete_original_response()
                await interaction.channel.send(embed=embed)

        except Exception as e:
            logger.error(f"Error advancing turn: {e}", exc_info=True)
            print(f"[ERROR] /init next failed: {str(e)}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"❌ Error advancing turn: {str(e)}",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(f"❌ Error advancing turn: {str(e)}", ephemeral=True)

    @init_group.command(name="end", description="End combat and clear initiative")
    async def end_combat(self, interaction: discord.Interaction):
        """End combat"""
        print(f"[CMD] {interaction.user.name} used /init end")
        try:
            async with aiosqlite.connect('database/ronan.db') as db:
                # Check if combat is active
                async with db.execute("SELECT combat_active FROM initiative WHERE id = 1") as cursor:
                    row = await cursor.fetchone()
                    if not row or row[0] == 0:
                        print(f"[ERROR] No active combat")
                        await interaction.response.send_message(
                            "❌ No active combat!",
                            ephemeral=True
                        )
                        return

            # Confirmation prompt with reactions
            embed = discord.Embed(
                title="⚠️ Confirm End Combat",
                description="End combat? This will clear all combat state.",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed)
            msg = await interaction.original_response()
            await msg.add_reaction("✅")
            await msg.add_reaction("❌")

            def check(reaction, user):
                return user == interaction.user and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == msg.id

            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=30.0, check=check)
                if str(reaction.emoji) == "❌":
                    await interaction.followup.send("❌ Combat end cancelled.")
                    return
            except:
                await interaction.followup.send("⏱️ Confirmation timed out. Combat end cancelled.")
                return

            # End combat
            async with aiosqlite.connect('database/ronan.db') as db:
                await db.execute(
                    "UPDATE initiative SET combat_active = 0, round_number = 0, current_turn_index = 0, turn_order_json = '[]' WHERE id = 1"
                )
                await db.execute("DELETE FROM combat_state")
                await db.commit()

            print(f"[OK] Combat ended")

            embed = discord.Embed(
                title="🏁 Combat Ended",
                description="Initiative tracker has been cleared.",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Error ending combat: {e}", exc_info=True)
            print(f"[ERROR] /init end failed: {str(e)}")
            await interaction.followup.send(
                f"❌ Error ending combat: {str(e)}",
                ephemeral=True
            )

    @init_group.command(name="remove", description="Remove a character from initiative")
    @app_commands.describe(character="Character name")
    @app_commands.autocomplete(character=character_autocomplete)
    async def remove_from_initiative(self, interaction: discord.Interaction, character: str):
        """Remove character from initiative mid-combat"""
        print(f"[CMD] {interaction.user.name} used /init remove with params: character={character}")
        try:
            async with aiosqlite.connect('database/ronan.db') as db:
                # Check if combat is active
                async with db.execute("SELECT combat_active, turn_order_json, current_turn_index FROM initiative WHERE id = 1") as cursor:
                    row = await cursor.fetchone()
                    if not row or row[0] == 0:
                        print(f"[ERROR] No active combat")
                        await interaction.response.send_message(
                            "❌ No active combat!",
                            ephemeral=True
                        )
                        return
                    turn_order = json.loads(row[1])
                    current_idx = row[2]

                # Find character in turn order
                char_index = None
                for i, entry in enumerate(turn_order):
                    if entry["name"] == character:
                        char_index = i
                        break

                if char_index is None:
                    print(f"[ERROR] {character} is not in initiative")
                    await interaction.response.send_message(
                        f"❌ {character} is not in initiative!",
                        ephemeral=True
                    )
                    return

                # Remove from turn order
                turn_order.pop(char_index)

                # Adjust current_turn_index if needed
                if char_index < current_idx:
                    # Character before current turn was removed, shift index back
                    current_idx -= 1
                elif char_index == current_idx:
                    # Current character was removed, keep index same (next character takes their place)
                    # But wrap around if we're now past the end
                    if current_idx >= len(turn_order) and len(turn_order) > 0:
                        current_idx = 0

                # Update database
                await db.execute(
                    "UPDATE initiative SET turn_order_json = ?, current_turn_index = ? WHERE id = 1",
                    (json.dumps(turn_order), current_idx)
                )

                # Remove from combat_state
                await db.execute(
                    "DELETE FROM combat_state WHERE character_name = ?",
                    (character,)
                )
                await db.commit()

            print(f"[OK] Removed {character} from initiative")

            # Trigger autosave (background task)
            self._autosave()

            embed = discord.Embed(
                title=f"👋 {character} removed from combat",
                description=f"{len(turn_order)} combatant(s) remaining",
                color=discord.Color.orange()
            )

            if turn_order:
                order_text = "\n".join([
                    f"{i+1}. **{entry['name']}** ({entry['initiative']})"
                    for i, entry in enumerate(turn_order)
                ])
                embed.add_field(name="Updated Turn Order", value=order_text, inline=False)

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error(f"Error removing from initiative: {e}", exc_info=True)
            print(f"[ERROR] /init remove failed: {str(e)}")
            await interaction.response.send_message(
                f"❌ Error removing from initiative: {str(e)}",
                ephemeral=True
            )

    async def _autosave_delayed(self):
        """Silent autosave with delay to avoid DB locks - no user-facing messages"""
        try:
            import datetime
            import asyncio

            # Wait a bit to let any ongoing DB operations finish
            await asyncio.sleep(0.1)

            async with aiosqlite.connect('database/ronan.db') as db:
                # Check if combat is active
                async with db.execute("SELECT combat_active FROM initiative WHERE id = 1") as cursor:
                    row = await cursor.fetchone()
                    if not row or row[0] == 0:
                        return  # No active combat, skip autosave

                # Get initiative data
                async with db.execute(
                    "SELECT turn_order_json, round_number, current_turn_index FROM initiative WHERE id = 1"
                ) as cursor:
                    init_row = await cursor.fetchone()
                    turn_order = json.loads(init_row[0])
                    round_number = init_row[1]
                    current_turn_index = init_row[2]

                # Get all character states
                character_states = {}
                async with db.execute("SELECT character_name, stars, effects_json FROM combat_state") as cursor:
                    async for row in cursor:
                        character_states[row[0]] = {
                            "stars": row[1],
                            "effects": json.loads(row[2])
                        }

            # Build save data with metadata
            save_data = {
                "timestamp": datetime.datetime.now().isoformat(),
                "round_number": round_number,
                "character_count": len(character_states),
                "turn_order": turn_order,
                "current_turn_index": current_turn_index,
                "character_states": character_states
            }

            # Create saves directory if it doesn't exist
            Path("data/saves").mkdir(parents=True, exist_ok=True)

            # Save to autosave slot
            autosave_path = "data/saves/autosave.json"
            with open(autosave_path, 'w') as f:
                json.dump(save_data, f, indent=2)

            print(f"[AUTOSAVE] Combat autosaved to {autosave_path}")

        except Exception as e:
            logger.error(f"Error during autosave: {e}", exc_info=True)
            print(f"[ERROR] Autosave failed: {str(e)}")
            # Silent failure - don't notify user

    def _autosave(self):
        """Trigger autosave in background (non-blocking)"""
        asyncio.create_task(self._autosave_delayed())

    @init_group.command(name="save", description="Save current combat state with a custom name")
    @app_commands.describe(name="Name for this save")
    async def save_combat(self, interaction: discord.Interaction, name: str):
        """Save current combat state to a named file"""
        print(f"[CMD] {interaction.user.name} used /init save with params: name={name}")
        try:
            import datetime

            async with aiosqlite.connect('database/ronan.db') as db:
                # Check if combat is active
                async with db.execute("SELECT combat_active FROM initiative WHERE id = 1") as cursor:
                    row = await cursor.fetchone()
                    if not row or not row[0]:
                        print(f"[ERROR] No active combat to save")
                        await interaction.response.send_message(
                            "❌ No active combat to save!",
                            ephemeral=True
                        )
                        return

                # Get initiative data
                async with db.execute(
                    "SELECT turn_order_json, round_number, current_turn_index FROM initiative WHERE id = 1"
                ) as cursor:
                    init_row = await cursor.fetchone()
                    turn_order = json.loads(init_row[0])
                    round_number = init_row[1]
                    current_turn_index = init_row[2]

                # Get all character states
                character_states = {}
                async with db.execute("SELECT character_name, stars, effects_json FROM combat_state") as cursor:
                    async for row in cursor:
                        character_states[row[0]] = {
                            "stars": row[1],
                            "effects": json.loads(row[2])
                        }

            # Build save data with metadata
            save_data = {
                "timestamp": datetime.datetime.now().isoformat(),
                "round_number": round_number,
                "character_count": len(character_states),
                "turn_order": turn_order,
                "current_turn_index": current_turn_index,
                "character_states": character_states
            }

            # Create saves directory if it doesn't exist
            Path("data/saves").mkdir(parents=True, exist_ok=True)

            # Save to named file (appears in load menu like quicksave)
            save_path = f"data/saves/save_{name}.json"
            with open(save_path, 'w') as f:
                json.dump(save_data, f, indent=2)

            print(f"[OK] Combat saved to {save_path}")

            await interaction.response.send_message(
                f"💾 Saved as **{name}** (Round {round_number})"
            )

        except Exception as e:
            logger.error(f"Error saving combat: {e}", exc_info=True)
            print(f"[ERROR] /init save failed: {str(e)}")
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    @init_group.command(name="quicksave", description="Quick save to dedicated slot (overwrites previous quicksave)")
    async def quicksave_combat(self, interaction: discord.Interaction):
        """Quick save combat state (silent overwrite)"""
        print(f"[CMD] {interaction.user.name} used /init quicksave")
        try:
            import datetime

            async with aiosqlite.connect('database/ronan.db') as db:
                # Check if combat is active
                async with db.execute("SELECT combat_active FROM initiative WHERE id = 1") as cursor:
                    row = await cursor.fetchone()
                    if not row or not row[0]:
                        print(f"[ERROR] No active combat to save")
                        await interaction.response.send_message(
                            "❌ No active combat to save!",
                            ephemeral=True
                        )
                        return

                # Get initiative data
                async with db.execute(
                    "SELECT turn_order_json, round_number, current_turn_index FROM initiative WHERE id = 1"
                ) as cursor:
                    init_row = await cursor.fetchone()
                    turn_order = json.loads(init_row[0])
                    round_number = init_row[1]
                    current_turn_index = init_row[2]

                # Get all character states
                character_states = {}
                async with db.execute("SELECT character_name, stars, effects_json FROM combat_state") as cursor:
                    async for row in cursor:
                        character_states[row[0]] = {
                            "stars": row[1],
                            "effects": json.loads(row[2])
                        }

            # Build save data with metadata
            save_data = {
                "timestamp": datetime.datetime.now().isoformat(),
                "round_number": round_number,
                "character_count": len(character_states),
                "turn_order": turn_order,
                "current_turn_index": current_turn_index,
                "character_states": character_states
            }

            # Create saves directory if it doesn't exist
            Path("data/saves").mkdir(parents=True, exist_ok=True)

            # Save to quicksave slot
            quicksave_path = "data/saves/quicksave.json"
            with open(quicksave_path, 'w') as f:
                json.dump(save_data, f, indent=2)

            print(f"[OK] Combat quicksaved to {quicksave_path}")

            await interaction.response.send_message(
                f"💾 Quicksave updated (Round {round_number})",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error quicksaving combat: {e}", exc_info=True)
            print(f"[ERROR] /init quicksave failed: {str(e)}")
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    @init_group.command(name="load", description="Load a saved combat state")
    async def load_combat(self, interaction: discord.Interaction):
        """Load combat state from saved files using select menu"""
        print(f"[CMD] {interaction.user.name} used /init load")
        try:
            import datetime
            from discord.ui import Select, View

            # Scan for available saves
            saves_dir = Path("data/saves")
            saves_dir.mkdir(parents=True, exist_ok=True)

            save_options = []

            # Check autosave
            autosave_path = saves_dir / "autosave.json"
            if autosave_path.exists():
                try:
                    with open(autosave_path, 'r') as f:
                        data = json.load(f)
                        timestamp = datetime.datetime.fromisoformat(data["timestamp"])
                        label = f"Autosave (Round {data['round_number']}, {timestamp.strftime('%m/%d %H:%M')})"
                        save_options.append(discord.SelectOption(
                            label=label,
                            value="autosave",
                            description=f"{data['character_count']} characters"
                        ))
                except:
                    pass

            # Check quicksave
            quicksave_path = saves_dir / "quicksave.json"
            if quicksave_path.exists():
                try:
                    with open(quicksave_path, 'r') as f:
                        data = json.load(f)
                        timestamp = datetime.datetime.fromisoformat(data["timestamp"])
                        label = f"Quicksave (Round {data['round_number']}, {timestamp.strftime('%m/%d %H:%M')})"
                        save_options.append(discord.SelectOption(
                            label=label,
                            value="quicksave",
                            description=f"{data['character_count']} characters"
                        ))
                except:
                    pass

            # Check named saves
            for save_file in sorted(saves_dir.glob("save_*.json")):
                try:
                    with open(save_file, 'r') as f:
                        data = json.load(f)
                        name = save_file.stem.replace("save_", "")
                        timestamp = datetime.datetime.fromisoformat(data["timestamp"])
                        label = f"{name} (Round {data['round_number']}, {timestamp.strftime('%m/%d %H:%M')})"
                        save_options.append(discord.SelectOption(
                            label=label[:100],  # Discord label limit
                            value=f"save_{name}",
                            description=f"{data['character_count']} characters"
                        ))
                except:
                    pass

            # Add empty slot options if no saves exist
            if not any(opt.value == "autosave" for opt in save_options):
                save_options.insert(0, discord.SelectOption(
                    label="Autosave (empty)",
                    value="empty_autosave",
                    description="No autosave available",
                    emoji="🚫"
                ))

            if not any(opt.value == "quicksave" for opt in save_options):
                # Insert after autosave
                insert_idx = 1 if save_options and save_options[0].value.startswith("autosave") else 0
                save_options.insert(insert_idx, discord.SelectOption(
                    label="Quicksave (empty)",
                    value="empty_quicksave",
                    description="No quicksave available",
                    emoji="🚫"
                ))

            if not save_options:
                await interaction.response.send_message(
                    "❌ No saves found!",
                    ephemeral=True
                )
                return

            # Create select menu
            select = Select(
                placeholder="Choose a save to load...",
                options=save_options[:25]  # Discord limit
            )

            async def select_callback(select_interaction: discord.Interaction):
                selected = select.values[0]

                # Check if empty slot was selected
                if selected.startswith("empty_"):
                    await select_interaction.response.send_message(
                        "❌ That save slot is empty!",
                        ephemeral=True
                    )
                    return

                # Load the save
                try:
                    if selected == "autosave":
                        load_path = saves_dir / "autosave.json"
                    elif selected == "quicksave":
                        load_path = saves_dir / "quicksave.json"
                    else:
                        # Named save
                        save_name = selected.replace("save_", "")
                        load_path = saves_dir / f"save_{save_name}.json"

                    with open(load_path, 'r') as f:
                        save_data = json.load(f)

                    # Restore combat state
                    async with aiosqlite.connect('database/ronan.db') as db:
                        # Clear existing combat
                        await db.execute("DELETE FROM combat_state")

                        # Restore initiative
                        await db.execute(
                            """UPDATE initiative SET
                               combat_active = 1,
                               turn_order_json = ?,
                               round_number = ?,
                               current_turn_index = ?
                               WHERE id = 1""",
                            (json.dumps(save_data["turn_order"]), save_data["round_number"], save_data["current_turn_index"])
                        )

                        # Restore character states
                        for char_name, state in save_data["character_states"].items():
                            await db.execute(
                                """INSERT INTO combat_state (character_name, stars, effects_json)
                                   VALUES (?, ?, ?)""",
                                (char_name, state["stars"], json.dumps(state["effects"]))
                            )

                        await db.commit()

                    print(f"[OK] Combat loaded from {load_path}")

                    # Show loaded state
                    turn_order = save_data["turn_order"]
                    current_idx = save_data["current_turn_index"]
                    current_char = turn_order[current_idx]["name"] if turn_order else "None"

                    embed = discord.Embed(
                        title="📂 Combat Loaded",
                        description=f"Loaded from **{selected}**",
                        color=discord.Color.green()
                    )
                    embed.add_field(
                        name="Round",
                        value=str(save_data["round_number"]),
                        inline=True
                    )
                    embed.add_field(
                        name="Current Turn",
                        value=current_char,
                        inline=True
                    )
                    embed.add_field(
                        name="Characters",
                        value=str(save_data["character_count"]),
                        inline=True
                    )

                    await select_interaction.response.send_message(embed=embed)

                except Exception as e:
                    logger.error(f"Error loading save: {e}", exc_info=True)
                    await select_interaction.response.send_message(
                        f"❌ Error loading save: {str(e)}",
                        ephemeral=True
                    )

            select.callback = select_callback
            view = View()
            view.add_item(select)

            embed = discord.Embed(
                title="📂 Load Combat Save",
                description="Select a save to load:",
                color=discord.Color.blue()
            )

            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in load menu: {e}", exc_info=True)
            print(f"[ERROR] /init load failed: {str(e)}")
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    # Effect commands
    effect_group = app_commands.Group(name="effect", description="Manage status effects")

    @effect_group.command(name="preset", description="Apply a preset mechanical effect")
    @app_commands.describe(
        character="Character name",
        effect_type="Type of effect",
        duration="Duration in rounds",
        value="Value for the effect (damage for DoT, modifier amount for stat/resource mods)",
        stat_name="Stat to modify (for Stat Mod preset only)",
        note="Optional note (e.g., 'fire damage from dragon')"
    )
    @app_commands.choices(
        effect_type=[
            app_commands.Choice(name="💀 DoT (Damage over Time)", value="dot"),
            app_commands.Choice(name="❤️ HP Mod (regen/drain per turn)", value="hp_mod"),
            app_commands.Choice(name="💙 MP Mod (regen/drain per turn)", value="mp_mod"),
            app_commands.Choice(name="📊 Stat Mod (temporary stat change)", value="stat_mod"),
            app_commands.Choice(name="🛡️ Cover (-1 incoming)", value="cover"),
            app_commands.Choice(name="👁️ Blinded (-1 attack)", value="blinded"),
            app_commands.Choice(name="🐌 Slowed (-DEX/2)", value="slowed"),
            app_commands.Choice(name="💫 Stunned (0 stars, no regen)", value="stunned"),
            app_commands.Choice(name="⬆️ Advantage (+1 attack)", value="advantage"),
            app_commands.Choice(name="⬇️ Disadvantage (-1 attack)", value="disadvantage")
        ],
        stat_name=[
            app_commands.Choice(name="STR (Strength)", value="str"),
            app_commands.Choice(name="DEX (Dexterity)", value="dex"),
            app_commands.Choice(name="CON (Constitution)", value="con"),
            app_commands.Choice(name="INT (Intelligence)", value="int"),
            app_commands.Choice(name="WIS (Wisdom)", value="wis"),
            app_commands.Choice(name="CHA (Charisma)", value="cha")
        ]
    )
    @app_commands.autocomplete(character=character_autocomplete)
    async def preset_effect(
        self,
        interaction: discord.Interaction,
        character: str,
        effect_type: str,
        duration: int,
        value: int = 0,
        stat_name: str = "str",
        note: str = None
    ):
        """Add a preset mechanical effect"""
        print(f"[CMD] {interaction.user.name} used /effect preset with params: character={character}, effect_type={effect_type}, duration={duration}, value={value}, note={note}")

        # Effect presets with new mechanics
        presets = {
            "dot": {
                "stackable": True,
                "emoji": "💀",
                "requires_value": True
            },
            "hp_mod": {
                "stackable": True,
                "emoji": "❤️",
                "requires_value": True
            },
            "mp_mod": {
                "stackable": True,
                "emoji": "💙",
                "requires_value": True
            },
            "stat_mod": {
                "stackable": False,
                "emoji": "📊",
                "requires_value": True
            },
            "cover": {
                "contributions": {"roll_modifiers": {"incoming_modifier": -1}},
                "stackable": False,
                "emoji": "🛡️",
                "requires_value": False
            },
            "blinded": {
                "contributions": {"roll_modifiers": {"attack_modifier": -1}},
                "stackable": False,
                "emoji": "👁️",
                "requires_value": False
            },
            "slowed": {
                # Slowed will be handled specially - reduces DEX by floor(DEX/2)
                "special": "slowed",
                "stackable": False,
                "emoji": "🐌",
                "requires_value": False
            },
            "stunned": {
                # Stunned will be handled specially - sets stars to 0 and blocks regen
                "special": "stunned",
                "stackable": False,
                "emoji": "💫",
                "requires_value": False
            },
            "advantage": {
                "contributions": {"roll_modifiers": {"attack_modifier": 1}},
                "stackable": True,
                "emoji": "⬆️",
                "requires_value": False
            },
            "disadvantage": {
                "contributions": {"roll_modifiers": {"attack_modifier": -1}},
                "stackable": True,
                "emoji": "⬇️",
                "requires_value": False
            }
        }

        try:
            if duration <= 0:
                print(f"[ERROR] Duration must be positive")
                await interaction.response.send_message(
                    "❌ Duration must be positive!",
                    ephemeral=True
                )
                return

            if effect_type not in presets:
                print(f"[ERROR] Unknown effect: {effect_type}")
                await interaction.response.send_message(
                    f"❌ Unknown effect: {effect_type}",
                    ephemeral=True
                )
                return

            preset = presets[effect_type]

            # Check if value is required
            if preset.get("requires_value") and value == 0:
                await interaction.response.send_message(
                    f"❌ {effect_type} requires a value parameter!",
                    ephemeral=True
                )
                return

            # Get current round
            db = self.bot.db
            async with db.execute("SELECT round_number, combat_active FROM initiative WHERE id = 1") as cursor:
                row = await cursor.fetchone()
                current_round = row[0] if row and row[1] == 1 else 99

            # Handle special effects
            if preset.get("special") == "stunned":
                # Stunned: set stars to 0 immediately
                await db.execute("UPDATE characters SET current_stars = 0 WHERE name = ?", (character,))
                await db.execute("UPDATE combat_state SET stars = 0 WHERE character_name = ?", (character,))
                await db.commit()
                print(f"[STUNNED] Set {character}'s stars to 0")

            elif preset.get("special") == "slowed":
                    # Slowed: calculate DEX penalty
                    async with db.execute("SELECT base_stats FROM characters WHERE name = ?", (character,)) as cursor:
                        char_row = await cursor.fetchone()
                        if char_row:
                            base_stats = json.loads(char_row[0]) if char_row[0] else {}
                            dex = base_stats.get("dex", 0)
                            dex_penalty = -(dex // 2)
                            # Apply as stat modifier
                            preset["contributions"] = {"stat_modifiers": {"dex": dex_penalty}}
                            print(f"[SLOWED] Applying DEX penalty of {dex_penalty} to {character}")

            # Build effect data
            effect_data = {
                "name": effect_type,
                "emoji": preset["emoji"],
                "available_until_round": current_round + duration,
                "contributions": preset.get("contributions", {}),
                "stackable": preset.get("stackable", False),
                "note": note or ""
            }

            # Add type-specific data
            if effect_type == "dot":
                effect_data["dot_value"] = str(value)
            elif effect_type == "hp_mod":
                # HP mod: positive = regen, negative = drain
                effect_data["resource_type"] = "hp"
                effect_data["resource_value"] = str(value)
            elif effect_type == "mp_mod":
                # MP mod: positive = regen, negative = drain
                effect_data["resource_type"] = "mp"
                effect_data["resource_value"] = str(value)
            elif effect_type == "stat_mod":
                # Use the stat_name parameter to determine which stat to modify
                effect_data["contributions"] = {"stat_modifiers": {stat_name: value}}

            # Apply effect using helper
            from utils.effects import apply_effect
            await apply_effect(character, effect_data, db=db)

            emoji = preset["emoji"]
            note_text = f" - {note}" if note else ""
            value_text = f" (value: {value})" if value != 0 else ""
            print(f"[OK] Added effect '{effect_type}' to {character} ({duration} rounds)")

            await interaction.response.send_message(
                f"{emoji} Applied **{effect_type}** to **{character}** ({duration} rounds){value_text}{note_text}"
            )

        except Exception as e:
            logger.error(f"Error adding preset effect: {e}", exc_info=True)
            print(f"[ERROR] /effect preset failed: {str(e)}")
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    @effect_group.command(name="dot", description="Apply damage over time effect")
    @app_commands.describe(
        character="Character name",
        value="Damage value (flat: 5, dice: 1d4, percent: 10%)",
        duration="Duration in rounds",
        note="Optional note (e.g., 'fire', 'bleed', 'venom')"
    )
    @app_commands.autocomplete(character=character_autocomplete)
    async def dot_effect(
        self,
        interaction: discord.Interaction,
        character: str,
        value: str,
        duration: int,
        note: str = None
    ):
        """Apply damage over time effect (stackable)"""
        print(f"[CMD] {interaction.user.name} used /effect dot with params: character={character}, value={value}, duration={duration}, note={note}")
        try:
            from utils.value_parser import validate_value_format

            # Validate value format
            if not validate_value_format(value):
                print(f"[ERROR] Invalid value format: {value}")
                await interaction.response.send_message(
                    f"❌ Invalid value format '{value}'! Use flat (5), dice (1d4), or percentage (10%)",
                    ephemeral=True
                )
                return

            if duration <= 0:
                print(f"[ERROR] Duration must be positive")
                await interaction.response.send_message(
                    "❌ Duration must be positive!",
                    ephemeral=True
                )
                return

            # Get current round
            async with aiosqlite.connect('database/ronan.db') as db:
                async with db.execute("SELECT round_number, combat_active FROM initiative WHERE id = 1") as cursor:
                    row = await cursor.fetchone()
                    if not row or row[1] == 0:
                        print(f"[ERROR] No active combat")
                        await interaction.response.send_message(
                            "❌ No active combat!",
                            ephemeral=True
                        )
                        return
                    current_round = row[0]

            # Build DoT effect data
            effect_data = {
                "name": "dot",
                "emoji": "🩸",
                "available_until_round": current_round + duration,
                "contributions": {},
                "dot_value": value,
                "stackable": True,
                "note": note or ""
            }

            # Apply effect using helper
            from utils.effects import apply_effect
            await apply_effect(character, effect_data, db=db)

            note_text = f" ({note})" if note else ""
            print(f"[OK] Applied DoT {value}{note_text} to {character} ({duration} rounds)")

            await interaction.response.send_message(
                f"🩸 Applied **DoT{note_text}** to **{character}** - {value} HP/turn ({duration} rounds)"
            )

        except Exception as e:
            logger.error(f"Error adding DoT effect: {e}", exc_info=True)
            print(f"[ERROR] /effect dot failed: {str(e)}")
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    @effect_group.command(name="add", description="Add a custom status effect to a character")
    @app_commands.describe(
        character="Character name",
        name="Effect name",
        duration="Duration in rounds",
        description="Optional description/note for visual tracking"
    )
    @app_commands.autocomplete(character=character_autocomplete)
    async def add_effect(
        self,
        interaction: discord.Interaction,
        character: str,
        name: str,
        duration: int,
        description: str = None
    ):
        """Add a custom status effect"""
        print(f"[CMD] {interaction.user.name} used /effect add with params: character={character}, name={name}, duration={duration}")
        try:
            if duration <= 0:
                print(f"[ERROR] Duration must be positive")
                await interaction.response.send_message(
                    "❌ Duration must be positive!",
                    ephemeral=True
                )
                return

            async with aiosqlite.connect('database/ronan.db') as db:
                # Check if combat is active
                async with db.execute("SELECT combat_active FROM initiative WHERE id = 1") as cursor:
                    row = await cursor.fetchone()
                    if not row or row[0] == 0:
                        print(f"[ERROR] No active combat")
                        await interaction.response.send_message(
                            "❌ No active combat!",
                            ephemeral=True
                        )
                        return

                # Get current effects
                async with db.execute(
                    "SELECT effects_json FROM combat_state WHERE character_name = ?",
                    (character,)
                ) as cursor:
                    effects_row = await cursor.fetchone()

                if not effects_row:
                    print(f"[ERROR] {character} is not in combat")
                    await interaction.response.send_message(
                        f"❌ {character} is not in combat!",
                        ephemeral=True
                    )
                    return

                effects = json.loads(effects_row[0])

                # Check if effect already exists
                for effect in effects:
                    if effect["name"].lower() == name.lower():
                        print(f"[ERROR] {character} already has the effect '{name}'")
                        await interaction.response.send_message(
                            f"❌ {character} already has the effect '{name}'!",
                            ephemeral=True
                        )
                        return

                # Add new effect (with optional description)
                effect_data = {"name": name, "duration": duration}
                if description:
                    effect_data["description"] = description

                effects.append(effect_data)

                await db.execute(
                    "UPDATE combat_state SET effects_json = ? WHERE character_name = ?",
                    (json.dumps(effects), character)
                )
                await db.commit()

            desc_text = f" - {description}" if description else ""
            print(f"[OK] Added effect '{name}' to {character} ({duration} rounds){desc_text}")

            await interaction.response.send_message(
                f"🔮 Added **{name}** to **{character}** ({duration} rounds){desc_text}"
            )

        except Exception as e:
            logger.error(f"Error adding effect: {e}", exc_info=True)
            print(f"[ERROR] /effect add failed: {str(e)}")
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    @effect_group.command(name="remove", description="Remove a status effect from a character")
    @app_commands.describe(
        character="Character name",
        name="Effect name"
    )
    @app_commands.autocomplete(character=character_autocomplete)
    async def remove_effect(
        self,
        interaction: discord.Interaction,
        character: str,
        name: str
    ):
        """Remove a status effect"""
        print(f"[CMD] {interaction.user.name} used /effect remove with params: character={character}, name={name}")
        try:
            async with aiosqlite.connect('database/ronan.db') as db:
                # Get current effects
                async with db.execute(
                    "SELECT effects_json FROM combat_state WHERE character_name = ?",
                    (character,)
                ) as cursor:
                    effects_row = await cursor.fetchone()

                if not effects_row:
                    print(f"[ERROR] {character} is not in combat")
                    await interaction.response.send_message(
                        f"❌ {character} is not in combat!",
                        ephemeral=True
                    )
                    return

                effects = json.loads(effects_row[0])

                # Remove effect
                initial_count = len(effects)
                effects = [e for e in effects if e["name"].lower() != name.lower()]

                if len(effects) == initial_count:
                    print(f"[ERROR] {character} doesn't have the effect '{name}'")
                    await interaction.response.send_message(
                        f"❌ {character} doesn't have the effect '{name}'!",
                        ephemeral=True
                    )
                    return

                await db.execute(
                    "UPDATE combat_state SET effects_json = ? WHERE character_name = ?",
                    (json.dumps(effects), character)
                )
                await db.commit()

            print(f"[OK] Removed effect '{name}' from {character}")

            await interaction.response.send_message(
                f"💨 Removed **{name}** from **{character}**"
            )

        except Exception as e:
            logger.error(f"Error removing effect: {e}", exc_info=True)
            print(f"[ERROR] /effect remove failed: {str(e)}")
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    @effect_group.command(name="list", description="List all effects on a character")
    @app_commands.describe(character="Character name")
    @app_commands.autocomplete(character=character_autocomplete)
    async def list_effects(self, interaction: discord.Interaction, character: str):
        """List character's active effects"""
        print(f"[CMD] {interaction.user.name} used /effect list with params: character={character}")
        try:
            async with aiosqlite.connect('database/ronan.db') as db:
                async with db.execute(
                    "SELECT effects_json FROM combat_state WHERE character_name = ?",
                    (character,)
                ) as cursor:
                    effects_row = await cursor.fetchone()

            if not effects_row:
                print(f"[ERROR] {character} is not in combat")
                await interaction.response.send_message(
                    f"❌ {character} is not in combat!",
                    ephemeral=True
                )
                return

            effects = json.loads(effects_row[0])

            if not effects:
                await interaction.response.send_message(
                    f"{character} has no active effects.",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title=f"🔮 {character}'s Active Effects",
                color=discord.Color.purple()
            )

            # Build effect list with emojis and notes
            effects_lines = []
            for effect in effects:
                emoji = effect.get("emoji", "🔮")
                name = effect["name"]
                duration = effect["duration"]
                note = effect.get("note", "")

                if note:
                    effects_lines.append(f"- {emoji} **{name}** ({duration} rounds) - {note}")
                else:
                    effects_lines.append(f"- {emoji} **{name}** ({duration} rounds)")

            embed.description = "\n".join(effects_lines)

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error(f"Error listing effects: {e}", exc_info=True)
            print(f"[ERROR] /effect list failed: {str(e)}")
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    # Attack command
    @app_commands.command(name="attack", description="Attack a target (damage is projected, not auto-applied)")
    @app_commands.describe(
        attacker="Character making the attack",
        attack_type="Attack type (light=1⭐, medium=2⭐, heavy=4⭐)",
        target="Target character name",
        damage="Damage amount (optional - auto-calculates based on attack type + highest STR/DEX)",
        roll_stat="Stat to roll with (optional - if omitted, no roll, just damage projection)",
        hide_ac="Hide AC and show flavor text instead (default: false)",
        roll_mod="Optional roll modifier for this attack (e.g., 1 for advantage, -1 for disadvantage)"
    )
    @app_commands.choices(attack_type=[
        app_commands.Choice(name="Light (1 star)", value="light"),
        app_commands.Choice(name="Medium (2 stars)", value="medium"),
        app_commands.Choice(name="Heavy (4 stars)", value="heavy")
    ])
    @app_commands.choices(roll_stat=[
        app_commands.Choice(name="STR (Strength)", value="str"),
        app_commands.Choice(name="DEX (Dexterity)", value="dex"),
        app_commands.Choice(name="CON (Constitution)", value="con"),
        app_commands.Choice(name="INT (Intelligence)", value="int"),
        app_commands.Choice(name="WIS (Wisdom)", value="wis"),
        app_commands.Choice(name="CHA (Charisma)", value="cha")
    ])
    @app_commands.autocomplete(attacker=character_and_deployable_autocomplete, target=character_and_deployable_autocomplete)
    async def attack(
        self,
        interaction: discord.Interaction,
        attacker: str,
        attack_type: str,
        target: str,
        damage: int = None,
        roll_stat: str = None,
        hide_ac: bool = False,
        roll_mod: Optional[int] = 0
    ):
        """Perform an attack with damage projection (not auto-applied)"""
        print(f"[CMD] {interaction.user.name} used /attack with params: attacker={attacker}, attack_type={attack_type}, target={target}, damage={damage}, roll_stat={roll_stat}, hide_ac={hide_ac}")
        try:
            from utils.dice import roll_dice_pool, check_result
            import random

            # Star costs
            star_costs = {"light": 1, "medium": 2, "heavy": 4}
            star_cost = star_costs[attack_type]

            # Base damage by attack type (before stat modifiers)
            base_damages = {"light": 4, "medium": 8, "heavy": 14}

            # Helper function to create damage visualization health bar
            def create_damage_bar(current_hp: int, max_hp: int, damage: int, temp_hp: int = 0) -> tuple:
                """Create health bar showing projected HP after damage with Discord emojis (5 blocks)"""
                if max_hp <= 0:
                    return ":black_large_square:" * 5, 0

                # Calculate HP after damage (accounting for temp HP)
                total_effective_hp = current_hp + temp_hp
                hp_after_damage = max(0, total_effective_hp - damage)

                # Calculate blocks for projected state (5 total)
                remaining_blocks = int((hp_after_damage / max_hp) * 5)
                damage_blocks = int((damage / max_hp) * 5)
                missing_blocks = 5 - remaining_blocks - damage_blocks

                # Clamp to prevent overflow
                if remaining_blocks + damage_blocks > 5:
                    damage_blocks = 5 - remaining_blocks
                    missing_blocks = 0

                # Ensure non-negative
                remaining_blocks = max(0, remaining_blocks)
                damage_blocks = max(0, damage_blocks)
                missing_blocks = max(0, missing_blocks)

                # Build bar with Discord emojis: green (remaining), red (damage), black (missing)
                bar = (":green_square:" * remaining_blocks +
                       ":red_square:" * damage_blocks +
                       ":black_large_square:" * missing_blocks)

                # Calculate percentage of projected HP
                after_pct = int((hp_after_damage / max_hp) * 100)

                return bar, after_pct

            # Helper function for flavor text based on damage
            def get_damage_flavor(damage: int, max_hp: int, current_hp: int) -> str:
                """Get flavor text based on damage % and current HP"""
                damage_pct = (damage / max_hp) * 100
                hp_pct = (current_hp / max_hp) * 100

                # Choose flavor based on damage % and current HP
                if damage_pct < 25:  # Light damage
                    if hp_pct > 75:
                        return random.choice(["staggers slightly", "barely flinches", "shrugs it off"])
                    elif hp_pct > 25:
                        return random.choice(["winces", "takes the hit", "grits their teeth"])
                    else:
                        return random.choice(["reels back", "struggles to stand", "looks hurt"])
                elif damage_pct < 50:  # Medium damage
                    if hp_pct > 50:
                        return random.choice(["reels from the impact", "looks hurt", "stumbles back"])
                    else:
                        return random.choice(["cries out in pain", "is badly wounded", "struggles to stay standing"])
                elif damage_pct < 75:  # Heavy damage
                    if hp_pct > 25:
                        return random.choice(["is badly wounded", "clutches the wound", "gasps in pain"])
                    else:
                        return random.choice(["struggles to stand", "is on the verge of collapse", "can barely stay upright"])
                else:  # Massive damage
                    return random.choice(["is on the verge of collapse", "barely remains conscious", "collapses to one knee"])

            async with aiosqlite.connect('database/ronan.db') as db:
                # Check if combat is active
                in_combat = False
                current_stars = 0
                async with db.execute(
                    "SELECT combat_active FROM initiative WHERE id = 1"
                ) as cursor:
                    row = await cursor.fetchone()
                    if row and row[0] == 1:
                        in_combat = True

                # Get current stars (from combat_state if in combat, otherwise from characters)
                if in_combat:
                    async with db.execute(
                        "SELECT stars FROM combat_state WHERE LOWER(character_name) = LOWER(?)",
                        (attacker,)
                    ) as cursor:
                        stars_row = await cursor.fetchone()
                        if stars_row:
                            current_stars = stars_row[0]
                        else:
                            # Character not in combat_state yet - shouldn't happen but handle it
                            print(f"[WARNING] {attacker} not found in combat_state, checking characters table")
                            async with db.execute(
                                "SELECT current_stars FROM characters WHERE LOWER(name) = LOWER(?)",
                                (attacker,)
                            ) as cursor2:
                                fallback_row = await cursor2.fetchone()
                                if fallback_row:
                                    current_stars = fallback_row[0] if fallback_row[0] is not None else 0
                else:
                    # Get stars from characters table when not in combat
                    async with db.execute(
                        "SELECT current_stars FROM characters WHERE LOWER(name) = LOWER(?)",
                        (attacker,)
                    ) as cursor:
                        stars_row = await cursor.fetchone()
                        if stars_row:
                            current_stars = stars_row[0] if stars_row[0] is not None else 0
                        else:
                            print(f"[ERROR] Could not find {attacker} in characters table")

                print(f"[DEBUG] {attacker} has {current_stars} stars, needs {star_cost} for {attack_type} attack")

                # Always validate star cost
                if current_stars < star_cost:
                    print(f"[ERROR] Not enough stars! Need {star_cost}, have {current_stars}")
                    await interaction.response.send_message(
                        f"❌ Not enough stars! Need {star_cost}, have {current_stars}.",
                        ephemeral=True
                    )
                    return

                # Get attacker's stats and modifiers
                async with db.execute(
                    """SELECT stats_json, base_stats, stat_modifiers, roll_modifiers
                       FROM characters WHERE LOWER(name) = LOWER(?)""",
                    (attacker,)
                ) as cursor:
                    attacker_row = await cursor.fetchone()
                    if not attacker_row:
                        print(f"[ERROR] Attacker '{attacker}' not found")
                        await interaction.response.send_message(
                            f"❌ Attacker '{attacker}' not found!",
                            ephemeral=True
                        )
                        return

                attacker_stats = json.loads(attacker_row[0])
                attacker_base_stats = json.loads(attacker_row[1]) if attacker_row[1] else attacker_stats
                attacker_stat_mods = json.loads(attacker_row[2]) if attacker_row[2] else {"str": 0, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0}
                attacker_roll_mods = json.loads(attacker_row[3]) if attacker_row[3] else {"attack_modifier": 0, "save_modifier": 0, "incoming_modifier": 0}

                # Auto-calculate damage if not provided
                if damage is None:
                    # Use just the base damage - stat will be added when rolling
                    damage = base_damages[attack_type]
                    print(f"[AUTO] Using base damage for {attack_type} attack: {damage}")

                # Validate damage
                if damage < 0:
                    print(f"[ERROR] Damage must be non-negative")
                    await interaction.response.send_message(
                        "❌ Damage must be non-negative!",
                        ephemeral=True
                    )
                    return

                # Check if target is a character or deployable
                is_deployable = False
                target_threshold_damage = None
                target_threshold_dc = None
                async with db.execute(
                    """SELECT ac, hp, max_hp, temp_hp, ac_modifier, roll_modifiers, threshold_damage, threshold_dc, hidden_resources
                       FROM characters WHERE LOWER(name) = LOWER(?)""",
                    (target,)
                ) as cursor:
                    target_row = await cursor.fetchone()

                if not target_row:
                    # Check if it's a deployable
                    async with db.execute(
                        """SELECT id, hp, max_hp, owner_name
                           FROM deployables WHERE LOWER(deployable_name) = LOWER(?)""",
                        (target,)
                    ) as cursor:
                        deployable_row = await cursor.fetchone()

                        if not deployable_row:
                            print(f"[ERROR] Target '{target}' not found (neither character nor deployable)")
                            await interaction.response.send_message(
                                f"❌ Target '{target}' not found (neither character nor deployable)!",
                                ephemeral=True
                            )
                            return

                        # Get owner's AC (deployable uses owner's AC)
                        deployable_id, dep_hp, dep_max_hp, owner_name = deployable_row

                        async with db.execute(
                            """SELECT ac, ac_modifier, roll_modifiers, hidden_resources
                               FROM characters WHERE LOWER(name) = LOWER(?)""",
                            (owner_name,)
                        ) as cursor:
                            owner_row = await cursor.fetchone()

                            if not owner_row:
                                print(f"[ERROR] Deployable owner '{owner_name}' not found")
                                await interaction.response.send_message(
                                    f"❌ Deployable owner '{owner_name}' not found!",
                                    ephemeral=True
                                )
                                return

                        is_deployable = True
                        target_base_ac = owner_row[0]
                        target_hp = dep_hp
                        target_max_hp = dep_max_hp
                        target_temp_hp = 0  # Deployables don't have temp HP
                        target_ac_mod = owner_row[1] if owner_row[1] else 0
                        target_roll_mods = json.loads(owner_row[2]) if owner_row[2] else {"attack_modifier": 0, "save_modifier": 0, "incoming_modifier": 0}
                        target_hidden = bool(owner_row[3]) if owner_row[3] is not None else False
                else:
                    target_base_ac = target_row[0]
                    target_hp = target_row[1]
                    target_max_hp = target_row[2]
                    target_temp_hp = target_row[3] if target_row[3] else 0
                    target_ac_mod = target_row[4] if target_row[4] else 0
                    target_roll_mods = json.loads(target_row[5]) if target_row[5] else {"attack_modifier": 0, "save_modifier": 0, "incoming_modifier": 0}
                    target_threshold_damage = target_row[6]
                    target_threshold_dc = target_row[7]
                    target_hidden = bool(target_row[8]) if target_row[8] is not None else False

                # Calculate effective AC
                target_ac = target_base_ac + target_ac_mod

                # Initialize variables for roll path
                outcome = None
                highest = None
                all_dice = []
                is_critical = False

                # If roll_stat provided, do the roll
                if roll_stat:
                    # Get base stat and calculate effective stat with modifiers
                    base_stat = attacker_base_stats.get(roll_stat, 0)
                    stat_mod = attacker_stat_mods.get(roll_stat, 0)
                    effective_stat = base_stat + stat_mod

                    # Calculate net dice modifier (attack_modifier + incoming_modifier + roll_mod)
                    attack_modifier = attacker_roll_mods['attack_modifier']
                    incoming_modifier = target_roll_mods['incoming_modifier']
                    net_modifier = attack_modifier + incoming_modifier + (roll_mod if roll_mod else 0)

                    if roll_mod and roll_mod != 0:
                        print(f"[ROLL_MOD] Applying temporary roll modifier: {roll_mod:+d}")

                    # Roll dice pool with new system
                    highest, all_dice, is_critical = roll_dice_pool(effective_stat, net_modifier)

                    # Check result vs AC
                    outcome = check_result(highest, target_ac)

                    print(f"[ROLL] {attacker} rolled {len(all_dice)}d6 ({effective_stat} stat + {net_modifier} net mod) = {all_dice}, highest={highest}")
                    print(f"[OK] {outcome} vs AC {target_ac}")

                    # If miss, show miss message and stop
                    if outcome == "miss":
                        embed = discord.Embed(
                            title=f"💨 {attacker} attacks {target}",
                            description=f"**{attack_type.upper()} ATTACK** using **{roll_stat.upper()}**",
                            color=discord.Color.dark_gray()
                        )
                        ac_display = "???" if target_hidden else str(target_ac)
                        embed.add_field(name="🎲 Roll", value=f"{highest} vs AC {ac_display} → MISS", inline=False)
                        embed.add_field(name="❌ Result", value="Combo breaks - can't attack anymore this turn!", inline=False)
                        await interaction.response.send_message(embed=embed)
                        print(f"[OK] {attacker} MISSED {target}")
                        return

                    # Calculate damage with effective stat
                    total_damage = damage + effective_stat
                    if is_critical:
                        total_damage *= 2
                else:
                    # No roll - just damage projection
                    total_damage = damage
                    outcome = None

                # Calculate projected HP after damage
                projected_hp = max(0, target_hp - total_damage)

                # Prepare HP display (hide if target has hidden_resources enabled)
                if target_hidden:
                    hp_display_value = "???"
                    print(f"[HIDDEN] {target} | HP after attack: {projected_hp}/{target_max_hp}")
                else:
                    damage_bar, after_pct = create_damage_bar(target_hp, target_max_hp, total_damage, target_temp_hp)
                    hp_display_value = f"{projected_hp}/{target_max_hp}\n{damage_bar} ({after_pct}%)"

                # Check damage threshold (only for character targets, not deployables)
                threshold_exceeded = False
                if not is_deployable and target_threshold_damage is not None and target_threshold_dc is not None:
                    if total_damage >= target_threshold_damage:
                        threshold_exceeded = True
                        print(f"[THRESHOLD] {target} took {total_damage} damage (threshold: {target_threshold_damage}) - CON save DC {target_threshold_dc} required!")

                # Spend stars (only if roll was made)
                if roll_stat is not None:
                    if in_combat:
                        await db.execute(
                            "UPDATE combat_state SET stars = stars - ? WHERE LOWER(character_name) = LOWER(?)",
                            (star_cost, attacker)
                        )
                    else:
                        await db.execute(
                            "UPDATE characters SET current_stars = current_stars - ? WHERE LOWER(name) = LOWER(?)",
                            (star_cost, attacker)
                        )
                    await db.commit()
                    print(f"[OK] Spent {star_cost} stars from {attacker} ({current_stars} → {current_stars - star_cost})")

            # Build embed based on hide_ac flag
            if roll_stat:
                if hide_ac:
                    # Style: Flavor text instead of AC
                    embed = discord.Embed(
                        title=f"⚔️ {attacker} attacks {target}",
                        description=f"**{attack_type.upper()} strike**",
                        color=discord.Color.blue()
                    )

                    # Get flavor text
                    flavor = get_damage_flavor(total_damage, target_max_hp, target_hp)
                    embed.add_field(name="📖 Effect", value=f"{target} {flavor}", inline=False)

                    # 2x2 table: damage on left, projected HP on right
                    embed.add_field(name="💥 Damage", value=f"**{total_damage}** ({damage} base + {effective_stat} {roll_stat.upper()})", inline=True)
                    embed.add_field(name="Projected HP", value=hp_display_value, inline=True)

                    # Add threshold warning if exceeded
                    if threshold_exceeded:
                        embed.add_field(
                            name="⚠️ Damage Threshold",
                            value=f"**{target}** must make a **DC {target_threshold_dc} CON save** or suffer additional effects!",
                            inline=False
                        )

                else:
                    # Style 3: Full details with AC
                    embed = discord.Embed(
                        title=f"⚔️ {attacker} attacks {target} with a {attack_type.upper()} strike using {roll_stat.upper()}",
                        color=discord.Color.green() if outcome == "clean_hit" else discord.Color.orange()
                    )

                    # Roll result
                    result_emoji = "✅ CLEAN HIT" if outcome == "clean_hit" else "⚠️ HIT WITH COST"
                    if is_critical:
                        result_emoji += " 🔥 **CRIT!**"
                    ac_display = "???" if target_hidden else str(target_ac)
                    embed.add_field(name="🎲 Roll", value=f"{highest} vs AC {ac_display} → {result_emoji}", inline=False)

                    # 2x2 table: damage on left, projected HP on right
                    if is_critical:
                        base_calc = damage + effective_stat
                        embed.add_field(name="💥 Damage", value=f"{base_calc} (base {damage} + {effective_stat} {roll_stat.upper()}) x2 CRIT = **{total_damage}**", inline=True)
                    else:
                        embed.add_field(name="💥 Damage", value=f"{damage} base + {effective_stat} {roll_stat.upper()} = **{total_damage}**", inline=True)
                    embed.add_field(name="Projected HP", value=hp_display_value, inline=True)

                    # Add threshold warning if exceeded
                    if threshold_exceeded:
                        embed.add_field(
                            name="⚠️ Damage Threshold",
                            value=f"**{target}** must make a **DC {target_threshold_dc} CON save** or suffer additional effects!",
                            inline=False
                        )

            else:
                # No roll - just damage projection
                embed = discord.Embed(
                    title=f"⚔️ {attacker} attacks {target}",
                    description=f"**{attack_type.upper()} strike** (damage projection)",
                    color=discord.Color.blue()
                )

                # 2x2 table: damage on left, projected HP on right
                embed.add_field(name="💥 Damage", value=f"**{total_damage}** (base damage only)", inline=True)
                embed.add_field(name="Projected HP", value=hp_display_value, inline=True)

                # Add threshold warning if exceeded
                if threshold_exceeded:
                    embed.add_field(
                        name="⚠️ Damage Threshold",
                        value=f"**{target}** must make a **DC {target_threshold_dc} CON save** or suffer additional effects!",
                        inline=False
                    )

            # Add note that damage isn't auto-applied
            embed.set_footer(text=f"⚠️ Damage NOT auto-applied. Use /hp {target} -{total_damage} to apply.")

            await interaction.response.send_message(embed=embed)
            print(f"[OK] {attacker} attacked {target} for {total_damage} projected damage")

        except Exception as e:
            logger.error(f"Error attacking: {e}", exc_info=True)
            print(f"[ERROR] /attack failed: {str(e)}")
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    # Skill check command
    @app_commands.command(name="skill", description="Roll a d6 pool skill check (2d6k1 + modifiers)")
    @app_commands.describe(
        character="Character making the check",
        skill="Skill to use",
        tier="Difficulty tier (1=Easy, 2=Medium, 3=Hard)",
        note="Optional note/label for the roll",
        hide_tier="Hide tier in output for suspense (default: false)"
    )
    @app_commands.choices(skill=[
        app_commands.Choice(name="Athletics (STR)", value="athletics"),
        app_commands.Choice(name="Acrobatics (DEX)", value="acrobatics"),
        app_commands.Choice(name="Sleight of Hand (DEX)", value="sleight_of_hand"),
        app_commands.Choice(name="Stealth (DEX)", value="stealth"),
        app_commands.Choice(name="Arcana (INT)", value="arcana"),
        app_commands.Choice(name="History (INT)", value="history"),
        app_commands.Choice(name="Investigation (INT)", value="investigation"),
        app_commands.Choice(name="Nature (INT)", value="nature"),
        app_commands.Choice(name="Religion (INT)", value="religion"),
        app_commands.Choice(name="Animal Handling (WIS)", value="animal_handling"),
        app_commands.Choice(name="Insight (WIS)", value="insight"),
        app_commands.Choice(name="Medicine (WIS)", value="medicine"),
        app_commands.Choice(name="Perception (WIS)", value="perception"),
        app_commands.Choice(name="Survival (WIS)", value="survival"),
        app_commands.Choice(name="Deception (CHA)", value="deception"),
        app_commands.Choice(name="Intimidation (CHA)", value="intimidation"),
        app_commands.Choice(name="Performance (CHA)", value="performance"),
        app_commands.Choice(name="Persuasion (CHA)", value="persuasion")
    ], tier=[
        app_commands.Choice(name="Easy", value=1),
        app_commands.Choice(name="Medium", value=2),
        app_commands.Choice(name="Hard", value=3)
    ])
    @app_commands.autocomplete(character=character_autocomplete)
    async def skill_check(
        self,
        interaction: discord.Interaction,
        character: str,
        skill: str,
        tier: int,
        note: str = None,
        hide_tier: bool = False
    ):
        """Roll a d6 pool skill check"""
        try:
            from utils.dice import roll_d6_skill, get_skill_tier_thresholds

            # Map skills to stats
            skill_to_stat = {
                "athletics": "str", "acrobatics": "dex", "sleight_of_hand": "dex", "stealth": "dex",
                "arcana": "int", "history": "int", "investigation": "int", "nature": "int", "religion": "int",
                "animal_handling": "wis", "insight": "wis", "medicine": "wis", "perception": "wis", "survival": "wis",
                "deception": "cha", "intimidation": "cha", "performance": "cha", "persuasion": "cha"
            }

            stat_name = skill_to_stat.get(skill, "str")

            async with aiosqlite.connect('database/ronan.db') as db:
                # Get character's stats and modifiers (case-insensitive)
                async with db.execute(
                    """SELECT stats_json, stat_modifiers, roll_modifiers, proficiency
                       FROM characters WHERE LOWER(name) = LOWER(?)""",
                    (character,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        await interaction.response.send_message(
                            f"❌ Character '{character}' not found!",
                            ephemeral=True
                        )
                        return

                stats_json = json.loads(row[0]) if row[0] else {}
                stat_mods = json.loads(row[1]) if row[1] else {}
                roll_mods = json.loads(row[2]) if row[2] else {}
                proficiency = row[3] if row[3] else 0

            # Calculate stat modifier (stats are already 1-5 modifiers, just add effect modifiers)
            base_stat = stats_json.get(stat_name, 1)  # Default to 1 if missing
            stat_mod_value = stat_mods.get(stat_name, 0)
            stat_modifier = base_stat + stat_mod_value

            # Convert proficiency to advantage dice (0 to +2)
            prof_modifier = min(2, proficiency // 2)

            # Get any skill modifiers from effects (TODO: implement skill-specific modifiers)
            skill_modifier = roll_mods.get('attack_modifier', 0)  # Reuse attack modifier for now

            # Roll d6 skill (2d6k1 + modifiers)
            skill_result = roll_d6_skill(stat_modifier, prof_modifier, skill_modifier, tier)
            tier_data = get_skill_tier_thresholds(tier)

            # Format skill name nicely
            skill_display = skill.replace("_", " ").title()

            # Log command and result
            logger.info(f"[CMD] {interaction.user.name} used /skill: character={character}, skill={skill}, tier={tier}, note={note}")
            logger.info(f"[ROLL] {character} rolled {skill_display}: {len(skill_result.all_dice)}d6k1 = {skill_result.all_dice} -> kept {skill_result.roll} vs Tier {tier} ({tier_data['label']}) -> {skill_result.outcome}")

            # Color based on outcome
            if skill_result.outcome == "clean_success":
                color = 0x57F287  # Green
                outcome = "✅ **SUCCESS**"
            elif skill_result.outcome == "success_with_cost":
                color = 0xFEE75C  # Yellow
                outcome = "⚠️ **SUCCESS** (with cost)"
            else:
                color = 0xED4245  # Red
                outcome = "❌ **FAILURE**"

            embed = discord.Embed(color=color)

            # Format dice display
            def format_dice(all_dice, kept_die):
                parts = []
                for die in all_dice:
                    if die == kept_die:
                        parts.append(f"**{die}**")  # Bold the kept die
                    else:
                        parts.append(f"~~{die}~~")  # Strikethrough dropped dice
                return f"({', '.join(parts)})"

            dice_display = format_dice(skill_result.all_dice, skill_result.roll)

            # Build description
            # Format: [note:] skill_name → {num}d6k1 → (dice) → [tier info] → result
            parts = []
            if note:
                parts.append(f"**{note}:**")

            parts.append(f"🎲 {skill_display}")
            parts.append("→")
            parts.append(f"`{len(skill_result.all_dice)}d6k1`")
            parts.append("→")
            parts.append(dice_display)
            parts.append("→")

            # Show tier info unless hidden
            if not hide_tier:
                parts.append(f"{skill_result.roll} vs Tier {tier}")
                parts.append("→")
            else:
                parts.append(f"**{skill_result.roll}**")
                parts.append("→")

            parts.append(outcome)

            embed.description = " ".join(parts)

            # Send ephemeral confirmation, then post to channel
            await interaction.response.send_message("✓ Rolled skill", ephemeral=True, delete_after=2)
            await interaction.channel.send(embed=embed)

        except Exception as e:
            logger.error(f"Error rolling skill check: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="save", description="Roll a d6 pool saving throw (2d6kl1 + modifiers)")
    @app_commands.describe(
        character="Character making the save",
        save_type="Type of save (STR/DEX/CON/INT/WIS/CHA)",
        tier="Save difficulty tier: 1 (easy), 2 (medium), 3 (hard)",
        note="Optional note (e.g., RESISTING POISON)",
        hide_tier="Hide tier in output for suspense (default: false)"
    )
    @app_commands.choices(
        save_type=[
            app_commands.Choice(name="💪 STR (Strength)", value="str"),
            app_commands.Choice(name="🤸 DEX (Dexterity)", value="dex"),
            app_commands.Choice(name="🛡️ CON (Constitution)", value="con"),
            app_commands.Choice(name="🧠 INT (Intelligence)", value="int"),
            app_commands.Choice(name="👁️ WIS (Wisdom)", value="wis"),
            app_commands.Choice(name="✨ CHA (Charisma)", value="cha")
        ],
        tier=[
            app_commands.Choice(name="Easy", value=1),
            app_commands.Choice(name="Medium", value=2),
            app_commands.Choice(name="Hard", value=3)
        ]
    )
    @app_commands.autocomplete(character=character_autocomplete)
    async def save(
        self,
        interaction: discord.Interaction,
        character: str,
        save_type: str,
        tier: int,
        note: str = None,
        hide_tier: bool = False
    ):
        """Roll a d6 pool saving throw (2d6kl1 + modifiers)"""
        try:
            from utils.dice import roll_d6_save, get_save_tier_thresholds

            # Save type emojis
            save_emojis = {
                "str": "💪", "dex": "🤸", "con": "🛡️",
                "int": "🧠", "wis": "👁️", "cha": "✨"
            }

            async with aiosqlite.connect('database/ronan.db') as db:
                # Get character's stats and modifiers (case-insensitive)
                async with db.execute(
                    """SELECT stats_json, stat_modifiers, roll_modifiers
                       FROM characters WHERE LOWER(name) = LOWER(?)""",
                    (character,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        await interaction.response.send_message(
                            f"❌ Character '{character}' not found!",
                            ephemeral=True
                        )
                        return

                stats_json = json.loads(row[0]) if row[0] else {}
                stat_mods = json.loads(row[1]) if row[1] else {}
                roll_mods = json.loads(row[2]) if row[2] else {}

            # Calculate stat modifier (stats are already 1-5 modifiers, just add effect modifiers)
            base_stat = stats_json.get(save_type, 1)  # Default to 1 if missing
            stat_mod_value = stat_mods.get(save_type, 0)
            stat_modifier = base_stat + stat_mod_value

            # Get save modifier from effects
            save_modifier = roll_mods.get('save_modifier', 0)

            # Roll d6 save (2d6kl1 + modifiers)
            save_result = roll_d6_save(stat_modifier, save_modifier, tier)
            tier_data = get_save_tier_thresholds(tier)

            # Log command and result
            logger.info(f"[CMD] {interaction.user.name} used /save: character={character}, save_type={save_type}, tier={tier}, note={note}")
            logger.info(f"[ROLL] {character} rolled {len(save_result.all_dice)}d6kl1 = {save_result.all_dice} -> kept {save_result.roll} vs Tier {tier} ({tier_data['label']}) -> {save_result.outcome}")

            # Build compact embed (similar to /roll style)
            save_emoji = save_emojis.get(save_type, "🎲")

            # Color based on outcome
            if save_result.outcome == "clean_success":
                color = 0x57F287  # Green
                outcome = "✅ **SUCCESS**"
            elif save_result.outcome == "success_with_cost":
                color = 0xFEE75C  # Yellow
                outcome = "⚠️ **SUCCESS** (with cost)"
            else:
                color = 0xED4245  # Red
                outcome = "❌ **FAILURE**"

            embed = discord.Embed(color=color)

            # Format dice display
            def format_dice(all_dice, kept_die):
                parts = []
                for die in all_dice:
                    if die == kept_die:
                        parts.append(f"**{die}**")  # Bold the kept die
                    else:
                        parts.append(f"~~{die}~~")  # Strikethrough dropped dice
                return f"({', '.join(parts)})"

            dice_display = format_dice(save_result.all_dice, save_result.roll)

            # Build description
            # Format: [note:] emoji SAVE_TYPE Save → {num}d6kl1 → (dice) → [tier info] → result
            parts = []
            if note:
                parts.append(f"**{note}:**")

            parts.append(f"{save_emoji} {save_type.upper()} Save")
            parts.append("→")
            parts.append(f"`{len(save_result.all_dice)}d6kl1`")
            parts.append("→")
            parts.append(dice_display)
            parts.append("→")

            # Show tier info unless hidden
            if not hide_tier:
                parts.append(f"{save_result.roll} vs Tier {tier}")
                parts.append("→")
            else:
                parts.append(f"**{save_result.roll}**")
                parts.append("→")

            parts.append(outcome)

            embed.description = " ".join(parts)

            # Send ephemeral confirmation, then post to channel
            await interaction.response.send_message("✓ Rolled save", ephemeral=True, delete_after=2)
            await interaction.channel.send(embed=embed)

        except Exception as e:
            logger.error(f"Error rolling save: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    # Stack tracker commands
    stack_group = app_commands.Group(name="stack", description="Manage character stacks (counters)")

    @stack_group.command(name="add", description="Add a stack to a character")
    @app_commands.describe(
        character="Character name",
        stack_name="Stack name (e.g., 'focus', 'charges')",
        amount="Amount to add (default: 1)",
        duration="Optional duration in rounds (if omitted, lasts until manually removed)"
    )
    @app_commands.autocomplete(character=character_autocomplete)
    async def add_stack(
        self,
        interaction: discord.Interaction,
        character: str,
        stack_name: str,
        amount: int = 1,
        duration: int = None
    ):
        """Add stacks to a character"""
        try:
            async with aiosqlite.connect('database/ronan.db') as db:
                # Get character's current stacks
                async with db.execute(
                    "SELECT stacks_json FROM characters WHERE name = ?",
                    (character,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        await interaction.followup.send(
                            f"❌ Character '{character}' not found!",
                            ephemeral=True
                        )
                        return

                    stacks = json.loads(row[0]) if row[0] else {}

                # Add or update stack
                if stack_name in stacks:
                    stacks[stack_name]["amount"] += amount
                else:
                    stacks[stack_name] = {"amount": amount}

                if duration:
                    # Get current round
                    async with db.execute("SELECT round_number FROM initiative WHERE id = 1") as cursor:
                        init_row = await cursor.fetchone()
                        current_round = init_row[0] if init_row else 99
                    stacks[stack_name]["expires_round"] = current_round + duration

                # Update database
                await db.execute(
                    "UPDATE characters SET stacks_json = ? WHERE name = ?",
                    (json.dumps(stacks), character)
                )
                await db.commit()

            duration_text = f" ({duration} rounds)" if duration else " (permanent)"
            await interaction.response.send_message(
                f"📊 Added **{amount}** {stack_name} stack(s) to **{character}**{duration_text} (total: {stacks[stack_name]['amount']})"
            )
            print(f"[STACK] Added {amount} {stack_name} to {character}")

        except Exception as e:
            logger.error(f"Error adding stack: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    @stack_group.command(name="remove", description="Remove stacks from a character")
    @app_commands.describe(
        character="Character name",
        stack_name="Stack name to remove",
        amount="Amount to remove (omit to remove all)"
    )
    @app_commands.autocomplete(character=character_autocomplete)
    async def remove_stack(
        self,
        interaction: discord.Interaction,
        character: str,
        stack_name: str,
        amount: int = None
    ):
        """Remove stacks from a character"""
        try:
            async with aiosqlite.connect('database/ronan.db') as db:
                async with db.execute(
                    "SELECT stacks_json FROM characters WHERE name = ?",
                    (character,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        await interaction.followup.send(
                            f"❌ Character '{character}' not found!",
                            ephemeral=True
                        )
                        return

                    stacks = json.loads(row[0]) if row[0] else {}

                if stack_name not in stacks:
                    await interaction.response.send_message(
                        f"❌ {character} has no '{stack_name}' stacks!",
                        ephemeral=True
                    )
                    return

                # Remove stacks
                if amount is None:
                    # Remove entirely
                    del stacks[stack_name]
                    removed_amount = "all"
                else:
                    stacks[stack_name]["amount"] -= amount
                    if stacks[stack_name]["amount"] <= 0:
                        del stacks[stack_name]
                        removed_amount = "all"
                    else:
                        removed_amount = str(amount)

                # Update database
                await db.execute(
                    "UPDATE characters SET stacks_json = ? WHERE name = ?",
                    (json.dumps(stacks), character)
                )
                await db.commit()

            await interaction.response.send_message(
                f"📉 Removed **{removed_amount}** {stack_name} stack(s) from **{character}**"
            )
            print(f"[STACK] Removed {removed_amount} {stack_name} from {character}")

        except Exception as e:
            logger.error(f"Error removing stack: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    @stack_group.command(name="view", description="View all stacks for a character")
    @app_commands.describe(character="Character name")
    @app_commands.autocomplete(character=character_autocomplete)
    async def view_stacks(
        self,
        interaction: discord.Interaction,
        character: str
    ):
        """View all stacks for a character"""
        try:
            async with aiosqlite.connect('database/ronan.db') as db:
                async with db.execute(
                    "SELECT stacks_json FROM characters WHERE name = ?",
                    (character,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        await interaction.followup.send(
                            f"❌ Character '{character}' not found!",
                            ephemeral=True
                        )
                        return

                    stacks = json.loads(row[0]) if row[0] else {}

            if not stacks:
                await interaction.response.send_message(
                    f"📊 {character} has no stacks.",
                    ephemeral=True
                )
                return

            # Build embed
            embed = discord.Embed(
                title=f"📊 {character}'s Stacks",
                color=discord.Color.blue()
            )

            for stack_name, stack_data in stacks.items():
                amount = stack_data.get("amount", 0)
                expires = stack_data.get("expires_round")
                duration_text = f" (expires round {expires})" if expires else " (permanent)"
                embed.add_field(
                    name=stack_name,
                    value=f"**{amount}** stack(s){duration_text}",
                    inline=False
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)
            print(f"[STACK] Viewed stacks for {character}")

        except Exception as e:
            logger.error(f"Error viewing stacks: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(CombatCommands(bot))
