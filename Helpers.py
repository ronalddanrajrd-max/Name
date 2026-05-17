import discord
import time
import re
import math
import os


# ===== COULEURS =====
class Colors:
    MAIN    = 0x5865F2
    SUCCESS = 0x57F287
    ERROR   = 0xED4245
    WARNING = 0xFEE75C
    INFO    = 0x00B0F4
    PURPLE  = 0x9B59B6
    GOLD    = 0xF1C40F
    ORANGE  = 0xE67E22


# ===== EMBEDS RAPIDES =====
def embed_success(description: str, title: str = "✅ Succès") -> discord.Embed:
    return discord.Embed(title=title, description=description, color=Colors.SUCCESS)

def embed_error(description: str, title: str = "❌ Erreur") -> discord.Embed:
    return discord.Embed(title=title, description=description, color=Colors.ERROR)

def embed_warning(description: str, title: str = "⚠️ Attention") -> discord.Embed:
    return discord.Embed(title=title, description=description, color=Colors.WARNING)

def embed_info(description: str, title: str = "ℹ️ Information") -> discord.Embed:
    return discord.Embed(title=title, description=description, color=Colors.INFO)

def embed_main(description: str = None, title: str = None) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=Colors.MAIN)


# ===== PERMISSIONS =====
def is_admin(member: discord.Member) -> bool:
    return (
        member.guild_permissions.administrator
        or str(member.id) == str(os.getenv("ROLE_ADMIN", ""))
        or any(str(r.id) == str(os.getenv("ROLE_ADMIN", "")) for r in member.roles)
    )

def is_mod(member: discord.Member) -> bool:
    return (
        is_admin(member)
        or member.guild_permissions.moderate_members
        or any(str(r.id) in [
            str(os.getenv("ROLE_MODERATEUR", "")),
            str(os.getenv("ROLE_STAFF", "")),
        ] for r in member.roles)
    )

def is_staff(member: discord.Member) -> bool:
    return is_mod(member) or any(str(r.id) == str(os.getenv("ROLE_STAFF", "")) for r in member.roles)


# ===== XP / NIVEAUX =====
def calculate_level(xp: int) -> int:
    return int(0.1 * math.sqrt(xp))

def xp_for_level(level: int) -> int:
    return int((level / 0.1) ** 2)


# ===== DURÉE =====
def parse_duration(s: str) -> int:
    """Parse '1h30m' en secondes. Retourne 0 si invalide."""
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800, "y": 31536000}
    total = 0
    for match in re.finditer(r"(\d+)([smhdwy])", s.lower()):
        total += int(match.group(1)) * units.get(match.group(2), 0)
    return total

def format_duration(seconds: int) -> str:
    if seconds <= 0:
        return "0s"
    parts = []
    for unit, val in [("j", 86400), ("h", 3600), ("m", 60), ("s", 1)]:
        if seconds >= val:
            parts.append(f"{seconds // val}{unit}")
            seconds %= val
    return " ".join(parts[:2])


# ===== TIMESTAMP DISCORD =====
def dt(ts, fmt="R") -> str:
    """Retourne un timestamp Discord <t:unix:format>"""
    if isinstance(ts, (int, float)):
        unix = int(ts / 1000) if ts > 9999999999 else int(ts)
    else:
        unix = int(ts.timestamp())
    return f"<t:{unix}:{fmt}>"


# ===== PAGINATION =====
def paginate(lst: list, per_page: int, page: int) -> list:
    return lst[page * per_page: (page + 1) * per_page]


# ===== BARRE DE PROGRESSION =====
def progress_bar(pct: float, length: int = 20) -> str:
    filled = round((pct / 100) * length)
    return "█" * filled + "░" * (length - filled)


# ===== TRUNCATE =====
def truncate(text: str, max_len: int = 1024) -> str:
    return text if len(text) <= max_len else text[:max_len - 3] + "..."
