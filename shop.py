import discord
from discord.ext import commands
import json
import os

FLUFFY_EMOJI = "{FLUFFY_EMOJI}"

bot = commands.Bot(command_prefix="/", intents=discord.Intents.default())

# =====================================================
# ===============  SHOP.JSON HELPERS  =================
# =====================================================

SHOP_FILE = "shop.json"

def load_shop():
    if not os.path.exists(SHOP_FILE):
        return {}
    with open(SHOP_FILE, "r") as f:
        return json.load(f)


# =========== QUEUE SAVE ==============

from json_queue import queued_write
import asyncio

def save_db(data):
    async def _write():
        with open(USERS_FILE, "w") as f:
            json.dump(data, f, indent=2)

    asyncio.create_task(queued_write(_write))


# =====================================================
# =============== BLOOP_USERS.JSON HELPERS ============
# =====================================================

USERS_FILE = "bloop_users.json"

def load_db():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r") as f:
        return json.load(f)

def save_db(data):
    with open(USERS_FILE, "w") as f:
        json.dump(data, f, indent=2)


# =====================================================
# ==================  SHOP COMMAND  ====================
# =====================================================


# VIEW SHOP

# ===== SHOP COMMANDS ============

async def shop(ctx):
    guild_id = str(ctx.guild.id)
    shop_data = load_shop()

    if guild_id not in shop_data or "shop" not in shop_data[guild_id]:
        return await ctx.send("🛍️ No shop items added for this server yet!")

    items = shop_data[guild_id]["shop"]

    if not items:
        return await ctx.send("🛍️ No items found in the shop!")

    lines = [
        "🛍️ **BLOOP SHOP**",
        "────────────────────────"
    ]

    for i, item in enumerate(items, start=1):
        role_id = item["role_id"]
        price = item["price"]

        # SHOW ROLE AS A PING WITHOUT PINGING ANYONE
        # <@&ROLE_ID> works visually but doesn't ping if bot has no ping perms
        role_mention = f"<@&{role_id}>"

        lines.append(
            f"**{i}. {role_mention}** — **{price}** <a:Fluffy:1428274705206612060>"
        )

        lines.append("—————")

    await ctx.send("\n".join(lines))


# ========= NORMALISE FONT =============

import unicodedata
import re

def normalize_name(text: str):
    # Remove emojis
    text = re.sub(r"<a?:\w+:\d+>", "", text)
    text = re.sub(
        "["                   
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002700-\U000027BF"
        "\U000024C2-\U0001F251"
        "]+",
        "",
        text
    )

    # Normalize weird fonts → plain ascii
    text = unicodedata.normalize("NFKD", text)

    # 🔥 REMOVE COMBINING ACCENTS ("́" etc.)
    text = "".join(c for c in text if not unicodedata.combining(c))

    # keep only ASCII
    text = "".join(c for c in text if ord(c) < 128)

    return text.lower().strip()
    

# =======  BUY COMMAND ==============

async def buy(ctx, *, item_name: str):
    guild_id = str(ctx.guild.id)
    user_id = str(ctx.author.id)

    shop_data = load_shop()
    user_db = load_db()

    if guild_id not in shop_data or "shop" not in shop_data[guild_id]:
        return await ctx.send("❌ No shop items available in this server.")

    items = shop_data[guild_id]["shop"]

    # user input cleaned
    clean_input = normalize_name(item_name)

    found_item = None
    found_role = None

    for item in items:
        # item["item_name"] is something like "<@&123456789012345678>"
        mention = item["item_name"]

        # extract the role ID from string
        match = re.search(r"\d+", mention)
        if not match:
            continue

        role_id = int(match.group())
        role = ctx.guild.get_role(role_id)
        if not role:
            continue  # role was deleted

        clean_role_name = normalize_name(role.name)

        # now compare user's input to REAL ROLE NAME (cleaned)
        if clean_role_name == clean_input:
            found_item = item
            found_role = role
            break

    if not found_item:
        return await ctx.send("❌ No such item found in the shop.")

    # ==========================================
    # BUY LOGIC
    # ==========================================

    if user_id not in user_db:
        user_db[user_id] = {"fluffies": 0, "inventory": {}}

    user = user_db[user_id]

    if user["fluffies"] < found_item["price"]:
        return await ctx.send("❌ Not enough fluffies!")

    user["fluffies"] -= found_item["price"]

    # inventory
    inv = user["inventory"]
    real_item_name = found_item["item_name"]

    if real_item_name not in inv:
        inv[real_item_name] = [1]
    else:
        inv[real_item_name][0] += 1

    save_db(user_db)

    # assign role
    try:
        await ctx.author.add_roles(found_role)
    except:
        await ctx.send("⚠️ Couldn't assign role (missing perms).")

    await ctx.send(f"🎉 You bought **{found_role.mention}** for `{found_item['price']}` fluffies!")


# ====== CREATE SHOP ============

# Create an empty shop for the server
async def create_shop(ctx):
    guild_id = str(ctx.guild.id)
    shop = load_shop()

    shop[guild_id] = {"shop": []}
    save_shop(shop)

    await ctx.send("✅ Shop created for this server!")


# Add a role to the shop
async def add_item(ctx, *, text: str = None):

    if not text:
        return await ctx.send(
            "❌ **Usage:**\n"
            "`Blp add @role 50`\n"
            "Example: `Blp add @cremé 80`"
        )

    # split input: everything except last word = role, last word = price
    parts = text.rsplit(" ", 1)
    if len(parts) < 2:
        return await ctx.send(
            "❌ **Usage:** `Blp add <role> <price>`\nExample: `Blp add @cremé 80`"
        )

    role_part, price_str = parts

    # parse price
    try:
        price = int(price_str)
    except:
        return await ctx.send("❌ Price must be a number (e.g. `80`).")

    # 1) mentioned role?
    if ctx.message.role_mentions:
        role = ctx.message.role_mentions[0]

    # 2) digits → role ID
    elif role_part.isdigit():
        role = ctx.guild.get_role(int(role_part))

    # 3) fallback → normal name match (case-insensitive)
    else:
        role = discord.utils.get(ctx.guild.roles, name=role_part)
        if role is None:
            # try lowercase compare
            for r in ctx.guild.roles:
                if r.name.lower() == role_part.lower():
                    role = r
                    break

    if role is None:
        return await ctx.send("❌ No role with that name/mention/id found.")

    # now save to shop
    guild_id = str(ctx.guild.id)
    shop = load_shop()
    if guild_id not in shop:
        shop[guild_id] = {"shop": []}

    # prevent duplicates
    for item in shop[guild_id]["shop"]:
        if item["role_id"] == str(role.id):
            return await ctx.send(f"⚠️ {role.mention} is already in the shop.")

    shop[guild_id]["shop"].append({
        "role_id": str(role.id),
        "item_name": f"<@&{role.id}>",   # pretty ping display
        "price": price
    })

    save_shop(shop)

    await ctx.send(f"✅ {role.mention} is added for **{price}** fluffies! 🧁☁️")


# Remove item from shop
async def remove_item(ctx, role_name: str = None):
    if role_name is None:
       return await ctx.send(
       "❌ Usage:\n"
"Blp remove {role_name}\n"
"Example: Blp remove cremé"
)

    guild_id = str(ctx.guild.id)
    shop = load_shop()

    if guild_id not in shop:
       return await ctx.send("❌ Shop not created yet.")

    before = len(shop[guild_id]["shop"])

    shop[guild_id]["shop"] = [
item for item in shop[guild_id]["shop"]
    if item["item_name"] != role_name
]

    if len(shop[guild_id]["shop"]) == before:
        return await ctx.send("No role with that name found ❌")

    save_shop(shop)

    await ctx.send("Item removed from the shop")   



# ====  ALL COMMANDS =========


async def setup(bot):
 @bot.command(name="shop")
 async def shop_cmd(ctx):
        await shop(ctx)
     
 @bot.command(name="buy")
 async def buy_cmd(ctx, *, item_name: str):
       await buy(ctx, item_name=item_name)

 @bot.command(name="create_shop")
 async def create_shop_cmd(ctx):
     await create_shop(ctx)

 @bot.command(name="add")
 async def add_item_cmd(ctx, *, text: str = None):
      await add_item(ctx, text=text)

 @bot.command(name="remove")
 async def remove_item_cmd(ctx, role_name: str = None):
      await remove_item(ctx, role_name=role_name)

     
     