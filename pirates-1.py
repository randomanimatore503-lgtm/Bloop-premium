# =========== PIRATE GAME============
# Required imports (already in your main.py)
# import discord, asyncio, json, os, random
# from discord.ext import commands, tasks
# from discord import app_commands

#---------imports-------------

import discord, asyncio, json, os, random, time, copy



#---------checking the loading-------

print("Pirates module loaded!")

#------------- Constants / Custom Emojis ---------
IRON_SHELL = "<:Iron_shell:1431172962043691051>"
SHIP_ABLAZE = "<a:ship_ablaze:1431147397882445895>"
LEVIATHAN_FIRE = "<a:Leviathan:1431122303923519511>"
RAFT = "<:raft:1431111831963045888>"
TIMBER = "<:timber:1431109800552566877>"
RUBY = "<a:Ruby:1431098635634081792>"
VIOGEM = "<a:Viogem:1430449310553735209>"
TREASURE_CHEST_OPEN = "<:treasure_chest_opened:1431094613103345674>"
TREASURE_CHEST_CLOSED = "<:treasure_chest_closed:1431094504638906368>"
GIANT_SQUID = "<a:gaintsquid:1430986741694857426>"
SERPEND = "<a:Serpent:1430978623191519432>"
HALF_LIVE = "<:livebar_half:1430943361048514671>"
FULL_LIVE = "<:livebar_full:1430943234535981206>"
SANK_SHIP = "<:sankship:1430919147067281539>"
SINKING_SHIP = "<a:sinkingship:1430918749556572240>"
SAIL_SHIP = "<a:sailship:1430621453522571364>"
ISLAND = "<:Island:1430621337033904268>"
GUNPOWDER = "<:gunpowder:1431110389055361065>"
BURNING_CHEST = "<a:burning_chest:1433422078459121685>"

DB_FILE = "bloop_users.json"
ISLANDS_FILE = "islands.json"

#------------- Helpers / DB ------------

# main db
def load_db():
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, "w") as f:
            json.dump({}, f)
    with open(DB_FILE, "r") as f:
        return json.load(f)

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=4)

def ensure_user(db, user_id):
    if user_id not in db:
        db[user_id] = {
            "inventory": {},
            "ship": {"lives": 6, "status": "port", "storage": {}},
            "clan": None,
            "voyage": {"active": False, "loot": []}
        }
    return db[user_id]

db = load_db()


# islands DB

# ------------------ LOAD ------------------
def load_islands():
    """Loads islands.json, creates it if missing."""
    if not os.path.exists(ISLANDS_FILE):
        with open(ISLANDS_FILE, "w") as f:
            json.dump({}, f, indent=4)
    with open(ISLANDS_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

# ------------------ SAVE ------------------
def save_islands(data):
    """Saves data safely into islands.json."""
    with open(ISLANDS_FILE, "w") as f:
        json.dump(data, f, indent=4)

# ------------------ DEFAULT STRUCTURE ------------------
def ensure_island(user_id: str, username: str):
    """Makes sure every user has an island initialized."""
    islands = load_islands()
    island = islands.setdefault(user_id, {
        "owner": username,
        "island_name": f"{username}'s Island",
        "chests": {
            "chest_1": {
                "location": "island",
                "items": {},
                "locked": False
            }
        },
        "allowed_users": [],  # people who can visit/open
        "resources": {
            "timber": 0,
            "gunpowder": 0
        }
    })
    islands[user_id] = island
    save_islands(islands)
    return island


#------------- Game Manual -------------

async def game_manual(ctx):
    embed = discord.Embed(
        title="🗺️ Pirate Game Manual",
        description=(
            "**Clan Commands:**\n"
            "`Blp create_clan {role}` → Create/assign clans\n"
            "`Blp join {clan}` → Join a clan\n\n"
            "**Ship Commands:**\n"
            "`Blp attack {user}` → Attack a player\n"
            "`Blp repair` → Repair your ship (requires 🪵 timber)\n\n"
            "**Voyage Commands:**\n"
            "`Blp sail` → Start sailing\n"
            "**Inventory:**\n"
            "`Blp store {item} {chest name}` → Store items in your chest\n"
            "`Blp chest` → View your chests\n"
            "`Blp bury {chest_name}` → bury your chest to save it from getting stolen\n"
            
            "`Blp unbury {chest_name}` → unbury to fetch resources from your Island\n"
            "`Blp steal {user} {chest_name}` → steal a chest from the user. only works when it's unburied\n"
            "`Blp burn {chest_name}` → burn a chest in emergency to get timber"
            "`Blp build` → build a chest using timber\n"
            "`Blp fetch {chest_name}` → to fetch resources from your Island in thst chest(only works when unburied)"
            "⚠️ Ships have 3 lives (half-heart per hit). Lose all? You’re stuck on a raft! 🛶\n"
            "Islands can be landed on to gather resources.\n"
            "Special items: RUBY 💎, VIOGEM 💎\n"
            "Attack wisely, repair wisely, sail smartly!"
        ),
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed)

#------------- Clan Management -------------


#------------- Voyage System -----------

async def sail(ctx):
    user_id = str(ctx.author.id)

    # load DB (keeps a single source of truth)
    db = load_db()

    # ensure top-level structure
    if "players" not in db:
        db["players"] = {}
    players = db["players"]

    # ensure user entry exists
    user = players.setdefault(user_id,{})
        
    
    # use 'sailing' flag on the user
    if user.get("sailing", False):
        # emoji on first message, text on second — per your rule
        await ctx.send(f"{SAIL_SHIP}")
        await ctx.send("**You're already on a sail, matey!** 🌊")
        return

    # mark sailing
    user["sailing"] = True
    save_db(db)

    # announce departure (emoji message then text message)
    await ctx.send(f"{SAIL_SHIP}")
    await ctx.send("**You're on a sail...** ⛵🌊 The sea be callin’...")

    # random sail duration (5-10 minutes)
    duration = random.randint(300, 600)  # 300..600 seconds
    # for quick tests you can temporarily use: duration = random.randint(10, 30)

    await asyncio.sleep(duration)

    # possible finds: (emoji, description, fluffies_reward)
    finds = [
        ("⚓", "an **Anchor**! Strong and steady, like the heart of a sailor.", 0),
        ("🐡", "a **Pufferfish**... uh oh, careful mate, it's poisonous! ☠️", 0),
        ("🐠", "some **Fishes** floppin’ in yer net!", random.randint(1, 3)),
        ("🐟", "a fine **Catch of Fish**!", random.randint(2, 4)),
        ("🪵", "a few logs of **Timber** floatin’ around!", random.randint(1, 2)),
        ("🦞", "a **Lobster**! Delicious and can fetch ya Fluffies!", random.randint(3, 5)),
        ("🦐", "some **Shrimps**! Good trade value for Fluffies!", random.randint(3, 5)),
        ("🪸", "some **Coral**! Beautiful and nice for trade.", random.randint(3, 5)),
    ]

    emoji, description, reward = random.choice(finds)

    # show results (emoji first, then text)
    await ctx.send(f"{SAIL_SHIP}")
    await ctx.send(f"{emoji}\nYou found {description}")

    # give fluffies if reward > 0
    if reward and reward > 0:
        user["fluffies"] = user.get("fluffies", 0) + reward
        save_db(db)
        await ctx.send(f"{FLUFFY_EMOJI} **+{reward} Fluffies earned!**")

    # mark sail complete
    user["sailing"] = False
    save_db(db)

#------------- Repair System -----------


async def repair(ctx):
    user_id = str(ctx.author.id)
    db = load_db()
    user = db.setdefault(user_id, {})
    ship = user.setdefault("ship", {"lives": 6, "status": "port", "storage": {}})
    inv = user.setdefault("inventory", {})

    # --- Normalize lives (same as status) ---
    raw_lives = ship.get("lives", 6)
    if isinstance(raw_lives, list):
        raw_lives = raw_lives[0] if raw_lives else 6
    try:
        lives = float(raw_lives)
    except Exception:
        lives = 6.0

    # Clamp between 0–6
    lives = max(0.0, min(lives, 6.0))
    ship["lives"] = lives
    user["ship"] = ship
    db[user_id] = user
    save_db(db)

    # --- Check condition ---
    if lives >= 6:
        await ctx.send("⚙️ Your ship is already in **perfect condition**!")
        return

    # --- Repair logic ---
    repair_cost = 1  # timber needed per repair
    timber = inv.get("timber", 0)

    # --- Fix legacy list storage----
    if isinstance(timber, list):
     timber = timber[0] if timber else 0
    try:
       timber = int(timber)
    except Exception:
       timber = 0

    if timber < repair_cost:
        await ctx.send(f"🪵 Not enough timber! You need at least {repair_cost} to repair.")
        return

    # --- Deduct timber and repair ---

    # --- Normalize inventory timber (handle legacy list storage) ---
    if isinstance(inv.get("timber", 0), list):
        inv["timber"] = inv["timber"][0] if inv["timber"] else 0

    # ensure inventory timber is an int we can subtract from
    try:
        inv["timber"] = int(inv.get("timber", 0))
    except Exception:
        inv["timber"] = 0

    # safety check (again) before consuming
    if inv["timber"] < repair_cost:
        await ctx.send(f"🪵 Not enough timber! You need at least {repair_cost} to repair.")
        return

    # consume timber and apply heal (1 timber -> +1 life, clamped to 6)
    inv["timber"] -= repair_cost
    new_lives = min(6.0, lives + 1.0)
    ship["lives"] = float(new_lives)

    # persist cleaned values
    user["ship"] = ship
    user["inventory"] = inv
    db[user_id] = user
    save_db(db)
    
    # --- Deduct/repair over--------
    await ctx.send(f"🛠️ You repaired your ship! Current health: {ship['lives']} ❤️")

#------------- PvP System -------------

async def attack(ctx, target: discord.Member = None):

    # Resolve target robustly:
    # 1) use converter result if provided
    # 2) else try message mentions
    # 3) else try parse an ID or username from the message
    if target is None:
        # prefer explicit mentions first
        if ctx.message.mentions:
            target = ctx.message.mentions[0]
        else:
            # try parse second token as id or name (e.g. Blp attack 123456789012345678 or Blp attack username)
            parts = ctx.message.content.split()
            if len(parts) >= 2:
                possible = parts[1]
                # try numeric id inside <@...> or plain id
                digits = ''.join(ch for ch in possible if ch.isdigit())
                if digits:
                    try:
                        member = ctx.guild.get_member(int(digits))
                        if member:
                            target = member
                    except Exception:
                        target = None
                # fallback: try exact name/display name match
                if target is None:
                    target = discord.utils.find(lambda m: (m.name == possible) or (m.display_name == possible), ctx.guild.members)

    if target is None:
        return await ctx.send("⚔️ Please mention a user to attack, captain!")

    attacker_id = str(ctx.author.id)

    target_id = str(target.id)

    # --- Load database ---
    db = load_db()

    # make sure both users exist
    if attacker_id not in db:
        return await ctx.send("☠️ You don’t even have a ship yet!")
    if target_id not in db:
        return await ctx.send(f"🏝️ {target.display_name} doesn’t have a ship yet!")

    attacker = db[attacker_id]
    defender = db[target_id]

    ship = attacker.setdefault("ship", {"lives": 6})
    target_ship = defender.setdefault("ship", {"lives": 6})

 # iron shell inventory check

    inv = attacker.setdefault("inventory", {})
    inv["cannonballs"] =inv.get("cannonballs",0)

# --- List to int conversion ---
    if isinstance(inv["cannonballs"], list):
      inv["cannonballs"] =                    inv["cannonballs"][0] if                inv["cannonballs"] else 0

# --- Check if player has cannonballs ---
    if inv["cannonballs"] <= 0:
     return await ctx.send(f"{IRON_SHELL} You don’t have any Iron Shells to attack with!")

    #inv["cannonballs"] -= 1
    #save_db(db)


    # --- Cooldown check ---
    now = time.time()
    if "cooldown" in attacker and now - attacker["cooldown"] < 5:
        wait = round(5 - (now - attacker["cooldown"]), 1)
        return await ctx.send(f"🕰️ Hold fire, captain! Reloading cannons... ({wait}s)")
    attacker["cooldown"] = now

    # --- Status checks ---
    if attacker.get("status") == "raft":
        return await ctx.send("You’re stranded on a raft, captain! Wait until you rebuild your ship.")
    if defender.get("status") == "raft":
        return await ctx.send(f"{RAFT} {target.display_name} is already on a raft, don’t waste your cannonballs!")

    # --- Iron shell check ---
    if inv["cannonballs"] <= 0:
        return await ctx.send(f"{IRON_SHELL} You don’t have any Iron Shells to attack with!")
    inv["cannonballs"] -= 1

    save_db(db)

    # --- Attack sequence ---
    await ctx.send(f"**{ctx.author.mention}’s loading the attack... 🧨**")
    await asyncio.sleep(2)
    await ctx.send(f"{SAIL_SHIP} {IRON_SHELL} 💥")
    await asyncio.sleep(1)
    await ctx.send(f"**{ctx.author.mention} has attacked {target.mention}!**")

    # --- Reduce target HP ---
    target_ship["lives"] -= 0.5
    if target_ship["lives"] < 0:
        target_ship["lives"] = 0

    # --- Display HP bar ---
    full = FULL_LIVE
    half = HALF_LIVE
    hp = target_ship["lives"]
    display = ""

    for i in range(6):
        if hp >= i + 1:
            display += full
        elif hp > i:
            display += half

    if hp < 6:
        display += SHIP_ABLAZE

    await ctx.send(f"**{target.display_name}’s Ship:**\n{display}")

    # --- If ship sunk ---
    if target_ship["lives"] <= 0:
        await ctx.send(f"{SINKING_SHIP} → {SANK_SHIP}")
        await asyncio.sleep(2)
        await ctx.send(f"☠️ **{target.display_name}’s ship has sunk!**")
        await ctx.send(f"{RAFT} They’re stranded on a raft..")

        defender["status"] = "raft"
        save_db(db)

        # --- Rebuild sequence ---

        await asyncio.sleep(120)
        defender["status"] = "active"
        defender["ship"]["lives"] = 3
        await ctx.send(f"⚓ **{target.display_name}** has rebuilt their ship and returned to the sea!")

    save_db(db)

# ============= COMMANDS =============

async def setup(bot):

  @bot.command(name="clan")
  async def clan_cmd(ctx, *, role_name):
    clan_manager.create_clan(role_name)
    clan_manager.join_clan(role_name, str(ctx.author.id))
    await ctx.send(f"🛡️ You joined/created clan **{role_name}**")

  @bot.command(name="manual")
  async def manual_cmd(ctx):
    await game_manual(ctx)

  @bot.command(name="sail")
  async def sail_cmd(ctx):
    await sail(ctx)

  @bot.command(name="status")
  async def status_cmd(ctx):
    await status(ctx)

  @bot.command(name="repair")
  async def repair_cmd(ctx):
    await repair(ctx)

  @bot.command(name="attack")
  async def attack_cmd(ctx):
    await attack(ctx)

  @bot.command(name="chest")
  async def chest_cmd(ctx):
    await chest(ctx)

  @bot.command(name="open")
  async def open_chest_cmd(ctx, *, chest_name: str):
    await open_chest(ctx, chest_name=chest_name)

  @bot.command(name="store")
  async def store_cmd(ctx, item_name: str, amount: int, *, chest_name: str):
    await store_item(ctx, item_name, amount, chest_name=chest_name)

  @bot.command(name="pick")
  async def pick_cmd(ctx, item_name: str):
    await pick(ctx, item_name)

  @bot.command(name="bury")
  async def bury_chest_cmd(ctx, *, chest_name: str):
      await bury_chest(ctx, chest_name = chest_name)

  @bot.command(name="unbury")
  async def unbury_cmd(ctx, *, chest_name: str):
    await handle_unbury(ctx, chest_name = chest_name)   # renamed

  @bot.command(name="steal")
  async def steal_cmd(ctx, target: discord.Member, *, chest_name: str):
      await steal(ctx, target, chest_name = chest_name)

  @bot.command(name="burn")
  async def burn_chest_cmd(ctx, *, chest_name: str):
      await burn_chest(ctx, chest_name = chest_name)

  @bot.command(name="build")
  async def build_chest_cmd(ctx):
    await build_chest(ctx)

  @bot.command(name="fetch")
  async def fetch_resources_cmd(ctx, *, chest_name: str):
      await fetch_resources(ctx, chest_name = chest_name)

  @bot.command(name="cannonballs")
  async def cannonballs_cmd(ctx):
      await cannonballs(ctx)

  @bot.command(name="clan_create")
  async def clan_create_cmd(ctx, *, role_name: str):
      await clan_create(ctx, role_name=role_name)

  @bot.command(name="join")
  async def clan_join_cmd(ctx, *, clan_name: str):
      await clan_join(ctx, clan_name=clan_name)

  @bot.command(name="clan_remove")
  async def clan_remove_cmd(ctx, *, clan_name: str):
      await clan_remove(ctx, clan_name=clan_name)

  @bot.command(name="clan_members")
  async def clan_members_cmd(ctx, *, clan_name: str):
      await clan_members(ctx, clan_name=clan_name)

  @bot.command(name="clanwar")
  async def clanwar_cmd(ctx):
      await clanwar(ctx)

  @bot.command(name="clan_lb")
  async def clan_leaderboard_cmd(ctx):
      await clan_leaderboard(ctx)
      
    

#------- STATUS BAR--------------

async def status(ctx):
    user_id = str(ctx.author.id)
    username = ctx.author.name

    db = load_db()
    user = db.setdefault(user_id, {})
    ship = user.setdefault("ship", {"lives": 6, "status": "port", "storage": {}})
    inv = user.setdefault("inventory", {})

    # --- Normalize lives ---
    raw_lives = ship.get("lives", 6)
    if isinstance(raw_lives, list):
        raw_lives = raw_lives[0] if raw_lives else 6
    try:
        lives = float(raw_lives)
    except Exception:
        lives = 6.0

    # Clamp between 0–6
    lives = max(0.0, min(lives, 6.0))
    ship["lives"] = lives
    user["ship"] = ship

    # --- Default inventory ---
    inv.setdefault("timber", 0)
    inv.setdefault("cannonballs", 0)
    inv.setdefault("gunpowder", 0)
    user.setdefault("island", f"**{username}**'s Island")

    # Persist database
    db[user_id] = user
    save_db(db)

    # --- Health bar display (1 life = 1 heart, 0.5 = half heart) ---
    full_hearts = int(lives)  # full hearts
    half_heart = 1 if (lives - int(lives)) >= 0.5 else 0

    hearts = FULL_LIVE * full_hearts
    if half_heart:
        hearts += HALF_LIVE

    if lives <= 0:
        hearts = f"{SANK_SHIP} (Sunk!)"

    # --- Fix cannonball legacy lists ---
    cb = inv.get("cannonballs", 0)
    if isinstance(cb, list):
        cb = cb[0] if cb else 0
    try:
        cb = int(cb)
    except Exception:
        cb = 0
    inv["cannonballs"] = cb
    user["inventory"] = inv
    db[user_id] = user
    save_db(db)

    # --- Inventory display ---
    bag_display = (
        f"{TIMBER}  {inv.get('timber', 0)}  "
        f"{IRON_SHELL}  {inv.get('cannonballs', 0)}  "
        f"{GUNPOWDER}  {inv.get('gunpowder', 0)}"
    )

    # --- Embed display ---
    embed = discord.Embed(
        title=f"{SAIL_SHIP} {username}'s Status 🌊",
        description=(
            f"⛵ **Ship Health:** {hearts}\n\n"
            f"🎒 **Bag:** {bag_display}\n"
            f"{ISLAND} **Island:** {user['island']}"
        ),
        color=discord.Color.teal()
    )
    embed.set_footer(text="Bloop Pirates | Rule the seas!")

    await ctx.send(embed=embed)



# =========⚓ CHEST SYSTEM===========

#----------- Chest show---------


async def chest(ctx):
    """Shows all chests the user owns."""
    user_id = str(ctx.author.id)
    username = ctx.author.name
    islands = load_islands()

    # Ensure the user has default chests
    if user_id not in islands:
        islands[user_id] = {"chests": {}}

    chests = islands[user_id]["chests"]

    if not chests:
        for i in range(1, 4):
            chest_name = f"{username}'s Chest {i}"
            chests[chest_name] = {
                "owner": user_id,
                "location": "island",
                "status": "buried",
                "items": {},
                "capacity": 15
            }
        save_islands(islands)
        chests = islands[user_id]["chests"]

    # Show all chests
    # Show all chests (embed version)

    embed = discord.Embed(
    title=f"🏴‍☠️ {username}'s Treasure Chests",
    description=f"You currently own **{len(chests)}/3** chests.",
    color=discord.Color.gold()
)

    for name, data in chests.items():
      total_items =                           sum(data["items"].values()) if              data["items"] else 0
      emoji = TREASURE_CHEST_CLOSED if          data["status"] == "buried" else TREASURE_CHEST_OPEN
      embed.add_field(
        name=f"{emoji} {name}",
        value=f"**{total_items}/15** items\nStatus: `{data['status']}`",
        inline=False
    )

    embed.set_footer(text="Use 'blp open <chest name>' to open a chest.")
    await ctx.send(embed=embed)

#----------- Chest Open-------------


async def open_chest(ctx, *, chest_name: str):
    """Opens a specific chest to view items."""
    user_id = str(ctx.author.id)
    islands = load_islands()

    #---------- verification---------
    if user_id not in islands or "chests" not in islands[user_id]:
      await ctx.send("❌ You don’t own any chests yet.")
      return

    chests = islands[user_id]["chests"]

# make sure chest exists AND belongs to this user
    if chest_name not in chests:
        await ctx.send("❌ You don't own a chest with that name.")
        return

    chest = chests[chest_name]

# extra safety check(in case if data gets mixed)
    if chest["owner"] != user_id:
        await ctx.send("❌ That chest doesn't belong to you!")
        return



# ------ chest owner matching---------
    chests = islands[user_id]["chests"]
    matched = None
    for name in chests.keys():
      if chest_name.lower() in name.lower():
        matched = name
        break

      if not matched:
        await ctx.send("❌ You don’t own a chest with that name.")
      return

    chest = chests[matched]

#---------- verification over--------


    chest = islands[user_id]["chests"][chest_name]
    emoji = TREASURE_CHEST_OPEN

    if not chest["items"]:
        await ctx.send(f"{emoji} **{chest_name}** is empty.")
        return

    items_list = "\n".join([f"• {item}: {qty}" for item, qty in chest["items"].items()])
    await ctx.send(f"{emoji} **{chest_name}** contains:\n{items_list}")


# -------- Chest store ------------

async def store_item(ctx, item_name: str, amount: int, *, chest_name: str):
    """Stores a specific amount of an item into a chest."""
    user_id = str(ctx.author.id)
    db = load_db()
    islands = load_islands()

    user = db.get(user_id)
    if not user:
        await ctx.send("❌ You don’t have an account yet!")
        return

    inv = user.get("inventory", {})

    # normalize the stored value in case it's wrapped in a list
    if isinstance(inv.get(item_name), list):
     inv[item_name] = inv[item_name][0]

    # make sure then item exists and has enough amount 
    if item_name not in inv or inv[item_name] < amount:
        await ctx.send(f"❌ You don’t have `{amount}` of `{item_name}` to store.")
        return

    # Make sure the chest exists
    if user_id not in islands or chest_name not in islands[user_id]["chests"]:
        await ctx.send("❌ You don’t own a chest with that name.")
        return

    chest = islands[user_id]["chests"][chest_name]
    total_items = sum(chest["items"].values())

    if total_items + amount > chest["capacity"]:
        await ctx.send(f"❌ Chest is full! It can only hold {chest['capacity']} items.")
        return

    # Move the specified amount
    inv[item_name] -= amount
    if inv[item_name] == 0:
        del inv[item_name]

    chest["items"][item_name] = chest["items"].get(item_name, 0) + amount

    # Save everything
    user["inventory"] = inv
    db[user_id] = user
    islands[user_id]["chests"][chest_name] = chest
    save_db(db)
    save_islands(islands)

    await ctx.send(f"{TREASURE_CHEST_CLOSED} You stored **{amount}× {item_name}** in **{chest_name}**!")


# --------- chest pick-------------

async def pick(ctx, item_name: str, amount: int = 1):
    """
    Pick `amount` of item_name from the first chest on the user's island that contains it.
    Defensive: handles item counts stored as int, str, or [int], and inventory values similarly.
    Enforces inventory limit (15 total items).
    """
    user_id = str(ctx.author.id)
    username = ctx.author.name

    # sanitize amount
    try:
        amount = int(amount)
        if amount <= 0:
            raise ValueError()
    except Exception:
        await ctx.send("❌ Invalid amount. Use a positive whole number.")
        return

    # load DBs
    db = load_db()               # bloop_users.json
    islands = load_islands()     # islands.json

    # ensure user exists in main db
    ensure_user(db, user_id)
    user = db.setdefault(user_id, {})
    inventory = user.setdefault("inventory", {})

    # ensure island exists
    if user_id not in islands:
        # create default island entry (keeps older behaviour)
        islands[user_id] = {
            "owner": username,
            "island_name": f"{username}'s Island",
            "chests": {},
            "allowed_users": [],
            "resources": {"timber": 0, "gunpowder": 0}
        }
        save_islands(islands)

    current_island = islands[user_id]

    # ensure chests key exists
    current_island.setdefault("chests", {})
    chests = current_island["chests"]

    if not chests:
        await ctx.send(f"{TREASURE_CHEST_CLOSED if 'TREASURE_CHEST_CLOSED' in globals() else '🏴‍☠️'} No chests found on your island!")
        return

    item_name = item_name.lower()

    # helper normalizer (safe conversion to int)
    def norm_to_int(v):
        if isinstance(v, list):
            v = v[0] if v else 0
        try:
            return int(v)
        except Exception:
            return 0

    # Find the first chest that contains the item (owner's chests only)
    found_chest_name = None
    found_chest_items = None
    for cname, cdata in chests.items():
        # cdata can be { "items": {...}, "owner": "...", ... }
        if not isinstance(cdata, dict):
            continue
        items = cdata.get("items", {})
        # Some earlier code stored items at chest root; handle both
        if item_name in items:
            found_chest_name = cname
            found_chest_items = items
            break
        # fallback: if cdata itself directly contains items mapping (legacy)
        if item_name in cdata:
            # treat cdata as items mapping
            found_chest_name = cname
            found_chest_items = cdata
            break

    if not found_chest_items:
        await ctx.send(f"❌ No `{item_name}` found in any chest on your island!")
        return

    # amount available in chest
    chest_amount = norm_to_int(found_chest_items.get(item_name, 0))
    if chest_amount < amount:
        await ctx.send(
            f"❌ Not enough `{item_name}` in **{found_chest_name}** — you have **{chest_amount}**, tried to pick **{amount}**."
        )
        return

    # Calculate total inventory items (normalize every value)
    total_items = len(inventory)

    # debug print to console (remove later if you want)
    print(f"DEBUG: user {user_id} inventory total before pick = {total_items}, inventory={inventory}")

    INVENTORY_LIMIT = 15
    if total_items + amount > INVENTORY_LIMIT:
        await ctx.send(
            f"⚠️ You don't have enough inventory space. Current: {total_items}/{INVENTORY_LIMIT}, trying to pick {amount}."
        )
        return

    # remove from chest
    new_chest_amount = chest_amount - amount
    if new_chest_amount <= 0:
        # remove the key entirely
        found_chest_items.pop(item_name, None)
    else:
        # store as int (or list if you prefer legacy); choose int for clean DB
        found_chest_items[item_name] = new_chest_amount

    # add to inventory (normalize existing)
    inv_now = norm_to_int(inventory.get(item_name, 0))
    inventory[item_name] = inv_now + amount

    # persist both DBs
    user["inventory"] = inventory
    db[user_id] = user
    save_db(db)

    current_island["chests"] = chests
    islands[user_id] = current_island
    save_islands(islands)

    await ctx.send(f"✅ You picked **{amount} x {item_name}** from **{found_chest_name}** and added to your inventory.")


# ======== BURY/UNBURY CHESTS ======

#----------- chest bury-------------
async def bury_chest(ctx, *, chest_name: str):
    import copy

    user_id = str(ctx.author.id)
    islands = load_islands()

    if not isinstance(islands, dict) or len(islands) == 0:
        await ctx.send("⚠️ Island data unavailable. Try again later.")
        return

    # ✅ Ensure island always has base structure
    if user_id not in islands:
        await ctx.send("❌ You don’t have an island yet.")
        return

    island = islands[user_id]
    if "chests" not in island:
        island["chests"] = {}

    chests = island["chests"]

    # 🔍 Chest lookup
    if chest_name not in chests:
        await ctx.send("❌ No chest found with that name on your island.")
        return

    chest = chests[chest_name]

    # ✅ Ownership check
    if str(chest.get("owner")) != user_id:
        await ctx.send("⚠️ You can only bury your own chests.")
        return

    # ✅ Prevent duplicate burying
    if str(chest.get("status", "unburied")).lower() == "buried" or chest.get("buried", False):
        await ctx.send("⚠️ That chest is already buried.")
        return

    # ✅ Sync both flags
    chest["status"] = "buried"
    chest["buried"] = True
    chests[chest_name] = chest
    island["chests"] = chests
    islands[user_id] = island

    # ✅ Refill missing island keys (to avoid overwriting)
    island.setdefault("owner", ctx.author.name)
    island.setdefault("allowed_users", [])
    island.setdefault("resources", {"timber": 0, "gunpowder": 0})

    save_islands(islands)
    await ctx.send(f"✅ You buried **{chest_name}** safely on your island.")
    
    # --------- unbury chest ------------

async def handle_unbury(ctx, *, chest_name: str):
    user_id = str(ctx.author.id)

    islands = load_islands()
    if user_id not in islands:
        await ctx.send("❌ You don’t have an island yet.")
        return

    island = islands[user_id]
    chests = island.get("chests", {})

    # --- allow partial / case-insensitive matching so users don't need full prefix ---
    found_key = None
    # prefer exact (case-sensitive) first, then case-insensitive exact, then substring
    if chest_name in chests:
        found_key = chest_name
    else:
        lower_name = chest_name.strip().lower()
        # exact case-insensitive
        for key in chests.keys():
            if key.lower() == lower_name:
                found_key = key
                break
        # substring match fallback
        if not found_key:
            for key in chests.keys():
                if lower_name in key.lower():
                    found_key = key
                    break

    if not found_key:
        await ctx.send("❌ No chest found with that name on your island.")
        return

    chest = chests[found_key]

    # Only owner can unbury
    if str(chest.get("owner")) != user_id:
        await ctx.send("⚠️ You can only unbury your own chests.")
        return

    # --- Determine buried state from either boolean or status string ---
    # Treat truthy boolean True as buried; if 'status' exists prefer that for clarity
    is_buried = False
    if "status" in chest:
        is_buried = str(chest.get("status", "")).lower() == "buried"
    else:
        # chest.get("buried") may be a real boolean in your JSON
        is_buried = bool(chest.get("buried", False))

    if not is_buried:
        await ctx.send("⚠️ That chest is already unburied.")
        return

    # Update both representations so data stays consistent
    chest["buried"] = False        # boolean canonical
    chest["status"] = "unburied"  # optional human-friendly field

    # Save back
    chests[found_key] = chest
    island["chests"] = chests
    islands[user_id] = island
    save_islands(islands)

    await ctx.send(f"✅ You unburied **{found_key}**. Be careful!")



# --------- CHEST STEALING ----------


async def steal(ctx, target: discord.Member, *, chest_name: str):
    """
    Allows a player to steal another user's chest only if it's unburied.
    Safely updates islands.json with validation and backup protection.
    """
    import shutil, datetime

    thief_id = str(ctx.author.id)
    victim_id = str(target.id)

    if thief_id == victim_id:
        await ctx.send("⚠️ You can’t steal from yourself.")
        return

    # ---------------- Load & Validate ----------------
    islands = load_islands()
    if not isinstance(islands, dict) or len(islands) == 0:
        await ctx.send("⚠️ Island data unavailable or corrupted. Try again later.")
        return

    thief_island = islands.get(thief_id)
    victim_island = islands.get(victim_id)

    if not victim_island:
        await ctx.send("❌ The target doesn’t have an island.")
        return
    if not thief_island:
        await ctx.send("❌ You don’t have an island yet.")
        return

    victim_chests = victim_island.get("chests", {})
    thief_chests = thief_island.get("chests", {})

    # ---------------- Find the Chest ----------------
    found_key = None
    for k in victim_chests:
        if k.lower() == chest_name.lower():
            found_key = k
            break

    if not found_key:
        await ctx.send("❌ No chest found with that name on their island.")
        return

    chest = victim_chests[found_key]
    status = chest.get("status", "unburied").lower()
    buried_flag = chest.get("buried", False)

 # ------ Check Conditions ----------------
    if status == "buried" or buried_flag:
        await ctx.send("💨 The chest is buried deep underground. You couldn’t steal it!")
        return

# ------- Backup islands.json ---------
    try:
        backup_path = f"{ISLANDS_FILE}.bak_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy(ISLANDS_FILE, backup_path)
    except Exception as e:
        print(f"[WARN] Couldn’t create backup before stealing: {e}")

# ----- Safe Data Transfer ----------------
    transferred = copy.deepcopy(chest)
    transferred["owner"] = thief_id
    transferred["status"] = "unburied"
    transferred["buried"] = False
    transferred["location"] = "stolen"

    # Create unique chest name if collision
    new_name = chest_name
    while new_name in thief_chests:
        new_name += "_stolen"

    thief_chests[new_name] = transferred
    victim_chests.pop(found_key, None)

    victim_island["chests"] = victim_chests
    thief_island["chests"] = thief_chests

    islands[victim_id] = victim_island
    islands[thief_id] = thief_island

# -------- Atomic Save ----------------
    
    tmp_path = f"{ISLANDS_FILE}.tmp"
    try:
        with open(tmp_path, "w") as f:
            json.dump(islands, f, indent=4)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, ISLANDS_FILE)
    except Exception as e:
        await ctx.send("❌ Failed to save data. Theft canceled.")
        print(f"[ERROR] Save failed: {e}")
        return
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except:
                pass

# ---------------- Success Message ----
    await ctx.send(
        f"🏴‍☠️ **{ctx.author.name}** successfully stole **{found_key}** "
        f"from **{target.name}**’s island!"
    )


# ===== BURING AND BULDING ==========

# ----- burning chest ----------


async def burn_chest(ctx, *, chest_name: str):
    user_id = str(ctx.author.id)

    # Load both databases
    islands = load_islands()
    users = load_db()

    # Basic validation
    if user_id not in islands:
        await ctx.send("❌ You don’t have an island yet.")
        return
    if user_id not in users:
        await ctx.send("⚠️ Your player data wasn’t found.")
        return

    island = islands[user_id]
    chests = island.get("chests", {})

    if chest_name not in chests:
        await ctx.send("❌ No chest found with that name on your island.")
        return

    chest = chests[chest_name]

    # Ownership check
    if chest.get("owner") != user_id:
        await ctx.send("⚠️ You can only burn your own chests.")
        return

    # Remove the chest safely
    del chests[chest_name]
    island["chests"] = chests
    islands[user_id] = island

    # Add timber reward (+5)
    inventory = users[user_id].get("inventory", {})
    timber_val = inventory.get("timber", 0)

# 🧹 Normalize the value (if it's not a number, reset it)
    if not isinstance(timber_val, (int, float)):
        timber_val = 0

        inventory["timber"] =                  timber_val + 5
        users[user_id]["inventory"] =          inventory

    # Save both files safely
    save_islands(islands)
    save_db(users)

    await ctx.send(f"{BURNING_CHEST} 💥 **{chest_name}** reduced to ashes! You gained 🪵 **+5 Timber**.")


# ------- building chest ----------

async def build_chest(ctx):
    user_id = str(ctx.author.id)
    username = ctx.author.name

    # load DBs
    users_db = load_db()
    islands = load_islands()

    # basic existence checks
    if not isinstance(users_db, dict) or not isinstance(islands, dict):
        await ctx.send("⚠️ Data unavailable. Try again later.")
        return

    if user_id not in users_db:
        await ctx.send("⚠️ Your player profile wasn't found. Create a profile first.")
        return
    if user_id not in islands:
        await ctx.send("⚠️ You don't have an island yet.")
        return

    user_data = users_db[user_id]
    island = islands[user_id]

    inventory = user_data.setdefault("inventory", {})

    # normalize timber value (legacy list/string -> int)
    raw_timber = inventory.get("timber", 0)
    if isinstance(raw_timber, list):
        raw_timber = raw_timber[0] if raw_timber else 0
    try:
        timber = int(raw_timber)
    except Exception:
        timber = 0

    # cost & limit
    COST = 5
    CHEST_LIMIT = 3

    # check timber
    if timber < COST:
        await ctx.send(f"❌ You need **{COST}** 🪵 timber to build a chest. You have **{timber}**.")
        return

    # ensure chests structure
    chests = island.setdefault("chests", {})

    # enforce chest limit
    if len(chests) >= CHEST_LIMIT:
        await ctx.send(f"⚠️ You already own **{len(chests)}/{CHEST_LIMIT}** chests. Burn one to free space.")
        return

    # compute next unique chest number (scan existing names for trailing number)
    max_n = 0
    for name in chests.keys():
        # try to find a trailing number after 'Chest '
        try:
            if "Chest" in name:
                tail = name.split("Chest")[-1].strip()
                # tail might be like '3' or "3" or "3 - extra"; try to extract integer prefix
                token = tail.split()[0]
                n = int(token)
                if n > max_n:
                    max_n = n
        except Exception:
            continue
    next_n = max_n + 1 if max_n >= 1 else len(chests) + 1
    # safety: cap next_n to CHEST_LIMIT (but we already enforced len < limit)
    chest_name = f"{username}'s Chest {next_n}"

    # ensure unique chest_name (fallback)
    i = 1
    base = chest_name
    while chest_name in chests:
        i += 1
        chest_name = f"{username}'s Chest {next_n}_{i}"

    # create chest
    chests[chest_name] = {
        "owner": user_id,
        "location": "island",
        "status": "unburied",
        "buried": False,
        "items": {},
        "capacity": 15
    }
    island["chests"] = chests
    islands[user_id] = island

    # deduct timber and normalize store as int
    inventory["timber"] = timber - COST
    user_data["inventory"] = inventory
    users_db[user_id] = user_data

    # safe save
    save_db(users_db)
    save_islands(islands)

    await ctx.send(f"⚙️ Built **{chest_name}** using {COST} 🪵 timber! You now have **{inventory.get('timber',0)}** 🪵 left.")



# --------- BUILD SHIP ----------------



# ========== ISLAND SYSTEM =========

# --------- Island fetch ----------

FETCH_COOLDOWN = 3 * 60 * 60  # 3 hours

async def fetch_resources(ctx, *, chest_name: str):
    user_id = str(ctx.author.id)
    username = ctx.author.name

    if not chest_name:
        await ctx.send("correct way: `Blp fetch <chest name>`")
        return

    islands = load_islands()
    if user_id not in islands:
        await ctx.send("❌ You don’t have an island yet.")
        return

    island = islands[user_id]
    chests = island.get("chests", {})

    if chest_name not in chests:
        await ctx.send("❌ No chest found with that name on your island.")
        return

    chest = chests[chest_name]
    if str(chest.get("status", "unburied")).lower() == "buried":
        await ctx.send("⚠️ You can’t fetch resources with a buried chest.")
        return

    now = time.time()
    last_fetch = island.get("last_fetch", 0)
    remaining = int((last_fetch + FETCH_COOLDOWN) - now)

    if remaining > 0:
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        seconds = remaining % 60
        await ctx.send(
            f"⏳ You can fetch again in **{hours}h {minutes}m {seconds}s.**"
        )
        return

    island["last_fetch"] = now
    save_islands(islands)

    # 🌴 Your preferred intro message
    await ctx.send(ISLAND)
    await ctx.send(f"⚙️⛏️ **You're fetching resources from your Island**")

    for i in range(3):
        await asyncio.sleep(20)
        res_type = random.choice(["timber", "gunpowder"])
        amount = random.randint(2, 5)

        items = chest.get("items", {})
        items[res_type] = items.get(res_type, 0) + amount
        chest["items"] = items
        chests[chest_name] = chest
        island["chests"] = chests
        islands[user_id] = island

        save_islands(islands)
        await ctx.send(f"🌿 +{amount} {res_type} added to **{chest_name}** ({i+1}/3)")

    await ctx.send(f"✅ Fetch complete! Check **{chest_name}** for new resources.")


# ------- make cannon balls ----------


async def cannonballs(ctx):
    user_id = str(ctx.author.id)
    db = load_db()

    user_data = db.get(user_id)
    if not user_data:
        await ctx.send("❌ You don’t have an account yet. Try again after you start your adventure!")
        return

    inventory = user_data.get("inventory", {})
    gunpowder = inventory.get("gunpowder", 0)

    # 🧹 Normalizer (convert lists or strings to int safely)
    if isinstance(gunpowder, list):
        gunpowder = gunpowder[0] if gunpowder else 0
    elif isinstance(gunpowder, str):
        gunpowder = int(gunpowder) if gunpowder.isdigit() else 0

    # ⚙️ Check if enough gunpowder
    if gunpowder < 1:
        await ctx.send("💥 You don’t have enough gunpowder to make cannonballs!")
        return

    # ⚙️ Crafting logic
    inventory["gunpowder"] = gunpowder - 1
    inventory["cannonballs"] = inventory.get("cannonballs", 0) + 5

    user_data["inventory"] = inventory
    db[user_id] = user_data
    save_db(db)

    await ctx.send("⚙️💣 You’ve successfully crafted **5 cannonballs** using 1 gunpowder!")




# ========  CLAN SYSTEM ===============

# ---------- clan create -----------

CLANS_FILE = "clans.json"

def load_clans():
    if not os.path.exists(CLANS_FILE):
        with open(CLANS_FILE, "w") as f:
            json.dump({"clans": {}}, f, indent=4)

    with open(CLANS_FILE, "r") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            data = {"clans": {}}

    # 🪄 ensure each clan has xp + members fields
    for clan_name, info in data.get("clans", {}).items():
        if "xp" not in info:
            info["xp"] = 0
        if "members" not in info:
            info["members"] = []

    # save back if anything was added
    with open(CLANS_FILE, "w") as f:
        json.dump(data, f, indent=4)

    return data

def save_clans(data):
    with open(CLANS_FILE, "w") as f:
        json.dump(data, f, indent=4)



# ---------- clan create -----------


async def clan_create(ctx, *, role_name: str):
    """Assign a role as a clan. Admin-only."""

    # Admin check
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("⚠️ Only admins can create clans.")
        return

    clans = load_clans()

    # Check if role exists
    role = discord.utils.get(ctx.guild.roles, name=role_name)
    if not role:
        await ctx.send("❌ No such role found in this server.")
        return

    # Check if role already registered
    for cname, cdata in clans["clans"].items():
        if cdata["role_id"] == role.id:
            await ctx.send(f"⚠️ The role is already registered as **{cname}** clan.")
            return

    # Save clan
    clans["clans"][role_name] = {
        "role_id": role.id,
        "members": [],
        "xp": 0,
    }
    save_clans(clans)
    await ctx.send(f"✅ Clan **{role_name}** successfully registered!")


# --------- join clan ---------------


async def clan_join(ctx, *, clan_name: str):
    guild = ctx.guild
    user = ctx.author

    # guard: command used in DMs?
    if guild is None:
        await ctx.send("❌ Use this command in a server, not in DMs.")
        return

    # Load clans via helper (returns dict like {"clans": {...}} usually)
    clans_data = load_clans()
    # Normalise two possible shapes:
    # A) {"clans": { "ClanName": {...}, ... }}
    # B) {"clans": { "<guild_id>": { "ClanName": {...} } } }
    all_clans_root = clans_data.get("clans", {})
    if str(guild.id) in all_clans_root and isinstance(all_clans_root[str(guild.id)], dict):
        guild_clans = all_clans_root[str(guild.id)]
    else:
        # fallback: assume clans are stored directly under "clans"
        guild_clans = all_clans_root

    # Debug helper (uncomment if you want console output)
    print(f"[DEBUG] guild_clans keys for guild {guild.id}: {list(guild_clans.keys())}")

    # Check existence
    if clan_name not in guild_clans:
        # Try case-insensitive match as a friendly fallback
        match = None
        for k in guild_clans.keys():
            if k.lower() == clan_name.lower():
                match = k
                break
        if match:
            clan_name = match  # use canonical key
        else:
            await ctx.send("❌ That clan doesn't exist in this server!")
            return

    # Remove old clan roles if any (safely)
    for cname, clan_info in guild_clans.items():
        rid = clan_info.get("role_id")
        if rid is None:
            continue
        try:
            rid_int = int(rid)
        except Exception:
            # bad stored role id; skip but warn in console
            print(f"[WARN] bad role_id for clan {cname}: {rid!r}")
            continue
        role = guild.get_role(rid_int)
        if role and role in user.roles:
            try:
                await user.remove_roles(role)
            except Exception as e:
                print(f"[WARN] failed to remove role {role} from {user}: {e}")

    # Grab role id for the chosen clan and convert to int
    raw_role_id = guild_clans[clan_name].get("role_id")
    if raw_role_id is None:
        await ctx.send("⚠️ That clan has no role assigned (ask admin to recreate it).")
        return

    try:
        clan_role_id = int(raw_role_id)
    except Exception:
        await ctx.send("⚠️ Clan role id saved in an unexpected format. Ask an admin to fix it.")
        print(f"[ERROR] invalid role_id for clan {clan_name}: {raw_role_id!r}")
        return

    clan_role = guild.get_role(clan_role_id)
    if not clan_role:
        await ctx.send("⚠️ Clan role not found on this server. Admin may need to re-create the clan role.")
        return

    # Add the role
    try:
        await user.add_roles(clan_role)
    except Exception as e:
        await ctx.send("⚠️ Couldn't assign the clans role. Check the bot's role position and permissions.")
        print(f"[ERROR] failed to give role {clan_role} to {user}: {e}")
        return

   # Add user to the clan's member list in clans.json
    try:
        clans_data = load_clans()
        all_clans_root = clans_data.get("clans", {})
        guild_id = str(ctx.guild.id)

    # Handle both structures (per guild or global)
        if guild_id in all_clans_root:
            guild_clans = all_clans_root[guild_id]
        else:
            guild_clans = all_clans_root

        if clan_name in guild_clans:
            members = guild_clans[clan_name].setdefault("members", [])
            
            if str(user.id) not in members:
                members.append(str(user.id))
        save_clans(clans_data)
    except Exception as e:
        print(f"[WARN] Failed to add {user} to clan members list: {e}")


    

    # Persist player's clan
    #try:
     #   with open("players.json", "r") #as f:
#            players = json.load(f)
 #   except Exception:
 #       players = {}

 #   pid = str(user.id)
 #   players.setdefault(pid, {})["clan"] = clan_name
   # with open("players.json", "w") as f:
     #   json.dump(players, f, indent=4)

    await ctx.send(f"🏴‍☠️ {user.mention} has joined the **{clan_name}** clan!")


# ----- remove clan role ----------

async def clan_remove(ctx, *, clan_name: str):
    guild = ctx.guild
    clans_data = load_clans()
    clans = clans_data.get("clans", {})

    if not ctx.author.guild_permissions.administrator:
        await ctx.send("⚠️ Only admins can remove clans.")

    if clan_name not in clans:
        await ctx.send("❌ That clan doesn’t exist!")
        return

    # Get the role from the stored role_id
    role_id = clans[clan_name].get("role_id")
    role = guild.get_role(role_id)

    # Delete the role if it exists
    if role:
        try:
            await role.delete(reason=f"Clan removed by {ctx.author}")
        except discord.Forbidden:
            await ctx.send("⚠️ I don’t have permission to delete that role!")
            return

    # Remove the clan from JSON
    del clans[clan_name]
    save_clans({"clans": clans})

    await ctx.send(f"🗑️ The clan **{clan_name}** and its role have been removed successfully.")



# ======== CLAN BATTLE =============


 # ------ Clan show -----------

async def clan_members(ctx, *, clan_name: str):
    guild = ctx.guild
    clans_data = load_clans()
    clans = clans_data.get("clans", {})

    # Check if clan exists
    if clan_name not in clans:
        await ctx.send("❌ That clan doesn't exist in this server!")
        return

    clan_info = clans[clan_name]
    member_ids = clan_info.get("members", [])

    if not member_ids:
        await ctx.send(f"🏴‍☠️ **{clan_name}** has no members yet!")
        return

    # Convert IDs to actual member mentions or names
    member_mentions = []
    for m_id in member_ids:
        member = guild.get_member(int(m_id))
        if member:
            member_mentions.append(member.mention)
        else:
            member_mentions.append(f"<@{m_id}>")  # fallback if user left the server

    members_display = "\n".join(member_mentions)
    embed = discord.Embed(
        title=f"🏴‍☠️ Clan Members - {clan_name}",
        description=members_display,
        color=discord.Color.gold()
    )
    embed.set_footer(text=f"Total Members: {len(member_ids)}")

    await ctx.send(embed=embed)


# ===== CLAN BATTLE ==========


async def clanwar(ctx):
    import asyncio
    import discord
    from discord.ui import View, Button

    participants = []

    # ====== JOIN PHASE ======
    embed = discord.Embed(
        title="⚔️ Clan War Incoming!",
        description="Press **Join** to enter the battle!\nYou have 15 seconds!",
        color=discord.Color.orange()
    )

    view = View()
    join_button = Button(label="Join", style=discord.ButtonStyle.green)

    async def join_callback(interaction):
        if interaction.user not in participants:
            participants.append(interaction.user)
            await interaction.response.send_message(f"{interaction.user.mention} joined the war!", ephemeral=True)
        else:
            await interaction.response.send_message("You're already in!", ephemeral=True)

    join_button.callback = join_callback
    view.add_item(join_button)

    msg = await ctx.send(embed=embed, view=view)
    await asyncio.sleep(15)

    view.clear_items()
    await msg.edit(content="⚓ Joining time’s up!", view=None)

    if len(participants) < 2:
        return await ctx.send("❌ Not enough participants to start a clan war!")

    # ====== GROUP BY CLAN ======
   # from utils import clan_load, clan_save, load_db, save_db  # Your helpers

    clan_data = load_clans()
    user_db = load_db()

    # Reverse lookup for members → clan
    member_to_clan = {}
    for clan_name, info in clan_data["clans"].items():
        for mid in info.get("members", []):
            member_to_clan[mid] = clan_name

    clans = {}
    for p in participants:
        pid = str(p.id)
        if pid not in member_to_clan:
            await ctx.send(f"⚠️ {p.mention} is not in any clan, skipping.")
            continue
        cname = member_to_clan[pid]
        clans.setdefault(cname, []).append(p)

    if len(clans.keys()) < 2:
        return await ctx.send("❌ Need at least 2 clans to battle!")

    clan_names = list(clans.keys())
    clan_a, clan_b = clan_names[0], clan_names[1]
    team_a, team_b = clans[clan_a], clans[clan_b]

    await ctx.send(
        f"🔥 **{clan_a}** vs **{clan_b}** has begun!\n"
        f"Attack using your normal PvP commands — you have **1 minute!**"
    )

    await asyncio.sleep(60)

    # ====== DETERMINE SURVIVORS ======
    def get_alive(team):
        alive = []
        for member in team:
            pid = str(member.id)
            ship_data = user_db.get(pid, {}).get("ship", {})
            lives = ship_data.get("lives", 0)
            status = user_db.get(pid, {}).get("status", "")
            if lives > 0 and status == "active":
                alive.append(member)
        return alive

    alive_a = get_alive(team_a)
    alive_b = get_alive(team_b)

    # ====== RESULT ======
    if len(alive_a) == len(alive_b):
        await ctx.send("🤝 The war ended in a **draw!** No rewards this time.")
        return

    winner = clan_a if len(alive_a) > len(alive_b) else clan_b
    survivors = alive_a if winner == clan_a else alive_b

    # ====== REWARD ======
    clan_data["clans"][winner]["xp"] += 100

    for survivor in survivors:
        sid = str(survivor.id)
        if sid not in user_db:
            continue
        user_db[sid]["fluffies"] = user_db[sid].get("fluffies", 0) + 100

    # Save back
    save_db(user_db)
    save_clans(clan_data)

    await ctx.send(
        f"🏆 **{winner}** emerges victorious!\n"
        f"🎖️ Each surviving member earned **100 fluffies!**\n"
        f"The clan gained **+100 XP!**"
    )



# ======== CLAN LEADERBOARD ==========


async def clan_leaderboard(ctx):
    from discord import Embed

    clans_data = load_clans()
    clans = clans_data.get("clans", {})

    if not clans:
        await ctx.send("⚓ No clans found yet, sailor!")
        return

    # Sort clans by XP
    sorted_clans = sorted(clans.items(), key=lambda x: x[1].get("xp", 0), reverse=True)

    # Create Embed
    embed = Embed(
        title="🏴‍☠️ Clan Leaderboard",
        description="Top clans ranked by XP!",
        color=discord.Color.gold()
    )

    rank_emojis = ["🥇", "🥈", "🥉"]

    for i, (clan_name, clan_info) in enumerate(sorted_clans, start=1):
        xp = clan_info.get("xp", 0)
        emoji = rank_emojis[i-1] if i <= 3 else f"#{i}"
        embed.add_field(
            name=f"{emoji} {clan_name}",
            value=f"**XP:** {xp}",
            inline=False
        )

    embed.set_footer(text="🏴 Fight hard, rise higher! | Bloop Premium")

    await ctx.send(embed=embed)