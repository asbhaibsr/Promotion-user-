# main.py - मुख्य बॉट + Flask

import logging
import asyncio
from flask import Flask, render_template, request, jsonify
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, CallbackQueryHandler
)
from config import Config
from database import db
from handlers import BotHandlers
from admin import AdminHandlers
import nest_asyncio

nest_asyncio.apply()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

flask_app = Flask(__name__)
bot_app = None

# ====== FLASK ROUTES ======
@flask_app.route('/')
def index():
    user_id = request.args.get('user', '0')
    try:
        user_id = int(user_id)
    except:
        user_id = 0
    
    return render_template('index.html',
                         user_id=user_id,
                         channel=Config.CHANNEL_USERNAME,
                         channel_link=Config.CHANNEL_LINK,
                         channel_bonus=Config.CHANNEL_BONUS,
                         movie_group=Config.MOVIE_GROUP_LINK,
                         new_group=Config.NEW_MOVIE_GROUP_LINK,
                         all_groups=Config.ALL_GROUPS_LINK,
                         min_withdrawal=Config.MIN_WITHDRAWAL)

@flask_app.route('/api/user/<int:user_id>')
def api_user(user_id):
    stats = db.get_user_stats(user_id)
    return jsonify(stats or {"error": "Not found"})

@flask_app.route('/api/leaderboard')
def api_leaderboard():
    return jsonify(db.get_current_leaderboard())

@flask_app.route(f'/{Config.BOT_TOKEN}', methods=['POST'])
def webhook():
    global bot_app
    try:
        update = Update.de_json(request.get_json(), bot_app.bot)
        asyncio.run(bot_app.process_update(update))
        return 'OK', 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return 'Error', 500

# ====== BOT INIT ======
async def initialize_bot():
    global bot_app
    bot_app = Application.builder().token(Config.BOT_TOKEN).build()
    
    # Commands
    bot_app.add_handler(CommandHandler("start", BotHandlers.start))
    bot_app.add_handler(CommandHandler("check", BotHandlers.check_command))
    bot_app.add_handler(CommandHandler("admin", AdminHandlers.admin_panel))
    bot_app.add_handler(CommandHandler("stats", AdminHandlers.handle_admin_text))
    bot_app.add_handler(CommandHandler("add", AdminHandlers.handle_admin_text))
    bot_app.add_handler(CommandHandler("remove", AdminHandlers.handle_admin_text))
    bot_app.add_handler(CommandHandler("clear", AdminHandlers.handle_admin_text))
    
    # Message handlers
    bot_app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, BotHandlers.web_app_data))
    bot_app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, AdminHandlers.handle_broadcast_message))
    bot_app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, AdminHandlers.handle_clear_reply))
    bot_app.add_handler(CallbackQueryHandler(AdminHandlers.admin_callback, pattern="^admin_"))
    bot_app.add_error_handler(BotHandlers.error_handler)
    
    await bot_app.initialize()
    
    webhook_url = f"{Config.WEB_APP_URL}/{Config.BOT_TOKEN}"
    await bot_app.bot.set_webhook(url=webhook_url)
    logger.info(f"✅ Webhook set: {webhook_url}")
    return bot_app

# ====== MAIN ======
def main():
    logger.info("🚀 Starting...")
    asyncio.run(initialize_bot())
    flask_app.run(host='0.0.0.0', port=Config.PORT)

if __name__ == "__main__":
    main()
