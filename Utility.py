import discord
from discord import app_commands
from discord.ext import commands
import os
from Database import db_execute, db_fetchone, db_fetchall
from Helpers import *

class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ══════════ /suggestion ══════════
    @app_commands.command(name="suggestion", description="💡 Faire une suggestion pour OkveHUB")
    @app_commands.describe(suggestion="Ta suggestion")
    async def suggestion(self, interaction: discord.Interaction, suggestion: str):
        ch_id = os.getenv("CHANNEL_SUGGESTIONS")
        if not ch_id:
            return await interaction.response.send_message(embed=error_embed("Config", "Salon de suggestions non configuré."), ephemeral=True)
        channel = self.bot.get_channel(int(ch_id))
        if not channel:
            return await interaction.response.send_message(embed=error_embed("Config", "Salon de suggestions introuvable."), ephemeral=True)

        embed = discord.Embed(title="💡 Nouvelle Suggestion", description=suggestion, color=COLOR_INFO, timestamp=discord.utils.utcnow())
        embed.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="📊 Statut", value="⏳ En attente", inline=True)
        embed.set_footer(text=f"ID: {interaction.user.id}")

        msg = await channel.send(embed=embed)
        await msg.add_reaction("👍")
        await msg.add_reaction("👎")
        await db_execute("INSERT INTO suggestions (user_id, message_id, content) VALUES (?,?,?)",
            (str(interaction.user.id), str(msg.id), suggestion))
        await interaction.response.send_message(embed=success_embed("Suggestion Envoyée !", f"Ta suggestion a été envoyée dans {channel.mention} !"), ephemeral=True)

    # ══════════ /suggestion-approve ══════════
    @app_commands.command(name="suggestion-approve", description="✅ Approuver une suggestion")
    @app_commands.describe(message_id="ID du message", reponse="Commentaire")
    async def suggestion_approve(self, interaction: discord.Interaction, message_id: str, reponse: str = "Approuvée !"):
        if not await check_permission(interaction, "admin"): return
        sugg = await db_fetchone("SELECT * FROM suggestions WHERE message_id=?", (message_id,))
        if not sugg:
            return await interaction.response.send_message(embed=error_embed("Introuvable", "Suggestion non trouvée."), ephemeral=True)
        await db_execute("UPDATE suggestions SET status='approved', staff_id=?, response=? WHERE message_id=?",
            (str(interaction.user.id), reponse, message_id))
        ch_id = os.getenv("CHANNEL_SUGGESTIONS")
        if ch_id:
            channel = self.bot.get_channel(int(ch_id))
            if channel:
                try:
                    msg = await channel.fetch_message(int(message_id))
                    embed = msg.embeds[0]
                    embed.color = COLOR_SUCCESS
                    for i, field in enumerate(embed.fields):
                        if field.name == "📊 Statut":
                            embed.set_field_at(i, name="📊 Statut", value="✅ Approuvée", inline=True)
                    embed.add_field(name=f"✅ Réponse de {interaction.user}", value=reponse, inline=False)
                    await msg.edit(embed=embed)
                except: pass
        await interaction.response.send_message(embed=success_embed("Suggestion Approuvée", "La suggestion a été approuvée."), ephemeral=True)

    # ══════════ /suggestion-deny ══════════
    @app_commands.command(name="suggestion-deny", description="❌ Refuser une suggestion")
    @app_commands.describe(message_id="ID du message", raison="Raison du refus")
    async def suggestion_deny(self, interaction: discord.Interaction, message_id: str, raison: str):
        if not await check_permission(interaction, "admin"): return
        sugg = await db_fetchone("SELECT * FROM suggestions WHERE message_id=?", (message_id,))
        if not sugg:
            return await interaction.response.send_message(embed=error_embed("Introuvable", "Suggestion non trouvée."), ephemeral=True)
        await db_execute("UPDATE suggestions SET status='denied', staff_id=?, response=? WHERE message_id=?",
            (str(interaction.user.id), raison, message_id))
        ch_id = os.getenv("CHANNEL_SUGGESTIONS")
        if ch_id:
            channel = self.bot.get_channel(int(ch_id))
            if channel:
                try:
                    msg = await channel.fetch_message(int(message_id))
                    embed = msg.embeds[0]
                    embed.color = COLOR_ERROR
                    for i, field in enumerate(embed.fields):
                        if field.name == "📊 Statut":
                            embed.set_field_at(i, name="📊 Statut", value="❌ Refusée", inline=True)
                    embed.add_field(name=f"❌ Refus de {interaction.user}", value=raison, inline=False)
                    await msg.edit(embed=embed)
                except: pass
        await interaction.response.send_message(embed=success_embed("Suggestion Refusée", "La suggestion a été refusée."), ephemeral=True)

    # ══════════ /note-add ══════════
    @app_commands.command(name="note-add", description="📝 Ajouter une note sur un utilisateur")
    @app_commands.describe(utilisateur="Utilisateur", note="Contenu de la note")
    async def note_add(self, interaction: discord.Interaction, utilisateur: discord.Member, note: str):
        if not await check_permission(interaction, "staff"): return
        await db_execute("INSERT INTO notes (user_id, note, added_by) VALUES (?,?,?)",
            (str(utilisateur.id), note, str(interaction.user.id)))
        await interaction.response.send_message(embed=success_embed("Note Ajoutée", f"Note ajoutée pour **{utilisateur}**."), ephemeral=True)

    # ══════════ /note-list ══════════
    @app_commands.command(name="note-list", description="📝 Voir les notes d'un utilisateur")
    @app_commands.describe(utilisateur="Utilisateur")
    async def note_list(self, interaction: discord.Interaction, utilisateur: discord.Member):
        if not await check_permission(interaction, "staff"): return
        rows = await db_fetchall("SELECT * FROM notes WHERE user_id=? ORDER BY created_at DESC", (str(utilisateur.id),))
        if not rows:
            return await interaction.response.send_message(embed=info_embed("Aucune note", f"Aucune note pour **{utilisateur}**."), ephemeral=True)
        embed = discord.Embed(title=f"📝 Notes — {utilisateur}", color=COLOR_INFO, timestamp=discord.utils.utcnow())
        embed.description = "\n\n".join(f"**#{r['id']}** <t:{r['created_at']}:d> par <@{r['added_by']}>\n└ {r['note']}" for r in rows)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ══════════ /note-delete ══════════
    @app_commands.command(name="note-delete", description="🗑️ Supprimer une note")
    @app_commands.describe(id="ID de la note")
    async def note_delete(self, interaction: discord.Interaction, id: int):
        if not await check_permission(interaction, "staff"): return
        await db_execute("DELETE FROM notes WHERE id=?", (id,))
        await interaction.response.send_message(embed=success_embed("Note Supprimée", f"Note `#{id}` supprimée."), ephemeral=True)

    # ══════════ /reactionrole ══════════
    @app_commands.command(name="reactionrole", description="🎭 Créer un rôle réaction")
    @app_commands.describe(message_id="ID du message", emoji="Emoji", role="Rôle à donner")
    async def reactionrole(self, interaction: discord.Interaction, message_id: str, emoji: str, role: discord.Role):
        if not await check_permission(interaction, "admin"): return
        try:
            msg = await interaction.channel.fetch_message(int(message_id))
            await msg.add_reaction(emoji)
        except:
            return await interaction.response.send_message(embed=error_embed("Erreur", "Message introuvable ou emoji invalide."), ephemeral=True)
        await db_execute("INSERT OR IGNORE INTO reaction_roles (message_id, channel_id, emoji, role_id) VALUES (?,?,?,?)",
            (message_id, str(interaction.channel_id), emoji, str(role.id)))
        await interaction.response.send_message(embed=success_embed("Rôle Réaction Créé", f"L'emoji {emoji} donnera le rôle {role.mention}."), ephemeral=True)

    # ══════════ /clear-cache ══════════
    @app_commands.command(name="clear-cache", description="🗑️ Vider les données expirées de la whitelist")
    async def clear_cache(self, interaction: discord.Interaction):
        if not await check_permission(interaction, "admin"): return
        await db_execute("DELETE FROM whitelist WHERE expires_at IS NOT NULL AND expires_at < strftime('%s','now')", ())
        await db_execute("DELETE FROM antispam WHERE last_message < strftime('%s','now') - 3600", ()) if False else None
        await interaction.response.send_message(embed=success_embed("Cache Nettoyé", "Les entrées expirées ont été supprimées."), ephemeral=True)

async def setup(bot):
    await bot.add_cog(Utility(bot))
