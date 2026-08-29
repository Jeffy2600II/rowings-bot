# Synapse Bot — Rowings Universe
# Architecture: Render (free tier) + Base44 (AI brain)

"""
Synapse — Rowings Universe Community Bot
Hybrid Architecture: Render + Base44

Modules:
1. Conversation Starter + Theme Day — จุดประเด็นอัตโนมัติ 1 ครั้ง/วัน 18:30
2. Weekly Poll — โหวตประจำสัปดาห์ทุกวันอาทิตย์ 19:00
3. Slash Commands — /topic /stats /ping /faq /reload /poll /suggest
4. New Member Helper — รีแอ็คชันอัตโนมัติใน #แนะนำตัว
5. Daily Report — สรุปสถิติเซิร์ฟเวอร์ทุกคืน 22:00 (สมาชิกใหม่ การเปลี่ยนแปลง คนจริง)
6. Keep-Alive HTTP Server — bind port ให้ Render + self-ping กัน sleep
"""

import os
import json
import random
import logging
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone, timedelta
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands, tasks

# ─── Config ─────────────────────────────────────────────

ICT = timezone(timedelta(hours=7))

GUILD_ID = 1164948652469538907  # Rowings Universe

# Channel IDs
CHANNELS = {
    "general":   1173548567307235378,  # พูดคุยทั่วไป
    "welcome":   1532258749308338236,  # Welcome
    "intro":     1540955038153707583,  # แนะนำตัว
    "anime":     1219894750342021160,  # อนิเมะ
    "art":       1219891903865163787,  # งานศิลปะ
    "movie":     1220422352085581844,  # ภาพยนตร์และซีรีส์
    "music":     1220509773406142474,  # เพลงโปรดวันนี้
    "food":      1532279261707370546,  # กินอะไรดีวันนี้
    "pets":      1532279421095116811,  # สมาคมทาสแมว-ทาสหมา
    "meme":      1219894681622810644,  # มีม
    "mod_log":   1238727178548674580,  # แตะ-หมดเวลา-แบน
    "support":   1460095076943397081,  # ติดต่อทีมซัพพอร์ต
    "suggest":   1542912628697993298,  # แนะนำ (ส่งคำแนะนำ)
    "verify":    1460173581496619090,  # ยืนยันตัวตน
    "roles":     1532359278512574585,  # จุดรับยศ
    "rules":     1164949047384215632,  # กฎของเรา
}

# Role IDs (สำหรับ tag ใน conversation starter)
ROLE_TAGS = {
    "gamer":    1532274855880425552,
    "anime":    1532275685433806979,
    "music":    1532275353437999304,
    "foodie":   1532276051668107405,
    "pet":      1532276482724859904,
    "art":      1532276613180424232,
    "movie":    1532275139406860403,
}

# Admin role IDs
ADMIN_ROLES = {1219406400120426576, 1173176875183521834}  # Owner, Core Team

# ตารางหมุนหัวข้อตามวัน (จันทร์-อาทิตย์)
DAILY_SCHEDULE = {
    0: "general",   # จันทร์ → พูดคุยทั่วไป
    1: "anime",      # อังคาร → อนิเมะ
    2: "art",       # พุธ → งานศิลปะ
    3: "music",     # พฤหัส → เพลง
    4: "food",      # ศุกร์ → อาหาร
    5: "pets",      # เสาร์ → สัตว์เลี้ยง
    6: "meme",      # อาทิตย์ → มีม
}

# Theme Day headers
THEME_HEADERS = {
    "general": {"emoji": "💬", "title": "Topic of the Day"},
    "anime":   {"emoji": "🌸", "title": "Anime Discussion"},
    "art":     {"emoji": "🎨", "title": "Art Showcase"},
    "music":   {"emoji": "🎧", "title": "Music Monday"},
    "food":    {"emoji": "🍔", "title": "Foodie Friday"},
    "pets":    {"emoji": "🐱", "title": "Pet Saturday"},
    "meme":    {"emoji": "🤔", "title": "Meme Sunday"},
    "gaming":  {"emoji": "🎮", "title": "Gaming Talk"},
    "movie":   {"emoji": "🎭", "title": "Movie Night"},
}

# ─── Keep-Alive HTTP Server ─────────────────────────────

class KeepAliveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Synapse is alive")
    
    def log_message(self, format, *args):
        pass

def start_http_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), KeepAliveHandler)
    server.serve_forever()

# ─── Setup ──────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True
intents.presences = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None,
)

# ─── Data Files ─────────────────────────────────────────

TOPICS_FILE = Path("topics.json")
STATS_FILE = Path("stats.json")

def load_topics() -> dict:
    if not TOPICS_FILE.exists():
        return {}
    with open(TOPICS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_topics(topics: dict):
    with open(TOPICS_FILE, "w", encoding="utf-8") as f:
        json.dump(topics, f, ensure_ascii=False, indent=2)

def load_stats() -> dict:
    """โหลดสถิติสะสม — ใช้เก็บจำนวนสมาชิกย้อนหลังและตัวนับรายวัน"""
    if not STATS_FILE.exists():
        return {}
    with open(STATS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_stats(data: dict):
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ตัวนับรายวัน (เก็บใน memory + sync ลงไฟล์)
daily_joins: int = 0
daily_leaves: int = 0
last_human_count: int = 0
last_report_date: str = ""

# ติดตาม topic ที่ใช้แล้ว
used_topics: dict[str, list[int]] = {}
used_polls: list[int] = []

def pick_topic(category: str) -> dict | None:
    topics = load_topics()
    pool = topics.get(category, [])
    if not pool:
        return None
    
    used = set(used_topics.get(category, []))
    available = [(i, t) for i, t in enumerate(pool) if i not in used]
    
    if not available:
        used_topics[category] = []
        available = list(enumerate(pool))
    
    idx, topic = random.choice(available)
    used_topics.setdefault(category, []).append(idx)
    return topic

def pick_poll() -> dict | None:
    topics = load_topics()
    pool = topics.get("poll", [])
    if not pool:
        return None
    
    available = [(i, p) for i, p in enumerate(pool) if i not in used_polls]
    if not available:
        used_polls.clear()
        available = list(enumerate(pool))
    
    idx, poll = random.choice(available)
    used_polls.append(idx)
    return poll

# ─── Logging ─────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger("synapse")

# ─── Thai Date Helper ───────────────────────────────────

THAI_MONTHS = [
    "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
    "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."
]

def thai_date(dt: datetime) -> str:
    """แปลงวันที่เป็นรูปแบบไทย — เช่น 29 ส.ค. 2026"""
    return f"{dt.day} {THAI_MONTHS[dt.month - 1]} {dt.year}"

# ─── Helper: Guild with counts ─────────────────────────────

async def fetch_guild_with_counts(guild_id: int) -> dict | None:
    """ดึงข้อมูลเซิร์ฟเวอร์พร้อมจำนวนออนไลน์จาก REST API — fallback เมื่อ presences intent ไม่พร้อม"""
    import urllib.request, urllib.error
    token = os.environ.get("DISCORD_BOT_TOKEN", "")
    url = f"https://discord.com/api/v10/guilds/{guild_id}?with_counts=true"
    req = urllib.request.Request(url, headers={"Authorization": f"Bot {token}"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        log.warning(f"Failed to fetch guild with counts: {e}")
        return None

# ─── Events ──────────────────────────────────────────────

@bot.event
async def on_ready():
    log.info(f"Synapse online — {bot.user} (ID: {bot.user.id})")
    
    # โหลดสถิติย้อนหลัง
    global last_human_count, last_report_date, daily_joins, daily_leaves
    stats = load_stats()
    last_human_count = stats.get("last_human_count", 0)
    last_report_date = stats.get("last_report_date", "")
    daily_joins = stats.get("daily_joins", 0)
    daily_leaves = stats.get("daily_leaves", 0)
    
    # ถ้าวันที่เปลี่ยน → รีเซ็ตตัวนับรายวัน
    today = datetime.now(ICT).strftime("%Y-%m-%d")
    if last_report_date != today:
        daily_joins = 0
        daily_leaves = 0
    
    # อัปเดตจำนวนคนจริงปัจจุบัน
    guild = bot.get_guild(GUILD_ID)
    if guild:
        humans = sum(1 for m in guild.members if not m.bot)
        if last_human_count == 0:
            last_human_count = humans
    
    # ซิงค์ slash commands
    try:
        guild_obj = discord.Object(id=GUILD_ID)
        bot.tree.copy_global_to(guild=guild_obj)
        synced = await bot.tree.sync(guild=guild_obj)
        log.info(f"Synced {len(synced)} slash commands")
    except Exception as e:
        log.error(f"Failed to sync commands: {e}")
    
    # เริ่ม scheduled tasks
    conversation_starter.start()
    weekly_poll.start()
    daily_report.start()
    keep_alive_ping.start()

@bot.event
async def on_member_join(member: discord.Member):
    """นับสมาชิกใหม่ที่เข้ามา"""
    global daily_joins
    if not member.bot:
        daily_joins += 1
        log.info(f"Member joined: {member.name} (daily joins: {daily_joins})")

@bot.event
async def on_member_remove(member: discord.Member):
    """นับสมาชิกที่จากไป"""
    global daily_leaves
    if not member.bot:
        daily_leaves += 1
        log.info(f"Member left: {member.name} (daily leaves: {daily_leaves})")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    
    # รีแอ็คชันอัตโนมัติใน #แนะนำตัว
    if message.channel.id == CHANNELS["intro"]:
        try:
            await message.add_reaction("👋")
            await message.add_reaction("🩵")
        except discord.HTTPException:
            pass
    
    await bot.process_commands(message)

# ─── Slash Commands ─────────────────────────────────────

@bot.tree.command(name="topic", description="ขอหัวข้อคุยสุ่มจาก pool")
@app_commands.choices(category=[
    app_commands.Choice(name="ทั่วไป", value="general"),
    app_commands.Choice(name="อนิเมะ", value="anime"),
    app_commands.Choice(name="เกม", value="gaming"),
    app_commands.Choice(name="เพลง", value="music"),
    app_commands.Choice(name="อาหาร", value="food"),
    app_commands.Choice(name="สัตว์เลี้ยง", value="pets"),
    app_commands.Choice(name="งานศิลปะ", value="art"),
    app_commands.Choice(name="มีม", value="meme"),
    app_commands.Choice(name="ภาพยนตร์", value="movie"),
])
async def topic_cmd(interaction: discord.Interaction, category: app_commands.Choice[str] = None):
    """ขอหัวข้อคุยทันที"""
    cat = category.value if category else "general"
    topic = pick_topic(cat)
    
    if not topic:
        await interaction.response.send_message(
            f"หมวดนี้ยังไม่มีหัวข้อใน pool เลย 🥲 ลองหมวดอื่นดูได้", ephemeral=True
        )
        return
    
    header = THEME_HEADERS.get(cat, {"emoji": "💬", "title": "Topic"})
    text = topic.get("text", topic) if isinstance(topic, dict) else topic
    
    embed = discord.Embed(
        title=f"{header['emoji']} {header['title']}",
        description=text,
        color=0x5865F2
    )
    if isinstance(topic, dict) and topic.get("tag_role"):
        role_id = ROLE_TAGS.get(topic["tag_role"])
        if role_id:
            embed.description = f"<@&{role_id}> {text}"
    
    embed.set_footer(text="Synapse • Rowings Universe")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="stats", description="ดูสถิติเซิร์ฟเวอร์")
async def stats_cmd(interaction: discord.Interaction):
    """ดูสถิติเซิร์ฟเวอร์"""
    guild = interaction.guild
    total = guild.member_count
    bots = sum(1 for m in guild.members if m.bot)
    humans = total - bots
    
    # ใช้ REST API สำหรับจำนวนออนไลน์ที่แม่นยำ
    guild_data = await fetch_guild_with_counts(GUILD_ID)
    if guild_data:
        online_total = guild_data.get("approximate_presence_count", 0)
    else:
        # Fallback: นับจาก cache (อาจไม่แม่นยำหากไม่มี presences intent)
        online_total = sum(1 for m in guild.members if m.status != discord.Status.offline)
    online_humans = max(0, online_total - bots)
    
    embed = discord.Embed(
        title="📊 สถิติ Rowings Universe",
        description=f"อัปเดตล่าสุด — {thai_date(datetime.now(ICT))}",
        color=0x5865F2
    )
    embed.add_field(name="คนจริงทั้งหมด", value=f"👤 {humans}", inline=True)
    embed.add_field(name="ออนไลน์ตอนนี้", value=f"🟢 {online_humans}", inline=True)
    embed.add_field(name="บอท", value=f"🤖 {bots}", inline=True)
    embed.add_field(name="ช่องทั้งหมด", value=f"📁 {len(guild.channels)}", inline=True)
    embed.add_field(name="ยศทั้งหมด", value=f"🏷️ {len(guild.roles)}", inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ping", description="เช็คว่าบอทยังอยู่")
async def ping_cmd(interaction: discord.Interaction):
    """เช็ค latency"""
    latency = round(bot.latency * 1000)
    if latency < 200:
        status = "แจ่มอยู่ 👍"
    elif latency < 500:
        status = "ปกติดี"
    else:
        status = "ช้าหน่อย แต่ยังทำงานได้"
    await interaction.response.send_message(
        f"🏓 Pong! Latency: {latency}ms — {status}", ephemeral=True
    )

@bot.tree.command(name="faq", description="คำถามที่พบบ่อย")
async def faq_cmd(interaction: discord.Interaction):
    """FAQ — ใช้ channel mention แทนชื่อธรรมดา"""
    embed = discord.Embed(
        title="❓ คำถามที่พบบ่อย",
        description="ไม่รู้จะเริ่มยังไง? ดูคู่มือสั้นๆ ได้ที่นี่เลย",
        color=0x5865F2
    )
    embed.add_field(
        name="🔐 ยืนยันตัวตน",
        value=f"ไปที่ <#{CHANNELS['verify']}> แล้วกดปุ่มยืนยันได้เลย",
        inline=False
    )
    embed.add_field(
        name="🏷️ รับยศ",
        value=f"ไปที่ <#{CHANNELS['roles']}> แล้วเลือก emoji ที่ตรงกับความสนใจของคุณ",
        inline=False
    )
    embed.add_field(
        name="👋 แนะนำตัว",
        value=f"ไปที่ <#{CHANNELS['intro']}> แล้วเล่าเรื่องตัวเองสั้นๆ ให้คนในเซิร์ฟรู้จัก",
        inline=False
    )
    embed.add_field(
        name="📜 กฎของเรา",
        value=f"อ่านได้ที่ <#{CHANNELS['rules']}>",
        inline=False
    )
    embed.add_field(
        name="💡 ส่งคำแนะนำ",
        value="ใช้คำสั่ง `/suggest` ได้เลยทุกช่อง — ทีมงานจะรับเรื่องไปพิจารณา",
        inline=False
    )
    embed.set_footer(text="Synapse • Rowings Universe")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="reload", description="[Admin] โหลด topic pool ใหม่")
async def reload_cmd(interaction: discord.Interaction):
    if not any(r.id in ADMIN_ROLES for r in interaction.user.roles):
        await interaction.response.send_message("คำสั่งนี้สำหรับ Admin เท่านั้นนะ", ephemeral=True)
        return
    
    global used_topics, used_polls
    used_topics = {}
    used_polls = []
    topics = load_topics()
    total = sum(len(v) for v in topics.values())
    
    await interaction.response.send_message(
        f"✅ โหลด topic pool ใหม่แล้ว — {total} หัวข้อ จาก {len(topics)} หมวด",
        ephemeral=True
    )

@bot.tree.command(name="poll", description="[Admin] สร้างโหวตในช่องปัจจุบัน")
@app_commands.describe(
    question="คำถามสำหรับโหวต",
    options="ตัวเลือก คั่นด้วย | (เช่น แมว|หมา|หนู)"
)
async def poll_cmd(interaction: discord.Interaction, question: str, options: str):
    if not any(r.id in ADMIN_ROLES for r in interaction.user.roles):
        await interaction.response.send_message("คำสั่งนี้สำหรับ Admin เท่านั้นนะ", ephemeral=True)
        return
    
    choices = [o.strip() for o in options.split("|") if o.strip()]
    if len(choices) < 2:
        await interaction.response.send_message("ต้องมีอย่างน้อย 2 ตัวเลือกนะ", ephemeral=True)
        return
    if len(choices) > 10:
        await interaction.response.send_message("ได้สูงสุด 10 ตัวเลือก", ephemeral=True)
        return
    
    poll_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    description = "\n\n".join(
        f"{poll_emojis[i]} **{choice}**"
        for i, choice in enumerate(choices)
    )
    
    embed = discord.Embed(
        title="📊 โหวต",
        description=f"**{question}**\n\n{description}\n\n*กด reaction ที่ตัวเลือกของคุณได้เลย*",
        color=0x5865F2
    )
    embed.set_footer(text=f"โดย {interaction.user.display_name} • Synapse")
    
    await interaction.response.send_message(embed=embed)
    msg = await interaction.original_response()
    
    for i in range(len(choices)):
        await msg.add_reaction(poll_emojis[i])

@bot.tree.command(name="suggest", description="ส่งคำแนะนำ/ไอเดียให้ทีมงาน")
@app_commands.describe(
    suggestion="คำแนะนำหรือไอเดียที่อยากเสนอ"
)
async def suggest_cmd(interaction: discord.Interaction, suggestion: str):
    """สมาชิกส่งคำแนะนำไปยังช่องแนะนำ"""
    suggest_channel = bot.get_channel(CHANNELS["suggest"])
    if not suggest_channel:
        await interaction.response.send_message("ไม่พบช่องรับคำแนะนำ ติดต่อแอดมินโดยตรงนะ", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="💡 คำแนะนำจากสมาชิก",
        description=suggestion,
        color=0xFEE75C
    )
    embed.set_author(
        name=interaction.user.display_name,
        icon_url=interaction.user.display_avatar.url if interaction.user.display_avatar else None
    )
    embed.add_field(name="ส่งจากช่อง", value=f"#{interaction.channel.name}", inline=True)
    embed.set_footer(text=f"User ID: {interaction.user.id} • Synapse")
    embed.timestamp = datetime.now(ICT)
    
    try:
        await suggest_channel.send(embed=embed)
        await interaction.response.send_message(
            "✅ ส่งคำแนะนำไปยังทีมงานแล้ว ขอบคุณที่ช่วยพัฒนาเซิร์ฟเวอร์! 🩵",
            ephemeral=True
        )
        log.info(f"Suggestion from {interaction.user}: {suggestion[:50]}...")
    except discord.HTTPException as e:
        await interaction.response.send_message("ส่งไม่สำเร็จ ลองใหม่อีกครั้งนะ", ephemeral=True)
        log.error(f"Failed to send suggestion: {e}")


@bot.tree.command(name="userinfo", description="[Admin] ดูข้อมูลสมาชิก")
@app_commands.describe(member="สมาชิกที่ต้องการดู (ไม่ระบุ = ตัวเอง)")
async def userinfo_cmd(interaction: discord.Interaction, member: discord.Member = None):
    """ดูข้อมูลสมาชิกแบบละเอียดสำหรับแอดมิน"""
    if not any(r.id in ADMIN_ROLES for r in interaction.user.roles):
        await interaction.response.send_message("คำสั่งนี้สำหรับ Admin เท่านั้นนะ", ephemeral=True)
        return
    
    target = member or interaction.user
    
    # คำนวณวันเข้าร่วม
    joined_at = target.joined_at
    if joined_at:
        joined_at_ict = joined_at.astimezone(ICT)
        join_str = f"{thai_date(joined_at_ict)} ({(datetime.now(ICT) - joined_at_ict).days} วันที่แล้ว)"
    else:
        join_str = "ไม่ทราบ"
    
    # วันสร้างบัญชี
    created_at = target.created_at
    if created_at:
        created_ict = created_at.astimezone(ICT)
        account_age = (datetime.now(ICT) - created_ict).days
        created_str = f"{thai_date(created_ict)} ({account_age} วันที่แล้ว)"
    else:
        created_str = "ไม่ทราบ"
    
    # ยศ (เรียงตาม position)
    roles_list = [r.mention for r in target.roles if r.name != "@everyone"]
    roles_str = " ".join(roles_list) if roles_list else "ไม่มียศ"
    if len(roles_str) > 1024:
        roles_str = roles_str[:1021] + "..."
    
    # สถานะ (ต้องมี GUILD_PRESENCES intent ถึงจะแม่นยำ)
    if target.status != discord.Status.offline:
        status_map = {
            discord.Status.online: "🟢 ออนไลน์",
            discord.Status.idle: "🟡 ไม่อยู่",
            discord.Status.dnd: "🔴 ห้ามรบกวน",
        }
        status_str = status_map.get(target.status, "🟢 ออนไลน์")
    else:
        # ถ้าเป็น offline อาจเป็นเพราะ intent ไม่พร้อม หรือออฟไลน์จริง
        # ตรวจจาก desktop/mobile/web status ถ้ามี
        raw_status = str(target.raw_status) if hasattr(target, 'raw_status') else 'offline'
        if raw_status != 'offline':
            status_str = "🟢 ออนไลน์"
        else:
            status_str = "⚫ ออฟไลน์ (หรือซ่อนสถานะ)"
    
    embed = discord.Embed(
        title=f"👤 ข้อมูลสมาชิก — {target.display_name}",
        color=target.color if target.color.value != 0 else 0x5865F2
    )
    embed.set_thumbnail(url=target.display_avatar.url if target.display_avatar else None)
    
    embed.add_field(name="ชื่อผู้ใช้", value=target.name, inline=True)
    embed.add_field(name="แสดงตัว", value=target.display_name, inline=True)
    embed.add_field(name="ID", value=str(target.id), inline=True)
    
    embed.add_field(name="สถานะ", value=status_str, inline=True)
    embed.add_field(name="บอท", value="ใช่ 🤖" if target.bot else "ไม่ใช่", inline=True)
    embed.add_field(name="ปิดเสียง", value="ใช่ 🔇" if target.is_timed_out() else "ไม่ใช่", inline=True)
    
    embed.add_field(name="วันเข้าร่วมเซิร์ฟ", value=join_str, inline=False)
    embed.add_field(name="วันสร้างบัญชี", value=created_str, inline=False)
    
    embed.add_field(name="ยศ", value=roles_str, inline=False)
    
    # บทบาทเด่น
    key_roles = []
    if target.guild.owner_id == target.id:
        key_roles.append("👑 เจ้าของเซิร์ฟ")
    if any(r.id in ADMIN_ROLES for r in target.roles):
        key_roles.append("🛡️ แอดมิน")
    if key_roles:
        embed.add_field(name="บทบาท", value=" | ".join(key_roles), inline=False)
    
    embed.set_footer(text=f"Synapse • Rowings Universe | {thai_date(datetime.now(ICT))}")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="serverinfo", description="[Admin] ดูภาพรวมเซิร์ฟเวอร์")
async def serverinfo_cmd(interaction: discord.Interaction):
    """ดูภาพรวมเซิร์ฟเวอร์สำหรับแอดมิน"""
    if not any(r.id in ADMIN_ROLES for r in interaction.user.roles):
        await interaction.response.send_message("คำสั่งนี้สำหรับ Admin เท่านั้นนะ", ephemeral=True)
        return
    
    guild = interaction.guild
    
    # นับสมาชิก
    humans = sum(1 for m in guild.members if not m.bot)
    bots = sum(1 for m in guild.members if m.bot)
    
    # ใช้ REST API สำหรับจำนวนออนไลน์
    guild_data = await fetch_guild_with_counts(GUILD_ID)
    if guild_data:
        online_total = guild_data.get("approximate_presence_count", 0)
    else:
        online_total = sum(1 for m in guild.members if m.status != discord.Status.offline)
    online_humans = max(0, online_total - bots)
    online_bots = 0  # ไม่สามารถแยกบอทออนไลน์ได้แม่นยำจาก REST API
    
    # นับช่อง
    text_channels = sum(1 for c in guild.channels if isinstance(c, discord.TextChannel))
    voice_channels = sum(1 for c in guild.channels if isinstance(c, discord.VoiceChannel))
    categories = sum(1 for c in guild.channels if isinstance(c, discord.CategoryChannel))
    
    # วันสร้างเซิร์ฟ
    created_ict = guild.created_at.astimezone(ICT)
    age_days = (datetime.now(ICT) - created_ict).days
    
    # ยศที่ไม่ใช่ @everyone และ bot roles
    human_roles = [r for r in guild.roles if r.name != "@everyone" and not r.managed]
    bot_managed_roles = [r for r in guild.roles if r.managed]
    
    # สมาชิกใหม่ 7 วันล่าสุด
    now = datetime.now(ICT)
    recent_members = []
    for m in guild.members:
        if m.bot:
            continue
        if m.joined_at:
            joined_ict = m.joined_at.astimezone(ICT)
            if (now - joined_ict).days <= 7:
                recent_members.append(m)
    recent_members.sort(key=lambda x: x.joined_at, reverse=True)
    
    embed = discord.Embed(
        title=f"🏛️ ข้อมูลเซิร์ฟเวอร์ — {guild.name}",
        description=f"สร้างเมื่อ {thai_date(created_ict)} ({age_days} วันที่แล้ว)",
        color=0x5865F2
    )
    
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    
    embed.add_field(name="คนจริง", value=f"👤 {humans}", inline=True)
    embed.add_field(name="ออนไลน์", value=f"🟢 {online_humans}", inline=True)
    embed.add_field(name="บอท", value=f"🤖 {bots} ({online_bots} ออนไลน์)", inline=True)
    
    embed.add_field(name="ช่องข้อความ", value=f"📝 {text_channels}", inline=True)
    embed.add_field(name="ช่องเสียง", value=f"🔊 {voice_channels}", inline=True)
    embed.add_field(name="หมวดหมู่", value=f"📁 {categories}", inline=True)
    
    embed.add_field(name="ยศทั้งหมด", value=f"🏷️ {len(guild.roles)}", inline=True)
    embed.add_field(name="ยศผู้ใช้", value=f"👥 {len(human_roles)}", inline=True)
    embed.add_field(name="ยศบอท", value=f"🤖 {len(bot_managed_roles)}", inline=True)
    
    # ระดับ verification
    ver_levels = {0: "ไม่มี", 1: "ต่ำ (Email)", 2: "กลาง (เข้า Discord 5+ นาที)", 3: "สูง (สมาชิก 10+ นาที)", 4: "สูงสุด (เบอร์โทร)"}
    embed.add_field(name="ระดับยืนยัน", value=ver_levels.get(guild.verification_level, "ไม่ทราบ"), inline=True)
    embed.add_field(name="Owner", value=f"<@{guild.owner_id}>", inline=True)
    embed.add_field(name="Boost", value=f"🚀 {guild.premium_subscription_count} (Level {guild.premium_tier})", inline=True)
    
    # สมาชิกใหม่ล่าสุด
    if recent_members:
        recent_str = "\n".join(f"• {m.display_name} — {thai_date(m.joined_at.astimezone(ICT))}" for m in recent_members[:5])
        if len(recent_members) > 5:
            recent_str += f"\n• และอีก {len(recent_members) - 5} คน..."
        embed.add_field(name=f"🆕 สมาชิกใหม่ (7 วันล่าสุด)", value=recent_str, inline=False)
    else:
        embed.add_field(name="🆕 สมาชิกใหม่ (7 วันล่าสุด)", value="ไม่มีสมาชิกใหม่ในช่วง 7 วัน", inline=False)
    
    embed.set_footer(text=f"Synapse • Rowings Universe | {thai_date(datetime.now(ICT))}")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ─── Scheduled Tasks ────────────────────────────────────

@tasks.loop(minutes=1)
async def conversation_starter():
    """โพสต์ conversation starter วันละ 1 ครั้ง เวลา 18:30 ICT"""
    now = datetime.now(ICT)
    
    if now.hour == 18 and now.minute == 30:
        day_of_week = now.weekday()
        category = DAILY_SCHEDULE.get(day_of_week, "general")
        channel_id = CHANNELS.get(category, CHANNELS["general"])
        
        topic = pick_topic(category)
        if not topic:
            log.warning(f"No topics available for category: {category}")
            return
        
        channel = bot.get_channel(channel_id)
        if not channel:
            log.error(f"Cannot find channel: {channel_id}")
            return
        
        header = THEME_HEADERS.get(category, {"emoji": "💬", "title": "Topic of the Day"})
        text = topic.get("text", topic) if isinstance(topic, dict) else topic
        tag_role = topic.get("tag_role") if isinstance(topic, dict) else None
        
        embed = discord.Embed(
            title=f"{header['emoji']} {header['title']}",
            description=text,
            color=0x5865F2
        )
        if tag_role:
            role_id = ROLE_TAGS.get(tag_role)
            if role_id:
                embed.description = f"<@&{role_id}> {text}"
        
        embed.set_footer(text="Synapse • Rowings Universe")
        
        try:
            await channel.send(embed=embed)
            log.info(f"Posted theme day '{header['title']}' in #{channel.name}")
        except discord.HTTPException as e:
            log.error(f"Failed to post: {e}")

@tasks.loop(minutes=1)
async def weekly_poll():
    """โพสต์ poll ประจำสัปดาห์ ทุกวันอาทิตย์ 19:00 ICT"""
    now = datetime.now(ICT)
    
    if now.weekday() == 6 and now.hour == 19 and now.minute == 0:
        poll_data = pick_poll()
        if not poll_data:
            log.warning("No poll data available")
            return
        
        channel = bot.get_channel(CHANNELS["general"])
        if not channel:
            log.error("Cannot find general channel")
            return
        
        question = poll_data.get("question", "โหวตประจำสัปดาห์")
        options = poll_data.get("options", [])
        
        if len(options) < 2:
            log.warning("Poll has fewer than 2 options")
            return
        
        poll_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        
        description = "\n\n".join(
            f"{poll_emojis[i]} **{opt}**"
            for i, opt in enumerate(options[:10])
        )
        
        embed = discord.Embed(
            title="📊 โหวตประจำสัปดาห์",
            description=f"**{question}**\n\n{description}\n\n*กด reaction ที่ตัวเลือกของคุณได้เลย*",
            color=0x5865F2
        )
        embed.set_footer(text="Synapse • Rowings Universe — Weekly Poll")
        
        try:
            msg = await channel.send(embed=embed)
            for i in range(len(options[:10])):
                await msg.add_reaction(poll_emojis[i])
            log.info(f"Posted weekly poll: {question}")
        except discord.HTTPException as e:
            log.error(f"Failed to post poll: {e}")

@tasks.loop(minutes=1)
async def daily_report():
    """ส่งสรุปสถิติไป mod_log ทุกคืน 22:00 ICT — สมาชิกใหม่ การเปลี่ยนแปลง คนจริง"""
    global last_human_count, last_report_date, daily_joins, daily_leaves
    
    now = datetime.now(ICT)
    
    if now.hour == 22 and now.minute == 0:
        guild = bot.get_guild(GUILD_ID)
        if not guild:
            return
        
        channel = bot.get_channel(CHANNELS["mod_log"])
        if not channel:
            return
        
        # นับคนจริงและออนไลน์ (ไม่นับบอท)
        humans = sum(1 for m in guild.members if not m.bot)
        # ใช้ REST API สำหรับจำนวนออนไลน์
        import asyncio as _aio
        guild_data = await fetch_guild_with_counts(GUILD_ID)
        if guild_data:
            online_total = guild_data.get("approximate_presence_count", 0)
            online_humans = max(0, online_total - sum(1 for m in guild.members if m.bot))
        else:
            online_humans = sum(1 for m in guild.members if not m.bot and m.status != discord.Status.offline)
        
        # คำนวณการเปลี่ยนแปลง
        net_change = humans - last_human_count
        prev_count = last_human_count if last_human_count > 0 else humans
        
        # สร้างสรุป
        date_str = thai_date(now)
        
        embed = discord.Embed(
            title="📊 สรุปประจำวัน",
            description=f"**{date_str}**",
            color=0x5865F2,
            timestamp=now
        )
        
        # สมาชิกใหม่และการจากไป
        join_text = f"➕ {daily_joins} คน" if daily_joins > 0 else "ไม่มี"
        leave_text = f"➖ {daily_leaves} คน" if daily_leaves > 0 else "ไม่มี"
        
        if net_change > 0:
            net_text = f"📈 +{net_change} คน"
        elif net_change < 0:
            net_text = f"📉 {net_change} คน"
        else:
            net_text = "➖ ไม่เปลี่ยนแปลง"
        
        embed.add_field(name="สมาชิกใหม่วันนี้", value=join_text, inline=True)
        embed.add_field(name="จากไป", value=leave_text, inline=True)
        embed.add_field(name="สุทธิ", value=net_text, inline=True)
        
        # สถิติรวม
        embed.add_field(name="คนจริงทั้งหมด", value=f"👤 {humans}", inline=True)
        embed.add_field(name="ออนไลน์ตอนนี้", value=f"🟢 {online_humans}", inline=True)
        embed.add_field(name="เมื่อวาน", value=f"👤 {prev_count}", inline=True)
        
        embed.set_footer(text="Synapse • Rowings Universe — Daily Report")
        
        try:
            await channel.send(embed=embed)
            log.info(f"Daily report sent — joins: {daily_joins}, leaves: {daily_leaves}, net: {net_change}")
        except discord.HTTPException as e:
            log.error(f"Failed to send report: {e}")
        
        # บันทึกและรีเซ็ต
        last_human_count = humans
        last_report_date = now.strftime("%Y-%m-%d")
        daily_joins = 0
        daily_leaves = 0
        save_stats({
            "last_human_count": last_human_count,
            "last_report_date": last_report_date,
            "daily_joins": 0,
            "daily_leaves": 0,
        })

@tasks.loop(minutes=5)
async def keep_alive_ping():
    """Self-ping ทุก 5 นาที เพื่อกัน Render free tier sleep"""
    import urllib.request
    app_url = os.environ.get("RENDER_EXTERNAL_URL")
    if not app_url:
        return
    try:
        urllib.request.urlopen(f"{app_url}/", timeout=10)
        log.debug("Keep-alive ping sent")
    except Exception as e:
        log.debug(f"Keep-alive ping failed: {e}")

# ─── Main ────────────────────────────────────────────────

def main():
    token = os.environ.get("DISCORD_BOT_TOKEN", "")
    if not token:
        log.error("DISCORD_BOT_TOKEN not set")
        return
    
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()
    log.info(f"HTTP keep-alive server started on port {os.environ.get('PORT', 10000)}")
    
    bot.run(token)

if __name__ == "__main__":
    main()
