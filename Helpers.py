import discord
import os
import time
import random
import string
from datetime import datetime, timezone

# ══════════════════════════════════
#     COULEURS
# ══════════════════════════════════
COLOR_SUCCESS = 0x2ecc71
COLOR_ERROR   = 0xe74c3c
COLOR_WARNING = 0xf39c12
COLOR_INFO    = 0x3498db
COLOR_MAIN    = 0x7289da
COLOR_GOLD    = 0xf1c40f
COLOR_WL      = 0x9b59b6
COLOR_TICKET  = 0x1abc9c
COLOR_VENTE   = 0xe67e22

# ══════════════════════════════════
#     EMBEDS
# ══════════════════════════════════
def success_embed(title, description=None, fields=None):
    e = discord.Embed(title=f"✅ {title}", color=COLOR_SUCCESS, timestamp=datetime.now(timezone.utc))
    if description: e.description = description
    if fields:
        for f in fields: e.add_field(name=f[0], value=f[1], inline=f[2] if len(f) > 2 else True)
    return e

def error_embed(title, description):
    return discord.Embed(title=f"❌ {title}", description=description, color=COLOR_ERROR, timestamp=datetime.now(timezone.utc))

def warn_embed(title, description):
    return discord.Embed(title=f"⚠️ {title}", description=description, color=COLOR_WARNING, timestamp=datetime.now(timezone.utc))

def info_embed(title, description=None, fields=None):
    e = discord.Embed(title=f"ℹ️ {title}", color=COLOR_INFO, timestamp=datetime.now(timezone.utc))
    if description: e.description = description
    if fields:
        for f in fields: e.add_field(name=f[0], value=f[1], inline=f[2] if len(f) > 2 else True)
    return e

def main_embed(title, description=None, color=None, fields=None):
    e = discord.Embed(title=title, color=color or COLOR_MAIN, timestamp=datetime.now(timezone.utc))
    if description: e.description = description
    if fields:
        for f in fields: e.add_field(name=f[0], value=f[1], inline=f[2] if len(f) > 2 else True)
    return e

# ══════════════════════════════════
#     PERMISSIONS
# ══════════════════════════════════
def is_owner(member: discord.Member) -> bool:
    role_id = os.getenv("ROLE_OWNER")
    return (role_id and discord.utils.get(member.roles, id=int(role_id)) is not None) or member.guild_permissions.administrator

def is_admin(member: discord.Member) -> bool:
    role_id = os.getenv("ROLE_ADMIN")
    return is_owner(member) or (role_id and discord.utils.get(member.roles, id=int(role_id)) is not None)

def is_moderator(member: discord.Member) -> bool:
    role_id = os.getenv("ROLE_MODERATEUR")
    return is_admin(member) or (role_id and discord.utils.get(member.roles, id=int(role_id)) is not None)

def is_staff(member: discord.Member) -> bool:
    role_id = os.getenv("ROLE_STAFF")
    return is_moderator(member) or (role_id and discord.utils.get(member.roles, id=int(role_id)) is not None)

async def check_permission(interaction: discord.Interaction, level: str = "staff") -> bool:
    checks = {"owner": is_owner, "admin": is_admin, "moderator": is_moderator, "staff": is_staff}
    fn = checks.get(level, is_staff)
    if not fn(interaction.user):
        await interaction.response.send_message(embed=error_embed("Permissions insuffisantes", f"Tu as besoin du niveau **{level}** pour utiliser cette commande."), ephemeral=True)
        return False
    return True

# ══════════════════════════════════
#     DURÉE
# ══════════════════════════════════
def parse_duration(s: str):
    if not s: return None
    units = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400, 'w': 604800}
    if len(s) >= 2 and s[:-1].isdigit() and s[-1] in units:
        return int(s[:-1]) * units[s[-1]]
    return None

def format_duration(seconds: int) -> str:
    if not seconds: return "Permanent"
    parts = []
    for unit, val in [("j", 86400), ("h", 3600), ("m", 60), ("s", 1)]:
        if seconds >= val:
            parts.append(f"{seconds // val}{unit}")
            seconds %= val
    return " ".join(parts) or "0s"

def ts(timestamp) -> str:
    return f"<t:{int(timestamp)}:F>"

def ts_rel(timestamp) -> str:
    return f"<t:{int(timestamp)}:R>"

# ══════════════════════════════════
#     UTILS
# ══════════════════════════════════
def generate_id(prefix="OKV") -> str:
    chars = string.ascii_uppercase + string.digits
    return f"{prefix}-{''.join(random.choices(chars, k=8))}"

def now_ts() -> int:
    return int(time.time())

async def send_log(bot, channel_env: str, embed: discord.Embed):
    try:
        ch_id = os.getenv(channel_env)
        if not ch_id: return
        ch = bot.get_channel(int(ch_id))
        if ch: await ch.send(embed=embed)
    except Exception:
        pass
