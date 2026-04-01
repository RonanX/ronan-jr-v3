"""
Autocomplete functions for Discord commands.
Centralized to avoid code duplication.
"""

import discord
from discord import app_commands
import aiosqlite
import logging

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
        return choices[:25]  # Discord limit
    except Exception as e:
        logger.error(f"Character autocomplete failed: {e}")
        return []


async def character_and_deployable_autocomplete(
    interaction: discord.Interaction,
    current: str
) -> list[app_commands.Choice[str]]:
    """Autocomplete for character and deployable names"""
    try:
        async with aiosqlite.connect('database/ronan.db') as db:
            # Get characters
            async with db.execute('SELECT name FROM characters') as cursor:
                characters = await cursor.fetchall()

            # Get deployables
            async with db.execute('SELECT deployable_name FROM deployables') as cursor:
                deployables = await cursor.fetchall()

        # Combine and filter by what user is typing
        all_names = [(char[0], "char") for char in characters] + [(dep[0], "dep") for dep in deployables]
        choices = [
            app_commands.Choice(name=name, value=name)
            for name, entity_type in all_names
            if current.lower() in name.lower()
        ]
        return choices[:25]  # Discord limit
    except Exception as e:
        logger.error(f"Autocomplete failed: {e}")
        return []


async def deployable_autocomplete(
    interaction: discord.Interaction,
    current: str
) -> list[app_commands.Choice[str]]:
    """Autocomplete for deployable names only"""
    try:
        async with aiosqlite.connect('database/ronan.db') as db:
            async with db.execute('SELECT deployable_name FROM deployables') as cursor:
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
