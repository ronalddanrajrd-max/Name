import discord
from discord import app_commands
from discord.ext import commands
import os
import secrets
import aiohttp
import datetime

from Database import db_execute, db_fetchone, db_fetchall
from Helpers import *

DEFAULT_SCRIPT = "OkveHUB"
DEFAULT_VERSION = "stable"
PRICE_DISPLAY = "3¢ LTC"


def make_loader(key_code: str):
    base_url = os.getenv("BASE_URL", "https://name-production-e582.up.railway.app").rstrip("/")
    return f'''local script_key = "{key_code}"
local hwid = game:GetService("RbxAnalyticsService"):GetClientId()
local executor = identifyexecutor and identifyexecutor() or "Unknown"

loadstring(game:HttpGet("{base_url}/load?key=" .. script_key .. "&hwid=" .. hwid .. "&executor=" .. executor))()'''


async def init_purchase_db():
    await db_execute("""
    CREATE TABLE IF NOT EXISTS purchases (
        purchase_id TEXT PRIMARY KEY,
        user_id TEXT,
        username TEXT,
        method TEXT,
        script_name TEXT DEFAULT 'OkveHUB',
        script_version TEXT DEFAULT 'stable',
        amount_ltc REAL,
        status TEXT DEFAULT 'pending',
        created_at INTEGER DEFAULT (strftime('%s','now')),
        completed_at INTEGER,
        tx_hash TEXT
    )
    """)


async def give_buyer_roles(member: discord.Member):
    for role_id in [os.getenv("ROLE_WHITELIST"), os.getenv("ROLE_ACHETEUR")]:
        if role_id:
            role = member.guild.get_role(int(role_id))
            if role:
                try:
                    await member.add_roles(role)
                except:
                    pass


async def whitelist_after_payment(interaction, purchase_id, script_name, script_version, tx_hash=None):
    user_id = str(interaction.user.id)
    key_code = "OKV-" + secrets.token_hex(8).upper()

    await db_execute("""
    INSERT INTO keys (key_code, script_name, script_version, used_by, used_at, status)
    VALUES (?, ?, ?, ?, strftime('%s','now'), 'active')
    """, (key_code, script_name, script_version, user_id))

    await db_execute("""
    INSERT INTO whitelist (user_id, username, added_by, reason, script_access)
    VALUES (?, ?, ?, ?, ?)
    ON CONFLICT(user_id) DO UPDATE SET
        username=excluded.username,
        reason=excluded.reason,
        script_access=excluded.script_access
    """, (user_id, str(interaction.user), "purchase_auto", f"Purchase {purchase_id}", script_name))

    await db_execute(
        "UPDATE purchases SET status='completed', completed_at=strftime('%s','now'), tx_hash=? WHERE purchase_id=?",
        (tx_hash, purchase_id)
    )

    await give_buyer_roles(interaction.user)

    return discord.Embed(
        title="✅ Payment Confirmed",
        description=(
            f"Access delivered.\n\n"
            f"**Script:** `{script_name}`\n"
            f"**Version:** `{script_version}`\n"
            f"**Key:** `{key_code}`\n\n"
            f"```lua\n{make_loader(key_code)}\n```"
        ),
        color=0x2ECC71
    )


async def check_ltc_payment(address: str, required_amount: float, created_at: int):
    url = f"https://api.blockcypher.com/v1/ltc/main/addrs/{address}/full?limit=50"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=15) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()

    required_satoshis = int(required_amount * 100_000_000)

    for tx in data.get("txs", []):
        tx_hash = tx.get("hash")
        tx_time = tx.get("confirmed") or tx.get("received")
        if not tx_time:
            continue

        tx_timestamp = int(datetime.datetime.fromisoformat(tx_time.replace("Z", "+00:00")).timestamp())

        if tx_timestamp < created_at:
            continue

        used = await db_fetchone("SELECT * FROM purchases WHERE tx_hash=?", (tx_hash,))
        if used:
            continue

        total_received = 0
        for out in tx.get("outputs", []):
            if address in out.get("addresses", []):
                total_received += int(out.get("value", 0))

        if total_received >= required_satoshis:
            return tx_hash

    return None


class PurchaseCheckView(discord.ui.View):
    def __init__(self, purchase_id: str):
        super().__init__(timeout=900)
        self.purchase_id = purchase_id

    @discord.ui.button(label="✅ I Paid", style=discord.ButtonStyle.success, custom_id="okvehub_purchase_check_version")
    async def check_payment(self, interaction: discord.Interaction, button: discord.ui.Button):
        purchase = await db_fetchone("SELECT * FROM purchases WHERE purchase_id=?", (self.purchase_id,))

        if not purchase:
            return await interaction.response.send_message("❌ Purchase not found.", ephemeral=True)

        if purchase["status"] == "completed":
            return await interaction.response.send_message("✅ Already completed.", ephemeral=True)

        if str(interaction.user.id) != purchase["user_id"]:
            return await interaction.response.send_message("❌ This purchase is not yours.", ephemeral=True)

        await interaction.response.send_message(
            embed=discord.Embed(title="⏳ Checking Payment", description="Checking Litecoin payment...", color=0xF1C40F),
            ephemeral=True
        )

        test_mode = os.getenv("PURCHASE_TEST_MODE", "false").lower() == "true"

        if test_mode:
            tx_hash = "TEST-LTC-" + secrets.token_hex(6).upper()
        else:
            address = os.getenv("LTC_ADDRESS")
            amount = float(purchase["amount_ltc"])
            created_at = int(purchase["created_at"])
            tx_hash = await check_ltc_payment(address, amount, created_at)

        if not tx_hash:
            return await interaction.followup.send("⌛ Payment still pending.", ephemeral=True)

        embed = await whitelist_after_payment(
            interaction,
            purchase["purchase_id"],
            purchase["script_name"] or DEFAULT_SCRIPT,
            purchase["script_version"] or DEFAULT_VERSION,
            tx_hash
        )

        await interaction.followup.send(embed=embed, ephemeral=True)


class PurchasePanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="💰 Buy with LTC", style=discord.ButtonStyle.success, custom_id="okvehub_purchase_ltc_version")
    async def buy_ltc(self, interaction: discord.Interaction, button: discord.ui.Button):
        address = os.getenv("LTC_ADDRESS")
        amount = float(os.getenv("LTC_AMOUNT", "0.0006"))
        script_name = os.getenv("PURCHASE_SCRIPT", DEFAULT_SCRIPT)
        script_version = os.getenv("PURCHASE_VERSION", DEFAULT_VERSION)

        if not address:
            return await interaction.response.send_message("❌ LTC_ADDRESS missing.", ephemeral=True)

        purchase_id = "PUR-" + secrets.token_hex(4).upper()

        await db_execute("""
        INSERT INTO purchases (purchase_id, user_id, username, method, script_name, script_version, amount_ltc)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (purchase_id, str(interaction.user.id), str(interaction.user), "ltc", script_name, script_version, amount))

        embed = discord.Embed(
            title="💰 Litecoin Checkout",
            description=(
                f"**Purchase ID:** `{purchase_id}`\n"
                f"**Product:** `{script_name}`\n"
                f"**Version:** `{script_version}`\n"
                f"**Price:** `{PRICE_DISPLAY}`\n\n"
                f"Send payment to:\n`{address}`\n\n"
                "After payment, click **I Paid**."
            ),
            color=0xF1C40F
        )

        await interaction.response.send_message(embed=embed, view=PurchaseCheckView(purchase_id), ephemeral=True)

    @discord.ui.button(label="🧠 Buy with BrainDrop", style=discord.ButtonStyle.primary, custom_id="okvehub_purchase_braindrop_version")
    async def buy_braindrop(self, interaction: discord.Interaction, button: discord.ui.Button):
        username = os.getenv("BRAINDROP_USERNAME")
        script_name = os.getenv("PURCHASE_SCRIPT", DEFAULT_SCRIPT)
        script_version = os.getenv("PURCHASE_VERSION", DEFAULT_VERSION)

        if not username:
            return await interaction.response.send_message("❌ BRAINDROP_USERNAME missing.", ephemeral=True)

        purchase_id = "BRD-" + secrets.token_hex(4).upper()

        await db_execute("""
        INSERT INTO purchases (purchase_id, user_id, username, method, script_name, script_version, amount_ltc, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (purchase_id, str(interaction.user.id), str(interaction.user), "braindrop", script_name, script_version, 0, "pending"))

        await interaction.response.send_message(
            embed=discord.Embed(
                title="🧠 BrainDrop Payment",
                description=f"Send payment to:\n`{username}`\n\nPurchase ID: `{purchase_id}`",
                color=0x5865F2
            ),
            ephemeral=True
        )


class Purchase(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="purchase-panel", description="Créer le panel d'achat")
    async def purchase_panel(self, interaction: discord.Interaction):
        if not await check_permission(interaction, "admin"):
            return

        embed = discord.Embed(
            title="🛒 OkveHUB Store",
            description=f"Price: `{PRICE_DISPLAY}`\nChoose your payment method below.",
            color=0x000000
        )

        await interaction.channel.send(embed=embed, view=PurchasePanel())
        await interaction.response.send_message("✅ Purchase panel sent.", ephemeral=True)

    @app_commands.command(name="purchase-list", description="Voir les achats")
    async def purchase_list(self, interaction: discord.Interaction):
        if not await check_permission(interaction, "staff"):
            return

        rows = await db_fetchall("SELECT * FROM purchases ORDER BY created_at DESC LIMIT 15")
        if not rows:
            return await interaction.response.send_message("No purchases found.", ephemeral=True)

        lines = [
            f"`{r['purchase_id']}` — <@{r['user_id']}> — `{r['script_name']}` `{r['script_version'] or 'stable'}` — `{r['status']}`"
            for r in rows
        ]

        await interaction.response.send_message(
            embed=discord.Embed(title="Purchases", description="\n".join(lines), color=0x3498DB),
            ephemeral=True
        )

    @app_commands.command(name="purchase-complete", description="Valider manuellement un achat")
    async def purchase_complete(self, interaction: discord.Interaction, purchase_id: str):
        if not await check_permission(interaction, "staff"):
            return

        purchase = await db_fetchone("SELECT * FROM purchases WHERE purchase_id=?", (purchase_id,))
        if not purchase:
            return await interaction.response.send_message("❌ Purchase not found.", ephemeral=True)

        member = interaction.guild.get_member(int(purchase["user_id"]))
        if not member:
            return await interaction.response.send_message("❌ Member not found.", ephemeral=True)

        class FakeInteraction:
            def __init__(self, original, user):
                self.guild = original.guild
                self.user = user

        embed = await whitelist_after_payment(
            FakeInteraction(interaction, member),
            purchase["purchase_id"],
            purchase["script_name"] or DEFAULT_SCRIPT,
            purchase["script_version"] or DEFAULT_VERSION,
            "manual-validation"
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await init_purchase_db()
    await bot.add_cog(Purchase(bot))
