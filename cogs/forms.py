"""
Transformation system - PROMPT 5
Form management and transformation mechanics
"""

import discord
from discord import app_commands
from discord.ext import commands
import json
import logging
import aiosqlite
from typing import Optional

logger = logging.getLogger(__name__)

STAT_NAMES = ["str", "dex", "con", "int", "wis", "cha"]


def parse_costs(cost_string: str) -> dict:
    """Parse transformation cost format (mp:10, hp:5, stars:2)"""
    costs = {"mp_cost": 0, "hp_cost": 0, "star_cost": 0}

    if not cost_string or cost_string.strip() in ["", "0", "none"]:
        return costs

    parts = cost_string.split(",")
    for part in parts:
        part = part.strip().lower()
        if ":" in part:
            resource, value = part.split(":")
            resource = resource.strip()
            value = int(value.strip())

            if resource == "mp":
                costs["mp_cost"] = value
            elif resource == "hp":
                costs["hp_cost"] = value
            elif resource == "stars" or resource == "star":
                costs["star_cost"] = value

    return costs


async def character_autocomplete(
    interaction: discord.Interaction,
    current: str
) -> list[app_commands.Choice[str]]:
    """Autocomplete for character names"""
    try:
        async with aiosqlite.connect('database/ronan.db') as db:
            async with db.execute('SELECT name FROM characters') as cursor:
                characters = await cursor.fetchall()

        choices = [
            app_commands.Choice(name=char[0], value=char[0])
            for char in characters
            if current.lower() in char[0].lower()
        ]
        return choices[:25]
    except Exception as e:
        logger.error(f"Character autocomplete failed: {e}")
        return []


async def form_autocomplete(
    interaction: discord.Interaction,
    current: str
) -> list[app_commands.Choice[str]]:
    """Autocomplete for form names"""
    try:
        character = interaction.namespace.character
        if not character:
            return [app_commands.Choice(name="base", value="base")]

        async with aiosqlite.connect('database/ronan.db') as db:
            async with db.execute(
                "SELECT form_name FROM forms WHERE character_name = ?",
                (character,)
            ) as cursor:
                forms = await cursor.fetchall()

        # Always include base
        choices = [app_commands.Choice(name="base", value="base")]

        for form in forms:
            if current.lower() in form[0].lower() and form[0] != "base":
                choices.append(app_commands.Choice(name=form[0], value=form[0]))

        return choices[:25]
    except Exception as e:
        logger.error(f"Form autocomplete failed: {e}")
        return [app_commands.Choice(name="base", value="base")]


class FormCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    form_group = app_commands.Group(name="form", description="Transformation commands")

    @form_group.command(name="add", description="Create a new form for a character")
    @app_commands.describe(
        character="Character name",
        form_name="Form name",
        stats="Stats (str,dex,con,int,wis,cha)",
        ac="Armor Class for this form",
        cost="Transformation cost (mp:10, hp:5, stars:2)",
        duration="Duration in rounds (0 = indefinite)",
        cancellable="Can manually revert (true/false)"
    )
    @app_commands.autocomplete(character=character_autocomplete)
    async def add_form(
        self,
        interaction: discord.Interaction,
        character: str,
        form_name: str,
        stats: str,
        ac: int,
        cost: Optional[str] = "",
        duration: Optional[int] = 0,
        cancellable: Optional[bool] = True
    ):
        """Create a new transformation form"""
        print(f"[CMD] {interaction.user.name} used /form add | character={character}, form={form_name}")
        try:
            # Parse stats
            stat_values = [int(x.strip()) for x in stats.split(",")]
            if len(stat_values) != 6:
                await interaction.response.send_message(
                    "❌ Stats must be 6 comma-separated numbers (str,dex,con,int,wis,cha)",
                    ephemeral=True
                )
                return

            stats_dict = dict(zip(STAT_NAMES, stat_values))

            async with aiosqlite.connect('database/ronan.db') as db:
                # Check if character exists
                async with db.execute(
                    "SELECT name FROM characters WHERE name = ?",
                    (character,)
                ) as cursor:
                    if not await cursor.fetchone():
                        await interaction.response.send_message(
                            f"❌ Character '{character}' not found!",
                            ephemeral=True
                        )
                        return

                # Insert form
                await db.execute("""
                    INSERT INTO forms (
                        character_name, form_name, stats_json, ac,
                        transformation_cost, duration, cancellable
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    character, form_name, json.dumps(stats_dict), ac,
                    cost, duration if duration > 0 else None, 1 if cancellable else 0
                ))

                await db.commit()

            # Build success embed
            embed = discord.Embed(
                title=f"✨ Form Created: {form_name}",
                description=f"For **{character}**",
                color=discord.Color.purple()
            )

            stats_text = ", ".join([f"{s.upper()}: {v}" for s, v in stats_dict.items()])
            embed.add_field(name="📊 Stats", value=stats_text, inline=False)
            embed.add_field(name="🛡️ AC", value=str(ac), inline=True)

            if cost:
                embed.add_field(name="💸 Cost", value=cost, inline=True)
            if duration and duration > 0:
                embed.add_field(name="⏱️ Duration", value=f"{duration} rounds", inline=True)

            embed.add_field(
                name="🔄 Cancellable",
                value="Yes" if cancellable else "No",
                inline=True
            )

            print(f"[OK] Created form '{form_name}' for {character}")
            await interaction.response.send_message(embed=embed)

        except ValueError:
            await interaction.response.send_message(
                "❌ Invalid stats format. Use: str,dex,con,int,wis,cha (numbers only)",
                ephemeral=True
            )
        except aiosqlite.IntegrityError:
            await interaction.response.send_message(
                f"❌ Form '{form_name}' already exists for {character}!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error creating form: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    @form_group.command(name="list", description="List all forms for a character")
    @app_commands.describe(character="Character name")
    @app_commands.autocomplete(character=character_autocomplete)
    async def list_forms(
        self,
        interaction: discord.Interaction,
        character: str
    ):
        """List character's forms"""
        print(f"[CMD] {interaction.user.name} used /form list | character={character}")
        try:
            async with aiosqlite.connect('database/ronan.db') as db:
                # Get base stats
                async with db.execute(
                    "SELECT base_stats, ac FROM characters WHERE name = ?",
                    (character,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        await interaction.response.send_message(
                            f"❌ Character '{character}' not found!",
                            ephemeral=True
                        )
                        return

                    base_stats = json.loads(row[0]) if row[0] else {}
                    base_ac = row[1]

                # Get other forms
                async with db.execute("""
                    SELECT form_name, stats_json, ac, transformation_cost,
                           duration, cancellable, dot_damage, dot_type
                    FROM forms WHERE character_name = ?
                """, (character,)) as cursor:
                    forms = await cursor.fetchall()

            # Build embed
            embed = discord.Embed(
                title=f"✨ {character}'s Forms",
                color=discord.Color.purple()
            )

            # Base form
            base_stats_text = ", ".join([f"{s.upper()}: {v}" for s, v in base_stats.items()])
            base_info = f"📊 {base_stats_text}\n🛡️ AC: {base_ac}\n💸 Cost: Free"
            embed.add_field(name="🔹 base (default)", value=base_info, inline=False)

            # Other forms
            for form in forms:
                form_name, stats_json, ac, cost, duration, cancellable, dot_dmg, dot_type = form
                stats = json.loads(stats_json)

                stats_text = ", ".join([f"{s.upper()}: {v}" for s, v in stats.items()])

                info_parts = [f"📊 {stats_text}", f"🛡️ AC: {ac}"]

                if cost:
                    info_parts.append(f"💸 Cost: {cost}")

                if duration:
                    info_parts.append(f"⏱️ Duration: {duration} rounds")
                else:
                    info_parts.append(f"⏱️ Duration: indefinite")

                info_parts.append(f"🔄 Cancellable: {'Yes' if cancellable else 'No'}")

                if dot_dmg and dot_dmg > 0:
                    info_parts.append(f"💢 Recoil: {dot_dmg} {dot_type} damage/turn")

                embed.add_field(
                    name=f"✨ {form_name}",
                    value="\n".join(info_parts),
                    inline=False
                )

            print(f"[OK] Listed {len(forms) + 1} forms for {character}")
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error(f"Error listing forms: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    @form_group.command(name="transform", description="Transform into another form")
    @app_commands.describe(
        character="Character name",
        form="Form to transform into"
    )
    @app_commands.autocomplete(character=character_autocomplete, form=form_autocomplete)
    async def transform(
        self,
        interaction: discord.Interaction,
        character: str,
        form: str
    ):
        """Transform character into specified form"""
        print(f"[CMD] {interaction.user.name} used /form transform | character={character}, form={form}")

        # Defer FIRST to prevent "user used command" bloat
        await interaction.response.defer(ephemeral=True)

        try:
            async with aiosqlite.connect('database/ronan.db') as db:
                # Get character data
                async with db.execute("""
                    SELECT current_form, base_stats, hp, mp, max_mp, ac, current_stars
                    FROM characters WHERE name = ?
                """, (character,)) as cursor:
                    char_row = await cursor.fetchone()
                    if not char_row:
                        await interaction.followup.send(
                            f"❌ Character '{character}' not found!",
                            ephemeral=True
                        )
                        return

                current_form, base_stats_json, hp, mp, max_mp, base_ac, char_current_stars = char_row
                base_stats = json.loads(base_stats_json) if base_stats_json else {}

                if current_form == form:
                    await interaction.followup.send(
                        f"❌ {character} is already in {form} form!",
                        ephemeral=True
                    )
                    return

                # Handle base form transformation (revert)
                if form == "base":
                    # Reset to base stats (stat_modifiers = 0)
                    zero_mods = {s: 0 for s in STAT_NAMES}

                    await db.execute("""
                        UPDATE characters
                        SET current_form = 'base',
                            stat_modifiers = ?,
                            ac = ?
                        WHERE name = ?
                    """, (json.dumps(zero_mods), base_ac, character))

                    await db.commit()

                    embed = discord.Embed(
                        description=f"🔄 {character} reverts to base form",
                        color=discord.Color.blue()
                    )

                    print(f"[OK] {character} reverted to base form")
                    # Delete ephemeral thinking message, send fresh visible message
                    await interaction.delete_original_response()
                    await interaction.channel.send(embed=embed)
                    return

                # Get target form data
                async with db.execute("""
                    SELECT stats_json, ac, transformation_cost, duration,
                           cancellable, dot_damage, dot_type
                    FROM forms WHERE character_name = ? AND form_name = ?
                """, (character, form)) as cursor:
                    form_row = await cursor.fetchone()

                if not form_row:
                    await interaction.followup.send(
                        f"❌ Form '{form}' not found for {character}!",
                        ephemeral=True
                    )
                    return

                form_stats_json, form_ac, cost_str, duration, cancellable, dot_dmg, dot_type = form_row
                form_stats = json.loads(form_stats_json)

                # Parse transformation costs
                costs = parse_costs(cost_str)

                # Check if in combat for star validation
                in_combat = False
                current_stars = char_current_stars or 0  # Use character's stars by default

                async with db.execute(
                    "SELECT combat_active FROM initiative WHERE id = 1"
                ) as cursor:
                    row = await cursor.fetchone()
                    if row and row[0] == 1:
                        in_combat = True

                        # Get current stars from combat_state (overrides character stars)
                        async with db.execute(
                            "SELECT stars FROM combat_state WHERE character_name = ?",
                            (character,)
                        ) as cursor:
                            stars_row = await cursor.fetchone()
                            if stars_row:
                                current_stars = stars_row[0]

                # Validate costs (check stars whether in combat or not)
                if mp < costs["mp_cost"]:
                    print(f"[ERROR] {character} lacks MP for {form} transformation: need {costs['mp_cost']}, have {mp}")
                    await interaction.followup.send(
                        f"❌ Not enough MP! Need {costs['mp_cost']}, have {mp}.",
                        ephemeral=True
                    )
                    return

                if hp <= costs["hp_cost"]:
                    print(f"[ERROR] {character} lacks HP for {form} transformation: need {costs['hp_cost']}, have {hp}")
                    await interaction.followup.send(
                        f"❌ Not enough HP! Need {costs['hp_cost']}, have {hp}.",
                        ephemeral=True
                    )
                    return

                if costs["star_cost"] > 0 and current_stars < costs["star_cost"]:
                    print(f"[ERROR] {character} lacks stars for {form} transformation: need {costs['star_cost']}, have {current_stars}")
                    await interaction.followup.send(
                        f"❌ Not enough stars! Need {costs['star_cost']}, have {current_stars}.",
                        ephemeral=True
                    )
                    return

                # Calculate stat modifiers for new form
                # stat_modifiers = new_form_stats - base_stats
                new_mods = {}
                for stat in STAT_NAMES:
                    new_mods[stat] = form_stats.get(stat, 0) - base_stats.get(stat, 0)

                # Spend resources
                new_mp = mp - costs["mp_cost"]
                new_hp = max(1, hp - costs["hp_cost"])  # Don't kill yourself transforming

                await db.execute("""
                    UPDATE characters
                    SET current_form = ?,
                        stat_modifiers = ?,
                        ac = ?,
                        mp = ?,
                        hp = ?
                    WHERE name = ?
                """, (form, json.dumps(new_mods), form_ac, new_mp, new_hp, character))

                # Spend stars
                if costs["star_cost"] > 0:
                    if in_combat:
                        # Update combat_state stars
                        await db.execute(
                            "UPDATE combat_state SET stars = stars - ? WHERE character_name = ?",
                            (costs["star_cost"], character)
                        )
                    else:
                        # Update character stars
                        await db.execute(
                            "UPDATE characters SET current_stars = current_stars - ? WHERE name = ?",
                            (costs["star_cost"], character)
                        )

                # Create transformation effect if has duration
                if duration and duration > 0:
                    async with db.execute(
                        "SELECT round_number FROM initiative WHERE id = 1"
                    ) as cursor:
                        row = await cursor.fetchone()
                        current_round = row[0] if row else 0

                    from utils.effects import apply_effect

                    effect_data = {
                        "name": f"{form}_transformation",
                        "emoji": "✨",
                        "available_until_round": current_round + duration,
                        "contributions": {},
                        "dot_damage": dot_dmg or 0,
                        "dot_type": dot_type or ""
                    }

                    await apply_effect(character, effect_data, db=db)

                await db.commit()

            # Build embed with horizontal format
            embed = discord.Embed(
                title=f"✨ {character} transforms into {form} form!",
                color=discord.Color.gold()
            )

            # Costs with deltas (horizontal)
            cost_parts = []
            if costs["mp_cost"] > 0:
                cost_parts.append(f"💙 {mp} → {new_mp}")
            if costs["hp_cost"] > 0:
                cost_parts.append(f"❤️ {hp} → {new_hp}")
            if costs["star_cost"] > 0:
                new_stars = current_stars - costs["star_cost"]
                cost_parts.append(f"⭐ {current_stars} → {new_stars}")

            if cost_parts:
                embed.add_field(name="💸 Cost", value=", ".join(cost_parts), inline=False)

            # Stat changes (compact horizontal format)
            stat_changes = []
            for stat in STAT_NAMES:
                old_val = base_stats.get(stat, 0)
                new_val = form_stats.get(stat, 0)
                diff = new_val - old_val

                if diff != 0:
                    stat_changes.append(f"{stat.upper()}: {old_val}→{new_val}")

            changes_text = ""
            if stat_changes:
                changes_text = ", ".join(stat_changes)

            # AC change
            if base_ac != form_ac:
                if changes_text:
                    changes_text += f" | 🛡️ AC: {base_ac}→{form_ac}"
                else:
                    changes_text = f"🛡️ AC: {base_ac}→{form_ac}"

            if changes_text:
                embed.add_field(name="📊 Changes", value=changes_text, inline=False)

            # Duration and recoil warnings
            warnings = []
            if duration and duration > 0:
                warnings.append(f"⏱️ Reverts in {duration} rounds")
            if dot_dmg and dot_dmg > 0:
                warnings.append(f"💢 {dot_dmg} {dot_type} DoT/turn")

            if warnings:
                embed.add_field(name="⚠️ Warnings", value="\n".join(warnings), inline=False)

            # Build detailed log message
            log_parts = []
            if costs["mp_cost"] > 0:
                log_parts.append(f"💙 {mp}→{new_mp}")
            if costs["hp_cost"] > 0:
                log_parts.append(f"❤️ {hp}→{new_hp}")
            if costs["star_cost"] > 0:
                log_parts.append(f"⭐ {current_stars}→{current_stars - costs['star_cost']}")

            stat_log_parts = []
            for stat in STAT_NAMES:
                old_val = base_stats.get(stat, 0)
                new_val = form_stats.get(stat, 0)
                if old_val != new_val:
                    stat_log_parts.append(f"{stat.upper()}: {old_val}→{new_val}")

            if base_ac != form_ac:
                stat_log_parts.append(f"AC: {base_ac}→{form_ac}")

            costs_str = ", ".join(log_parts) if log_parts else "no cost"
            stats_str = " | ".join(stat_log_parts) if stat_log_parts else "no stat changes"

            print(f"[OK] {character} transformed to {form} form ({costs_str} | {stats_str})")
            # Delete ephemeral thinking message, send fresh visible message
            await interaction.delete_original_response()
            await interaction.channel.send(embed=embed)

        except Exception as e:
            logger.error(f"Error transforming: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    @form_group.command(name="revert", description="Revert to base form")
    @app_commands.describe(character="Character name")
    @app_commands.autocomplete(character=character_autocomplete)
    async def revert(
        self,
        interaction: discord.Interaction,
        character: str
    ):
        """Manually revert to base form"""
        print(f"[CMD] {interaction.user.name} used /form revert | character={character}")

        # Defer to prevent "user used command" bloat
        await interaction.response.defer(ephemeral=True)

        try:
            async with aiosqlite.connect('database/ronan.db') as db:
                # Get character data
                async with db.execute("""
                    SELECT current_form, ac FROM characters WHERE name = ?
                """, (character,)) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        await interaction.followup.send(
                            f"❌ Character '{character}' not found!",
                            ephemeral=True
                        )
                        return

                    current_form, base_ac = row

                if current_form == "base":
                    await interaction.followup.send(
                        f"❌ {character} is already in base form!",
                        ephemeral=True
                    )
                    return

                # Check if form is cancellable
                async with db.execute("""
                    SELECT cancellable FROM forms
                    WHERE character_name = ? AND form_name = ?
                """, (character, current_form)) as cursor:
                    form_row = await cursor.fetchone()

                    if form_row and form_row[0] == 0:
                        await interaction.followup.send(
                            f"❌ {current_form} form is not cancellable!",
                            ephemeral=True
                        )
                        return

                # Revert to base
                zero_mods = {s: 0 for s in STAT_NAMES}

                # Get base AC from characters table (stored in base_stats context)
                async with db.execute(
                    "SELECT ac FROM characters WHERE name = ? AND current_form = 'base'",
                    (character,)
                ) as cursor:
                    base_ac_row = await cursor.fetchone()

                # If not found, query from earliest record or default
                if not base_ac_row:
                    base_ac = 10  # Default fallback

                await db.execute("""
                    UPDATE characters
                    SET current_form = 'base',
                        stat_modifiers = ?
                    WHERE name = ?
                """, (json.dumps(zero_mods), character))

                # Remove transformation effect
                await db.execute("""
                    DELETE FROM effects
                    WHERE character_name = ? AND effect_name LIKE '%_transformation'
                """, (character,))

                await db.commit()

            embed = discord.Embed(
                title=f"🔄 {character} reverts to base form",
                color=discord.Color.blue()
            )

            print(f"[OK] {character} manually reverted to base form")
            # Delete ephemeral thinking message, send fresh visible message
            await interaction.delete_original_response()
            await interaction.channel.send(embed=embed)

        except Exception as e:
            logger.error(f"Error reverting form: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    @form_group.command(name="delete", description="Delete a form")
    @app_commands.describe(
        character="Character name",
        form="Form to delete"
    )
    @app_commands.autocomplete(character=character_autocomplete, form=form_autocomplete)
    async def delete_form(
        self,
        interaction: discord.Interaction,
        character: str,
        form: str
    ):
        """Delete a transformation form"""
        print(f"[CMD] {interaction.user.name} used /form delete | character={character}, form={form}")
        try:
            if form == "base":
                await interaction.response.send_message(
                    "❌ Cannot delete base form!",
                    ephemeral=True
                )
                return

            async with aiosqlite.connect('database/ronan.db') as db:
                # Check if form exists
                async with db.execute("""
                    SELECT form_name FROM forms
                    WHERE character_name = ? AND form_name = ?
                """, (character, form)) as cursor:
                    if not await cursor.fetchone():
                        await interaction.response.send_message(
                            f"❌ Form '{form}' not found for {character}!",
                            ephemeral=True
                        )
                        return

                # Delete form
                await db.execute("""
                    DELETE FROM forms WHERE character_name = ? AND form_name = ?
                """, (character, form))

                # Delete associated movesets
                await db.execute("""
                    DELETE FROM movesets WHERE character_name = ? AND form_name = ?
                """, (character, form))

                await db.commit()

            print(f"[OK] Deleted form '{form}' for {character}")
            await interaction.response.send_message(
                f"✅ Deleted form **{form}** for **{character}**"
            )

        except Exception as e:
            logger.error(f"Error deleting form: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(FormCommands(bot))
