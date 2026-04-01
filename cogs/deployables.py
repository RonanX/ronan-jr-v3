"""
Deployables system - PROMPT 4
Summons, clones, constructs, etc.
"""

import discord
from discord import app_commands
from discord.ext import commands
import json
import logging
import aiosqlite
from typing import Optional

logger = logging.getLogger(__name__)


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


async def deployable_autocomplete(
    interaction: discord.Interaction,
    current: str
) -> list[app_commands.Choice[str]]:
    """Autocomplete for deployable names"""
    try:
        async with aiosqlite.connect('database/ronan.db') as db:
            async with db.execute(
                "SELECT deployable_name FROM deployables"
            ) as cursor:
                deployables = await cursor.fetchall()

        choices = [
            app_commands.Choice(name=dep[0], value=dep[0])
            for dep in deployables
            if current.lower() in dep[0].lower()
        ]
        return choices[:25]
    except Exception as e:
        logger.error(f"Deployable autocomplete failed: {e}")
        return []


async def deployable_by_owner_autocomplete(
    interaction: discord.Interaction,
    current: str
) -> list[app_commands.Choice[str]]:
    """Autocomplete for deployable names filtered by owner"""
    try:
        # Get owner from namespace
        owner = interaction.namespace.owner
        if not owner:
            return []

        async with aiosqlite.connect('database/ronan.db') as db:
            async with db.execute(
                "SELECT deployable_name FROM deployables WHERE owner_name = ?",
                (owner,)
            ) as cursor:
                deployables = await cursor.fetchall()

        choices = [
            app_commands.Choice(name=dep[0], value=dep[0])
            for dep in deployables
            if current.lower() in dep[0].lower()
        ]
        return choices[:25]
    except Exception as e:
        logger.error(f"Deployable by owner autocomplete failed: {e}")
        return []


class DeployableCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    deploy_group = app_commands.Group(name="deploy", description="Deployable management commands")

    @deploy_group.command(name="create", description="Create a deployable")
    @app_commands.describe(
        owner="Character who owns the deployable",
        name="Deployable name",
        hp="Max HP for deployable",
        stars="Max stars per turn for deployable",
        ac="Armor Class for deployable",
        archetype="Deployable archetype (Striker/Tank/Support/Balanced)",
        duration="Duration in rounds (optional - permanent if not specified)",
        mp="Max MP for deployable (optional, default 0)",
        hp_cost="HP cost to create (optional)",
        mp_cost="MP cost to create (optional)",
        star_cost="Star cost to create (optional)",
        hidden_resources="If true, HP/MP/Stars/AC display as ??? in embeds"
    )
    @app_commands.choices(archetype=[
        app_commands.Choice(name="Striker", value="Striker"),
        app_commands.Choice(name="Tank", value="Tank"),
        app_commands.Choice(name="Support", value="Support"),
        app_commands.Choice(name="Balanced", value="Balanced")
    ])
    @app_commands.autocomplete(owner=character_autocomplete)
    async def create_deployable(
        self,
        interaction: discord.Interaction,
        owner: str,
        name: str,
        hp: int,
        stars: int,
        ac: int,
        archetype: str,
        duration: int = None,
        mp: int = 0,
        hp_cost: int = None,
        mp_cost: int = None,
        star_cost: int = None,
        hidden_resources: bool = False
    ):
        """Create a deployable entity"""
        print(f"[CMD] {interaction.user.name} used /deploy create | owner={owner}, name={name}, hp={hp}, stars={stars}, ac={ac}, archetype={archetype}")

        # Defer FIRST to prevent "user used command" bloat
        await interaction.response.defer(ephemeral=True)

        try:
            async with aiosqlite.connect('database/ronan.db') as db:
                # Check if combat is active (for round tracking)
                current_round = 1  # Default round if not in combat
                in_combat = False
                async with db.execute(
                    "SELECT combat_active, round_number FROM initiative WHERE id = 1"
                ) as cursor:
                    row = await cursor.fetchone()
                    if row and row[0] == 1:
                        in_combat = True
                        current_round = row[1]

                # Handle duration
                if duration is not None and not in_combat:
                    print(f"[WARNING] Duration specified but no active combat - creating permanent deployable")

                # Check if owner exists and get current resources
                async with db.execute(
                    "SELECT name, hp, mp, current_stars FROM characters WHERE name = ?",
                    (owner,)
                ) as cursor:
                    owner_row = await cursor.fetchone()
                    if not owner_row:
                        print(f"[ERROR] Owner character '{owner}' not found")
                        await interaction.followup.send(
                            f"❌ Character '{owner}' not found!",
                            ephemeral=True
                        )
                        return

                    owner_hp = owner_row[1]
                    owner_mp = owner_row[2]
                    owner_stars = owner_row[3] or 0

                # Validate and deduct costs
                costs_deducted = []

                if hp_cost and hp_cost > 0:
                    if owner_hp < hp_cost:
                        print(f"[ERROR] {owner} lacks HP: need {hp_cost}, have {owner_hp}")
                        await interaction.followup.send(
                            f"❌ Not enough HP! Need {hp_cost}, {owner} has {owner_hp}.",
                            ephemeral=True
                        )
                        return
                    await db.execute(
                        "UPDATE characters SET hp = hp - ? WHERE name = ?",
                        (hp_cost, owner)
                    )
                    costs_deducted.append(f"❤️ {hp_cost} HP")
                    print(f"[OK] Deducted {hp_cost} HP from {owner} ({owner_hp} → {owner_hp - hp_cost})")

                if mp_cost and mp_cost > 0:
                    if owner_mp < mp_cost:
                        print(f"[ERROR] {owner} lacks MP: need {mp_cost}, have {owner_mp}")
                        await interaction.followup.send(
                            f"❌ Not enough MP! Need {mp_cost}, {owner} has {owner_mp}.",
                            ephemeral=True
                        )
                        return
                    await db.execute(
                        "UPDATE characters SET mp = mp - ? WHERE name = ?",
                        (mp_cost, owner)
                    )
                    costs_deducted.append(f"💙 {mp_cost} MP")
                    print(f"[OK] Deducted {mp_cost} MP from {owner} ({owner_mp} → {owner_mp - mp_cost})")

                if star_cost and star_cost > 0:
                    if owner_stars < star_cost:
                        print(f"[ERROR] {owner} lacks stars: need {star_cost}, have {owner_stars}")
                        await interaction.followup.send(
                            f"❌ Not enough stars! Need {star_cost}, {owner} has {owner_stars}.",
                            ephemeral=True
                        )
                        return
                    await db.execute(
                        "UPDATE characters SET current_stars = current_stars - ? WHERE name = ?",
                        (star_cost, owner)
                    )
                    costs_deducted.append(f"⭐ {star_cost} stars")
                    print(f"[OK] Deducted {star_cost} stars from {owner} ({owner_stars} → {owner_stars - star_cost})")

                # Calculate expiration round
                if duration is not None and in_combat:
                    available_until = current_round + duration
                else:
                    available_until = 999999  # Effectively permanent

                await db.execute("""
                    INSERT INTO deployables (
                        owner_name, deployable_name, hp, max_hp,
                        stars, max_stars, available_until_round, created_round,
                        ac, archetype, mp, max_mp, hidden_resources
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (owner, name, hp, hp, stars, stars, available_until, current_round, ac, archetype, mp, mp, 1 if hidden_resources else 0))

                await db.commit()

            embed = discord.Embed(
                title=f"🎭 Deployable Created: {name}",
                description=f"Owner: **{owner}** | {archetype}",
                color=discord.Color.purple()
            )

            embed.add_field(name="❤️ HP", value=f"{hp}/{hp}", inline=True)
            embed.add_field(name="⭐ Stars", value=f"{stars}/{stars}", inline=True)
            embed.add_field(name="🛡️ AC", value=f"{ac}", inline=True)

            if mp > 0:
                embed.add_field(name="💙 MP", value=f"{mp}/{mp}", inline=True)

            if duration is not None:
                embed.add_field(name="⏱️ Duration", value=f"{duration} rounds (expires round {available_until})", inline=True)
            else:
                embed.add_field(name="⏱️ Duration", value="Permanent", inline=True)

            # Show costs if any
            if costs_deducted:
                embed.add_field(
                    name="💸 Cost",
                    value=", ".join(costs_deducted),
                    inline=False
                )

            print(f"[OK] Created deployable '{name}' for {owner} ({archetype}, AC {ac})")
            # Delete ephemeral thinking message, send fresh visible message
            await interaction.delete_original_response()
            await interaction.channel.send(embed=embed)

        except Exception as e:
            logger.error(f"Error creating deployable: {e}", exc_info=True)

            # Provide helpful error messages for common issues
            error_msg = f"❌ Error: {str(e)}"
            if "no column named" in str(e).lower():
                error_msg = f"❌ Database schema error! Run: `python database/fix_deployables_schema.py`\nError: {str(e)}"
            elif "foreign key" in str(e).lower():
                error_msg = f"❌ Database constraint error (owner may not exist)\nError: {str(e)}"

            print(f"[ERROR] Failed to create deployable: {e}")
            await interaction.followup.send(error_msg, ephemeral=True)

    @deploy_group.command(name="attack", description="Deployable attacks a target")
    @app_commands.describe(
        owner="Owner character name",
        deployable="Deployable name",
        attack_type="Attack type (light=1⭐, medium=2⭐, heavy=4⭐)",
        target="Target character",
        damage="Damage amount (optional - auto-calculates based on attack type + owner's highest STR/DEX)",
        roll_stat="Stat to roll with (optional - uses owner's stats)",
        hide_ac="Hide AC and show flavor text instead (default: false)"
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
    @app_commands.autocomplete(owner=character_autocomplete, deployable=deployable_by_owner_autocomplete, target=character_autocomplete)
    async def attack_with_deployable(
        self,
        interaction: discord.Interaction,
        owner: str,
        deployable: str,
        attack_type: str,
        target: str,
        damage: int = None,
        roll_stat: str = None,
        hide_ac: bool = False
    ):
        """Deployable executes an attack"""
        print(f"[CMD] {interaction.user.name} used /deploy attack | owner={owner}, deployable={deployable}, attack_type={attack_type}, target={target}, damage={damage}")

        # Defer to prevent "user used command" bloat
        await interaction.response.defer(ephemeral=True)

        try:
            from utils.dice import roll_dice_pool, check_result
            import random

            # Star costs and base damages by attack type
            star_costs = {"light": 1, "medium": 2, "heavy": 4}
            base_damages = {"light": 4, "medium": 8, "heavy": 14}
            star_cost = star_costs[attack_type]

            async with aiosqlite.connect('database/ronan.db') as db:
                # Get deployable data (filtered by owner)
                async with db.execute("""
                    SELECT id, owner_name, hp, stars
                    FROM deployables WHERE deployable_name = ? AND owner_name = ?
                """, (deployable, owner)) as cursor:
                    dep_row = await cursor.fetchone()
                    if not dep_row:
                        print(f"[ERROR] Deployable '{deployable}' not found for owner '{owner}'")
                        await interaction.followup.send(
                            f"❌ Deployable '{deployable}' not found for owner '{owner}'!",
                            ephemeral=True
                        )
                        return

                deployable_id, owner_name, dep_hp, dep_stars = dep_row

                # Check if deployable has enough stars
                if dep_stars < star_cost:
                    print(f"[ERROR] Not enough stars! {deployable} has {dep_stars}⭐, needs {star_cost}⭐")
                    await interaction.followup.send(
                        f"❌ Not enough stars! {deployable} has {dep_stars}⭐, needs {star_cost}⭐",
                        ephemeral=True
                    )
                    return

                # Get owner's stats (deployable uses owner's stats)
                async with db.execute("""
                    SELECT base_stats, stat_modifiers, roll_modifiers
                    FROM characters WHERE name = ?
                """, (owner_name,)) as cursor:
                    owner_row = await cursor.fetchone()
                    if not owner_row:
                        print(f"[ERROR] Owner '{owner_name}' not found")
                        await interaction.followup.send(
                            f"❌ Owner '{owner_name}' not found!",
                            ephemeral=True
                        )
                        return

                base_stats = json.loads(owner_row[0]) if owner_row[0] else {}
                stat_mods = json.loads(owner_row[1]) if owner_row[1] else {}
                roll_mods = json.loads(owner_row[2]) if owner_row[2] else {}

                # Auto-calculate damage if not provided
                if damage is None:
                    # Use highest offensive stat (str or dex) as default
                    str_total = base_stats.get("str", 0) + stat_mods.get("str", 0)
                    dex_total = base_stats.get("dex", 0) + stat_mods.get("dex", 0)
                    highest_offensive_stat = max(str_total, dex_total)

                    # Calculate damage: base_damage + stat
                    damage = base_damages[attack_type] + highest_offensive_stat
                    print(f"[AUTO] Calculated damage for {attack_type} attack: {base_damages[attack_type]} (base) + {highest_offensive_stat} (stat) = {damage}")

                # Get target data
                async with db.execute("""
                    SELECT ac, ac_modifier, hp, max_hp, roll_modifiers
                    FROM characters WHERE name = ?
                """, (target,)) as cursor:
                    target_row = await cursor.fetchone()
                    if not target_row:
                        print(f"[ERROR] Target '{target}' not found")
                        await interaction.followup.send(
                            f"❌ Target '{target}' not found!",
                            ephemeral=True
                        )
                        return

                target_ac = target_row[0] + (target_row[1] or 0)
                target_hp = target_row[2]
                target_max_hp = target_row[3]
                target_roll_mods = json.loads(target_row[4]) if target_row[4] else {}

                # Attack type emoji
                attack_emojis = {"light": "⚡", "medium": "⚔️", "heavy": "💥"}
                emoji = attack_emojis[attack_type]

                # Roll if roll_stat provided
                outcome = None
                highest = None
                all_dice = []

                if roll_stat:
                    # Calculate effective stat
                    base_stat = base_stats.get(roll_stat, 0)
                    stat_mod = stat_mods.get(roll_stat, 0)
                    effective_stat = base_stat + stat_mod

                    # Calculate net modifier
                    attack_modifier = roll_mods.get("attack_modifier", 0)
                    incoming_modifier = target_roll_mods.get("incoming_modifier", 0)
                    net_modifier = attack_modifier + incoming_modifier

                    # Roll dice pool
                    highest, all_dice, is_crit = roll_dice_pool(effective_stat, net_modifier)
                    outcome = check_result(highest, target_ac)

                    print(f"[ROLL] {deployable} ({owner}'s) rolled {len(all_dice)}d6 ({effective_stat} stat + {net_modifier} net mod) = {all_dice}, highest={highest}")
                    print(f"[OK] {outcome} vs AC {target_ac}")

                # Spend stars from deployable
                await db.execute(
                    "UPDATE deployables SET stars = stars - ? WHERE id = ?",
                    (star_cost, deployable_id)
                )

                # Project new HP
                projected_hp = max(0, target_hp - damage)

                await db.commit()

                # Build embed
                if roll_stat and outcome:
                    # With roll - show outcome
                    if outcome == "clean_hit":
                        color = discord.Color.green()
                        result_text = "✅ Clean Hit"
                    elif outcome == "partial_hit":
                        color = discord.Color.orange()
                        result_text = "⚠️ Hit With Cost"
                    else:  # miss
                        color = discord.Color.dark_gray()
                        result_text = "❌ Miss"
                else:
                    # No roll - just damage projection
                    color = discord.Color.blue()
                    result_text = None

                embed = discord.Embed(
                    title=f"{emoji} {deployable} ({owner}'s) → {attack_type.capitalize()} Attack → {target}",
                    color=color
                )

                # Roll info if rolled
                if roll_stat and all_dice:
                    dice_str = f"[{','.join(map(str, all_dice))}]"
                    if hide_ac:
                        roll_text = f"{effective_stat}d6 {dice_str} → {highest} - {result_text}"
                    else:
                        roll_text = f"{effective_stat}d6 {dice_str} → {highest} vs AC {target_ac} - {result_text}"
                    embed.add_field(name="🎲 Roll", value=roll_text, inline=False)

                # Damage projection
                damage_text = f"💥 {damage} damage\n{target}: ❤️ {target_hp} → {projected_hp}"
                embed.add_field(name="Damage", value=damage_text, inline=False)

                # Cost
                embed.add_field(name="💸 Cost", value=f"⭐ {star_cost} (from {deployable})", inline=True)

                print(f"[OK] {deployable} ({owner}'s) attacked {target} for {damage} projected damage")

                # Delete ephemeral thinking message, send fresh visible message
                await interaction.delete_original_response()
                await interaction.channel.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in deployable attack: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    @deploy_group.command(name="damage", description="Apply damage to a deployable")
    @app_commands.describe(
        deployable="Deployable name",
        amount="Damage amount"
    )
    @app_commands.autocomplete(deployable=deployable_autocomplete)
    async def damage_deployable(
        self,
        interaction: discord.Interaction,
        deployable: str,
        amount: int
    ):
        """Apply damage to deployable, auto-remove if hp <= 0"""
        print(f"[CMD] {interaction.user.name} used /deploy damage | deployable={deployable}, amount={amount}")
        try:
            async with aiosqlite.connect('database/ronan.db') as db:
                # Get deployable
                async with db.execute("""
                    SELECT id, hp, max_hp FROM deployables WHERE deployable_name = ?
                """, (deployable,)) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        print(f"[ERROR] Deployable '{deployable}' not found")
                        await interaction.response.send_message(
                            f"❌ Deployable '{deployable}' not found!",
                            ephemeral=True
                        )
                        return

                deployable_id, current_hp, max_hp = row
                new_hp = max(0, current_hp - amount)

                if new_hp == 0:
                    # Remove deployable
                    await db.execute(
                        "DELETE FROM deployables WHERE id = ?",
                        (deployable_id,)
                    )
                    await db.commit()

                    embed = discord.Embed(
                        title=f"💀 {deployable} Destroyed",
                        description=f"{amount} damage → 0 HP",
                        color=discord.Color.red()
                    )

                    print(f"[OK] Deployable '{deployable}' destroyed")
                else:
                    # Update HP
                    await db.execute(
                        "UPDATE deployables SET hp = ? WHERE id = ?",
                        (new_hp, deployable_id)
                    )
                    await db.commit()

                    percentage = int((new_hp / max_hp) * 100) if max_hp > 0 else 0

                    embed = discord.Embed(
                        title=f"💥 {deployable} Takes Damage",
                        description=f"{amount} damage",
                        color=discord.Color.orange()
                    )

                    from utils.move_execution import create_health_bar
                    health_bar = create_health_bar(new_hp, max_hp)

                    embed.add_field(
                        name="❤️ HP",
                        value=f"{new_hp}/{max_hp} {health_bar} ({percentage}%)",
                        inline=False
                    )

                    print(f"[OK] Deployable '{deployable}' HP: {current_hp} → {new_hp}")

                await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error(f"Error damaging deployable: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    @deploy_group.command(name="list", description="List active deployables")
    @app_commands.describe(owner="Character name (optional)")
    @app_commands.autocomplete(owner=character_autocomplete)
    async def list_deployables(
        self,
        interaction: discord.Interaction,
        owner: Optional[str] = None
    ):
        """List all active deployables for a character"""
        print(f"[CMD] {interaction.user.name} used /deploy list | owner={owner}")
        try:
            async with aiosqlite.connect('database/ronan.db') as db:
                # Get current round
                async with db.execute(
                    "SELECT round_number FROM initiative WHERE id = 1"
                ) as cursor:
                    row = await cursor.fetchone()
                    current_round = row[0] if row else 0

                # Get deployables
                if owner:
                    async with db.execute("""
                        SELECT deployable_name, hp, max_hp, stars, max_stars,
                               available_until_round, created_round
                        FROM deployables WHERE owner_name = ?
                    """, (owner,)) as cursor:
                        deployables = await cursor.fetchall()
                else:
                    async with db.execute("""
                        SELECT deployable_name, hp, max_hp, stars, max_stars,
                               available_until_round, created_round, owner_name
                        FROM deployables
                    """) as cursor:
                        deployables = await cursor.fetchall()

            if not deployables:
                print(f"[ERROR] No active deployables{f' for {owner}' if owner else ''}")
                await interaction.response.send_message(
                    f"❌ No active deployables{f' for {owner}' if owner else ''}!",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title=f"🎭 Active Deployables{f' ({owner})' if owner else ''}",
                color=discord.Color.purple()
            )

            for dep in deployables:
                if owner:
                    name, hp, max_hp, stars, max_stars, expires, created = dep
                    owner_name = owner
                else:
                    name, hp, max_hp, stars, max_stars, expires, created, owner_name = dep

                rounds_left = expires - current_round

                dep_info = (
                    f"**Owner:** {owner_name}\n"
                    f"❤️ **HP:** {hp}/{max_hp}\n"
                    f"⭐ **Stars:** {stars}/{max_stars}\n"
                    f"⏱️ **Remaining:** {rounds_left} rounds (expires round {expires})"
                )

                embed.add_field(
                    name=f"🎭 {name}",
                    value=dep_info,
                    inline=False
                )

            print(f"[OK] Listed {len(deployables)} deployables")
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error(f"Error listing deployables: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    @deploy_group.command(name="remove", description="Remove a deployable")
    @app_commands.describe(deployable="Deployable to remove")
    @app_commands.autocomplete(deployable=deployable_autocomplete)
    async def remove_deployable(
        self,
        interaction: discord.Interaction,
        deployable: str
    ):
        """Manually remove a deployable"""
        print(f"[CMD] {interaction.user.name} used /deploy remove | deployable={deployable}")
        try:
            async with aiosqlite.connect('database/ronan.db') as db:
                # Check if exists
                async with db.execute(
                    "SELECT id FROM deployables WHERE deployable_name = ?",
                    (deployable,)
                ) as cursor:
                    if not await cursor.fetchone():
                        print(f"[ERROR] Deployable '{deployable}' not found")
                        await interaction.response.send_message(
                            f"❌ Deployable '{deployable}' not found!",
                            ephemeral=True
                        )
                        return

                # Delete
                await db.execute(
                    "DELETE FROM deployables WHERE deployable_name = ?",
                    (deployable,)
                )
                await db.commit()

            print(f"[OK] Removed deployable '{deployable}'")
            await interaction.response.send_message(
                f"✅ Removed **{deployable}**"
            )

        except Exception as e:
            logger.error(f"Error removing deployable: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    @deploy_group.command(name="move_use", description="Use a move with a deployable")
    @app_commands.describe(
        deployable="Deployable name",
        move_name="Move to use",
        target="Target (required for attacks/saves)",
        owner_pays="If true, owner pays costs instead of deployable (default: false)"
    )
    @app_commands.autocomplete(deployable=deployable_autocomplete)
    async def deployable_move_use(
        self,
        interaction: discord.Interaction,
        deployable: str,
        move_name: str,
        target: Optional[str] = None,
        owner_pays: bool = False
    ):
        """Execute a move using a deployable"""
        print(f"[CMD] {interaction.user.name} used /deploy move_use | deployable={deployable}, move={move_name}, target={target}, owner_pays={owner_pays}")
        await interaction.response.defer(ephemeral=True)

        try:
            async with aiosqlite.connect('database/ronan.db') as db:
                # Get deployable data
                async with db.execute("""
                    SELECT owner_name, hp, max_hp, mp, max_mp, stars, max_stars
                    FROM deployables WHERE deployable_name = ?
                """, (deployable,)) as cursor:
                    dep_row = await cursor.fetchone()
                    if not dep_row:
                        await interaction.followup.send(f"❌ Deployable '{deployable}' not found!", ephemeral=True)
                        return

                owner_name, dep_hp, dep_max_hp, dep_mp, dep_max_mp, dep_stars, dep_max_stars = dep_row

                # Get move data
                async with db.execute("""
                    SELECT category, star_cost, mp_cost, hp_cost
                    FROM movesets WHERE character_name = ? AND move_name = ?
                """, (deployable, move_name)) as cursor:
                    move_row = await cursor.fetchone()
                    if not move_row:
                        await interaction.followup.send(
                            f"❌ Move '{move_name}' not found for deployable '{deployable}'!",
                            ephemeral=True
                        )
                        return

                category, star_cost, mp_cost, hp_cost = move_row

                # Validate and spend costs
                if owner_pays:
                    # Check owner resources
                    async with db.execute(
                        "SELECT current_stars, mp, hp FROM characters WHERE name = ?",
                        (owner_name,)
                    ) as cursor:
                        owner_res = await cursor.fetchone()
                        if not owner_res:
                            await interaction.followup.send(f"❌ Owner '{owner_name}' not found!", ephemeral=True)
                            return

                        owner_stars, owner_mp, owner_hp = owner_res
                        if owner_stars < star_cost or owner_mp < mp_cost or owner_hp <= hp_cost:
                            await interaction.followup.send(
                                f"❌ {owner_name} lacks resources! Needs ⭐{star_cost} 💙{mp_cost} ❤️{hp_cost}",
                                ephemeral=True
                            )
                            return

                    # Deduct from owner
                    await db.execute("""
                        UPDATE characters
                        SET current_stars = current_stars - ?, mp = mp - ?, hp = hp - ?
                        WHERE name = ?
                    """, (star_cost, mp_cost, hp_cost, owner_name))
                else:
                    # Check deployable resources
                    if dep_stars < star_cost or dep_mp < mp_cost or dep_hp <= hp_cost:
                        await interaction.followup.send(
                            f"❌ {deployable} lacks resources! Needs ⭐{star_cost} 💙{mp_cost} ❤️{hp_cost}",
                            ephemeral=True
                        )
                        return

                    # Deduct from deployable
                    await db.execute("""
                        UPDATE deployables
                        SET stars = stars - ?, mp = mp - ?, hp = hp - ?
                        WHERE deployable_name = ?
                    """, (star_cost, mp_cost, hp_cost, deployable))

                await db.commit()

                # Build cost display
                costs = []
                if star_cost > 0:
                    costs.append(f"⭐ {star_cost}")
                if mp_cost > 0:
                    costs.append(f"💙 {mp_cost}")
                if hp_cost > 0:
                    costs.append(f"❤️ {hp_cost}")
                cost_str = " ".join(costs) if costs else "Free"

                payer = owner_name if owner_pays else deployable

                embed = discord.Embed(
                    title=f"🎭 {deployable} uses {move_name}",
                    description=f"Target: {target if target else 'None'}\nCost: {cost_str} (paid by {payer})",
                    color=discord.Color.purple()
                )

                await interaction.delete_original_response()
                await interaction.channel.send(embed=embed)
                print(f"[OK] {deployable} used {move_name}")

        except Exception as e:
            logger.error(f"Error using deployable move: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

    @deploy_group.command(name="move_list", description="List moves for a deployable")
    @app_commands.describe(deployable="Deployable name")
    @app_commands.autocomplete(deployable=deployable_autocomplete)
    async def deployable_move_list(
        self,
        interaction: discord.Interaction,
        deployable: str
    ):
        """List all moves assigned to a deployable"""
        print(f"[CMD] {interaction.user.name} used /deploy move_list | deployable={deployable}")

        try:
            async with aiosqlite.connect('database/ronan.db') as db:
                # Verify deployable exists
                async with db.execute(
                    "SELECT owner_name FROM deployables WHERE deployable_name = ?",
                    (deployable,)
                ) as cursor:
                    dep_row = await cursor.fetchone()
                    if not dep_row:
                        await interaction.response.send_message(
                            f"❌ Deployable '{deployable}' not found!",
                            ephemeral=True
                        )
                        return

                owner_name = dep_row[0]

                # Get moves
                async with db.execute("""
                    SELECT move_name, category, star_cost, mp_cost, hp_cost
                    FROM movesets WHERE character_name = ?
                    ORDER BY category, move_name
                """, (deployable,)) as cursor:
                    moves = await cursor.fetchall()

                if not moves:
                    await interaction.response.send_message(
                        f"📋 **{deployable}** has no moves assigned.",
                        ephemeral=True
                    )
                    return

                # Build embed
                embed = discord.Embed(
                    title=f"📋 {deployable}'s Moves",
                    description=f"Owner: {owner_name}",
                    color=discord.Color.blue()
                )

                for move_name, category, star_cost, mp_cost, hp_cost in moves:
                    costs = []
                    if star_cost > 0:
                        costs.append(f"⭐{star_cost}")
                    if mp_cost > 0:
                        costs.append(f"💙{mp_cost}")
                    if hp_cost > 0:
                        costs.append(f"❤️{hp_cost}")
                    cost_str = " ".join(costs) if costs else "Free"

                    embed.add_field(
                        name=f"{move_name} ({category})",
                        value=cost_str,
                        inline=True
                    )

                await interaction.response.send_message(embed=embed, ephemeral=True)
                print(f"[OK] Listed {len(moves)} moves for {deployable}")

        except Exception as e:
            logger.error(f"Error listing deployable moves: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(DeployableCommands(bot))
