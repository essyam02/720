import logging
import os
import time
import random
import string

from pymongo import MongoClient

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# ---------------- CONFIG ----------------

TOKEN = "8261182027:AAH5_4mn4wXQkNROytm2YxqcT4mJnFPaBNo"
MONGO_URL = "mongodb+srv://esrskyn:Ciping27@720.ekl60b2.mongodb.net/?retryWrites=true&w=majority"

ADMIN_IDS = [1491285902]

FORCE_CHANNELS = [
    "@bornbeingfunny",
    "@ch720update"
]

COOLDOWN_SECONDS = 10

# ---------------- DATABASE ----------------

client = MongoClient(MONGO_URL)

db = client["telegram_file_bot"]

files = db["files"]

files.create_index("file_unique_id", unique=True)

# ---------------- LOGGER ----------------

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# ---------------- MEMORY ----------------

user_last_request = {}

# ---------------- UTIL ----------------

def generate_code(length=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def check_cooldown(user_id):

    now = time.time()

    if user_id in user_last_request:
        if now - user_last_request[user_id] < COOLDOWN_SECONDS:
            return False

    user_last_request[user_id] = now
    return True


async def check_force_join(user_id, bot):

    for channel in FORCE_CHANNELS:

        try:
            member = await bot.get_chat_member(channel, user_id)

            if member.status not in ["member", "administrator", "creator"]:
                return False

        except Exception:
            return False

    return True


def get_file_data(message):

    if message.document:
        return message.document.file_id, message.document.file_unique_id, "document"

    if message.photo:
        return message.photo[-1].file_id, message.photo[-1].file_unique_id, "photo"

    if message.video:
        return message.video.file_id, message.video.file_unique_id, "video"

    if message.audio:
        return message.audio.file_id, message.audio.file_unique_id, "audio"

    if message.voice:
        return message.voice.file_id, message.voice.file_unique_id, "voice"

    if message.animation:
        return message.animation.file_id, message.animation.file_unique_id, "animation"

    return None, None, None


async def send_file(message, file_id, file_type):

    if file_type == "photo":
        await message.reply_photo(file_id, protect_content=True)

    elif file_type == "video":
        await message.reply_video(file_id, protect_content=True)

    elif file_type == "audio":
        await message.reply_audio(file_id, protect_content=True)

    elif file_type == "voice":
        await message.reply_voice(file_id, protect_content=True)

    elif file_type == "animation":
        await message.reply_animation(file_id, protect_content=True)

    else:
        await message.reply_document(file_id, protect_content=True)


# ---------------- START ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id
    message = update.message

    joined = await check_force_join(user_id, context.bot)

    if not joined:

        buttons = []

        for ch in FORCE_CHANNELS:
            buttons.append([
                InlineKeyboardButton(
                    f"Join {ch}",
                    url=f"https://t.me/{ch.replace('@','')}"
                )
            ])

        buttons.append([
            InlineKeyboardButton("✅ Check Join", callback_data="check_join")
        ])

        await message.reply_text(
            "🚫 Please join all channels to use this bot.",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

        return

    if context.args:

        code = context.args[0]

        file_data = files.find_one({"code": code})

        if not file_data:

            await message.reply_text("❌ File not found.")
            return

        await send_file(
            message,
            file_data["file_id"],
            file_data["type"]
        )

        return

    await message.reply_text(
        "👋 Welcome!\n\nSend files to generate share links."
    )


# ---------------- FILE HANDLER ----------------

async def handle_files(update: Update, context: ContextTypes.DEFAULT_TYPE):

    message = update.message
    user_id = update.effective_user.id

    if not check_cooldown(user_id):

        await message.reply_text(
            "⏳ Please wait before sending another file."
        )
        return

    if user_id not in ADMIN_IDS:

        await message.reply_text(
            "🚫 Only admins can upload files."
        )
        return

    file_id, file_unique_id, file_type = get_file_data(message)

    if not file_id:
        return

    existing = files.find_one({"file_unique_id": file_unique_id})

    bot_username = context.bot.username

    if existing:

        link = f"https://t.me/{bot_username}?start={existing['code']}"

        await message.reply_text(
            f"⚠️ File already exists\n\n🔗 Link:\n{link}"
        )

        return

    code = generate_code()

    files.insert_one({
        "code": code,
        "file_id": file_id,
        "file_unique_id": file_unique_id,
        "type": file_type
    })

    link = f"https://t.me/{bot_username}?start={code}"

    await message.reply_text(
        f"✅ File stored successfully!\n\n🔗 Share Link:\n{link}"
    )


# ---------------- CHECK JOIN ----------------

async def check_join(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    user_id = query.from_user.id

    joined = await check_force_join(user_id, context.bot)

    if joined:

        await query.message.edit_text(
            "✅ You joined all channels.\n\nUse /start again."
        )

    else:

        await query.answer(
            "❌ You haven't joined all channels.",
            show_alert=True
        )


# ---------------- MAIN ----------------

def main():

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(
        MessageHandler(
            filters.Document.ALL
            | filters.PHOTO
            | filters.VIDEO
            | filters.AUDIO
            | filters.VOICE
            | filters.ANIMATION,
            handle_files
        )
    )

    app.add_handler(
        CallbackQueryHandler(check_join, pattern="check_join")
    )

    print("🚀 Bot Running...")

    app.run_polling()


if __name__ == "__main__":
    main()
