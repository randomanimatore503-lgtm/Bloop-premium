import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import json
import os
import random
from typing import Dict, List

# ---------- file path fix------------ 

# ----------------- Config -----------------
BOT_PREFIX = "Blp "
DATA_FILE = "bloop_users.json"
MAX_PLAYERS = 3
INVENTORY_SLOTS = 15
STACK_SIZE = 10

# Emojis (use the exact ids you gave)
FLUFFY_EMOJI = "<a:Fluffy:1428274705206612060>"
ANIM_SLOT = "<a:Blp_slotmachine:1427886140551331850>"
STATIC_SLOT = "<:static_slotmachine:1428335371044913184>"

# Snack items and their Fluffie values
SNACKS = [
    ("🍨", 5), ("🍬", 3), ("🍫", 6), ("🍭", 4), ("🍦", 7), ("🍰", 8),
    ("🥟", 9), ("🍡", 5), ("🧁", 10), ("🍮", 7), ("☕", 5), ("🥨", 4),
    ("🍟", 6), ("🍕", 8), ("🌮", 9), ("🍔", 9), ("🥞", 10), ("🥐", 8),
    ("🍿", 5), ("🍩", 6), ("🍪", 7), ("🥧", 9), ("🧇", 9), ("🍢", 6),
    ("🍙", 7), ("🍘", 8)
]
# Add 'nothing' ice item
NOTHING = ("🧊", 0)

# We'll weight 'nothing' a small chance
# Build a pool with weights by rarity feel (common snacks more likely)
ITEM_POOL = []
for emoji, val in SNACKS:
    # common weight
    ITEM_POOL.append((emoji, val))
# add several "nothing" entries so it sometimes happens
for _ in range(4):
    ITEM_POOL.append(NOTHING)


# ----- Helpers: persistent DB ---------



if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({}, f)

def load_db() -> Dict:
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_db(db: Dict):
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(db, f, indent=2)
    os.replace(tmp, DATA_FILE)

# Inventory helpers (stacked)
def ensure_user(db: Dict, user_id: str):
    if user_id not in db:
        db[user_id] = {"fluffies": 0, "inventory": {}}  # inventory: {emoji: [stack1, stack2,...]}
    return db[user_id]

def add_item_to_inventory(user_record: Dict, emoji: str, amount: int = 1):
    # ensure key
    inv = user_record["inventory"]
    if emoji not in inv:
        inv[emoji] = []
    stacks: List[int] = inv[emoji]
    # fill existing stacks
    for i in range(len(stacks)):
        if stacks[i] < STACK_SIZE:
            space = STACK_SIZE - stacks[i]
            add = min(space, amount)
            stacks[i] += add
            amount -= add
            if amount <= 0:
                return True
    # create new stacks as needed
    while amount > 0:
        add = min(amount, STACK_SIZE)
        if len(stacks) >= INVENTORY_SLOTS:
            # inventory slot cap reached globally? We'll still append per-item but we should
            # respect total slot limit — enforced at overall check before adding.
            # For now, return False so caller can handle full inventory.
            return False
        stacks.append(add)
        amount -= add
    return True

def total_slots_used(inv: Dict) -> int:
    return sum(
        len(stacks) if isinstance(stacks, list) else 1
        for stacks in inv.values()
    )

# ----------------- Bot setup -----------------


intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.messages = True

bot = commands.Bot(command_prefix=BOT_PREFIX, intents=intents)

# Active rounds stored in-memory
active_rounds = {}  # guild_id -> Round instance

# ----------------- Views &Buttons---------------

class JoinView(discord.ui.View):
    def __init__(self, round_obj):
        super().__init__(timeout=60)
        self.round = round_obj

    @discord.ui.button(label="Join", style=discord.ButtonStyle.green, emoji="✅")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.round.add_player(interaction)

class ClaimLeaveView(discord.ui.View):
    def __init__(self, round_obj, reward_id, owner_id):
        super().__init__(timeout=60)
        self.round = round_obj
        self.reward_id = reward_id
        self.owner_id = owner_id

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.success, emoji="🟢")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.round.claim_reward(interaction, self.reward_id)

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.danger, emoji="🔴")
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.round.leave_reward(interaction, self.reward_id)


# ----------------- Round Logic -----------------
class Round:
    def __init__(self, ctx_message: discord.Message):
        self.guild = ctx_message.guild
        self.channel = ctx_message.channel
        self.host_message = ctx_message  # message that initiated round
        self.players = []  # list of member objects
        self.player_ids = set()
        self.max_players = MAX_PLAYERS
        self.join_msg = None
        self.rewards = {}  # reward_id -> dict(owner_id, emoji, value, state) state: "reserved"|"left"|"claimed"
        self.reward_counter = 0
        self.lock = asyncio.Lock()

    async def start_join_phase(self):
        view = JoinView(self)
        embed = discord.Embed(
            title="🎰 Bloop Slot — Join the spin!",
            description=f"Press **Join** to secure a slot (max {self.max_players}).\nWhen {self.max_players} players join, the spin begins.\nJoin with the button — not a command. 🧁☁️",
            color=discord.Color.purple()
        )
        msg = await self.channel.send(embed=embed, view=view)
        self.join_msg = msg

        # Wait until either full or timeout
        try:
            # wait until players full
            await asyncio.wait_for(self._wait_for_full(), timeout=25)
        except asyncio.TimeoutError:
            # if at least 1 player present, continue; else cancel
            if len(self.players) == 0:
                await self.channel.send("No one joined the Blp spin. Round cancelled. ☁️")
                return False
        # proceed to spin
        await self._begin_spin()
        return True

    async def _wait_for_full(self):
        while len(self.players) < self.max_players:
            await asyncio.sleep(0.5)

    async def add_player(self, interaction: discord.Interaction):
        async with self.lock:
            user = interaction.user
            if user.id in self.player_ids:
                await interaction.response.send_message("You already joined!", ephemeral=True)
                return
            if len(self.players) >= self.max_players:
                await interaction.response.send_message("Slots are full!", ephemeral=True)
                return
            # add
            self.players.append(user)
            self.player_ids.add(user.id)
            await interaction.response.send_message(f"{user.mention} secured a slot! ☁️", ephemeral=False)
            # edit join embed to show players
            player_list = "\n".join([p.mention for p in self.players])
            embed = discord.Embed(
                title="🎰 Bloop Slot — Join the spin!",
                description=f"Players:\n{player_list}\n\nSlots left: {self.max_players - len(self.players)}",
                color=discord.Color.purple()
            )
            await self.join_msg.edit(embed=embed, view=self.join_msg.components[0].view)

    async def _begin_spin(self):
        # remove join view to prevent late joins
        try:
            await self.join_msg.edit(view=None)
        except:
            pass

        # Show the animated slot machine
        spin_message = await self.channel.send(ANIM_SLOT)
        # animate for random 1-3 seconds
        wait_time = random.uniform(1.0, 3.0)
        await asyncio.sleep(wait_time)
        # replace with static
        await spin_message.edit(content=STATIC_SLOT)

        # Now determine rewards for each player
        for p in self.players:
            emoji, val = random.choice(ITEM_POOL)
            # create reward id
            rid = str(self.reward_counter)
            self.reward_counter += 1
            self.rewards[rid] = {
                "owner_id": p.id,
                "emoji": emoji,
                "value": val,
                "state": "reserved",  # reserved / left / claimed
                "claimed_by": None,
                "message_id": None
            }
            # present result to the channel (one embed per player for clarity)
            amount_display = ""
            if emoji == NOTHING[0]:
                amount_display = f"**🧊 Nothing**"
            else:
                # For snack rewards, determine amount and display stacked format e.g. **3🍨**
                # Let's award 1-3 quantity randomly for most, or 1 for nothing
                qty = random.randint(1, 3)
                # calculate fluffie value as val * qty
                self.rewards[rid]["qty"] = qty
                self.rewards[rid]["value"] = val * qty
                amount_display = f"**{qty}{emoji}** — {self.rewards[rid]['value']} {FLUFFY_EMOJI}"

            owner_mention = f"<@{p.id}>"
            content = f"{owner_mention} — your spin result: {amount_display}\n\n🟢 **Claim** it (adds to your inventory) or 🔴 **Leave** it (others may claim if you leave it)."
            # We won't use an embed for the slot result (per your request); but format as message + buttons
            view = ClaimLeaveView(self, rid, p.id)
            msg = await self.channel.send(content, view=view)
            self.rewards[rid]["message_id"] = msg.id

        # start a cleanup task to remove unclaimed rewards after 60s
        asyncio.create_task(self._reward_cleanup_task())

    async def claim_reward(self, interaction: discord.Interaction, reward_id: str):
        async with self.lock:
            user = interaction.user
            if reward_id not in self.rewards:
                await interaction.response.send_message("This reward doesn't exist or expired.", ephemeral=True)
                return
            r = self.rewards[reward_id]
            # if already claimed
            if r["state"] == "claimed":
                await interaction.response.send_message("Already claimed.", ephemeral=True)
                return
            # if still reserved to owner: only owner can claim
            if r["state"] == "reserved":
                if user.id != r["owner_id"]:
                    await interaction.response.send_message("Only the player who spun this can claim it (unless they leave it).", ephemeral=True)
                    return
                # owner claiming
                success = await self._add_reward_to_user(r, user.id)
                if success:
                    r["state"] = "claimed"
                    r["claimed_by"] = user.id
                    await interaction.response.edit_message(content=f"{user.mention} claimed their reward **{r.get('qty',1)}{r['emoji']}** — +{r['value']} {FLUFFY_EMOJI}", view=None)
                    await interaction.response.send_message("Claimed and added to your inventory. 🧁☁️", ephemeral=True)
                else:
                    await interaction.response.send_message("Inventory full — cannot add item. Please free up space and try again.", ephemeral=True)
                return
            # if left (public) then anyone (except original players) can claim
            if r["state"] == "left":
                # players who were participants cannot claim other players' left rewards
                if user.id in self.player_ids and user.id != r["owner_id"]:
                    await interaction.response.send_message("Participants cannot claim another player's reward.", ephemeral=True)
                    return
                success = await self._add_reward_to_user(r, user.id)
                if success:
                    r["state"] = "claimed"
                    r["claimed_by"] = user.id
                    await interaction.response.edit_message(content=f"{user.mention} claimed this reward **{r.get('qty',1)}{r['emoji']}** — +{r['value']} {FLUFFY_EMOJI}", view=None)
                    await interaction.response.send_message("You claimed the reward. Yum! 🧁", ephemeral=True)
                else:
                    await interaction.response.send_message("Inventory full — cannot add item.", ephemeral=True)
                return

    async def leave_reward(self, interaction: discord.Interaction, reward_id: str):
        async with self.lock:
            user = interaction.user
            if reward_id not in self.rewards:
                await interaction.response.send_message("This reward doesn't exist or expired.", ephemeral=True)
                return
            r = self.rewards[reward_id]
            # only owner can leave their reserved reward
            if r["owner_id"] != user.id:
                await interaction.response.send_message("Only the owner can leave their reward.", ephemeral=True)
                return
            if r["state"] != "reserved":
                await interaction.response.send_message("This reward cannot be left.", ephemeral=True)
                return
            r["state"] = "left"
            # edit message to indicate left and allow others (non-participants) to claim
            msg = await self.channel.fetch_message(r["message_id"])
            await msg.edit(content=f"This reward was left by <@{r['owner_id']}> — anyone who didn't play can claim it now.\nReward: **{r.get('qty',1)}{r['emoji']}** — {r['value']} {FLUFFY_EMOJI}", view=ClaimLeaveView(self, reward_id, r["owner_id"]))
            await interaction.response.send_message("You left your reward. Others (non-participants) can now claim it.", ephemeral=True)

    async def _add_reward_to_user(self, r: Dict, user_id: int):
        db = load_db()
        u = ensure_user(db, str(user_id))
        # check inventory slot limit before adding stacks
        # Determine how many new stacks this reward will take:
        emoji = r["emoji"]
        qty = r.get("qty", 1)
        # simulate adding to count new stacks needed
        inv = u["inventory"]
        existing_stacks = inv.get(emoji, [])
        remaining = qty
        new_stacks_needed = 0
        # fill existing stacks
        for s in existing_stacks:
            space = STACK_SIZE - s
            to_add = min(space, remaining)
            remaining -= to_add
        # remaining will require new stacks
        while remaining > 0:
            to_make = min(remaining, STACK_SIZE)
            new_stacks_needed += 1
            remaining -= to_make
        # check if total slots used + new_stacks_needed > INVENTORY_SLOTS
        used = total_slots_used(inv)
        if used + new_stacks_needed > INVENTORY_SLOTS:
            return False
        # perform actual add
        add_item_to_inventory(u, emoji, qty)
        # also add fluffies value
        u["fluffies"] = u.get("fluffies", 0) + r.get("value", 0)
        save_db(db)
        return True

    async def _reward_cleanup_task(self):
        # after 60s, expire unclaimed rewards
        await asyncio.sleep(60)
        async with self.lock:
            to_delete = []
            for rid, r in list(self.rewards.items()):
                if r["state"] in ("reserved", "left"):
                    # edit message to say expired and remove buttons
                    try:
                        m = await self.channel.fetch_message(r["message_id"])
                        await m.edit(content=f"Reward expired. (was {r.get('qty',1)}{r['emoji']})", view=None)
                    except:
                        pass
                    to_delete.append(rid)
            for rid in to_delete:
                del self.rewards[rid]

# ----------------- Commands -----------------

# slot machine command

@bot.command(name="spin")
async def blp_start(ctx: commands.Context):
    """Start a new Blp spin round. Usage: Blp start"""
    guild_id = str(ctx.guild.id)
    if guild_id in active_rounds:
        await ctx.send("A round is already active in this server. Wait until it ends. ☁️")
        return
    # create a placeholder message and start round
    placeholder = await ctx.send("🎰 Starting a new Bloop spin... (players join with the button)")
    rnd = Round(placeholder)
    active_rounds[guild_id] = rnd
    ok = await rnd.start_join_phase()
    # cleanup active_rounds when done
    del active_rounds[guild_id]

# ------balance command---------

@bot.command(name="balance")
async def balance(ctx, member: discord.Member = None):
    user = member or ctx.author
    user_id = str(user.id)

    db = load_db()  # load from the same file as other features
    user_data = ensure_user(db, user_id)
    balance = user_data.get("fluffies", 0)

    embed = discord.Embed(
        title="💖 Fluffy Balance 💖",
        description=f"✨ **{user.display_name}** has **{balance} {FLUFFY_EMOJI} Fluffies!** ☁️",
        color=discord.Color.pink()
    )
    embed.set_footer(text="Stay sweet and keep spinning 🍭")

    await ctx.send(embed=embed)

    save_db(db)  # just to make sure the file stays updated



# ------inventory viewer---------



@bot.command(name="inv")
async def blp_inv(ctx: commands.Context, member: discord.Member = None):
    """View your or another user's inventory. Usage: Blp inv [user]"""
    db = load_db()
    user = member or ctx.author
    user_id = str(user.id)

    u = db.get(user_id, {"fluffies": 0, "inventory": {}})
    fluffies = u.get("fluffies", 0)
    inv = u.get("inventory", {})

    # --- Fix old data where stacks were stored as integers ---
    fixed = False
    for emoji, stacks in list(inv.items()):
        if isinstance(stacks, int):
            inv[emoji] = [stacks]
            fixed = True
    if fixed:
        db[user_id]["inventory"] = inv
        save_db(db)

# --- Build inventory display ---
    
    embed = discord.Embed(
        title=f"{user.display_name}'s Inventory ☁️🧁",
        color=discord.Color.teal()
    )
    embed.set_footer(text=f"Fluffies: {fluffies} {FLUFFY_EMOJI}")

    if not inv:
        if user == ctx.author:
            embed.description = "Your inventory is empty. Time to spin for snacks! 🧁"
        else:
            embed.description = f"{user.display_name} has nothing in their inventory. 😅"
    else:
        lines = []
        for emoji, stacks in inv.items():
            if isinstance(stacks, int):
                stacks = [stacks]
            elif not isinstance(stacks, list):
                continue
            for s in stacks:
                lines.append(f"**{s}{emoji}**")

        embed.add_field(name="Items", value="\n".join(lines) or "—", inline=False)
        embed.add_field(
            name="Slots used",
            value=f"{total_slots_used(inv)}/{INVENTORY_SLOTS}",
            inline=True
        )

    await ctx.send(embed=embed)
    
# ------help command---------



@bot.command(name="cmds")
async def blp_help(ctx: commands.Context):
    embed = discord.Embed(title="Blp Commands ☁️", color=discord.Color.gold())
    embed.add_field(name="Blp spin", value="Start a new slot round. Players join with the Join button.", inline=False)
    embed.add_field(name="Blp inv", value="View your inventory and fluffies.", inline=False)
    embed.add_field(name="Blp shop", value="(Coming soon) Open the Fluffie shop.", inline=False)
    embed.add_field(name="Blp leaderboard", value="shows the rank of the users in the server", inline=False)
    embed.add_field(name="Blp throw", value="lets you throw an item from your inventory", inline=False)
    embed.add_field(name="Blp claim", value="lets you claim an item that is thrown or abandoned", inline=False)
    embed.add_field(name="Blp balance", value="lets you check your balance", inline=False)
    await ctx.send(embed=embed)

# --------inventory item drop-----------


@bot.command(name="throw", aliases=["drop"])
async def blp_throw(ctx, emoji: str, amount: int = 1):
    user_id = str(ctx.author.id)
    db = load_db()
    user_data = ensure_user(db, user_id)
    inventory = user_data.get("inventory", {})

    # ✅ Make sure the emoji exists in their inv
    if emoji not in inventory:
        await ctx.send(f"❌ You don’t even have any {emoji} in your inventory!")
        return

    # ✅ Extract the actual item count safely
    item_data = inventory[emoji]
    if isinstance(item_data, list):  # some versions store like [amount, type]
        item_count = item_data[0]
    else:
        item_count = item_data

    # ✅ Check if user actually has enough
    if item_count <= 0:
        await ctx.send(f"❌ You don’t even have any {emoji} in your inventory!")
        return
    if item_count < amount:
        await ctx.send(f"😅 You only have {item_count}x {emoji}, not {amount}.")
        return

    # ✅ Remove items
    new_count = item_count - amount
    if isinstance(item_data, list):
        inventory[emoji][0] = new_count
    else:
        inventory[emoji] = new_count

    if new_count == 0:
        del inventory[emoji]

    save_db(db)

    # ✅ Send the drop message
    drop_msg = await ctx.send(f"🎁 **{ctx.author.display_name}** dropped {amount}x {emoji}! Type `Blp claim` to pick it up!")

    # ✅ Store the drop
    global dropped_items
    if "dropped_items" not in globals():
        dropped_items = {}

    dropped_items[drop_msg.id] = {
        "emoji": emoji,
        "amount": amount,
        "claimed": False,
        "message": drop_msg
    }

    await ctx.send(f"🌟 The {emoji} is now up for grabs!")

# ----------item claim------------------

@bot.command(name="claim")
async def blp_claim(ctx):
    global dropped_items
    if not dropped_items:
        await ctx.send("😅 There’s nothing dropped right now!")
        return

# Find the first unclaimed drop

    for msg_id, drop in list(dropped_items.items()):
        if not drop["claimed"]:
            emoji = drop["emoji"]
            amount = drop["amount"]
            drop_msg = drop["message"]

# Add to claimer’s inventory
            db = load_db()
            user_id = str(ctx.author.id)
            user_data = ensure_user(db, user_id)
            inventory = user_data.get("inventory", {})
            inventory[emoji] = inventory.get(emoji, 0) + amount
            save_db(db)

            await ctx.send(f"🎉 {ctx.author.mention} claimed {amount}x {emoji}!")
            del dropped_items[msg_id]
            return

    await ctx.send("😅 All dropped items have already been claimed!")


# -----------money transfer---------

@bot.command(name="send")
async def blp_send(ctx, member: discord.Member = None, amount: int = None):
    if member is None or amount is None:
        await ctx.send("❌ Usage: `Blp send @user <amount>`")
        return

    sender_id = str(ctx.author.id)
    receiver_id = str(member.id)

    db = load_db()
    sender_data = ensure_user(db, sender_id)
    receiver_data = ensure_user(db, receiver_id)

    # prevent self-send
    if sender_id == receiver_id:
        await ctx.send("😅 You can’t send Fluffies to yourself!")
        return

    # validate amount
    if amount <= 0:
        await ctx.send("❌ Invalid amount. Please send at least 1 Fluffy.")
        return

    # 💰 read correct field name ("fluffies" not "balance")
    sender_balance = sender_data.get("fluffies", 0)
    receiver_balance = receiver_data.get("fluffies", 0)

    if sender_balance < amount:
        await ctx.send(f"😢 You don’t have enough {FLUFFY_EMOJI}! Your balance: {sender_balance}.")
        return

    # transfer
    sender_data["fluffies"] = sender_balance - amount
    receiver_data["fluffies"] = receiver_balance + amount

    save_db(db)

    await ctx.send(
        f"💸 {ctx.author.mention} sent **{amount}x {FLUFFY_EMOJI}** to {member.mention}!"
    )


# -----------leaderboard--------------

@bot.command(name="leaderboard", aliases=["lb", "rich"])
async def blp_leaderboard(ctx):
    guild = ctx.guild

    try:
        db = load_db()  # ✅ use your main database loader
    except Exception:
        await ctx.send("😅 No data found yet — no one’s rich enough for a leaderboard!")
        return

    leaderboard = []

    for user_id, data in db.items():
        balance = data.get("fluffies", 0)  # ✅ always use correct key

        if balance <= 0:
            continue

        member = guild.get_member(int(user_id))
        if not member:
            continue

        leaderboard.append((member, balance))

    if not leaderboard:
        await ctx.send("🥺 No one in this server has any Fluffies yet!")
        return

    leaderboard.sort(key=lambda x: x[1], reverse=True)
    top_users = leaderboard[:10]

    desc = ""
    for i, (member, balance) in enumerate(top_users, start=1):
        rank_emoji = ["🥇", "🥈", "🥉"][i - 1] if i <= 3 else f"#{i}"
        desc += f"{rank_emoji} **{member.display_name}** — {FLUFFY_EMOJI} `{balance:,}`\n"

    embed = discord.Embed(
        title=f"🏆 {guild.name} Leaderboard",
        description=desc,
        color=0xffc6f9
    )
    embed.set_footer(text="Only the richest Fluffie holders make it here!")
    await ctx.send(embed=embed)


# ===========OTHER GAMES================

# pirates

import pirates

# ----------------- Run -----------------
@bot.event
async def on_ready():
    print(f"Bloop running as {bot.user} — ready to spin clouds of snacks! 🧁☁️")
    
#-----load other game modules----------

    # import Pirates commands
    await pirates.setup(bot)

    
    
# Run the bot

bot.run(os.getenv("TOKEN"))