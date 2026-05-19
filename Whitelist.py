import discord
from discord import app_commands
from discord.ext import commands
import os
import secrets
import time

from Database import db_execute, db_fetchone, db_fetchall
from Helpers import *

DEFAULT_SCRIPT = "OkveHUB"


def make_loader(key_code: str):
    base_url = os.getenv("BASE_URL", "https://name-production-e582.up.railway.app").rstrip("/")
    return f'''local script_key = "{key_code}"
local hwid = game:GetService("RbxAnalyticsService"):GetClientId()
local executor = identifyexecutor and identifyexecutor() or "Unknown"

loadstring(game:HttpGet("{base_url}/load?key=" .. script_key .. "&hwid=" .. hwid .. "&executor=" .. executor))()'''


async def give_roles(member: discord.Member):
    for role_id in [os.getenv("ROLE_WHITELIST"), os.getenv("ROLE_ACHETEUR")]:
        if role_id:
            role = member.guild.get_role(int(role_id))
            if role:
                try:
                    await member.add_roles(role)
                except:
                    pass


async def remove_roles(member: discord.Member):
    for role_id in [os.getenv("ROLE_WHITELIST"), os.getenv("ROLE_ACHETEUR")]:
        if role_id:
            role = member.guild.get_role(int(role_id))
            if role:
                try:
                    await member.remove_roles(role)
                except:
                    pass


class RedeemModal(discord.ui.Modal, title="Redeem Key"):
    key_code = discord.ui.TextInput(label="Enter your key", placeholder="OKV-XXXXXXXX", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        key = self.key_code.value.strip().upper()

        blacklist = await db_fetchone("SELECT * FROM blacklist WHERE user_id=?", (user_id,))
        if blacklist:
            return await interaction.response.send_message(embed=error_embed("Blacklisted", "You are blacklisted."), ephemeral=True)

        row = await db_fetchone("SELECT * FROM keys WHERE key_code=?", (key,))
        if not row:
            return await interaction.response.send_message(embed=error_embed("Invalid Key", "This key does not exist."), ephemeral=True)

        if row["status"] != "active":
            return await interaction.response.send_message(embed=error_embed("Key Disabled", "This key is disabled."), ephemeral=True)

        if row["expires_at"] and row["expires_at"] < int(time.time()):
            return await interaction.response.send_message(embed=error_embed("Key Expired", "This key has expired."), ephemeral=True)

        if row["used_by"] and row["used_by"] != user_id:
            return await interaction.response.send_message(embed=error_embed("Key Used", "This key is already linked."), ephemeral=True)

        script_name = row["script_name"] or DEFAULT_SCRIPT
        script_version = row["script_version"] or "stable"

        await db_execute("""
        INSERT INTO whitelist (user_id, username, added_by, reason, script_access, expires_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username=excluded.username,
            reason=excluded.reason,
            script_access=excluded.script_access,
            expires_at=excluded.expires_at
        """, (user_id, str(interaction.user), "redeem_key", f"Redeemed {key}", script_name, row["expires_at"]))

        await db_execute(
            "UPDATE keys SET used_by=?, used_at=strftime('%s','now') WHERE key_code=?",
            (user_id, key)
        )

        await give_roles(interaction.user)

        await interaction.response.send_message(
            embed=success_embed(
                "Redeemed",
                f"Access granted ✅\n\nScript: `{script_name}`\nVersion: `{script_version}`\n\n```lua\n{make_loader(key)}\n```"
            ),
            ephemeral=True
        )


class WhitelistPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔑 Redeem Key", style=discord.ButtonStyle.success, custom_id="okvehub_redeem_version")
    async def redeem_key(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RedeemModal())

    @discord.ui.button(label="📜 Get Script", style=discord.ButtonStyle.primary, custom_id="okvehub_get_script_version")
    async def get_script(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)

        wl = await db_fetchone("SELECT * FROM whitelist WHERE user_id=?", (user_id,))
        if not wl:
            return await interaction.response.send_message(embed=error_embed("Access Denied", "You are not whitelisted."), ephemeral=True)

        key = await db_fetchone("SELECT * FROM keys WHERE used_by=? ORDER BY used_at DESC LIMIT 1", (user_id,))
        if not key:
            return await interaction.response.send_message(embed=error_embed("No Key", "No key linked."), ephemeral=True)

        await interaction.response.send_message(
            f"📜 **Your OkveHUB loader:**\n```lua\n{make_loader(key['key_code'])}\n```",
            ephemeral=True
        )

    @discord.ui.button(label="👤 Get Role", style=discord.ButtonStyle.primary, custom_id="okvehub_get_role_version")
    async def get_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        wl = await db_fetchone("SELECT * FROM whitelist WHERE user_id=?", (str(interaction.user.id),))
        if not wl:
            return await interaction.response.send_message(embed=error_embed("Access Denied", "You are not whitelisted."), ephemeral=True)

        await give_roles(interaction.user)
        await interaction.response.send_message(embed=success_embed("Roles Given", "Roles added."), ephemeral=True)

    @discord.ui.button(label="⚙️ Reset HWID", style=discord.ButtonStyle.secondary, custom_id="okvehub_reset_hwid_version")
    async def reset_hwid(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        wl = await db_fetchone("SELECT * FROM whitelist WHERE user_id=?", (user_id,))
        if not wl:
            return await interaction.response.send_message(embed=error_embed("Access Denied", "You are not whitelisted."), ephemeral=True)

        old_hwid = wl["hwid"]
        await db_execute("UPDATE whitelist SET hwid=NULL WHERE user_id=?", (user_id,))
        await db_execute(
            "INSERT INTO hwid_resets (user_id, old_hwid, new_hwid, reset_by) VALUES (?, ?, ?, ?)",
            (user_id, old_hwid, None, user_id)
        )

        await interaction.response.send_message(embed=success_embed("HWID Reset", "Your HWID has been reset."), ephemeral=True)

    @discord.ui.button(label="📊 Get Stats", style=discord.ButtonStyle.secondary, custom_id="okvehub_stats_version")
    async def get_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)

        wl = await db_fetchone("SELECT * FROM whitelist WHERE user_id=?", (user_id,))
        if not wl:
            return await interaction.response.send_message(embed=error_embed("Access Denied", "You are not whitelisted."), ephemeral=True)

        key = await db_fetchone("SELECT * FROM keys WHERE used_by=? ORDER BY used_at DESC LIMIT 1", (user_id,))
        executions = await db_fetchall("SELECT * FROM execution_logs WHERE user_id=?", (user_id,))
        resets = await db_fetchall("SELECT * FROM hwid_resets WHERE user_id=?", (user_id,))

        embed = discord.Embed(title="📊 OkveHUB Stats", color=0xF1C40F)
        embed.description = (
            f"**Executions:** `{len(executions)}`\n"
            f"**Script:** `{wl['script_access']}`\n"
            f"**Version:** `{key['script_version'] if key else 'stable'}`\n"
            f"**HWID:** {'Assigned ✅' if wl['hwid'] else 'Not assigned ❌'}\n"
            f"**HWID Resets:** `{len(resets)}`\n"
            f"**Key:** ||{key['key_code'] if key else 'No key'}||"
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


class Whitelist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="whitelist-panel", description="Créer le panel whitelist")
    async def whitelist_panel(self, interaction: discord.Interaction):
        if not await check_permission(interaction, "admin"):
            return

        embed = discord.Embed(
            title="OkveHUB",
            description="Redeem your key, get your script, get your role or reset HWID.",
            color=0xF1C40F
        )

        await interaction.channel.send(embed=embed, view=WhitelistPanel())
        await interaction.response.send_message("✅ Panel envoyé.", ephemeral=True)

    @app_commands.command(name="wl-add", description="Ajouter un utilisateur à la whitelist")
    async def wl_add(
        self,
        interaction: discord.Interaction,
        utilisateur: discord.Member,
        script: str = DEFAULT_SCRIPT,
        version: str = "stable",
        jours: int = 0
    ):
        if not await check_permission(interaction, "staff"):
            return

        key_code = "OKV-" + secrets.token_hex(8).upper()
        expires_at = None if jours <= 0 else int(time.time()) + (jours * 86400)

        await db_execute("""
        INSERT INTO keys (key_code, script_name, script_version, used_by, used_at, expires_at, status)
        VALUES (?, ?, ?, ?, strftime('%s','now'), ?, 'active')
        """, (key_code, script, version, str(utilisateur.id), expires_at))

        await db_execute("""
        INSERT INTO whitelist (user_id, username, added_by, reason, script_access, expires_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username=excluded.username,
            added_by=excluded.added_by,
            reason=excluded.reason,
            script_access=excluded.script_access,
            expires_at=excluded.expires_at
        """, (str(utilisateur.id), str(utilisateur), str(interaction.user.id), "Manual whitelist", script, expires_at))

        await give_roles(utilisateur)

        try:
            await utilisateur.send(
                embed=success_embed(
                    "OkveHUB Access",
                    f"Access granted ✅\n\nScript: `{script}`\nVersion: `{version}`\nKey: `{key_code}`\n\n```lua\n{make_loader(key_code)}\n```"
                )
            )
            dm_status = "DM envoyé ✅"
        except:
            dm_status = "DM fermé ❌"

        await interaction.response.send_message(
            embed=success_embed("Whitelist ajoutée", f"{utilisateur.mention} ajouté.\nKey: `{key_code}`\nVersion: `{version}`\n{dm_status}"),
            ephemeral=True
        )

    @app_commands.command(name="wl-remove", description="Retirer un utilisateur de la whitelist")
    async def wl_remove(self, interaction: discord.Interaction, utilisateur: discord.Member):
        if not await check_permission(interaction, "staff"):
            return

        await db_execute("DELETE FROM whitelist WHERE user_id=?", (str(utilisateur.id),))
        await db_execute("DELETE FROM keys WHERE used_by=?", (str(utilisateur.id),))
        await remove_roles(utilisateur)

        await interaction.response.send_message(
            embed=success_embed("Whitelist retirée", f"{utilisateur.mention} retiré + key supprimée."),
            ephemeral=True
        )

    @app_commands.command(name="wl-check", description="Vérifier la whitelist")
    async def wl_check(self, interaction: discord.Interaction, utilisateur: discord.Member = None):
        target = utilisateur or interaction.user

        row = await db_fetchone("SELECT * FROM whitelist WHERE user_id=?", (str(target.id),))
        if not row:
            return await interaction.response.send_message(embed=error_embed("Non whitelist", f"{target.mention} n'est pas whitelist."), ephemeral=True)

        key = await db_fetchone("SELECT * FROM keys WHERE used_by=? ORDER BY used_at DESC LIMIT 1", (str(target.id),))

        embed = discord.Embed(title="Whitelist Check", color=COLOR_WL)
        embed.add_field(name="User", value=target.mention)
        embed.add_field(name="Script", value=row["script_access"] or DEFAULT_SCRIPT)
        embed.add_field(name="Version", value=key["script_version"] if key else "stable")
        embed.add_field(name="Key", value=f"||{key['key_code'] if key else 'No key'}||", inline=False)
        embed.add_field(name="HWID", value=row["hwid"] or "Not assigned", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="wl-list", description="Voir la liste whitelist")
    async def wl_list(self, interaction: discord.Interaction):
        if not await check_permission(interaction, "staff"):
            return

        rows = await db_fetchall("SELECT * FROM whitelist ORDER BY created_at DESC")
        if not rows:
            return await interaction.response.send_message("Whitelist vide.", ephemeral=True)

        lines = [f"`{i}.` <@{r['user_id']}> — `{r['script_access']}`" for i, r in enumerate(rows[:20], 1)]
        await interaction.response.send_message(embed=discord.Embed(title="Whitelist", description="\n".join(lines), color=COLOR_WL), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Whitelist(bot))
