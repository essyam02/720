import asyncio
import logging
import random
import time
import aiosqlite
from collections import defaultdict

from telegram import Update, ChatPermissions
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# ---------------- CONFIG ---------------- #

TOKEN = "8261182027:AAH5_4mn4wXQkNROytm2YxqcT4mJnFPaBNo"

FLOOD_LIMIT = 6
FLOOD_TIME = 8

CAPTCHA_TIMEOUT = 60

SCAM_WORDS = [
    "crypto",
    "investment",
    "profit",
    "airdrop",
    "binance",
    "free money"
]

LINK_WHITELIST = [
    "youtube.com",
    "github.com"
]

BOT_WHITELIST = []

# ---------------- LOGGER ---------------- #

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ---------------- STORAGE ---------------- #

captcha_users = {}
captcha_attempts = {}
message_tracker = defaultdict(list)
raid_tracker = defaultdict(list)

# ---------------- DATABASE ---------------- #

async def init_db():
    async with aiosqlite.connect("securitybot.db") as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS warnings(
            user_id INTEGER PRIMARY KEY,
            warns INTEGER
        )
        """)
        await db.commit()

async def add_warning(user_id):

    async with aiosqlite.connect("securitybot.db") as db:

        cursor = await db.execute(
            "SELECT warns FROM warnings WHERE user_id=?",
            (user_id,)
        )

        row = await cursor.fetchone()

        if row:
            warns = row[0] + 1
            await db.execute(
                "UPDATE warnings SET warns=? WHERE user_id=?",
                (warns, user_id)
            )
        else:
            warns = 1
            await db.execute(
                "INSERT INTO warnings VALUES (?,?)",
                (user_id, warns)
            )

        await db.commit()

    return warns

# ---------------- ADMIN CHECK ---------------- #

async def is_admin(update, context, user_id):

    member = await context.bot.get_chat_member(
        update.effective_chat.id,
        user_id
    )

    return member.status in ["administrator", "creator"]

# ---------------- CAPTCHA ---------------- #

async def new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):

    for member in update.message.new_chat_members:

        if member.is_bot and member.id not in BOT_WHITELIST:
            await context.bot.ban_chat_member(update.effective_chat.id, member.id)
            return

        a = random.randint(1, 9)
        b = random.randint(1, 9)

        captcha_users[member.id] = {
            "answer": a + b,
            "time": time.time()
        }

        captcha_attempts[member.id] = 0

        await update.message.reply_text(
            f"👋 Welcome {member.first_name}\n\n"
            f"🔒 Verifikasi SATPAM berlaku tegas!\n\n"
            f"🧩 Mari Berhitung:\n\n"
            f"{a} + {b} = ?\n\n"
            f"⚠ HANYA BISA MEMASUKKAN ANGKA.\n"
            f"❌ 3 kali salah jawab = kick."
        )

# ---------------- CAPTCHA CHECK ---------------- #

async def captcha_check(update: Update, context: ContextTypes.DEFAULT_TYPE):

    msg = update.message
    user = msg.from_user
    chat = update.effective_chat

    if user.id not in captcha_users:
        return

    data = captcha_users[user.id]

    # Timeout
    if time.time() - data["time"] > CAPTCHA_TIMEOUT:

        del captcha_users[user.id]
        del captcha_attempts[user.id]

        await msg.reply_text("❌ Captcha GAGAL. JOIN ulang!")
        await chat.ban_member(user.id)
        await chat.unban_member(user.id)

        return

    # Block links
    if msg.entities:
        await msg.delete()
        await context.bot.send_message(
            chat.id,
            f"⚠ {user.first_name}, LINK GABISA DIKIRIM."
        )
        return

    # If not number
    if not msg.text or not msg.text.isdigit():

        await msg.delete()

        await context.bot.send_message(
            chat.id,
            f"⚠ {user.first_name}, cuma bisa kirim jawaban ANGKA!!"
        )

        return

    # Correct answer
    if int(msg.text) == data["answer"]:

        del captcha_users[user.id]
        del captcha_attempts[user.id]

        await msg.reply_text("✅ Verifikasi SATPAM berhasil. Welcome!")

    else:

        captcha_attempts[user.id] += 1
        attempts = captcha_attempts[user.id]

        await msg.delete()

        if attempts >= 3:

            await context.bot.send_message(
                chat.id,
                f"🚫 {user.first_name} salah 3x langsung KICK."
            )

            await chat.ban_member(user.id)
            await chat.unban_member(user.id)

            del captcha_users[user.id]
            del captcha_attempts[user.id]

        else:

            await context.bot.send_message(
                chat.id,
                f"❌ SALAHHH!!! {user.first_name}\nAttempts: {attempts}/3"
            )

# ---------------- FLOOD / SPAM ---------------- #

async def spam_detector(update: Update, context: ContextTypes.DEFAULT_TYPE):

    msg = update.message
    user = msg.from_user

    if await is_admin(update, context, user.id):
        return

    if user.id in captcha_users:
        await msg.delete()
        return

    now = time.time()

    message_tracker[user.id].append(now)

    message_tracker[user.id] = [
        t for t in message_tracker[user.id]
        if now - t < FLOOD_TIME
    ]

    if len(message_tracker[user.id]) > FLOOD_LIMIT:

        await msg.delete()

        warns = await add_warning(user.id)

        await punish(update, context, user, warns)

# ---------------- SCAM FILTER ---------------- #

async def scam_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):

    msg = update.message
    user = msg.from_user

    if await is_admin(update, context, user.id):
        return

    text = msg.text.lower() if msg.text else ""

    if any(word in text for word in SCAM_WORDS):

        await msg.delete()

        warns = await add_warning(user.id)

        await punish(update, context, user, warns)

# ---------------- LINK FILTER ---------------- #

async def link_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):

    msg = update.message
    user = msg.from_user

    if await is_admin(update, context, user.id):
        return

    if not msg.entities:
        return

    text = msg.text.lower()

    for entity in msg.entities:

        if entity.type in ["url", "text_link"]:

            if not any(domain in text for domain in LINK_WHITELIST):

                await msg.delete()

                warns = await add_warning(user.id)

                await punish(update, context, user, warns)

# ---------------- RAID DETECTOR ---------------- #

async def raid_protection(update: Update, context: ContextTypes.DEFAULT_TYPE):

    msg = update.message
    user = msg.from_user

    now = time.time()

    raid_tracker[user.id].append(now)

    raid_tracker[user.id] = [
        t for t in raid_tracker[user.id]
        if now - t < 5
    ]

    if len(raid_tracker[user.id]) > 8:

        await msg.delete()

# ---------------- PUNISHMENT ---------------- #

async def punish(update, context, user, warns):

    chat = update.effective_chat

    if warns == 3:

        await chat.restrict_member(
            user.id,
            permissions=ChatPermissions(can_send_messages=False)
        )

        await context.bot.send_message(
            chat.id,
            f"⚠ {user.first_name} muted (3 warnings)"
        )

    if warns >= 5:

        await chat.ban_member(user.id)

        await context.bot.send_message(
            chat.id,
            f"🚫 {user.first_name} banned (5 warnings)"
        )

# ---------------- ADMIN COMMANDS ---------------- #

async def warnings(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message.reply_to_message:
        return

    user = update.message.reply_to_message.from_user

    async with aiosqlite.connect("securitybot.db") as db:

        cursor = await db.execute(
            "SELECT warns FROM warnings WHERE user_id=?",
            (user.id,)
        )

        row = await cursor.fetchone()

    if row:
        await update.message.reply_text(
            f"{user.first_name} warnings: {row[0]}"
        )
    else:
        await update.message.reply_text("No warnings")

async def resetwarn(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message.reply_to_message:
        return

    user = update.message.reply_to_message.from_user

    async with aiosqlite.connect("securitybot.db") as db:

        await db.execute(
            "DELETE FROM warnings WHERE user_id=?",
            (user.id,)
        )

        await db.commit()

    await update.message.reply_text("Warnings reset")

# ---------------- MAIN ---------------- #

def main():

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_member))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, captcha_check))

    app.add_handler(MessageHandler(filters.TEXT, scam_filter))
    app.add_handler(MessageHandler(filters.TEXT, link_filter))
    app.add_handler(MessageHandler(filters.TEXT, spam_detector))
    app.add_handler(MessageHandler(filters.TEXT, raid_protection))

    app.add_handler(CommandHandler("warnings", warnings))
    app.add_handler(CommandHandler("resetwarn", resetwarn))

    print("🔥 Advanced Security Bot Running")

    app.run_polling()

if __name__ == "__main__":
    asyncio.run(init_db())
    main()