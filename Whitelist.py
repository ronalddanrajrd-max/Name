import discord
from discord import app_commands
from discord.ext import commands
import os
import secrets
import time

from Database import db_execute, db_fetchone, db_fetchall
from Helpers import *


def make_loader(key_code: str):
    base_url = os.getenv("BASE_URL", "https://name-production-e582.up.railway.app").rstrip("/")
    return f'''local script_key = "{key_code}"
local hwid = game:GetService("RbxAnalyticsService"):GetClientId()
local executor = identifyexecutor and identifyexecutor() or "Unknown"

loadstring(game:HttpGet("{base_url}/load?key=" .. script_key .. "&hwid=" .. hwid .. "&executor=" .. executor))()'''


async def send_wl_log(guild, title, description, color=0x3498DB):
    log_id = os.getenv("LOG_WHITELIST")
    if not log_id or not guild:
        return

    channel = guild.get_channel(int(log_id))
    if not channel:
        return

    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_footer(text="OkveHUB Whitelist Logs")

    try:
        await channel.send(embed=embed)
    except:
        pass


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
    key_code = discord.ui.TextInput(
        label="Enter your key",
        placeholder="OKV-XXXXXXXX",
        required=True,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        key = self.key_code.value.strip().upper()
        user_id = str(interaction.user.id)

        blacklist = await db_fetchone("SELECT * FROM blacklist WHERE user_id=?", (user_id,))
        if blacklist:
            return await interaction.response.send_message(
                embed=error_embed("Blacklisted", "You are blacklisted from OkveHUB."),
                ephemeral=True
            )

        row = await db_fetchone("SELECT * FROM keys WHERE key_code=?", (key,))
        if not row:
            return await interaction.response.send_message(
                embed=error_embed("Invalid Key", "This key does not exist."),
                ephemeral=True
            )

        if row["status"] != "active":
            return await interaction.response.send_message(
                embed=error_embed("Key Disabled", "This key is disabled."),
                ephemeral=True
            )

        if row["expires_at"] and row["expires_at"] < int(time.time()):
            return await interaction.response.send_message(
                embed=error_embed("Key Expired", "This key has expired."),
                ephemeral=True
            )

        if row["used_by"] and row["used_by"] != user_id:
            return await interaction.response.send_message(
                embed=error_embed("Key Already Used", "This key is already linked to another user."),
                ephemeral=True
            )

        script_name = row["script_name"] or "OkveHUB"

        await db_execute("""
        INSERT INTO whitelist (user_id, username, added_by, reason, script_access, expires_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username=excluded.username,
            reason=excluded.reason,
            script_access=excluded.script_access,
            expires_at=excluded.expires_at
        """, (
            user_id,
            str(interaction.user),
            "redeem_key",
            f"Redeemed {key}",
            script_name,
            row["expires_at"]
        ))

        await db_execute(
            "UPDATE keys SET used_by=?, used_at=strftime('%s','now') WHERE key_code=?",
            (user_id, key)
        )

        await give_roles(interaction.user)

        loader = make_loader(key)

        await send_wl_log(
            interaction.guild,
            "🔑 Key Redeemed",
            f"User: {interaction.user.mention}\nKey: ||{key}||\nScript: `{script_name}`",
            0xF1C40F
        )

        await interaction.response.send_message(
            embed=success_embed(
                "Redeemed",
                f"You now have access to **{script_name}** ✅\n\n```lua\n{loader}\n```"
            ),
            ephemeral=True
        )


class WhitelistPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔑 Redeem Key", style=discord.ButtonStyle.success, custom_id="okvehub_redeem_secure_v1")
    async def redeem_key(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RedeemModal())

    @discord.ui.button(label="📜 Get Script", style=discord.ButtonStyle.primary, custom_id="okvehub_get_script_secure_v1")
    async def get_script(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)

        blacklist = await db_fetchone("SELECT * FROM blacklist WHERE user_id=?", (user_id,))
        if blacklist:
            return await interaction.response.send_message(
                embed=error_embed("Blacklisted", "You are blacklisted from OkveHUB."),
                ephemeral=True
            )

        wl = await db_fetchone("SELECT * FROM whitelist WHERE user_id=?", (user_id,))
        if not wl:
            return await interaction.response.send_message(
                embed=error_embed("Access Denied", "You are not whitelisted."),
                ephemeral=True
            )

        if wl["expires_at"] and wl["expires_at"] < int(time.time()):
            return await interaction.response.send_message(
                embed=error_embed("Access Expired", "Your whitelist access has expired."),
                ephemeral=True
            )

        key = await db_fetchone(
            "SELECT * FROM keys WHERE used_by=? ORDER BY used_at DESC LIMIT 1",
            (user_id,)
        )

        if not key:
            return await interaction.response.send_message(
                embed=error_embed("No Key", "No key is linked to your account."),
                ephemeral=True
            )

        loader = make_loader(key["key_code"])

        await interaction.response.send_message(
            f"📜 **Your OkveHUB loader:**\n```lua\n{loader}\n```",
            ephemeral=True
        )

    @discord.ui.button(label="👤 Get Role", style=discord.ButtonStyle.primary, custom_id="okvehub_get_role_secure_v1")
    async def get_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        wl = await db_fetchone("SELECT * FROM whitelist WHERE user_id=?", (str(interaction.user.id),))

        if not wl:
            return await interaction.response.send_message(
                embed=error_embed("Access Denied", "You are not whitelisted."),
                ephemeral=True
            )

        await give_roles(interaction.user)

        await interaction.response.send_message(
            embed=success_embed("Roles Given", "Your buyer and whitelist roles were added."),
            ephemeral=True
        )

    @discord.ui.button(label="⚙️ Reset HWID", style=discord.ButtonStyle.secondary, custom_id="okvehub_reset_hwid_secure_v1")
    async def reset_hwid(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)

        wl = await db_fetchone("SELECT * FROM whitelist WHERE user_id=?", (user_id,))
        if not wl:
            return await interaction.response.send_message(
                embed=error_embed("Access Denied", "You are not whitelisted."),
                ephemeral=True
            )

        old_hwid = wl["hwid"]

        await db_execute("UPDATE whitelist SET hwid=NULL WHERE user_id=?", (user_id,))
        await db_execute(
            "INSERT INTO hwid_resets (user_id, old_hwid, new_hwid, reset_by) VALUES (?, ?, ?, ?)",
            (user_id, old_hwid, None, user_id)
        )

        await send_wl_log(
            interaction.guild,
            "⚙️ HWID Reset",
            f"User: {interaction.user.mention}\nOld HWID: `{old_hwid or 'None'}`",
            0xE67E22
        )

        await interaction.response.send_message(
            embed=success_embed("HWID Reset", "Your HWID has been reset."),
            ephemeral=True
        )

    @discord.ui.button(label="📊 Get Stats", style=discord.ButtonStyle.secondary, custom_id="okvehub_stats_secure_v1")
    async def get_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)

        wl = await db_fetchone("SELECT * FROM whitelist WHERE user_id=?", (user_id,))
        key = await db_fetchone("SELECT * FROM keys WHERE used_by=? ORDER BY used_at DESC LIMIT 1", (user_id,))
        resets = await db_fetchall("SELECT * FROM hwid_resets WHERE user_id=?", (user_id,))
        executions = await db_fetchall("SELECT * FROM execution_logs WHERE user_id=?", (user_id,))
        blacklist = await db_fetchone("SELECT * FROM blacklist WHERE user_id=?", (user_id,))

        if not wl:
            return await interaction.response.send_message(
                embed=error_embed("Access Denied", "You are not whitelisted."),
                ephemeral=True
            )

        expires = "Never" if not wl["expires_at"] else f"<t:{wl['expires_at']}:R>"

        embed = discord.Embed(title="Stats", color=0xF1C40F)
        embed.description = (
            f"**Total Executions:** `{len(executions)}` 🧠\n"
            f"**HWID Status:** {'Assigned ✅' if wl['hwid'] else 'Not assigned ❌'}\n"
            f"**Key:** ||{key['key_code'] if key else 'No key'}|| 🔒\n"
            f"**Total HWID Resets:** `{len(resets)}` ⚙️\n"
            f"**Script:** `{wl['script_access'] or 'main'}`\n"
            f"**Expires At:** `{expires}` 📅\n"
            f"**Banned:** {'Yes ⛔' if blacklist else 'No ✅'}\n\n"
            f"**Note:**\nNot specified"
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
            description=(
                "This control panel is for the project: **OkveHUB**\n"
                "If you're a buyer, click on the buttons below to redeem your key, get the script or\n"
                "get your role"
            ),
            color=0xF1C40F
        )

        embed.set_footer(text=f"Sent by {interaction.user} • {discord.utils.utcnow().strftime('%d/%m/%Y %H:%M')}")

        msg = await interaction.channel.send(embed=embed, view=WhitelistPanel())

        for emoji in ["✅", "❤️", "🌐", "🆓", "😂", "🤧", "❌", "💀", "👍", "ℹ️"]:
            try:
                await msg.add_reaction(emoji)
            except:
                pass

        await interaction.response.send_message("✅ Panel envoyé.", ephemeral=True)

    @app_commands.command(name="wl-add", description="Ajouter un utilisateur à la whitelist")
    async def wl_add(
        self,
        interaction: discord.Interaction,
        utilisateur: discord.Member,
        script: str = "main",
        jours: int = 0
    ):
        if not await check_permission(interaction, "staff"):
            return

        key_code = "OKV-" + secrets.token_hex(8).upper()
        expires_at = None if jours <= 0 else int(time.time()) + (jours * 86400)

        await db_execute(
            "INSERT INTO keys (key_code, script_name, used_by, used_at, expires_at, status) VALUES (?, ?, ?, strftime('%s','now'), ?, 'active')",
            (key_code, script, str(utilisateur.id), expires_at)
        )

        await db_execute("""
        INSERT INTO whitelist (user_id, username, added_by, reason, script_access, expires_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username=excluded.username,
            added_by=excluded.added_by,
            reason=excluded.reason,
            script_access=excluded.script_access,
            expires_at=excluded.expires_at
        """, (
            str(utilisateur.id),
            str(utilisateur),
            str(interaction.user.id),
            "Ajout manuel + key générée",
            script,
            expires_at
        ))

        await give_roles(utilisateur)

        loader = make_loader(key_code)

        try:
            await utilisateur.send(
                embed=success_embed(
                    "OkveHUB Access",
                    f"You have been whitelisted ✅\n\n**Script:** `{script}`\n**Key:** `{key_code}`\n\n```lua\n{loader}\n```"
                )
            )
            dm_status = "DM envoyé ✅"
        except:
            dm_status = "DM fermé ❌"

        await send_wl_log(
            interaction.guild,
            "🔐 New Whitelist",
            f"User: {utilisateur.mention}\nScript: `{script}`\nKey: ||{key_code}||\nBy: {interaction.user.mention}\n{dm_status}",
            0x00FF88
        )

        await interaction.response.send_message(
            embed=success_embed(
                "Whitelist ajoutée",
                f"{utilisateur.mention} a accès à **{script}**.\nKey : `{key_code}`\n{dm_status}"
            ),
            ephemeral=True
        )

    @app_commands.command(name="wl-remove", description="Retirer un utilisateur de la whitelist")
    async def wl_remove(self, interaction: discord.Interaction, utilisateur: discord.Member):
        if not await check_permission(interaction, "staff"):
            return

await db_execute("DELETE FROM whitelist WHERE user_id=?", (str(utilisateur.id),))
await db_execute("DELETE FROM keys WHERE used_by=?", (str(utilisateur.id),))
        await send_wl_log(
            interaction.guild,
            "🗑️ Whitelist Removed",
            f"User: {utilisateur.mention}\nRemoved by: {interaction.user.mention}",
            0xFF4444
        )

        await interaction.response.send_message(
            embed=success_embed("Whitelist retirée", f"{utilisateur.mention} n'est plus whitelist."),
            ephemeral=True
        )

    @app_commands.command(name="wl-check", description="Vérifier la whitelist")
    async def wl_check(self, interaction: discord.Interaction, utilisateur: discord.Member = None):
        target = utilisateur or interaction.user

        row = await db_fetchone("SELECT * FROM whitelist WHERE user_id=?", (str(target.id),))

        if not row:
            return await interaction.response.send_message(
                embed=error_embed("Non whitelist", f"{target.mention} n'est pas whitelist."),
                ephemeral=True
            )

        key = await db_fetchone(
            "SELECT * FROM keys WHERE used_by=? ORDER BY used_at DESC LIMIT 1",
            (str(target.id),)
        )

        embed = discord.Embed(title="Whitelist Check", color=COLOR_WL)
        embed.add_field(name="User", value=target.mention, inline=True)
        embed.add_field(name="Script", value=row["script_access"] or "main", inline=True)
        embed.add_field(name="Key", value=f"||{key['key_code'] if key else 'No key'}||", inline=False)
        embed.add_field(name="HWID", value=row["hwid"] or "Not assigned", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="wl-blacklist", description="Blacklist un utilisateur")
    async def wl_blacklist(self, interaction: discord.Interaction, utilisateur: discord.Member, raison: str):
        if not await check_permission(interaction, "admin"):
            return

        await db_execute("""
        INSERT INTO blacklist (user_id, username, reason, added_by)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username=excluded.username,
            reason=excluded.reason,
            added_by=excluded.added_by
        """, (
            str(utilisateur.id),
            str(utilisateur),
            raison,
            str(interaction.user.id)
        ))

        await db_execute("DELETE FROM whitelist WHERE user_id=?", (str(utilisateur.id),))
        await remove_roles(utilisateur)

        await interaction.response.send_message(
            embed=success_embed("Blacklisted", f"{utilisateur.mention} est blacklist.\nRaison : {raison}"),
            ephemeral=True
        )

    @app_commands.command(name="wl-list", description="Voir la liste whitelist")
    async def wl_list(self, interaction: discord.Interaction):
        if not await check_permission(interaction, "staff"):
            return

        rows = await db_fetchall("SELECT * FROM whitelist ORDER BY created_at DESC")

        if not rows:
            return await interaction.response.send_message(
                embed=info_embed("Whitelist vide", "Aucun utilisateur whitelist."),
                ephemeral=True
            )

        lines = []
        for i, row in enumerate(rows[:20], 1):
            lines.append(f"`{i}.` <@{row['user_id']}> — **{row['script_access']}**")

        embed = discord.Embed(
            title=f"🔐 Whitelist ({len(rows)})",
            description="\n".join(lines),
            color=COLOR_WL
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Whitelist(bot))
