"""
Ronan Jr v3 - Discord RPG Bot
Simplified rewrite focusing on clean architecture and maintainability.
"""

import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import asyncio
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

if not TOKEN:
    logger.error("DISCORD_TOKEN not found in .env file!")
    exit(1)

# Bot setup
class RonanBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.messages = True

        super().__init__(
            command_prefix='!',  # Fallback prefix (we'll use slash commands)
            intents=intents,
            allowed_mentions=discord.AllowedMentions(
                roles=False,
                users=False,
                everyone=False
            )
        )

    async def setup_hook(self):
        """Called when the bot is starting up"""
        # Load cogs
        cogs_to_load = [
            'cogs.character',
            'cogs.combat',
            'cogs.moves',
            'cogs.deployables',
            'cogs.forms',
            'cogs.help',
            'cogs.misc'
        ]

        for cog in cogs_to_load:
            try:
                await self.load_extension(cog)
                print(f"[OK] Loaded {cog}")
            except Exception as e:
                print(f"[ERROR] Failed to load {cog}: {e}")
                logger.error(f"Failed to load {cog}: {e}", exc_info=True)

        # Sync commands (optional - can be done manually)
        # await self.tree.sync()

    async def on_ready(self):
        """Called when the bot is ready"""
        logger.info(f'Logged in as {self.user} (ID: {self.user.id})')
        logger.info(f'{self.user}: ok i pull up (v3 edition)')
        logger.info(f'Ready to process commands!')

        # Clear combat_active flag on startup
        import aiosqlite
        try:
            async with aiosqlite.connect('database/ronan.db') as db:
                await db.execute("UPDATE initiative SET combat_active = 0 WHERE id = 1")
                await db.commit()
            logger.info("Cleared combat_active flag on startup")
        except Exception as e:
            logger.error(f"Failed to clear combat_active flag: {e}", exc_info=True)

# Create and run bot
bot = RonanBot()

@bot.command()
@commands.is_owner()
async def sync(ctx):
    """Manually sync slash commands to Discord"""
    await bot.tree.sync()
    await ctx.send("✅ Slash commands synced!")

if __name__ == "__main__":
    bot.run(TOKEN)
