# Synapse Bot — Rowings Universe Hybrid System
## Architecture Plan (bot-hosting.net Edition)

> เอกสารนี้คือแผนสถาปัตยกรรมฉบับย่อ — ดู `ARCHITECTURE.md` สำหรับเวอร์ชันเต็ม

### Hosting: bot-hosting.net Free Tier
- **RAM:** 256 MB (เพียงพอสำหรับ bot เบา)
- **Storage:** 1 GB
- **Uptime:** 24/7 ไม่ sleep
- **Cost:** $0 (coins ฟรี 10/วัน, ใช้จ่าย weekly)
- **Renewal:** ทุก 4 วัน (กดปุ่ม manual ใน dashboard)

### Stack
- Python 3.11+ / discord.py 2.x
- Topic pool: JSON file (local)
- No database needed (เก็บ state ใน JSON)

### โมดูล
1. **Conversation Starter** — โพสต์หัวข้อคุย 1 ครั้ง/วัน (18:30)
2. **Slash Commands** — /topic, /stats, /ping, /faq, /reload (admin)
3. **New Member Helper** — รีแอ็คชันอัตโนมัติใน #แนะนำตัว
4. **Monitoring** — ส่งสถิติออกไปทุกคืน (ผ่าน HTTP → Base44)
