import discord
import os
from utils.helpers import Colors

_bot = None

def set_bot(bot):
    global _bot
    _bot = bot

LOG_COLORS = {
    "BAN": Colors.ERROR, "UNBAN": Colors.SUCCESS, "KICK": Colors.ERROR,
    "MUTE": Colors.WARNING, "UNMUTE": Colors.SUCCESS, "WARN": Colors.WARNING,
    "JOIN": Colors.SUCCESS, "LEAVE": Colors.ERROR, "MESSAGE_DELETE": Colors.WARNING,
    "MESSAGE_EDIT": Colors.INFO, "WHITELIST_ADD": Colors.SUCCESS,
    "WHITELIST_REMOVE": Colors.ERROR, "TICKET_OPEN": Colors.MAIN,
    "TICKET_CLOSE": Colors.PURPLE, "GIVEAWAY": Colors.GOLD, "NOTE": Colors.INFO,
    "PURGE": Colors.WARNING, "LOCK": Colors.WARNING, "UNLOCK": Colors.SUCCESS,
}

LOG_ICONS = {
    "BAN": "🔨", "UNBAN": "✅", "KICK": "👢", "MUTE": "🔇", "UNMUTE": "🔊",
    "WARN": "⚠️", "JOIN": "📥", "LEAVE": "📤", "MESSAGE_DELETE": "🗑️",
    "MESSAGE_EDIT": "✏️", "WHITELIST_ADD": "✅", "WHITELIST_REMOVE": "❌",
    "TICKET_OPEN": "🎫", "TICKET_CLOSE": "🔒", "GIVEAWAY": "🎉",
    "NOTE": "📝", "PURGE": "🧹", "LOCK": "🔒", "UNLOCK": "🔓",
}

async def send_log(log_type: str, fields: list = None, description: str = None,
                   thumbnail: str = None, channel_id: str = None):
    if not _bot:
        return
    cid = channel_id or os.getenv("CHANNEL_LOGS")
    if not cid:
        return
    channel = _bot.get_channel(int(cid))
    if not channel:
        return

    icon = LOG_ICONS.get(log_type, "📋")
    color = LOG_COLORS.get(log_type, Colors.MAIN)

    embed = discord.Embed(
        title=f"{icon} {log_type.replace('_', ' ')}",
        description=description,
        color=color
    )
    embed.set_footer(text="OkveHUB Logs")
    import datetime
    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)

    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
    if fields:
        for f in fields:
            embed.add_field(
                name=f.get("name", ""),
                value=f.get("value", ""),
                inline=f.get("inline", False)
            )
    try:
        await channel.send(embed=embed)
    except Exception:
        pass

async def send_mod_log(log_type: str, **kwargs):
    cid = os.getenv("CHANNEL_MOD_LOGS") or os.getenv("CHANNEL_LOGS")
    await send_log(log_type, channel_id=cid, **kwargs)
