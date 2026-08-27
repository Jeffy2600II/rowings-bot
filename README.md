# Synapse Bot — Rowings Universe

Discord bot สำหรับจุดประเด็นและดูแลเซิร์ฟเวอร์ Rowings Universe
Hosted on bot-hosting.net (free tier)

## โครงสร้างไฟล์

```
synapse-bot/
├── main.py          # โค้ดหลักของ bot
├── topics.json      # Topic pool (120 หัวข้อ, 8 หมวด)
├── requirements.txt # Python dependencies
└── README.md        # ไฟล์นี้
```

## โมดูล

1. **Conversation Starter** — โพสต์หัวข้อคุย 18:30 ทุกวัน หมุนตามวัน
2. **Slash Commands** — /topic /stats /ping /faq /reload
3. **New Member Helper** — รีแอ็คชันอัตโนมัติใน #แนะนำตัว
4. **Daily Report** — ส่งสถิติไป mod-log 22:00 ทุกคืน

## การ Deploy (bot-hosting.net)

1. สมัครที่ bot-hosting.net (login ด้วย Discord)
2. รับ coins ฟรี 10 coins ที่ Earn Coins page
3. Create Server → เลือก Python → Free plan
4. Upload ไฟล์ทั้งหมดเป็น .zip หรือ import จาก GitHub
5. ตั้งค่า Environment Variable:
   - `DISCORD_BOT_TOKEN` = [token]
6. ตั้งค่า Startup:
   - Bot Python file: `main.py`
   - Additional Python packages: `discord.py`
7. Start!

## การเพิ่ม Topic

แก้ `topics.json` โดยเพิ่มหัวข้อในหมวดที่ต้องการ:
```json
{"text": "คำถามของคุณ", "tag_role": "gamer"}
```

`tag_role` ที่ใช้ได้: gamer, anime, music, foodie, pet, art, movie, null

## การดูแล

- Renewal: ทุก 4 วัน กดปุ่มใน dashboard (ฟรี)
- แก้ topics.json แล้วใช้ /reload เพื่อโหลดใหม่ (ไม่ต้อง restart)
- ดู logs ได้ใน dashboard → Console tab
