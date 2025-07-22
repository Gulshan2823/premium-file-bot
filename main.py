import os
import time
import random
import string
import threading
from flask import Flask, request
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN")
VPLINK_API = os.getenv("VPLINK_API")
FORCE_SUB_CHANNELS = os.getenv("FORCE_SUB_CHANNELS", "").split(',')
TOKEN_EXPIRY = int(os.getenv("TOKEN_EXPIRY", 7200))  # default 2 hours
DELETE_AFTER = int(os.getenv("DELETE_AFTER", 900))   # default 15 min
BASE_URL = os.getenv("BASE_URL")

app = Flask(__name__)

# store temporary links: {token: {"file_id": ..., "expiry": ..., "chat_id": ..., "msg_id": ...}}
tokens = {}

# ---------------- Token Generation & Cleanup --------------------
def generate_token(length=12):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def cleanup_tokens():
    while True:
        time.sleep(60)
        now = time.time()
        expired = [token for token, data in tokens.items() if now > data['expiry']]
        for token in expired:
            tokens.pop(token, None)

threading.Thread(target=cleanup_tokens, daemon=True).start()

# ---------------- Force Subscribe --------------------
async def check_force_subscribe(user_id, context):
    for channel in FORCE_SUB_CHANNELS:
        try:
            member = await context.bot.get_chat_member(channel, user_id)
            if member.status in ["left", "kicked"]:
                return False
        except:
            return False
    return True

# ---------------- Bot Handlers --------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Welcome to Premium File Bot. Just send a file to get a download link.")

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user

    if not await check_force_subscribe(user.id, context):
        buttons = [[InlineKeyboardButton("🔗 Join Channels", url=f"https://t.me/{BASE_URL}")]]
        await update.message.reply_text("❌ You must join all required channels to use this bot.", reply_markup=InlineKeyboardMarkup(buttons))
        return

    file = update.message.document or update.message.video or update.message.audio or update.message.photo[-1]
    file_id = file.file_id

    token = generate_token()
    tokens[token] = {
        "file_id": file_id,
        "expiry": time.time() + TOKEN_EXPIRY,
        "chat_id": update.message.chat_id,
        "msg_id": update.message.message_id
    }

    short_url = requests.get(f"https://vplink.in/api?api={VPLINK_API}&url=https://{BASE_URL}/file/{token}").json().get("shortenedUrl")

    await update.message.reply_text(f"🔗 Your download link (expires in {TOKEN_EXPIRY//60} min):\n{short_url}")

    threading.Timer(DELETE_AFTER, delete_message, args=(context, update.message.chat_id, update.message.message_id)).start()

def delete_message(context, chat_id, msg_id):
    try:
        context.bot.delete_message(chat_id, msg_id)
    except:
        pass

async def serve_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    token = context.args[0] if context.args else None
    data = tokens.get(token)
    if data:
        await context.bot.send_document(chat_id=update.effective_chat.id, document=data['file_id'])
    else:
        await update.message.reply_text("❌ Invalid or expired link.")

# ---------------- Flask Webhook Route --------------------
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot.application.bot)
    bot.application.update_queue.put_nowait(update)
    return "ok"

@app.route("/")
def index():
    return "✅ Bot is Running!"

# ---------------- Start Bot --------------------
if __name__ == '__main__':
    bot = Application.builder().token(BOT_TOKEN).build()

    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CommandHandler("file", serve_file))
    bot.add_handler(MessageHandler(filters.Document.ALL | filters.Video.ALL | filters.Audio.ALL | filters.PHOTO, handle_file))

    bot.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        webhook_url=f"https://{BASE_URL}/{BOT_TOKEN}"
    )
