import json
import time
from collections import defaultdict
import discord
from discord.ext import commands
import os
from discord import app_commands
from datetime import timedelta

bot = commands.Bot(command_prefix="!",
intents=discord.Intents.all())
intents = discord.Intents.all()
intents.message_content = True
intents.members = True
intents.guilds = True

SETTINGS_FILE = "moderation_settings.json"

DEFAULT_SETTINGS = {
    "anti_spam": False,
    "raid_alerts": False,
    "welcome_enabled": False,
    "welcome_channel": None,
    "welcome_message": None,
    "welcome_image": None
}

def load_settings():
    try:
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_settings(data):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def ensure_guild(guild_id: int):
    data = load_settings()
    gid = str(guild_id)
    if gid not in data:
        data[gid] = DEFAULT_SETTINGS.copy()
        save_settings(data)
    return data

def feature_enabled(guild_id: int, feature: str) -> bool:
    data = ensure_guild(guild_id)
    return data[str(guild_id)].get(feature, False)

spam_tracker = defaultdict(list)


# -------- ANTI SPAM -------------

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    if not feature_enabled(message.guild.id, "anti_spam"):
        return

    key = (message.guild.id, message.author.id, message.content.lower())
    now = time.time()

    spam_tracker[key].append(now)

    # keep only last 10 seconds
    spam_tracker[key] = [t for t in spam_tracker[key] if now - t <= 30]

    if len(spam_tracker[key]) >= 3:
        try:
            until = discord.utils.utcnow() + timedelta(days=0.4)
            await message.author.timeout(until, reason="Spam detected")
            await message.channel.send(
                f"🔇 {message.author.mention} muted for spamming."
            )
        except:
            pass

        spam_tracker[key].clear()

    await bot.process_commands(message)


# -------- RAID ALERTS -------------

channel_delete_log = defaultdict(list)

@bot.event
async def on_guild_channel_delete(channel):
    guild = channel.guild

    if not feature_enabled(guild.id, "raid_alerts"):
        return

    now = time.time()
    channel_delete_log[guild.id].append(now)

    # keep only last 60 seconds
    channel_delete_log[guild.id] = [
        t for t in channel_delete_log[guild.id] if now - t <= 60
    ]

    if len(channel_delete_log[guild.id]) >= 2:
        owner = guild.owner

        msg = (
            f"⚠️ **Possible Raid Detected** in server **{guild.name}** \n"
            "Multiple channels were deleted in a short time.\n"
            "This may be a nuke attempt."
        )

        # DM owner
        try:
            await owner.send(msg)
        except:
            pass

        # DM admins & mods
        for member in guild.members:
            if member.guild_permissions.administrator or member.guild_permissions.manage_guild:
                try:
                    await member.send(msg)
                except:
                    pass

        channel_delete_log[guild.id].clear()


# -------- COMMANDS ----------------

@bot.tree.command(name="enable")
@app_commands.describe(feature="anti_spam or raid_alerts")
async def enable(interaction: discord.Interaction, feature: str):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Admin only.", ephemeral=True)

    data = load_settings()
    gid = str(interaction.guild.id)

    if feature not in DEFAULT_SETTINGS:
        return await interaction.response.send_message("❌ Invalid feature.")

    data.setdefault(gid, DEFAULT_SETTINGS.copy())
    data[gid][feature] = True
    save_settings(data)

    await interaction.response.send_message(f"✅ `{feature}` enabled.")


# ----- DISABLE COMMAND -------------

@bot.tree.command(name="disable")
@app_commands.describe(feature="anti_spam or raid_alerts")

# ------- DISBALE FUNCTION ------------

async def disable(interaction: discord.Interaction, feature: str):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message(
            "❌ Admin only.", ephemeral=True
        )

    if feature not in DEFAULT_SETTINGS:
        return await interaction.response.send_message(
            "❌ Invalid feature. Use `anti_spam` or `raid_alerts`.",
            ephemeral=True
        )

    data = load_settings()
    gid = str(interaction.guild.id)

    data.setdefault(gid, DEFAULT_SETTINGS.copy())
    data[gid][feature] = False
    save_settings(data)

    await interaction.response.send_message(
        f"⛔ `{feature}` disabled."
    )

# ------ MODERATION STATUS COMMAND ----

@bot.tree.command(name="mod_status")

# MODERATION STATUS FUNCTION 
async def mod_status(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message(
            "❌ Admin only.", ephemeral=True
        )

    data = ensure_guild(interaction.guild.id)
    settings = data[str(interaction.guild.id)]

    msg = (
        "🛡️ **Bloop Moderation Status**\n\n"
        f"• Anti-Spam: {'✅ Enabled' if settings['anti_spam'] else '❌ Disabled'}\n"
        f"• Raid Alerts: {'✅ Enabled' if settings['raid_alerts'] else '❌ Disabled'}"
    )

    await interaction.response.send_message(msg, ephemeral=True)

# ------- WELCOMER SETUP ----------

@bot.tree.command(name="welcomer")
@app_commands.describe(
    message="Custom welcome message (optional)",
    image_url="Image URL (optional)"
)
async def welcomer(
    interaction: discord.Interaction,
    message: str | None = None,
    image_url: str | None = None
):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message(
            "❌ Admin only.", ephemeral=True
        )

    data = load_settings()
    gid = str(interaction.guild.id)
    data.setdefault(gid, DEFAULT_SETTINGS.copy())

    data[gid]["welcome_enabled"] = True
    data[gid]["welcome_channel"] = interaction.channel.id
    data[gid]["welcome_message"] = message
    data[gid]["welcome_image"] = image_url

    save_settings(data)

    await interaction.response.send_message(
        f"👋 Welcomer enabled in {interaction.channel.mention}",
        ephemeral=True
    )


# -------- WELCOMER EVENT ------------

@bot.event
async def on_member_join(member: discord.Member):
    data = load_settings()
    gid = str(member.guild.id)

    if gid not in data:
        return

    settings = data[gid]

    if not settings.get("welcome_enabled"):
        return

    channel_id = settings.get("welcome_channel")
    channel = member.guild.get_channel(channel_id)

    if not channel:
        return

    embed = discord.Embed(
        description=f"✨ Welcome {member.mention} to **{member.guild.name}**!",
        color=discord.Color.blurple()
    )

    if settings.get("welcome_message"):
        embed.add_field(
            name="Message",
            value=settings["welcome_message"],
            inline=False
        )

    if settings.get("welcome_image"):
        embed.set_image(url=settings["welcome_image"])

    await channel.send(embed=embed)

# ------ WELCOMER DISABLE COMMAND ------

@bot.tree.command(name="welcomer_disable")
async def welcomer_disable(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message(
            "❌ Admin only.", ephemeral=True
        )

    data = load_settings()
    gid = str(interaction.guild.id)

    data.setdefault(gid, DEFAULT_SETTINGS.copy())

    if not data[gid]["welcome_enabled"]:
        return await interaction.response.send_message(
            "ℹ️ Welcomer is already disabled.",
            ephemeral=True
        )

    data[gid]["welcome_enabled"] = False
    save_settings(data)

    await interaction.response.send_message(
        "⛔ **Welcomer disabled**.\nSettings are preserved.",
        ephemeral=True
    )


# =========== HELP COMMAND ============

@bot.tree.command(name="help", description="How to use Bloop")
async def help(interaction: discord.Interaction):

        embed = discord.Embed(
            title="✨ How to use Bloop",
            description="Use the commands below to explore Bloop’s features 👇",
            color=discord.Color.blurple()
        )

        embed.add_field(
            name="🎰 Mini Games",
            value=(
                "`Blp cmds` → Slot machine & games\n"
                "`Blp manual` → Pirate game guide"
            ),
            inline=False
        )

        embed.add_field(
            name="🛡️ Moderation",
            value=(
                "`/enable` → Enable a moderation feature\n"
                "`/disable` → Disable a feature\n"
                "`/mod_status` → Check moderation status"
            ),
            inline=False
        )

        embed.add_field(
            name="🎨 Server Themes",
            value=(
                "`/themes` → View themes\n"
                "`/apply_theme` → Apply a server theme"
            ),
            inline=False
        )

        embed.add_field(
            name="📖 Need help?",
            value="Run any command with `/` and Discord will guide you.",
            inline=False
        )

        embed.set_footer(text="🎁 Bloop • Christmas Edition")

        await interaction.response.send_message(embed=embed, ephemeral=True)

# -------- RUN BOT -------------

async def setup(bot):
    bot.tree.add_command(enable)
    bot.tree.add_command(disable)
    bot.tree.add_command(mod_status)
    bot.tree.add_command(help)