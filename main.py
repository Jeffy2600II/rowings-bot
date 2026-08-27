# Synapse Bot — Rowings Universe
# Architecture: bot-hosting.net (free tier) + Base44 (AI brain)

"""
Synapse — Rowings Universe Community Bot
Hybrid Architecture: bot-hosting.net + Base44

Modules:
1. Conversation Starter — จุดประเด็นอัตโนมัติ 1 ครั้ง/วัน
2. Slash Commands — /topic /stats /ping /faq /reload
3. New Member Helper — รีแอ็คชันอัตโนมัติใน #แนะนำตัว
4. Monitoring — ส่งสถิติไป Base44 ทุกคืน
"""

import os
import json
import random
import logging
import asyncio
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
    "gaming":    1219891903865163787,  # งานศิลปะ (ไม่ใช่เกม แต่อยู่ในหมวดเดียวกัน)
    "movie":     1220422352085581844,  # ภาพยนตร์และซีรีส์
    "music":     1220509773406142474,  # เพลงโปรดวันนี้
    "food":      1532279261707370546,  # กินอะไรดีวันนี้
    "pets":      1532279421095116811,  # สมาคมทาสแมว-ทาสหมา
    "art":       1219891903865163787,  # งานศิลปะ
    "meme":      1219894681622810644,  # มีม
    "mod_log":   1238727178548674580,  # แตะ-หมดเวลา-แบน
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
    2: "gaming",     # พุธ → เกม (ใช้ช่อง art ชั่วคราว เพราะไม่มีช่องเกมเฉพาะ)
    3: "music",     # พฤหัส → เพลง
    4: "food",      # ศุกร์ → อาหาร
    5: "pets",      # เสาร์ → สัตว์เลี้ยง
    6: "meme",      # อาทิตย์ → มีม
}

# ─── Setup ──────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None,
)

# ─── Topic Pool ──────────────────────────────────────────

TOPICS_FILE = Path("topics.json")

def load_topics() -> dict:
    """โหลด topic pool จากไฟล์ JSON"""
    if not TOPICS_FILE.exists():
        return {}
    with open(TOPICS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_topics(topics: dict):
    """บันทึก topic pool"""
    with open(TOPICS_FILE, "w", encoding="utf-8") as f:
        json.dump(topics, f, ensure_ascii=False, indent=2)

# ติดตาม topic ที่ใช้แล้ว (เก็บใน memory ระหว่าง session)
used_topics: dict[str, list[int]] = {}

def pick_topic(category: str) -> dict | None:
    """สุ่ม topic ที่ยังไม่เคยใช้จากหมวด"""
    topics = load_topics()
    pool = topics.get(category, [])
    if not pool:
        return None
    
    used = set(used_topics.get(category, []))
    available = [(i, t) for i, t in enumerate(pool) if i not in used]
    
    if not available:
        # รีเซ็ตถ้าใช้ครบแล้ว
        used_topics[category] = []
        available = list(enumerate(pool))
    
    idx, topic = random.choice(available)
    used_topics.setdefault(category, []).append(idx)
    return topic

# ─── Logging ─────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger("synapse")

# ─── Events ──────────────────────────────────────────────

@bot.event
async def on_ready():
    log.info(f"Synapse online — {bot.user} (ID: {bot.user.id})")
    
    # ซิงค์ slash commands
    try:
        guild = discord.Object(id=GUILD_ID)
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        log.info(f"Synced {len(synced)} slash commands")
    except Exception as e:
        log.error(f"Failed to sync commands: {e}")
    
    # เริ่ม scheduled tasks
    conversation_starter.start()
    daily_report.start()

@bot.event
async def on_message(message: discord.Message):
    # ข้ามข้อความของบอท
    if message.author.bot:
        return
    
    # ถ้าเป็นข้อความแรกใน #แนะนำตัว → รีแอ็คชัน
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
            f"ยังไม่มีหัวข้อในหมวด {cat} อยู่ใน pool 🥲", ephemeral=True
        )
        return
    
    embed = discord.Embed(
        title="💬 หัวข้อคุย",
        description=topic.get("text", topic) if isinstance(topic, dict) else topic,
        color=0x5865F2
    )
    if isinstance(topic, dict) and topic.get("tag_role"):
        role_id = ROLE_TAGS.get(topic["tag_role"])
        if role_id:
            embed.description = f"<@&{role_id}> {embed.description}"
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="stats", description="ดูสถิติเซิร์ฟเวอร์")
async def stats_cmd(interaction: discord.Interaction):
    """ดูสถิติเซิร์ฟเวอร์"""
    guild = interaction.guild
    total = guild.member_count
    online = sum(1 for m in guild.members if m.status != discord.Status.offline)
    bots = sum(1 for m in guild.members if m.bot)
    humans = total - bots
    
    embed = discord.Embed(
        title="📊 สถิติ Rowings Universe",
        color=0x5865F2
    )
    embed.add_field(name="สมาชิกทั้งหมด", value=f"👥 {total}", inline=True)
    embed.add_field(name="คนจริง", value=f"👤 {humans}", inline=True)
    embed.add_field(name="บอท", value=f"🤖 {bots}", inline=True)
    embed.add_field(name="ออนไลน์", value=f"🟢 {online}", inline=True)
    embed.add_field(name="ช่อง", value=f"📁 {len(guild.channels)}", inline=True)
    embed.add_field(name="ยศ", value=f"🏷️ {len(guild.roles)}", inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ping", description="เช็คว่าบอทยังอยู่")
async def ping_cmd(interaction: discord.Interaction):
    """เช็ค latency"""
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(
        f"🏓 Pong! Latency: {latency}ms", ephemeral=True
    )

@bot.tree.command(name="faq", description="คำถามที่พบบ่อย")
async def faq_cmd(interaction: discord.Interaction):
    """FAQ"""
    embed = discord.Embed(
        title="❓ คำถามที่พบบ่อย",
        color=0x5865F2
    )
    embed.add_field(
        name="🔐 ยืนยันตัวตน",
        value="ไปที่ช่อง #ยืนยันตัวตน แล้วกดปุ่มยืนยัน",
        inline=False
    )
    embed.add_field(
        name="🏷️ รับยศ",
        value="ไปที่ช่อง #จุดรับยศ แล้วรีแอ็คชัน emoji ที่ตรงกับความสนใจ",
        inline=False
    )
    embed.add_field(
        name="👋 แนะนำตัว",
        value="ไปที่ช่อง #แนะนำตัว แล้วเล่าเรื่องตัวเองสั้นๆ",
        inline=False
    )
    embed.add_field(
        name="📜 กฎของเรา",
        value="อ่านได้ที่ช่อง #กฎของเรา",
        inline=False
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="reload", description="[Admin] โหลด topic pool ใหม่")
async def reload_cmd(interaction: discord.Interaction):
    """Admin only — reload topics"""
    if not any(r.id in ADMIN_ROLES for r in interaction.user.roles):
        await interaction.response.send_message("คำสั่งนี้สำหรับ Admin เท่านั้น", ephemeral=True)
        return
    
    global used_topics
    used_topics = {}
    topics = load_topics()
    total = sum(len(v) for v in topics.values())
    
    await interaction.response.send_message(
        f"✅ โหลด topic pool ใหม่แล้ว — {total} หัวข้อ จาก {len(topics)} หมวด",
        ephemeral=True
    )

# ─── Scheduled Tasks ────────────────────────────────────

@tasks.loop(minutes=1)
async def conversation_starter():
    """โพสต์ conversation starter วันละ 1 ครั้ง เวลา 18:30 ICT"""
    now = datetime.now(ICT)
    
    # 18:30 ทุกวัน
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
        
        # สร้าง embed
        text = topic.get("text", topic) if isinstance(topic, dict) else topic
        tag_role = topic.get("tag_role") if isinstance(topic, dict) else None
        
        content = ""
        if tag_role and tag_role in ROLE_TAGS:
            content = f"<@&{ROLE_TAGS[tag_role]}> "
        
        embed = discord.Embed(
            title="💬 หัวข้อคุยวันนี้",
            description=text,
            color=0x5865F2,
            timestamp=now,
        )
        embed.set_footer(text="Rowings Universe • พูดคุยกันเถอะ!")
        
        try:
            await channel.send(content=content, embed=embed)
            log.info(f"Posted conversation starter in #{channel.name}: {text[:50]}...")
        except discord.HTTPException as e:
            log.error(f"Failed to post: {e}")

@tasks.loop(minutes=1)
async def daily_report():
    """ส่งสถิติประจำวันไป mod-log ทุกคืน 22:00 ICT"""
    now = datetime.now(ICT)
    
    if now.hour == 22 and now.minute == 0:
        guild = bot.get_guild(GUILD_ID)
        if not guild:
            return
        
        total = guild.member_count
        online = sum(1 for m in guild.members if m.status != discord.Status.offline)
        bots = sum(1 for m in guild.members if m.bot)
        
        channel = bot.get_channel(CHANNELS["mod_log"])
        if channel:
            embed = discord.Embed(
                title="📊 สรุปประจำวัน",
                color=0x5865F2,
                timestamp=now,
            )
            embed.add_field(name="สมาชิกทั้งหมด", value=str(total), inline=True)
            embed.add_field(name="ออนไลน์", value=str(online), inline=True)
            embed.add_field(name="บอท", value=str(bots), inline=True)
            
            try:
                await channel.send(embed=embed)
                log.info("Daily report sent to mod-log")
            except discord.HTTPException as e:
                log.error(f"Failed to send daily report: {e}")

# ─── Startup ─────────────────────────────────────────────

def main():
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        log.error("DISCORD_BOT_TOKEN not set!")
        return
    
    bot.run(token)

if __name__ == "__main__":
    main()
