from telegram import Update, ChatPermissions
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

BOT_TOKEN = "8716813989:AAFzFobRdgUeeo4EigugOrIZ5iZ5suqWjH0"

SPAM_WORDS = [
    "crypto",
    "airdrop",
    "free money",
]

BLOCK_LINKS = True


# Delete service messages
async def clean_service(update: Update, context: ContextTypes.DEFAULT_TYPE):

    msg = update.effective_message

    try:

        if (
            msg.new_chat_members
            or msg.left_chat_member
            or msg.new_chat_title
            or msg.new_chat_photo
            or msg.delete_chat_photo
            or msg.pinned_message
        ):
            await msg.delete()
            return

        if msg.text:

            text = msg.text.lower()

            if BLOCK_LINKS:
                if "http://" in text or "https://" in text or "t.me/" in text:
                    await msg.delete()
                    return

            for word in SPAM_WORDS:
                if word in text:
                    await msg.delete()
                    return

    except:
        pass


# purge command
async def purge(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message.reply_to_message:
        return

    chat_id = update.effective_chat.id
    message_id = update.message.reply_to_message.message_id

    for i in range(message_id + 1, update.message.message_id):
        try:
            await context.bot.delete_message(chat_id, i)
        except:
            pass


# clean last messages
async def clean(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.args:
        return

    count = int(context.args[0])
    chat_id = update.effective_chat.id
    msg_id = update.message.message_id

    for i in range(msg_id - count, msg_id):
        try:
            await context.bot.delete_message(chat_id, i)
        except:
            pass


# mute command
async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message.reply_to_message:
        return

    user = update.message.reply_to_message.from_user.id

    permissions = ChatPermissions(
        can_send_messages=False
    )

    await context.bot.restrict_chat_member(
        update.effective_chat.id,
        user,
        permissions
    )


app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(MessageHandler(filters.ALL, clean_service))
app.add_handler(CommandHandler("purge", purge))
app.add_handler(CommandHandler("clean", clean))
app.add_handler(CommandHandler("mute", mute))

print("Ultimate cleaner bot running...")

app.run_polling()