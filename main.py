import os
from telegram import Update, Bot
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from flask import Flask, request

TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.environ.get('PORT', '8443'))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # e.g., https://your-railway-app.up.railway.app/webhook

app = Flask(__name__)
bot_app = None  # Store app globally to access in Flask

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Welcome! Send me a file to get started.")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = update.message.document or update.message.video or update.message.audio
    if not file:
        await update.message.reply_text("❌ Please send a valid file.")
        return
    file_info = await file.get_file()
    await update.message.reply_text(f"✅ File received: {file.file_name}\n🔗 Download: {file_info.file_path}")

@app.route('/webhook', methods=['POST'])
async def webhook():
    update = Update.de_json(request.get_json(force=True), bot_app.bot)
    await bot_app.process_update(update)
    return 'OK'

def main():
    global bot_app
    bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(MessageHandler(filters.Document.ALL | filters.Video.ALL | filters.Audio.ALL, handle_document))
    bot_app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=WEBHOOK_URL + "/webhook"
    )

if __name__ == '__main__':
    main()
