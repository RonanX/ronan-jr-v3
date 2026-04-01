"""
Move system commands - PROMPT 2 implementation
Uses movesets table with individual move rows
"""

import discord
from discord import app_commands
from discord.ext import commands
import json
import logging
import aiosqlite
from typing import Optional
from utils.autocomplete import character_autocomplete, character_and_deployable_autocomplete
from utils.effects import apply_effect, get_preset_effect

logger = logging.getLogger(__name__)

STAT_NAMES = ["str", "dex", "con", "int", "wis", "cha"]
CATEGORY_EMOJIS = {
    "light": "⚡",
    "medium": "⚔️",
    "heavy": "💥",
    "utility": "🛠️"
}
STAR_COSTS = {
    "light": 1,
    "medium": 2,
    "heavy": 4,
    "utility": 2
}


def parse_costs(cost_string: str) -> dict:
    """
    Parse flexible cost format like 'mp:10, hp:5' or 'mp:10' or 'hp:5'
    Returns dict with mp_cost and hp_cost (defaults to 0)
    """
    costs = {"mp_cost": 0, "hp_cost": 0}

    if not cost_string or cost_string.strip().lower() == "none":
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

    return costs


async def deduct_resources(db, character: str, mp_cost: int, hp_cost: int, star_cost: int):
    """
    Deduct resources from character, consuming temp pools first before permanent pools.

    Args:
        db: Database connection
        character: Character name
        mp_cost: MP to deduct
        hp_cost: HP to deduct
        star_cost: Stars to deduct
    """
    # Get current resources including temp pools
    async with db.execute("""
        SELECT mp, temp_mp, hp, temp_hp, current_stars, temp_stars
        FROM characters WHERE name = ?
    """, (character,)) as cursor:
        row = await cursor.fetchone()
        if not row:
            return

        perm_mp, temp_mp, perm_hp, temp_hp, perm_stars, temp_stars = row
        temp_mp = temp_mp or 0
        temp_hp = temp_hp or 0
        temp_stars = temp_stars or 0

    # Deduct MP (temp first, then permanent)
    mp_from_temp = min(temp_mp, mp_cost)
    mp_from_perm = mp_cost - mp_from_temp
    new_temp_mp = temp_mp - mp_from_temp
    new_perm_mp = perm_mp - mp_from_perm

    # Deduct HP (temp first, then permanent)
    hp_from_temp = min(temp_hp, hp_cost)
    hp_from_perm = hp_cost - hp_from_temp
    new_temp_hp = temp_hp - hp_from_temp
    new_perm_hp = perm_hp - hp_from_perm

    # Deduct Stars (temp first, then permanent)
    stars_from_temp = min(temp_stars, star_cost)
    stars_from_perm = star_cost - stars_from_temp
    new_temp_stars = temp_stars - stars_from_temp
    new_perm_stars = perm_stars - stars_from_perm

    # Update database
    await db.execute("""
        UPDATE characters
        SET mp = ?, temp_mp = ?, hp = ?, temp_hp = ?, current_stars = ?, temp_stars = ?
        WHERE name = ?
    """, (new_perm_mp, new_temp_mp, new_perm_hp, new_temp_hp, new_perm_stars, new_temp_stars, character))

    print(f"[RESOURCES] {character} spent: {mp_cost} MP ({mp_from_temp} temp + {mp_from_perm} perm), {hp_cost} HP ({hp_from_temp} temp + {hp_from_perm} perm), {star_cost} Stars ({stars_from_temp} temp + {stars_from_perm} perm)")


# Autocomplete functions now imported from utils.autocomplete


async def deployable_by_character_autocomplete(
    interaction: discord.Interaction,
    current: str
) -> list[app_commands.Choice[str]]:
    """Autocomplete for deployables filtered by character"""
    try:
        # Get character from namespace
        character = interaction.namespace.character
        if not character:
            return []

        async with aiosqlite.connect('database/ronan.db') as db:
            async with db.execute(
                "SELECT deployable_name FROM deployables WHERE owner_name = ?",
                (character,)
            ) as cursor:
                deployables = await cursor.fetchall()

        choices = [
            app_commands.Choice(name=dep[0], value=dep[0])
            for dep in deployables
            if current.lower() in dep[0].lower()
        ]
        return choices[:25]
    except Exception as e:
        logger.error(f"Deployable by character autocomplete failed: {e}")
        return []


async def move_autocomplete(
    interaction: discord.Interaction,
    current: str
) -> list[app_commands.Choice[str]]:
    """Autocomplete for move names"""
    try:
        # Get character from namespace
        character = interaction.namespace.character
        if not character:
            return []

        async with aiosqlite.connect('database/ronan.db') as db:
            # Get character's current form
            async with db.execute(
                "SELECT current_form FROM characters WHERE name = ?",
                (character,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return []

                current_form = row[0]

            # Get moves for this character/form
            async with db.execute(
                "SELECT move_name FROM movesets WHERE character_name = ? AND form_name = ?",
                (character, current_form)
            ) as cursor:
                moves = await cursor.fetchall()

        choices = [
            app_commands.Choice(name=move[0], value=move[0])
            for move in moves
            if current.lower() in move[0].lower()
        ]
        return choices[:25]
    except Exception as e:
        logger.error(f"Move autocomplete failed: {e}")
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


class MoveCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    move_group = app_commands.Group(name="move", description="Move management commands")

    @move_group.command(name="create", description="Create a new move for a character or deployable")
    @app_commands.describe(
        character="Character or deployable name",
        form="Form name (default: base)",
        move_name="Move name",
        category="Move category (light/medium/heavy/utility)",
        costs="Costs in format 'mp:10, hp:5' (optional)",
        stat="Stat to use (str/dex/con/int/wis/cha) - optional for non-roll moves",
        damage="Base damage (optional)",
        description="Move description (optional)"
    )
    @app_commands.autocomplete(character=character_and_deployable_autocomplete, form=form_autocomplete)
    async def create_move(
        self,
        interaction: discord.Interaction,
        character: str,
        move_name: str,
        category: str,
        form: Optional[str] = "base",
        stat: Optional[str] = None,
        costs: Optional[str] = None,
        damage: Optional[int] = 0,
        description: Optional[str] = ""
    ):
        """Create a move with basic properties"""
        print(f"[CMD] {interaction.user.name} used /move create | character={character}, move={move_name}")
        try:
            # Validate category
            category = category.lower()
            if category not in CATEGORY_EMOJIS:
                print(f"[ERROR] Invalid category '{category}'")
                await interaction.response.send_message(
                    f"❌ Category must be one of: {', '.join(CATEGORY_EMOJIS.keys())}",
                    ephemeral=True
                )
                return

            # Validate stat (optional for non-roll moves)
            if stat:
                stat = stat.lower()
                if stat not in STAT_NAMES:
                    print(f"[ERROR] Invalid stat '{stat}'")
                    await interaction.response.send_message(
                        f"❌ Stat must be one of: {', '.join(STAT_NAMES)}",
                        ephemeral=True
                    )
                    return
            else:
                stat = None  # No stat for this move (no roll)

            # Auto-assign star cost
            star_cost = STAR_COSTS[category]

            # Parse costs
            parsed_costs = parse_costs(costs) if costs else {"mp_cost": 0, "hp_cost": 0}
            mp_cost = parsed_costs["mp_cost"]
            hp_cost = parsed_costs["hp_cost"]

            async with aiosqlite.connect('database/ronan.db') as db:
                # Verify character or deployable exists
                entity_type = None
                async with db.execute(
                    "SELECT name FROM characters WHERE name = ?",
                    (character,)
                ) as cursor:
                    if await cursor.fetchone():
                        entity_type = "character"

                if not entity_type:
                    # Check if it's a deployable
                    async with db.execute(
                        "SELECT deployable_name FROM deployables WHERE deployable_name = ?",
                        (character,)
                    ) as cursor:
                        if await cursor.fetchone():
                            entity_type = "deployable"

                if not entity_type:
                    print(f"[ERROR] Character or deployable '{character}' not found")
                    await interaction.response.send_message(
                        f"❌ Character or deployable '{character}' not found!",
                        ephemeral=True
                    )
                    return

                # Insert move
                await db.execute("""
                    INSERT INTO movesets (
                        character_name, form_name, move_name, category,
                        star_cost, mp_cost, hp_cost, stat, damage, description
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (character, form, move_name, category, star_cost, mp_cost, hp_cost, stat, damage, description))

                await db.commit()

            # Build success embed
            embed = discord.Embed(
                title=f"✅ Move Created: {move_name}",
                description=f"For **{character}** ({form} form)",
                color=discord.Color.green()
            )

            emoji = CATEGORY_EMOJIS[category]
            embed.add_field(name="Category", value=f"{emoji} {category.title()}", inline=True)
            embed.add_field(name="⭐ Star Cost", value=str(star_cost), inline=True)
            embed.add_field(name="Stat", value=stat.upper(), inline=True)

            if mp_cost > 0:
                embed.add_field(name="💙 MP Cost", value=str(mp_cost), inline=True)
            if hp_cost > 0:
                embed.add_field(name="❤️ HP Cost", value=str(hp_cost), inline=True)
            if damage > 0:
                embed.add_field(name="💥 Damage", value=str(damage), inline=True)

            if description:
                embed.add_field(name="Description", value=description, inline=False)

            print(f"[OK] Created move '{move_name}' for {character} ({form} form)")
            await interaction.response.send_message(embed=embed)

        except aiosqlite.IntegrityError:
            print(f"[ERROR] Move '{move_name}' already exists for {character} ({form} form)")
            await interaction.response.send_message(
                f"❌ Move '{move_name}' already exists for {character} ({form} form)!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error creating move: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    @move_group.command(name="edit", description="Edit a move's properties")
    @app_commands.describe(
        character="Character name",
        move_name="Move to edit",
        property_name="Property to edit",
        new_value="New value"
    )
    @app_commands.autocomplete(character=character_autocomplete, move_name=move_autocomplete)
    async def edit_move(
        self,
        interaction: discord.Interaction,
        character: str,
        move_name: str,
        property_name: str,
        new_value: str
    ):
        """Edit a move property"""
        print(f"[CMD] {interaction.user.name} used /move edit | character={character}, move={move_name}, property={property_name}")
        try:
            # Map property names to column names
            valid_properties = {
                "category": "category",
                "mp_cost": "mp_cost",
                "hp_cost": "hp_cost",
                "stat": "stat",
                "damage": "damage",
                "hits": "hits",
                "targets": "targets",
                "save_type": "save_type",
                "save_dc": "save_dc",
                "save_effect": "save_effect",
                "half_on_save": "half_on_save",
                "bonus_on_hit": "bonus_on_hit",
                "duration": "duration",
                "cooldown": "cooldown",
                "uses": "uses",
                "description": "description"
            }

            property_name = property_name.lower()
            if property_name not in valid_properties:
                print(f"[ERROR] Invalid property '{property_name}'")
                await interaction.response.send_message(
                    f"❌ Invalid property. Valid properties: {', '.join(valid_properties.keys())}",
                    ephemeral=True
                )
                return

            column = valid_properties[property_name]

            # Type conversions
            if property_name in ["mp_cost", "hp_cost", "damage", "hits", "targets", "save_dc", "duration", "cooldown", "uses"]:
                new_value = int(new_value)
            elif property_name == "half_on_save":
                new_value = 1 if new_value.lower() in ["true", "1", "yes"] else 0
            elif property_name == "stat":
                new_value = new_value.lower()
                if new_value not in STAT_NAMES:
                    print(f"[ERROR] Invalid stat '{new_value}'")
                    await interaction.response.send_message(
                        f"❌ Stat must be one of: {', '.join(STAT_NAMES)}",
                        ephemeral=True
                    )
                    return
            elif property_name == "category":
                new_value = new_value.lower()
                if new_value not in CATEGORY_EMOJIS:
                    print(f"[ERROR] Invalid category '{new_value}'")
                    await interaction.response.send_message(
                        f"❌ Category must be one of: {', '.join(CATEGORY_EMOJIS.keys())}",
                        ephemeral=True
                    )
                    return
                # Update star cost if category changes
                star_cost = STAR_COSTS[new_value]

            async with aiosqlite.connect('database/ronan.db') as db:
                # Get current form
                async with db.execute(
                    "SELECT current_form FROM characters WHERE name = ?",
                    (character,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        print(f"[ERROR] Character '{character}' not found")
                        await interaction.response.send_message(
                            f"❌ Character '{character}' not found!",
                            ephemeral=True
                        )
                        return

                    current_form = row[0]

                # Update move
                if property_name == "category":
                    await db.execute(f"""
                        UPDATE movesets
                        SET {column} = ?, star_cost = ?
                        WHERE character_name = ? AND form_name = ? AND move_name = ?
                    """, (new_value, star_cost, character, current_form, move_name))
                else:
                    await db.execute(f"""
                        UPDATE movesets
                        SET {column} = ?
                        WHERE character_name = ? AND form_name = ? AND move_name = ?
                    """, (new_value, character, current_form, move_name))

                if db.total_changes == 0:
                    print(f"[ERROR] Move '{move_name}' not found for {character} ({current_form} form)")
                    await interaction.response.send_message(
                        f"❌ Move '{move_name}' not found for {character} ({current_form} form)!",
                        ephemeral=True
                    )
                    return

                await db.commit()

            print(f"[OK] Updated {property_name} for move '{move_name}'")
            await interaction.response.send_message(
                f"✅ Updated **{move_name}**: {property_name} = {new_value}"
            )

        except ValueError:
            print(f"[ERROR] Invalid value for {property_name}")
            await interaction.response.send_message(
                f"❌ Invalid value for {property_name}",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error editing move: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    @move_group.command(name="list", description="List a character's moves")
    @app_commands.describe(
        character="Character name",
        form="Form name (optional, defaults to current form)"
    )
    @app_commands.autocomplete(character=character_autocomplete, form=form_autocomplete)
    async def list_moves(
        self,
        interaction: discord.Interaction,
        character: str,
        form: Optional[str] = None
    ):
        """List character's moves organized by category"""
        print(f"[CMD] {interaction.user.name} used /move list | character={character}")
        try:
            async with aiosqlite.connect('database/ronan.db') as db:
                # Get character's current form if not specified
                async with db.execute(
                    "SELECT current_form FROM characters WHERE name = ?",
                    (character,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        print(f"[ERROR] Character '{character}' not found")
                        await interaction.response.send_message(
                            f"❌ Character '{character}' not found!",
                            ephemeral=True
                        )
                        return

                    display_form = form if form else row[0]

                # Get all moves for this character/form
                async with db.execute("""
                    SELECT move_name, category, star_cost, mp_cost, hp_cost,
                           stat, damage, hits, description, uses, max_uses
                    FROM movesets
                    WHERE character_name = ? AND form_name = ?
                    ORDER BY category, move_name
                """, (character, display_form)) as cursor:
                    moves = await cursor.fetchall()

            if not moves:
                print(f"[ERROR] {character} has no moves in {display_form} form")
                await interaction.response.send_message(
                    f"❌ {character} has no moves in {display_form} form!",
                    ephemeral=True
                )
                return

            # Build embed
            embed = discord.Embed(
                title=f"📜 {character}'s Moves",
                description=f"**Form:** {display_form.title()}",
                color=discord.Color.blue()
            )

            # Organize by category
            by_category = {}
            for move in moves:
                move_name, category, star_cost, mp_cost, hp_cost, stat, damage, hits, desc, uses, max_uses = move
                if category not in by_category:
                    by_category[category] = []
                by_category[category].append({
                    "name": move_name,
                    "star_cost": star_cost,
                    "mp_cost": mp_cost,
                    "hp_cost": hp_cost,
                    "stat": stat,
                    "damage": damage,
                    "hits": hits,
                    "desc": desc,
                    "uses": uses,
                    "max_uses": max_uses
                })

            # Add fields by category
            for category in ["light", "medium", "heavy", "utility"]:
                if category not in by_category:
                    continue

                emoji = CATEGORY_EMOJIS[category]
                move_list = by_category[category]

                move_texts = []
                for m in move_list:
                    # Build cost string
                    costs = []
                    if m["star_cost"] > 0:
                        costs.append(f"{m['star_cost']}⭐")
                    if m["mp_cost"] > 0:
                        costs.append(f"{m['mp_cost']}💙")
                    if m["hp_cost"] > 0:
                        costs.append(f"{m['hp_cost']}❤️")

                    cost_str = " ".join(costs) if costs else "Free"

                    # Add uses if applicable
                    if m["max_uses"] is not None and m["max_uses"] > 0:
                        cost_str += f" | 🔋 {m['uses']}/{m['max_uses']}"

                    # Build info string
                    info_parts = [f"{m['stat'].upper()}"] if m['stat'] else []
                    if m["damage"] > 0:
                        dmg_text = f"{m['damage']} dmg"
                        if m["hits"] and m["hits"] > 1:
                            dmg_text += f" x{m['hits']}"
                        info_parts.append(dmg_text)

                    info_str = " | ".join(info_parts)

                    move_text = f"**{m['name']}** ({cost_str}) - {info_str}"
                    if m["desc"]:
                        move_text += f"\n*{m['desc']}*"

                    move_texts.append(move_text)

                embed.add_field(
                    name=f"{emoji} {category.upper()}",
                    value="\n\n".join(move_texts),
                    inline=False
                )

            print(f"[OK] Listed {len(moves)} moves for {character} ({display_form} form)")
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error(f"Error listing moves: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    @move_group.command(name="info", description="Show detailed info for a specific move")
    @app_commands.describe(
        character="Character name",
        move_name="Move name"
    )
    @app_commands.autocomplete(character=character_autocomplete, move_name=move_autocomplete)
    async def move_info(
        self,
        interaction: discord.Interaction,
        character: str,
        move_name: str
    ):
        """Show detailed information about a specific move"""
        print(f"[CMD] {interaction.user.name} used /move info | character={character}, move={move_name}")
        try:
            async with aiosqlite.connect('database/ronan.db') as db:
                # Get character's current form
                async with db.execute(
                    "SELECT current_form FROM characters WHERE name = ?",
                    (character,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        print(f"[ERROR] Character '{character}' not found")
                        await interaction.response.send_message(
                            f"❌ Character '{character}' not found!",
                            ephemeral=True
                        )
                        return

                    current_form = row[0]

                # Get move data
                async with db.execute("""
                    SELECT category, star_cost, mp_cost, hp_cost, stat, damage,
                           hits, targets, save_type, save_dc, save_effect,
                           half_on_save, bonus_on_hit, duration, cooldown, uses, description
                    FROM movesets
                    WHERE character_name = ? AND form_name = ? AND move_name = ?
                """, (character, current_form, move_name)) as cursor:
                    move_row = await cursor.fetchone()

            if not move_row:
                print(f"[ERROR] Move '{move_name}' not found for {character} ({current_form} form)")
                await interaction.response.send_message(
                    f"❌ Move '{move_name}' not found for {character} ({current_form} form)!",
                    ephemeral=True
                )
                return

            # Parse move data
            (category, star_cost, mp_cost, hp_cost, stat, damage,
             hits, targets, save_type, save_dc, save_effect,
             half_on_save, bonus_on_hit, duration, cooldown, uses, description) = move_row

            # Convert to proper types (some may be strings from database)
            star_cost = int(star_cost) if star_cost is not None else 0
            mp_cost = int(mp_cost) if mp_cost is not None else 0
            hp_cost = int(hp_cost) if hp_cost is not None else 0
            damage = int(damage) if damage is not None else 0
            hits = int(hits) if hits is not None else 1
            targets = int(targets) if targets is not None else 1
            save_dc = int(save_dc) if save_dc is not None else None
            half_on_save = int(half_on_save) if half_on_save is not None else 0
            duration = int(duration) if duration is not None else 0
            cooldown = int(cooldown) if cooldown is not None else 0
            uses = int(uses) if uses is not None else None

            # Build embed
            emoji = CATEGORY_EMOJIS.get(category, "⚔️")
            embed = discord.Embed(
                title=f"{emoji} {move_name}",
                description=description or "*No description*",
                color=discord.Color.gold()
            )

            # Category info
            embed.add_field(
                name="📊 Category",
                value=f"{category.upper()} ({star_cost}⭐)",
                inline=True
            )

            # Stat info
            if stat:
                embed.add_field(
                    name="📈 Stat",
                    value=stat.upper(),
                    inline=True
                )

            # Costs
            costs = []
            if star_cost > 0:
                costs.append(f"{star_cost}⭐")
            if mp_cost > 0:
                costs.append(f"{mp_cost}💙")
            if hp_cost > 0:
                costs.append(f"{hp_cost}❤️")

            embed.add_field(
                name="💰 Cost",
                value=" ".join(costs) if costs else "Free",
                inline=True
            )

            # Damage info
            if damage > 0:
                dmg_text = f"{damage} damage"
                if hits and hits > 1:
                    dmg_text += f" × {hits} hits"
                if targets and targets > 1:
                    dmg_text += f"\n{targets} targets"
                embed.add_field(
                    name="⚔️ Damage",
                    value=dmg_text,
                    inline=True
                )

            # Save info
            if save_type:
                save_text = f"{save_type.upper()} save"
                if save_dc:
                    save_text += f" (DC {save_dc})"
                if half_on_save:
                    save_text += "\nHalf damage on save"
                if save_effect:
                    save_text += f"\nEffect: {save_effect}"
                embed.add_field(
                    name="🎲 Save",
                    value=save_text,
                    inline=True
                )

            # Bonus on hit
            if bonus_on_hit:
                embed.add_field(
                    name="⚠️ On Hit Effect",
                    value=bonus_on_hit,
                    inline=True
                )

            # Duration
            if duration and duration > 0:
                embed.add_field(
                    name="⏱️ Duration",
                    value=f"{duration} rounds",
                    inline=True
                )

            # Cooldown
            if cooldown and cooldown > 0:
                embed.add_field(
                    name="⏳ Cooldown",
                    value=f"{cooldown} rounds",
                    inline=True
                )

            # Limited uses
            if uses:
                embed.add_field(
                    name="🔢 Uses",
                    value=f"{uses} per combat",
                    inline=True
                )

            embed.set_footer(text=f"Character: {character} | Form: {current_form}")

            print(f"[OK] Displayed info for {character}'s {move_name}")
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error(f"Error showing move info: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    @move_group.command(name="delete", description="Delete a move")
    @app_commands.describe(
        character="Character name",
        move_name="Move to delete"
    )
    @app_commands.autocomplete(character=character_autocomplete, move_name=move_autocomplete)
    async def delete_move(
        self,
        interaction: discord.Interaction,
        character: str,
        move_name: str
    ):
        """Delete a move with reaction confirmation"""
        print(f"[CMD] {interaction.user.name} used /move delete | character={character}, move={move_name}")
        try:
            async with aiosqlite.connect('database/ronan.db') as db:
                # Get current form
                async with db.execute(
                    "SELECT current_form FROM characters WHERE name = ?",
                    (character,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        print(f"[ERROR] Character '{character}' not found")
                        await interaction.response.send_message(
                            f"❌ Character '{character}' not found!",
                            ephemeral=True
                        )
                        return

                    current_form = row[0]

                # Check if move exists
                async with db.execute("""
                    SELECT move_name FROM movesets
                    WHERE character_name = ? AND form_name = ? AND move_name = ?
                """, (character, current_form, move_name)) as cursor:
                    if not await cursor.fetchone():
                        print(f"[ERROR] Move '{move_name}' not found for {character} ({current_form} form)")
                        await interaction.response.send_message(
                            f"❌ Move '{move_name}' not found for {character} ({current_form} form)!",
                            ephemeral=True
                        )
                        return

            # Send confirmation message
            await interaction.response.send_message(
                f"⚠️ Delete **{move_name}** from **{character}** ({current_form} form)?\n"
                f"React with ✅ to confirm, ❌ to cancel."
            )

            msg = await interaction.original_response()
            await msg.add_reaction("✅")
            await msg.add_reaction("❌")

            def check(reaction, user):
                return (
                    user == interaction.user and
                    str(reaction.emoji) in ["✅", "❌"] and
                    reaction.message.id == msg.id
                )

            reaction, user = await self.bot.wait_for('reaction_add', timeout=30.0, check=check)

            if str(reaction.emoji) == "✅":
                async with aiosqlite.connect('database/ronan.db') as db:
                    await db.execute("""
                        DELETE FROM movesets
                        WHERE character_name = ? AND form_name = ? AND move_name = ?
                    """, (character, current_form, move_name))
                    await db.commit()

                print(f"[OK] Deleted move '{move_name}' from {character} ({current_form} form)")
                await msg.edit(content=f"✅ Deleted **{move_name}**")
                await msg.clear_reactions()
            else:
                await msg.edit(content="❌ Deletion cancelled")
                await msg.clear_reactions()

        except TimeoutError:
            await msg.edit(content="❌ Deletion timed out")
            await msg.clear_reactions()
        except Exception as e:
            logger.error(f"Error deleting move: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    @move_group.command(name="help", description="Show move system documentation")
    async def move_help(self, interaction: discord.Interaction):
        """Show comprehensive move system help"""
        print(f"[CMD] {interaction.user.name} used /move help")

        embed = discord.Embed(
            title="📖 Move System Documentation",
            description="Complete guide to creating and managing character moves",
            color=discord.Color.purple()
        )

        # Categories
        embed.add_field(
            name="🎯 Move Categories",
            value=(
                "⚡ **Light** (1⭐) - Quick attacks, small spells\n"
                "⚔️ **Medium** (2⭐) - Standard attacks, moderate spells\n"
                "💥 **Heavy** (4⭐) - Ultimate attacks, powerful spells\n"
                "🛠️ **Utility** (0⭐) - Buffs, heals, non-damage actions"
            ),
            inline=False
        )

        # Properties
        embed.add_field(
            name="⚙️ Move Properties (Tier 1: Basic)",
            value=(
                "**category** - light/medium/heavy/utility\n"
                "**stat** - str/dex/con/int/wis/cha\n"
                "**damage** - Base damage (before stat bonus)\n"
                "**description** - What the move does"
            ),
            inline=False
        )

        embed.add_field(
            name="💰 Move Properties (Tier 2: Costs)",
            value=(
                "**mp_cost** - Mana point cost\n"
                "**hp_cost** - Health point cost\n"
                "**star_cost** - Auto-assigned by category\n"
                "*Use costs parameter: 'mp:10, hp:5' or 'mp:10'*"
            ),
            inline=False
        )

        embed.add_field(
            name="🎲 Move Properties (Tier 3: Advanced)",
            value=(
                "**hits** - Multi-hit count\n"
                "**targets** - Number of targets\n"
                "**save_type** - Save stat (str/dex/etc)\n"
                "**save_dc** - Save difficulty\n"
                "**save_effect** - Effect on failed save\n"
                "**half_on_save** - Half damage on success\n"
                "**bonus_on_hit** - Extra effect on hit\n"
                "**duration** - Effect duration (rounds)\n"
                "**cooldown** - Rounds before reuse\n"
                "**uses** - Limited use count"
            ),
            inline=False
        )

        # Commands
        embed.add_field(
            name="📋 Commands",
            value=(
                "`/move create` - Create new move (basic properties)\n"
                "`/move edit` - Edit move property\n"
                "`/move list` - View all moves\n"
                "`/move delete` - Delete move (with confirmation)\n"
                "`/move help` - Show this help"
            ),
            inline=False
        )

        # Examples
        embed.add_field(
            name="💡 Example: Create Light Attack",
            value=(
                "`/move create`\n"
                "character: Ronan\n"
                "move_name: Quick Strike\n"
                "category: light\n"
                "stat: dex\n"
                "costs: mp:5\n"
                "damage: 8\n"
                "description: Fast slashing attack"
            ),
            inline=False
        )

        embed.add_field(
            name="💡 Example: Edit Move",
            value=(
                "`/move edit`\n"
                "character: Ronan\n"
                "move_name: Quick Strike\n"
                "property: hits\n"
                "new_value: 2"
            ),
            inline=False
        )

        await interaction.response.send_message(embed=embed)

    @move_group.command(name="use", description="Use a move in combat")
    @app_commands.describe(
        character="Character or deployable name",
        move_name="Move to use",
        target="Target (required for attacks/saves, optional for utility)",
        roll_mod="Optional roll modifier for this attack (e.g., 1 for advantage, -1 for disadvantage)"
    )
    @app_commands.autocomplete(character=character_and_deployable_autocomplete, move_name=move_autocomplete)
    async def use_move(
        self,
        interaction: discord.Interaction,
        character: str,
        move_name: str,
        target: Optional[str] = None,
        roll_mod: Optional[int] = 0
    ):
        """Execute a move in combat"""
        print(f"[CMD] {interaction.user.name} used /move use | character={character}, move={move_name}, target={target}")

        # Defer FIRST to prevent "user used command" bloat
        await interaction.response.defer(ephemeral=True)

        try:
            from utils.dice import roll_dice_pool, check_result
            from utils.move_execution import (
                validate_costs, determine_move_type, calculate_multihit_result,
                calculate_attack_damage, calculate_save_damage, calculate_save_dc,
                create_health_bar, format_move_costs
            )

            async with aiosqlite.connect('database/ronan.db') as db:
                # Check if character is a regular character or a deployable
                async with db.execute("""
                    SELECT current_form, base_stats, stat_modifiers, roll_modifiers,
                           proficiency, mp, hp, max_hp, current_stars
                    FROM characters WHERE name = ?
                """, (character,)) as cursor:
                    char_row = await cursor.fetchone()

                is_deployable = False
                deployable_id = None
                owner_name = None

                if char_row:
                    # It's a regular character
                    current_form = char_row[0]
                    base_stats = json.loads(char_row[1]) if char_row[1] else {}
                    stat_mods = json.loads(char_row[2]) if char_row[2] else {}
                    roll_mods = json.loads(char_row[3]) if char_row[3] else {}
                    proficiency = char_row[4]
                    current_mp = char_row[5]
                    current_hp = char_row[6]
                    max_hp = char_row[7]
                    current_stars = char_row[8] if char_row[8] is not None else 0
                    attacker_display_name = character
                else:
                    # Check if it's a deployable
                    async with db.execute("""
                        SELECT id, owner_name, stars, mp, hp, max_hp
                        FROM deployables WHERE deployable_name = ?
                    """, (character,)) as cursor:
                        dep_row = await cursor.fetchone()
                        if not dep_row:
                            print(f"[ERROR] '{character}' not found as character or deployable")
                            await interaction.followup.send(
                                f"❌ '{character}' not found!",
                                ephemeral=True
                            )
                            return

                        # It's a deployable - get owner's stats for calculations
                        is_deployable = True
                        deployable_id = dep_row[0]
                        owner_name = dep_row[1]
                        current_stars = dep_row[2]
                        current_mp = dep_row[3]
                        current_hp = dep_row[4]
                        max_hp = dep_row[5]
                        attacker_display_name = f"{character} ({owner_name}'s)"

                        # Get owner's stats for roll modifiers
                        async with db.execute("""
                            SELECT current_form, base_stats, stat_modifiers, roll_modifiers, proficiency
                            FROM characters WHERE name = ?
                        """, (owner_name,)) as cursor:
                            owner_row = await cursor.fetchone()
                            if not owner_row:
                                print(f"[ERROR] Deployable owner '{owner_name}' not found")
                                await interaction.followup.send(
                                    f"❌ Deployable owner '{owner_name}' not found!",
                                    ephemeral=True
                                )
                                return

                            current_form = owner_row[0]
                            base_stats = json.loads(owner_row[1]) if owner_row[1] else {}
                            stat_mods = json.loads(owner_row[2]) if owner_row[2] else {}
                            roll_mods = json.loads(owner_row[3]) if owner_row[3] else {}
                            proficiency = owner_row[4]

                        print(f"[INFO] Using deployable '{character}' with Stars={current_stars}, MP={current_mp}, HP={current_hp}")

                # Check if in combat to use combat_state stars instead (only for regular characters)
                in_combat = False
                if not is_deployable:
                    async with db.execute(
                        "SELECT combat_active FROM initiative WHERE id = 1"
                    ) as cursor:
                        init_row = await cursor.fetchone()
                        if init_row and init_row[0] == 1:
                            in_combat = True
                            # Override with combat state stars if available
                            async with db.execute(
                                "SELECT stars FROM combat_state WHERE character_name = ?",
                                (character,)
                            ) as cursor:
                                stars_row = await cursor.fetchone()
                                if stars_row:
                                    current_stars = stars_row[0]

                # Get move data (including uses)
                async with db.execute("""
                    SELECT category, star_cost, mp_cost, hp_cost, stat, damage,
                           hits, targets, save_type, save_dc, save_effect,
                           half_on_save, bonus_on_hit, duration, description, uses, cooldown, self_effect, target_effect
                    FROM movesets
                    WHERE character_name = ? AND form_name = ? AND move_name = ?
                """, (character, current_form, move_name)) as cursor:
                    move_row = await cursor.fetchone()

                if not move_row:
                    print(f"[ERROR] Move '{move_name}' not found for {character} ({current_form} form)")
                    await interaction.followup.send(
                        f"❌ Move '{move_name}' not found for {character} ({current_form} form)!",
                        ephemeral=True
                    )
                    return

                # Parse move data
                move = {
                    "category": move_row[0],
                    "star_cost": move_row[1],
                    "mp_cost": move_row[2],
                    "hp_cost": move_row[3],
                    "stat": move_row[4],
                    "damage": move_row[5] or 0,
                    "hits": move_row[6] or 1,
                    "targets": move_row[7] or 1,
                    "save_type": move_row[8],
                    "save_dc": move_row[9],
                    "save_effect": move_row[10],
                    "half_on_save": move_row[11] or 0,
                    "bonus_on_hit": move_row[12],
                    "duration": move_row[13] or 0,
                    "description": move_row[14] or "",
                    "uses": move_row[15],
                    "cooldown": move_row[16] or 0,
                    "self_effect": move_row[17],
                    "target_effect": move_row[18]
                }

                # CRITICAL: Check limited uses (if uses is defined and == 0, no uses left)
                if move["uses"] is not None and move["uses"] == 0:
                    print(f"[ERROR] No uses remaining for '{move_name}'")
                    await interaction.followup.send(
                        f"❌ You are out of uses for this move!",
                        ephemeral=True
                    )
                    return

                # CRITICAL: Check cooldown (only in combat)
                if in_combat and not is_deployable:
                    # Get current round
                    async with db.execute("SELECT round_number FROM initiative WHERE id = 1") as cursor:
                        round_row = await cursor.fetchone()
                        current_round = round_row[0] if round_row else 0

                    # Get cooldowns from combat_state
                    async with db.execute(
                        "SELECT cooldowns_json FROM combat_state WHERE character_name = ?",
                        (character,)
                    ) as cursor:
                        cooldown_row = await cursor.fetchone()
                        cooldowns = json.loads(cooldown_row[0]) if cooldown_row and cooldown_row[0] else {}

                    # Check if move is on cooldown
                    if move_name in cooldowns and current_round < cooldowns[move_name]:
                        print(f"[ERROR] Move '{move_name}' is on cooldown until round {cooldowns[move_name]}")
                        await interaction.followup.send(
                            f"❌ {move_name} is on cooldown until Round {cooldowns[move_name]}!",
                            ephemeral=True
                        )
                        return

                # Validate costs
                is_valid, error_msg = validate_costs(
                    current_stars, current_mp, current_hp,
                    move["star_cost"], move["mp_cost"], move["hp_cost"]
                )

                if not is_valid:
                    await interaction.followup.send(error_msg, ephemeral=True)
                    return

                # Determine move type
                move_type = determine_move_type(move)

                # Validate target requirement
                if move_type in ["attack", "save"] and not target:
                    print(f"[ERROR] This move requires a target")
                    await interaction.followup.send(
                        "❌ This move requires a target!",
                        ephemeral=True
                    )
                    return

                # Calculate effective stat
                base_stat = base_stats.get(move["stat"], 0)
                stat_mod = stat_mods.get(move["stat"], 0)
                effective_stat = base_stat + stat_mod

                # Apply on-the-fly roll modifier if provided (for this attack only)
                temp_roll_mods = roll_mods.copy()
                if roll_mod and roll_mod != 0:
                    temp_roll_mods["attack_modifier"] = temp_roll_mods.get("attack_modifier", 0) + roll_mod
                    print(f"[ROLL_MOD] Applying temporary roll modifier: {roll_mod:+d} (total: {temp_roll_mods['attack_modifier']:+d})")

                # Route to appropriate handler
                if move_type == "attack":
                    await self._execute_attack_move(
                        interaction, db, character, move_name, target, move,
                        effective_stat, temp_roll_mods, current_stars, current_mp, current_hp, in_combat,
                        deployable_id, attacker_display_name, current_form, is_deployable
                    )
                elif move_type == "save":
                    await self._execute_save_move(
                        interaction, db, character, move_name, target, move,
                        effective_stat, proficiency, base_stats,
                        current_stars, current_mp, current_hp, in_combat,
                        deployable_id, attacker_display_name, current_form, is_deployable
                    )
                else:  # utility
                    await self._execute_utility_move(
                        interaction, db, character, move_name, move,
                        current_stars, current_mp, current_hp, in_combat,
                        deployable_id, attacker_display_name, current_form, is_deployable
                    )

        except Exception as e:
            logger.error(f"Error using move: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    async def _execute_attack_move(
        self, interaction, db, character, move_name, target, move,
        effective_stat, roll_mods, current_stars, current_mp, current_hp, in_combat,
        deployable_id, attacker_display_name, current_form: str, is_deployable: bool
    ):
        """Execute an attack-based move"""
        from utils.dice import roll_dice_pool, check_result
        from utils.move_execution import (
            calculate_multihit_result, calculate_attack_damage,
            create_health_bar, format_move_costs, CATEGORY_EMOJIS
        )

        # Get target data (check character first, then deployable)
        is_deployable_target = False
        async with db.execute("""
            SELECT ac, ac_modifier, hp, max_hp, roll_modifiers, threshold_damage, threshold_dc
            FROM characters WHERE name = ?
        """, (target,)) as cursor:
            target_row = await cursor.fetchone()

        if not target_row:
            # Check if target is a deployable
            async with db.execute("""
                SELECT ac, hp, max_hp, owner_name
                FROM deployables WHERE deployable_name = ?
            """, (target,)) as cursor:
                dep_target_row = await cursor.fetchone()
                if not dep_target_row:
                    print(f"[ERROR] Target '{target}' not found (neither character nor deployable)")
                    await interaction.followup.send(
                        f"❌ Target '{target}' not found!",
                        ephemeral=True
                    )
                    return

                # Deployable target
                is_deployable_target = True
                target_ac = dep_target_row[0]
                target_hp = dep_target_row[1]
                target_max_hp = dep_target_row[2]
                target_roll_mods = {}  # Deployables don't have roll modifiers
                target_threshold_damage = None
                target_threshold_dc = None
        else:
            # Character target
            target_ac = target_row[0] + (target_row[1] or 0)
            target_hp = target_row[2]
            target_max_hp = target_row[3]
            target_roll_mods = json.loads(target_row[4]) if target_row[4] else {}
            target_threshold_damage = target_row[5]
            target_threshold_dc = target_row[6]

        # Calculate net modifier
        attack_modifier = roll_mods.get("attack_modifier", 0)
        incoming_modifier = target_roll_mods.get("incoming_modifier", 0)
        net_modifier = attack_modifier + incoming_modifier

        # Roll dice pool
        highest, all_dice, is_crit = roll_dice_pool(effective_stat, net_modifier)

        # Check result
        outcome = check_result(highest, target_ac)

        # Calculate hits
        total_hits = move["hits"]
        hits_landed = calculate_multihit_result(outcome, total_hits)

        if hits_landed == 0:
            # Miss - spend resources but no damage
            # Update stars (from deployable if using deployable, else from character)
            if deployable_id:
                await db.execute(
                    "UPDATE deployables SET stars = stars - ? WHERE id = ?",
                    (move["star_cost"], deployable_id)
                )
            else:
                # Deduct resources (temp pools first, then permanent) - includes stars
                await deduct_resources(db, character, move["mp_cost"], move["hp_cost"], move["star_cost"])

                # Sync stars with combat_state if in combat
                if in_combat:
                    async with db.execute("SELECT current_stars FROM characters WHERE name = ?", (character,)) as cursor:
                        row = await cursor.fetchone()
                        if row:
                            await db.execute(
                                "UPDATE combat_state SET stars = ? WHERE character_name = ?",
                                (row[0], character)
                            )

            await db.commit()

            # Build compact miss embed
            # Line 1: Result
            result_line = f"💨 **Highest: {highest}** (Miss) ➔ **0 Dmg**"

            # Line 2: Status/Cost (show costs or healing)
            cost_parts = []
            if move["mp_cost"] != 0:
                if move["mp_cost"] > 0:
                    cost_parts.append(f"💙 **-{move['mp_cost']} MP**")
                else:
                    cost_parts.append(f"📈 **+{abs(move['mp_cost'])} MP**")
            if move["hp_cost"] != 0:
                if move["hp_cost"] > 0:
                    cost_parts.append(f"❤️ **-{move['hp_cost']} HP**")
                else:
                    cost_parts.append(f"📈 **+{abs(move['hp_cost'])} HP**")
            if move["star_cost"] > 0:
                cost_parts.append(f"⭐ **-{move['star_cost']}**")

            # Add remaining uses if limited
            if move["uses"] is not None and move["uses"] >= 0:
                cost_parts.append(f"🔋 **{move['uses']} Uses Left**")

            status_line = " | ".join(cost_parts) if cost_parts else ""

            # Combine lines
            if status_line:
                description = f"{result_line}\n📉 {status_line}"
            else:
                description = result_line

            embed = discord.Embed(
                title=f"✨ **{attacker_display_name} uses {move_name}**",
                description=description,
                color=discord.Color.dark_gray()
            )

            # Delete ephemeral thinking message, send fresh visible message
            await interaction.delete_original_response()
            await interaction.channel.send(embed=embed)
            return

        # Calculate damage
        damage_per_hit, total_damage = calculate_attack_damage(
            move["damage"], effective_stat, hits_landed, is_crit
        )

        # Project new HP
        projected_hp = max(0, target_hp - total_damage)

        # Check damage threshold
        threshold_exceeded = False
        if target_threshold_damage is not None and target_threshold_dc is not None:
            if total_damage >= target_threshold_damage:
                threshold_exceeded = True
                print(f"[THRESHOLD] {target} took {total_damage} damage (threshold: {target_threshold_damage}) - CON save DC {target_threshold_dc} required!")

        # Spend resources
        # Update stars (from deployable if using deployable, else from character)
        if deployable_id:
            await db.execute(
                "UPDATE deployables SET stars = stars - ? WHERE id = ?",
                (move["star_cost"], deployable_id)
            )
        else:
            # Deduct resources (temp pools first, then permanent) - includes stars
            await deduct_resources(db, character, move["mp_cost"], move["hp_cost"], move["star_cost"])

            # Sync stars with combat_state if in combat
            if in_combat:
                async with db.execute("SELECT current_stars FROM characters WHERE name = ?", (character,)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        await db.execute(
                            "UPDATE combat_state SET stars = ? WHERE character_name = ?",
                            (row[0], character)
                        )

        # Deduct limited use if applicable
        if move["uses"] is not None and move["uses"] > 0:
            await db.execute(
                "UPDATE movesets SET uses = uses - 1 WHERE character_name = ? AND move_name = ? AND form_name = ?",
                (character, move_name, current_form)
            )
            move["uses"] -= 1  # Update local copy for embed display

        # Update cooldown if applicable (only in combat for regular characters)
        if in_combat and not is_deployable and move["cooldown"] > 0:
            # Get current round
            async with db.execute("SELECT round_number FROM initiative WHERE id = 1") as cursor:
                round_row = await cursor.fetchone()
                current_round = round_row[0] if round_row else 0

            # Get current cooldowns
            async with db.execute(
                "SELECT cooldowns_json FROM combat_state WHERE character_name = ?",
                (character,)
            ) as cursor:
                cooldown_row = await cursor.fetchone()
                cooldowns = json.loads(cooldown_row[0]) if cooldown_row and cooldown_row[0] else {}

            # Set cooldown expiration round
            cooldowns[move_name] = current_round + move["cooldown"]

            # Save updated cooldowns
            await db.execute(
                "UPDATE combat_state SET cooldowns_json = ? WHERE character_name = ?",
                (json.dumps(cooldowns), character)
            )

        await db.commit()

        # Build compact hit embed
        # Color based on outcome
        if outcome == "clean_hit":
            color = discord.Color.green()
            result_text = "Clean Hit"
        else:
            color = discord.Color.orange()
            result_text = "Hit With Cost"

        if is_crit:
            result_text += " 🔥 CRIT"

        # Line 1: Result (different format for single vs multihit)
        if total_hits > 1:
            # Multihit attack: show individual hit results
            hit_results = []
            for i in range(total_hits):
                if i < hits_landed:
                    hit_results.append("✅")
                else:
                    hit_results.append("❌")
            result_line = f"🎯 **Hits:** [{' '.join(hit_results)}] ➔ **{total_damage} Dmg**"
        else:
            # Single hit attack
            result_line = f"🎯 **Highest: {highest}** ({result_text}) ➔ **{total_damage} Dmg**"

        # Line 2: Status/Cost (show costs or healing)
        cost_parts = []
        if move["mp_cost"] != 0:
            if move["mp_cost"] > 0:
                cost_parts.append(f"💙 **-{move['mp_cost']} MP**")
            else:
                cost_parts.append(f"📈 **+{abs(move['mp_cost'])} MP**")
        if move["hp_cost"] != 0:
            if move["hp_cost"] > 0:
                cost_parts.append(f"❤️ **-{move['hp_cost']} HP**")
            else:
                cost_parts.append(f"📈 **+{abs(move['hp_cost'])} HP**")
        if move["star_cost"] > 0:
            cost_parts.append(f"⭐ **-{move['star_cost']}**")

        # Add effect to status line if present
        if move["bonus_on_hit"] and hits_landed > 0:
            effect_name = move["bonus_on_hit"].split(":")[0].strip()
            cost_parts.append(f"⚠️ **Effect:** {effect_name}")

        # Add remaining uses if limited
        if move["uses"] is not None and move["uses"] >= 0:
            cost_parts.append(f"🔋 **{move['uses']} Uses Left**")

        status_line = " | ".join(cost_parts) if cost_parts else ""

        # Combine lines
        if status_line:
            description = f"{result_line}\n📉 {status_line}"
        else:
            description = result_line

        embed = discord.Embed(
            title=f"✨ **{attacker_display_name} uses {move_name}**",
            description=description,
            color=color
        )

        # Bonus on hit - apply effect if present
        if move["bonus_on_hit"] and hits_landed > 0:
            # Actually apply the effect to the database
            try:
                # Get current round for duration calculation (default to 99 if no active combat)
                async with db.execute("SELECT round_number FROM initiative WHERE id = 1") as cursor:
                    round_row = await cursor.fetchone()
                    current_round = round_row[0] if round_row else 99

                # Parse effect name and duration from bonus_on_hit (format: "effect_name" or "effect_name:duration" or "effect_name:duration:note")
                effect_parts = move["bonus_on_hit"].split(":")
                effect_name = effect_parts[0].strip().lower()
                duration_rounds = int(effect_parts[1]) if len(effect_parts) > 1 else 2  # default 2 rounds
                custom_note = effect_parts[2].strip() if len(effect_parts) > 2 else ""  # optional custom note

                # Calculate expiration round
                expiration_round = current_round + duration_rounds

                # Get preset and apply
                effect_data = get_preset_effect(effect_name, expiration_round)
                if custom_note:
                    effect_data["note"] = custom_note
                await apply_effect(target, effect_data, db=db)
                print(f"[EFFECT] Applied '{effect_name}' to {target} (expires round {expiration_round})")
            except Exception as e:
                logger.warning(f"Failed to apply bonus_on_hit effect '{move['bonus_on_hit']}': {e}")

        # Apply guaranteed self_effect to attacker
        if move["self_effect"]:
            try:
                async with db.execute("SELECT round_number FROM initiative WHERE id = 1") as cursor:
                    round_row = await cursor.fetchone()
                    current_round = round_row[0] if round_row else 99

                effect_parts = move["self_effect"].split(":")
                effect_name = effect_parts[0].strip().lower()
                duration_rounds = int(effect_parts[1]) if len(effect_parts) > 1 else 2
                custom_note = effect_parts[2].strip() if len(effect_parts) > 2 else ""

                expiration_round = current_round + duration_rounds
                effect_data = get_preset_effect(effect_name, expiration_round)
                if custom_note:
                    effect_data["note"] = custom_note
                await apply_effect(character, effect_data, db=db)
                print(f"[SELF_EFFECT] Applied '{effect_name}' to {character} (expires round {expiration_round})")
            except Exception as e:
                logger.warning(f"Failed to apply self_effect '{move['self_effect']}': {e}")

        # Apply guaranteed target_effect to target
        if move["target_effect"]:
            try:
                async with db.execute("SELECT round_number FROM initiative WHERE id = 1") as cursor:
                    round_row = await cursor.fetchone()
                    current_round = round_row[0] if round_row else 99

                effect_parts = move["target_effect"].split(":")
                effect_name = effect_parts[0].strip().lower()
                duration_rounds = int(effect_parts[1]) if len(effect_parts) > 1 else 2
                custom_note = effect_parts[2].strip() if len(effect_parts) > 2 else ""

                expiration_round = current_round + duration_rounds
                effect_data = get_preset_effect(effect_name, expiration_round)
                if custom_note:
                    effect_data["note"] = custom_note
                await apply_effect(target, effect_data, db=db)
                print(f"[TARGET_EFFECT] Applied '{effect_name}' to {target} (expires round {expiration_round})")
            except Exception as e:
                logger.warning(f"Failed to apply target_effect '{move['target_effect']}': {e}")

        # Delete ephemeral thinking message, send fresh visible message
        await interaction.delete_original_response()
        await interaction.channel.send(embed=embed)

    async def _execute_save_move(
        self, interaction, db, character, move_name, target, move,
        effective_stat, proficiency, base_stats,
        current_stars, current_mp, current_hp, in_combat,
        deployable_id, attacker_display_name, current_form: str, is_deployable: bool
    ):
        """Execute a save-based move"""
        from utils.dice import roll_save
        from utils.move_execution import (
            calculate_save_damage, calculate_save_dc,
            format_move_costs, CATEGORY_EMOJIS
        )

        # Calculate DC
        if move["save_dc"]:
            dc = move["save_dc"]
        else:
            dc = calculate_save_dc(proficiency, base_stats)

        # Get target data
        async with db.execute("""
            SELECT base_stats, stat_modifiers, roll_modifiers, proficiency, hp, max_hp, threshold_damage, threshold_dc
            FROM characters WHERE name = ?
        """, (target,)) as cursor:
            target_row = await cursor.fetchone()
            if not target_row:
                print(f"[ERROR] Target '{target}' not found")
                await interaction.response.send_message(
                    f"❌ Target '{target}' not found!",
                    ephemeral=True
                )
                return

        target_base_stats = json.loads(target_row[0]) if target_row[0] else {}
        target_stat_mods = json.loads(target_row[1]) if target_row[1] else {}
        target_roll_mods = json.loads(target_row[2]) if target_row[2] else {}
        target_proficiency = target_row[3]
        target_hp = target_row[4]
        target_max_hp = target_row[5]
        target_threshold_damage = target_row[6]
        target_threshold_dc = target_row[7]

        # Calculate target's effective save stat
        save_stat = move["save_type"]
        target_base_stat = target_base_stats.get(save_stat, 0)
        target_stat_mod = target_stat_mods.get(save_stat, 0)
        target_effective_stat = target_base_stat + target_stat_mod

        # Target rolls save (d20 + stat + proficiency + save_modifier)
        save_modifier = target_roll_mods.get("save_modifier", 0)
        save_result = roll_save(target_effective_stat, target_proficiency, save_modifier, dc)
        save_success = save_result.success

        # Calculate damage
        total_damage = calculate_save_damage(
            move["damage"], effective_stat, save_success, bool(move["half_on_save"])
        )

        # Project new HP
        projected_hp = max(0, target_hp - total_damage)

        # Check damage threshold
        threshold_exceeded = False
        if target_threshold_damage is not None and target_threshold_dc is not None:
            if total_damage >= target_threshold_damage:
                threshold_exceeded = True
                print(f"[THRESHOLD] {target} took {total_damage} damage (threshold: {target_threshold_damage}) - CON save DC {target_threshold_dc} required!")

        # Spend resources
        # Update stars (from deployable if using deployable, else from character)
        if deployable_id:
            await db.execute(
                "UPDATE deployables SET stars = stars - ? WHERE id = ?",
                (move["star_cost"], deployable_id)
            )
        else:
            # Deduct resources (temp pools first, then permanent) - includes stars
            await deduct_resources(db, character, move["mp_cost"], move["hp_cost"], move["star_cost"])

            # Sync stars with combat_state if in combat
            if in_combat:
                async with db.execute("SELECT current_stars FROM characters WHERE name = ?", (character,)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        await db.execute(
                            "UPDATE combat_state SET stars = ? WHERE character_name = ?",
                            (row[0], character)
                        )

        # Deduct limited use if applicable
        if move["uses"] is not None and move["uses"] > 0:
            await db.execute(
                "UPDATE movesets SET uses = uses - 1 WHERE character_name = ? AND move_name = ? AND form_name = ?",
                (character, move_name, current_form)
            )
            move["uses"] -= 1  # Update local copy for embed display

        # Update cooldown if applicable (only in combat for regular characters)
        if in_combat and not is_deployable and move["cooldown"] > 0:
            # Get current round
            async with db.execute("SELECT round_number FROM initiative WHERE id = 1") as cursor:
                round_row = await cursor.fetchone()
                current_round = round_row[0] if round_row else 0

            # Get current cooldowns
            async with db.execute(
                "SELECT cooldowns_json FROM combat_state WHERE character_name = ?",
                (character,)
            ) as cursor:
                cooldown_row = await cursor.fetchone()
                cooldowns = json.loads(cooldown_row[0]) if cooldown_row and cooldown_row[0] else {}

            # Set cooldown expiration round
            cooldowns[move_name] = current_round + move["cooldown"]

            # Save updated cooldowns
            await db.execute(
                "UPDATE combat_state SET cooldowns_json = ? WHERE character_name = ?",
                (json.dumps(cooldowns), character)
            )

        await db.commit()

        # Build compact save embed
        # Color based on save result
        if save_success:
            color = discord.Color.blue()
            outcome = "Success"
        else:
            color = discord.Color.red()
            outcome = "Fail"

        # Line 1: Result
        result_line = f"🛡️ **{save_stat.upper()} Save: {save_result.total}** ({outcome}) ➔ **{total_damage} Dmg**"

        # Line 2: Status/Cost (show costs or healing)
        cost_parts = []
        if move["mp_cost"] != 0:
            if move["mp_cost"] > 0:
                cost_parts.append(f"💙 **-{move['mp_cost']} MP**")
            else:
                cost_parts.append(f"📈 **+{abs(move['mp_cost'])} MP**")
        if move["hp_cost"] != 0:
            if move["hp_cost"] > 0:
                cost_parts.append(f"❤️ **-{move['hp_cost']} HP**")
            else:
                cost_parts.append(f"📈 **+{abs(move['hp_cost'])} HP**")
        if move["star_cost"] > 0:
            cost_parts.append(f"⭐ **-{move['star_cost']}**")

        # Add effect to status line if present (only on failed save)
        if move["save_effect"] and not save_success:
            effect_name = move["save_effect"].split(":")[0].strip()
            cost_parts.append(f"⚠️ **Effect:** {effect_name}")

        # Add remaining uses if limited
        if move["uses"] is not None and move["uses"] >= 0:
            cost_parts.append(f"🔋 **{move['uses']} Uses Left**")

        status_line = " | ".join(cost_parts) if cost_parts else ""

        # Combine lines
        if status_line:
            description = f"{result_line}\n📉 {status_line}"
        else:
            description = result_line

        embed = discord.Embed(
            title=f"✨ **{attacker_display_name} uses {move_name}**",
            description=description,
            color=color
        )

        # Effect (only on failed save) - apply to database
        if move["save_effect"] and not save_success:
            # Actually apply the effect to the database
            try:
                # Get current round for duration calculation (default to 99 if no active combat)
                async with db.execute("SELECT round_number FROM initiative WHERE id = 1") as cursor:
                    round_row = await cursor.fetchone()
                    current_round = round_row[0] if round_row else 99

                # Parse effect name and duration from save_effect (format: "effect_name" or "effect_name:duration" or "effect_name:duration:note")
                effect_parts = move["save_effect"].split(":")
                effect_name = effect_parts[0].strip().lower()
                duration_rounds = int(effect_parts[1]) if len(effect_parts) > 1 else 2  # default 2 rounds
                custom_note = effect_parts[2].strip() if len(effect_parts) > 2 else ""  # optional custom note

                # Calculate expiration round
                expiration_round = current_round + duration_rounds

                # Get preset and apply
                effect_data = get_preset_effect(effect_name, expiration_round)
                if custom_note:
                    effect_data["note"] = custom_note
                await apply_effect(target, effect_data, db=db)
                print(f"[EFFECT] Applied '{effect_name}' to {target} (expires round {expiration_round})")
            except Exception as e:
                logger.warning(f"Failed to apply save_effect '{move['save_effect']}': {e}")

        # Apply guaranteed self_effect to attacker
        if move["self_effect"]:
            try:
                async with db.execute("SELECT round_number FROM initiative WHERE id = 1") as cursor:
                    round_row = await cursor.fetchone()
                    current_round = round_row[0] if round_row else 99

                effect_parts = move["self_effect"].split(":")
                effect_name = effect_parts[0].strip().lower()
                duration_rounds = int(effect_parts[1]) if len(effect_parts) > 1 else 2
                custom_note = effect_parts[2].strip() if len(effect_parts) > 2 else ""

                expiration_round = current_round + duration_rounds
                effect_data = get_preset_effect(effect_name, expiration_round)
                if custom_note:
                    effect_data["note"] = custom_note
                await apply_effect(character, effect_data, db=db)
                print(f"[SELF_EFFECT] Applied '{effect_name}' to {character} (expires round {expiration_round})")
            except Exception as e:
                logger.warning(f"Failed to apply self_effect '{move['self_effect']}': {e}")

        # Apply guaranteed target_effect to target
        if move["target_effect"]:
            try:
                async with db.execute("SELECT round_number FROM initiative WHERE id = 1") as cursor:
                    round_row = await cursor.fetchone()
                    current_round = round_row[0] if round_row else 99

                effect_parts = move["target_effect"].split(":")
                effect_name = effect_parts[0].strip().lower()
                duration_rounds = int(effect_parts[1]) if len(effect_parts) > 1 else 2
                custom_note = effect_parts[2].strip() if len(effect_parts) > 2 else ""

                expiration_round = current_round + duration_rounds
                effect_data = get_preset_effect(effect_name, expiration_round)
                if custom_note:
                    effect_data["note"] = custom_note
                await apply_effect(target, effect_data, db=db)
                print(f"[TARGET_EFFECT] Applied '{effect_name}' to {target} (expires round {expiration_round})")
            except Exception as e:
                logger.warning(f"Failed to apply target_effect '{move['target_effect']}': {e}")

        # Delete ephemeral thinking message, send fresh visible message
        await interaction.delete_original_response()
        await interaction.channel.send(embed=embed)

    async def _execute_utility_move(
        self, interaction, db, character, move_name, move,
        current_stars, current_mp, current_hp, in_combat,
        deployable_id, attacker_display_name, current_form: str, is_deployable: bool
    ):
        """Execute a utility move"""
        # CRITICAL: Utility moves ignore bonus_on_hit - they have no attack roll or save
        # bonus_on_hit and save_effect are ONLY for attack/save moves

        # Spend resources
        # Update stars (from deployable if using deployable, else from character)
        if deployable_id:
            await db.execute(
                "UPDATE deployables SET stars = stars - ? WHERE id = ?",
                (move["star_cost"], deployable_id)
            )
        else:
            # Deduct resources (temp pools first, then permanent) - includes stars
            await deduct_resources(db, character, move["mp_cost"], move["hp_cost"], move["star_cost"])

            # Sync stars with combat_state if in combat
            if in_combat:
                async with db.execute("SELECT current_stars FROM characters WHERE name = ?", (character,)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        await db.execute(
                            "UPDATE combat_state SET stars = ? WHERE character_name = ?",
                            (row[0], character)
                        )

        # Deduct limited use if applicable
        if move["uses"] is not None and move["uses"] > 0:
            await db.execute(
                "UPDATE movesets SET uses = uses - 1 WHERE character_name = ? AND move_name = ? AND form_name = ?",
                (character, move_name, current_form)
            )
            move["uses"] -= 1  # Update local copy for embed display

        # Update cooldown if applicable (only in combat for regular characters)
        if in_combat and not is_deployable and move["cooldown"] > 0:
            # Get current round
            async with db.execute("SELECT round_number FROM initiative WHERE id = 1") as cursor:
                round_row = await cursor.fetchone()
                current_round = round_row[0] if round_row else 0

            # Get current cooldowns
            async with db.execute(
                "SELECT cooldowns_json FROM combat_state WHERE character_name = ?",
                (character,)
            ) as cursor:
                cooldown_row = await cursor.fetchone()
                cooldowns = json.loads(cooldown_row[0]) if cooldown_row and cooldown_row[0] else {}

            # Set cooldown expiration round
            cooldowns[move_name] = current_round + move["cooldown"]

            # Save updated cooldowns
            await db.execute(
                "UPDATE combat_state SET cooldowns_json = ? WHERE character_name = ?",
                (json.dumps(cooldowns), character)
            )

        await db.commit()

        # Build compact utility embed
        # Line 1: Result (utility has no damage, just show success/effect)
        if move["description"]:
            result_line = f"✅ **{move['description']}**"
        else:
            result_line = "✅ **Success**"

        # Line 2: Status/Cost (show costs or healing)
        cost_parts = []
        if move["mp_cost"] != 0:
            if move["mp_cost"] > 0:
                cost_parts.append(f"💙 **-{move['mp_cost']} MP**")
            else:
                cost_parts.append(f"📈 **+{abs(move['mp_cost'])} MP**")
        if move["hp_cost"] != 0:
            if move["hp_cost"] > 0:
                cost_parts.append(f"❤️ **-{move['hp_cost']} HP**")
            else:
                cost_parts.append(f"📈 **+{abs(move['hp_cost'])} HP**")
        if move["star_cost"] > 0:
            cost_parts.append(f"⭐ **-{move['star_cost']}**")

        # Add remaining uses if limited
        if move["uses"] is not None and move["uses"] >= 0:
            cost_parts.append(f"🔋 **{move['uses']} Uses Left**")

        status_line = " | ".join(cost_parts) if cost_parts else ""

        # Combine lines (no ➔ X Dmg for utility)
        if status_line:
            description = f"{result_line}\n📉 {status_line}"
        else:
            description = result_line

        embed = discord.Embed(
            title=f"✨ **{attacker_display_name} uses {move_name}**",
            description=description,
            color=discord.Color.purple()
        )

        # Apply guaranteed self_effect to character (utility moves have no target)
        if move["self_effect"]:
            try:
                async with db.execute("SELECT round_number FROM initiative WHERE id = 1") as cursor:
                    round_row = await cursor.fetchone()
                    current_round = round_row[0] if round_row else 99

                effect_parts = move["self_effect"].split(":")
                effect_name = effect_parts[0].strip().lower()
                duration_rounds = int(effect_parts[1]) if len(effect_parts) > 1 else 2
                custom_note = effect_parts[2].strip() if len(effect_parts) > 2 else ""

                expiration_round = current_round + duration_rounds
                effect_data = get_preset_effect(effect_name, expiration_round)
                if custom_note:
                    effect_data["note"] = custom_note
                await apply_effect(character, effect_data, db=db)
                print(f"[SELF_EFFECT] Applied '{effect_name}' to {character} (expires round {expiration_round})")
            except Exception as e:
                logger.warning(f"Failed to apply self_effect '{move['self_effect']}': {e}")

        # Delete ephemeral thinking message, send fresh visible message
        await interaction.delete_original_response()
        await interaction.channel.send(embed=embed)

    moveset_group = app_commands.Group(name="moveset", description="Moveset import/export commands")

    @moveset_group.command(name="import", description="Import moveset from text or JSON")
    @app_commands.describe(
        character="Character name",
        form="Form name (default: base)"
    )
    @app_commands.autocomplete(character=character_autocomplete, form=form_autocomplete)
    async def import_moveset(
        self,
        interaction: discord.Interaction,
        character: str,
        form: Optional[str] = "base"
    ):
        """Import moveset from pasted text or JSON"""
        print(f"[CMD] {interaction.user.name} used /moveset import | character={character}, form={form}")

        await interaction.response.send_message(
            f"📥 **Moveset Import for {character} ({form} form)**\n\n"
            f"Please paste your moveset in the next message (60s timeout).\n\n"
            f"**Text format:**\n"
            f"```\nname - type, damage, hits, properties\n```\n"
            f"**JSON format:**\n"
            f"```json\n[{{\"name\": \"move\", \"category\": \"light\", \"damage\": 5}}]\n```"
        )

        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel

        try:
            msg = await self.bot.wait_for('message', timeout=60.0, check=check)
            input_text = msg.content.strip()

            # Remove code block markers if present
            if input_text.startswith('```'):
                # Remove first and last lines
                lines = input_text.split('\n')
                input_text = '\n'.join(lines[1:-1]) if len(lines) > 2 else input_text

            from utils.moveset_parser import (
                parse_text_moveset, parse_json_moveset, validate_moveset,
                format_moveset_preview, STAR_COSTS
            )

            # Try JSON first, then text
            moves = []
            warnings = []

            if input_text.strip().startswith('[') or input_text.strip().startswith('{'):
                moves, warnings = parse_json_moveset(input_text)
            else:
                moves, warnings = parse_text_moveset(input_text)

            if not moves:
                await interaction.channel.send(
                    f"❌ No moves parsed successfully.\n\n" +
                    ("\n".join(f"⚠️ {w}" for w in warnings) if warnings else "")
                )
                return

            # Additional validation
            validation_warnings = validate_moveset(moves)
            all_warnings = warnings + validation_warnings

            # Format preview
            preview_text = format_moveset_preview(moves, character, form)

            # Build preview embed
            embed = discord.Embed(
                title="📥 Moveset Import Preview",
                description=preview_text,
                color=discord.Color.blue()
            )

            if all_warnings:
                warning_text = "\n".join(f"⚠️ {w}" for w in all_warnings[:5])
                if len(all_warnings) > 5:
                    warning_text += f"\n... and {len(all_warnings) - 5} more warnings"
                embed.add_field(name="⚠️ Warnings", value=warning_text, inline=False)

            embed.set_footer(text="React ✅ to import or ❌ to cancel")

            preview_msg = await interaction.channel.send(embed=embed)
            await preview_msg.add_reaction("✅")
            await preview_msg.add_reaction("❌")

            def reaction_check(reaction, user):
                return (
                    user == interaction.user and
                    str(reaction.emoji) in ["✅", "❌"] and
                    reaction.message.id == preview_msg.id
                )

            reaction, user = await self.bot.wait_for('reaction_add', timeout=30.0, check=reaction_check)

            if str(reaction.emoji) == "✅":
                # Import moves
                async with aiosqlite.connect('database/ronan.db') as db:
                    # Check character exists
                    async with db.execute(
                        "SELECT name FROM characters WHERE name = ?",
                        (character,)
                    ) as cursor:
                        if not await cursor.fetchone():
                            await preview_msg.edit(content="❌ Character not found!", embed=None)
                            await preview_msg.clear_reactions()
                            return

                    # Delete existing moves for this character/form before importing
                    await db.execute("""
                        DELETE FROM movesets WHERE character_name = ? AND form_name = ?
                    """, (character, form))
                    print(f"[INFO] Deleted existing moves for {character} ({form})")

                    imported = 0
                    skipped = []

                    for move in moves:
                        try:
                            # Auto-assign star cost
                            star_cost = STAR_COSTS.get(move["category"], 0)

                            # Auto .lower() move name
                            move_name_lower = move["name"].lower()

                            await db.execute("""
                                INSERT INTO movesets (
                                    character_name, form_name, move_name, category,
                                    star_cost, mp_cost, hp_cost, stat, damage, hits,
                                    targets, save_type, save_dc, save_effect,
                                    half_on_save, bonus_on_hit, description
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                character, form, move_name_lower, move["category"],
                                star_cost, move["mp_cost"], move["hp_cost"],
                                move["stat"], move["damage"], move["hits"],
                                move["targets"], move.get("save_type"), move.get("save_dc"),
                                move.get("save_effect"), move.get("half_on_save", 0),
                                move.get("bonus_on_hit"), move["description"]
                            ))

                            imported += 1

                        except aiosqlite.IntegrityError:
                            skipped.append(move["name"])

                    await db.commit()

                result_text = f"✅ Successfully imported **{imported}** moves!"

                if skipped:
                    result_text += f"\n⚠️ Skipped {len(skipped)} duplicates: {', '.join(skipped)}"

                await preview_msg.edit(content=result_text, embed=None)
                await preview_msg.clear_reactions()

                print(f"[OK] Imported {imported} moves for {character} ({form})")

            else:
                await preview_msg.edit(content="❌ Import cancelled", embed=None)
                await preview_msg.clear_reactions()

        except TimeoutError:
            await interaction.channel.send("❌ Timed out waiting for input or confirmation")

        except Exception as e:
            logger.error(f"Error importing moveset: {e}", exc_info=True)
            await interaction.channel.send(f"❌ Error: {str(e)}")

    @moveset_group.command(name="export", description="Export moveset to JSON")
    @app_commands.describe(
        character="Character name",
        form="Form name (default: current form)"
    )
    @app_commands.autocomplete(character=character_autocomplete, form=form_autocomplete)
    async def export_moveset(
        self,
        interaction: discord.Interaction,
        character: str,
        form: Optional[str] = None
    ):
        """Export moveset to JSON"""
        print(f"[CMD] {interaction.user.name} used /moveset export | character={character}, form={form}")
        try:
            async with aiosqlite.connect('database/ronan.db') as db:
                # Get form if not specified
                if not form:
                    async with db.execute(
                        "SELECT current_form FROM characters WHERE name = ?",
                        (character,)
                    ) as cursor:
                        row = await cursor.fetchone()
                        if not row:
                            print(f"[ERROR] Character '{character}' not found")
                            await interaction.response.send_message(
                                f"❌ Character '{character}' not found!",
                                ephemeral=True
                            )
                            return
                        form = row[0]

                # Get moves
                async with db.execute("""
                    SELECT move_name, category, mp_cost, hp_cost, stat, damage,
                           hits, targets, save_type, save_dc, save_effect,
                           half_on_save, bonus_on_hit, description
                    FROM movesets
                    WHERE character_name = ? AND form_name = ?
                    ORDER BY category, move_name
                """, (character, form)) as cursor:
                    rows = await cursor.fetchall()

            if not rows:
                print(f"[ERROR] No moves found for {character} ({form} form)")
                await interaction.response.send_message(
                    f"❌ No moves found for {character} ({form} form)!",
                    ephemeral=True
                )
                return

            # Build move dicts
            moves = []
            for row in rows:
                move = {
                    "name": row[0],
                    "category": row[1],
                    "stat": row[4],
                    "damage": row[5],
                }

                # Add optional fields only if non-zero/non-empty
                if row[2] > 0:  # mp_cost
                    move["mp_cost"] = row[2]
                if row[3] > 0:  # hp_cost
                    move["hp_cost"] = row[3]
                if row[6] > 1:  # hits
                    move["hits"] = row[6]
                if row[7] != 1:  # targets
                    move["targets"] = row[7]
                if row[8]:  # save_type
                    move["save_type"] = row[8]
                if row[9]:  # save_dc
                    move["save_dc"] = row[9]
                if row[10]:  # save_effect
                    move["save_effect"] = row[10]
                if row[11]:  # half_on_save
                    move["half_on_save"] = row[11]
                if row[12]:  # bonus_on_hit
                    move["bonus_on_hit"] = row[12]
                if row[13]:  # description
                    move["description"] = row[13]

                moves.append(move)

            from utils.moveset_parser import export_moveset_json

            json_output = export_moveset_json(moves)

            # Send as file if too long, otherwise as code block
            if len(json_output) > 1800:
                import io
                file = discord.File(
                    io.BytesIO(json_output.encode()),
                    filename=f"{character}_{form}_moveset.json"
                )

                await interaction.response.send_message(
                    f"📤 Exported {len(moves)} moves for **{character}** ({form} form)",
                    file=file
                )
            else:
                await interaction.response.send_message(
                    f"📤 Exported {len(moves)} moves for **{character}** ({form} form):\n\n```json\n{json_output}\n```"
                )

            print(f"[OK] Exported {len(moves)} moves for {character} ({form})")

        except Exception as e:
            logger.error(f"Error exporting moveset: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    @moveset_group.command(name="clear", description="Delete all moves for a form")
    @app_commands.describe(
        character="Character name",
        form="Form name (default: base)"
    )
    @app_commands.autocomplete(character=character_autocomplete, form=form_autocomplete)
    async def clear_moveset(
        self,
        interaction: discord.Interaction,
        character: str,
        form: Optional[str] = "base"
    ):
        """Clear all moves for a character/form"""
        print(f"[CMD] {interaction.user.name} used /moveset clear | character={character}, form={form}")
        try:
            async with aiosqlite.connect('database/ronan.db') as db:
                # Count moves
                async with db.execute("""
                    SELECT COUNT(*) FROM movesets
                    WHERE character_name = ? AND form_name = ?
                """, (character, form)) as cursor:
                    count = (await cursor.fetchone())[0]

            if count == 0:
                print(f"[ERROR] No moves to clear for {character} ({form} form)")
                await interaction.response.send_message(
                    f"❌ No moves to clear for {character} ({form} form)!",
                    ephemeral=True
                )
                return

            # Send confirmation
            await interaction.response.send_message(
                f"⚠️ Delete **{count}** moves for **{character}** ({form} form)?\n"
                f"React ✅ to confirm or ❌ to cancel."
            )

            msg = await interaction.original_response()
            await msg.add_reaction("✅")
            await msg.add_reaction("❌")

            def check(reaction, user):
                return (
                    user == interaction.user and
                    str(reaction.emoji) in ["✅", "❌"] and
                    reaction.message.id == msg.id
                )

            reaction, user = await self.bot.wait_for('reaction_add', timeout=30.0, check=check)

            if str(reaction.emoji) == "✅":
                async with aiosqlite.connect('database/ronan.db') as db:
                    await db.execute("""
                        DELETE FROM movesets
                        WHERE character_name = ? AND form_name = ?
                    """, (character, form))
                    await db.commit()

                await msg.edit(content=f"✅ Deleted {count} moves for **{character}** ({form} form)")
                await msg.clear_reactions()

                print(f"[OK] Cleared {count} moves for {character} ({form})")

            else:
                await msg.edit(content="❌ Clear cancelled")
                await msg.clear_reactions()

        except TimeoutError:
            await msg.edit(content="❌ Timed out")
            await msg.clear_reactions()

        except Exception as e:
            logger.error(f"Error clearing moveset: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(MoveCommands(bot))
