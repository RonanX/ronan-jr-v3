"""
Constants for consistent formatting across the bot
"""

import discord

# Embed colors
class EmbedColors:
    SUCCESS = discord.Color.green()      # Successful actions
    ERROR = discord.Color.red()          # Errors
    INFO = discord.Color.blue()          # Informational
    WARNING = discord.Color.orange()     # Warnings
    COMBAT = discord.Color.red()         # Combat-related
    CHARACTER = discord.Color.purple()   # Character management
    TURN = discord.Color.gold()          # Turn announcements
    DAMAGE = discord.Color.dark_red()    # Damage dealt
    HEAL = discord.Color.green()         # Healing
    SAVE = discord.Color.dark_green()    # Save/Load

# Emoji constants (for consistent usage)
class Emoji:
    SUCCESS = "✅"
    ERROR = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    COMBAT = "⚔️"
    HP = "❤️"
    MP = "💙"
    STARS = "⭐"
    EFFECT = "🔮"
    DEPLOYABLE = "🔧"
    SAVE = "💾"
    LOAD = "📂"
    DELETE = "🗑️"
    TURN = "🎯"
    DICE = "🎲"
    SHIELD = "🛡️"
    EXPIRED = "💨"

# Default timeouts
class Timeouts:
    CONFIRMATION = 30.0
    USER_INPUT = 60.0
    DAMAGE_INPUT = 30.0

# Max values for validation
class Limits:
    MAX_STAT_RATING = 4
    MIN_STAT_RATING = 0
    MIN_STAT_TOTAL = 12
    MAX_STAT_TOTAL = 16
    MAX_STARS = 5
    MAX_NAME_LENGTH = 50
    MAX_EFFECT_NAME_LENGTH = 50
    MAX_MOVE_NAME_LENGTH = 50
