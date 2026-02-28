# main.py
import logging
import asyncio
import os
import traceback
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
from utils import is_admin

# ====== लॉगिंग सेटअप ======
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, Config.LOG_LEVEL)
)
logger = logging.getLogger(__name__)

# ====== फ्लास्क ऐप ======
flask_app = Flask(__name__)
bot_app = None

# ====== फ्लास्क रूट्स ======
@flask_app.route('/')
def index():
    """मिनी ऐप होम पेज"""
    user_id = request.args.get('user', '0')
    lang = request.args.get('lang', 'hi')
    
    try:
        user_id = int(user_id)
    except:
        user_id = 0
    
    return render_template('index.html', 
                         user_id=user_id, 
                         lang=lang,
                         channel=Config.CHANNEL_USERNAME,
                         channel_bonus=Config.CHANNEL_BONUS)

@flask_app.route('/api/user/<int:user_id>')
def api_user(user_id):
    """यूजर डेटा एपीआई"""
    stats = db.get_user_stats(user_id)
    if not stats:
        return jsonify({"error": "यूजर नहीं मिला"})
    return jsonify(stats)

@flask_app.route('/api/leaderboard')
def api_leaderboard():
    """लीडरबोर्ड एपीआई"""
    lb = db.get_leaderboard()
    result = []
    for idx, user in enumerate(lb, 1):
        result.append({
            "rank": idx,
            "name": user.get("full_name", "यूजर")[:20],
            "refs": user.get("active_referrals", 0),
            "balance": user.get("balance", 0)
        })
    return jsonify(result)

@flask_app.route('/api/ads')
def api_ads():
    """एड्स एपीआई"""
    if not Config.ENABLE_ADS:
        return jsonify([])
    
    ads = db.get_active_ads()
    result = []
    for ad in ads:
        result.append({
            "id": str(ad["_id"]),
            "title": ad["title"],
            "description": ad["description"],
            "image_url": ad["image_url"],
            "link_url": ad["link_url"]
        })
    return jsonify(result)

@flask_app.route(f'/{Config.BOT_TOKEN}', methods=['POST'])
def webhook():
    """टेलीग्राम वेबहुक हैंडलर"""
    global bot_app
    
    if not bot_app:
        logger.error("❌ बॉट ऐप इनिशियलाइज़ नहीं है")
        return 'बॉट तैयार नहीं है', 503
    
    try:
        update_data = request.get_json(force=True)
        logger.info(f"📩 अपडेट रिसीव: {update_data.get('update_id', 'unknown')}")
        
        update = Update.de_json(update_data, bot_app.bot)
        
        # नया इवेंट लूप बनाएं
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(bot_app.process_update(update))
        loop.close()
        
        logger.info("✅ अपडेट प्रोसेस सफल")
        return 'OK', 200
        
    except Exception as e:
        logger.error(f"❌ वेबहुक एरर: {e}")
        traceback.print_exc()
        return 'एरर', 500

# ====== बॉट इनिशियलाइज़ेशन ======
async def initialize_bot():
    """बॉट एप्लिकेशन इनिशियलाइज़ करें"""
    global bot_app
    
    # बॉट ऐप बनाएं
    bot_app = Application.builder().token(Config.BOT_TOKEN).build()
    
    # हैंडलर्स रजिस्टर करें
    bot_app.add_handler(CommandHandler("start", BotHandlers.start))
    bot_app.add_handler(CommandHandler("admin", AdminHandlers.admin_panel))
    
    # एडमिन कमांड्स
    if Config.ADMIN_IDS:
        bot_app.add_handler(CommandHandler("add", AdminHandlers.handle_admin_text))
        bot_app.add_handler(CommandHandler("remove", AdminHandlers.handle_admin_text))
        bot_app.add_handler(CommandHandler("block", AdminHandlers.handle_admin_text))
        bot_app.add_handler(CommandHandler("unblock", AdminHandlers.handle_admin_text))
        bot_app.add_handler(CommandHandler("stats", AdminHandlers.handle_admin_text))
    
    # मैसेज हैंडलर्स
    bot_app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, 
        BotHandlers.group_message
    ))
    bot_app.add_handler(MessageHandler(
        filters.StatusUpdate.WEB_APP_DATA, 
        BotHandlers.web_app_data
    ))
    
    # कॉलबैक हैंडलर
    bot_app.add_handler(CallbackQueryHandler(AdminHandlers.admin_callback, pattern="^admin_"))
    
    # ब्रॉडकास्ट हैंडलर (एडमिन के लिए)
    bot_app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
        AdminHandlers.handle_broadcast_message
    ))
    
    # एरर हैंडलर
    bot_app.add_error_handler(BotHandlers.error_handler)
    
    # बॉट इनिशियलाइज़ करें
    await bot_app.initialize()
    
    # वेबहुक सेट करें
    webhook_url = f"{Config.WEB_APP_URL}/{Config.BOT_TOKEN}"
    await bot_app.bot.set_webhook(
        url=webhook_url,
        allowed_updates=["message", "callback_query", "chat_member", "my_chat_member"]
    )
    
    logger.info(f"✅ बॉट इनिशियलाइज़ हुआ! वेबहुक: {webhook_url}")
    return bot_app

# ====== मेन फंक्शन ======
def main():
    """मेन एंट्री पॉइंट"""
    logger.info("🚀 एप्लिकेशन शुरू हो रहा है...")
    
    # इवेंट लूप बनाएं
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # बॉट इनिशियलाइज़ करें
        loop.run_until_complete(initialize_bot())
        logger.info("✅ बॉट तैयार है!")
        
        # फ्लास्क ऐप स्टार्ट करें
        logger.info(f"🌐 फ्लास्क ऐप पोर्ट {Config.PORT} पर शुरू हो रहा है")
        flask_app.run(host='0.0.0.0', port=Config.PORT, debug=False)
        
    except KeyboardInterrupt:
        logger.info("🛑 शटडाउन हो रहा है...")
    except Exception as e:
        logger.error(f"❌ फैटल एरर: {e}")
        traceback.print_exc()
    finally:
        # क्लीन शटडाउन
        if bot_app:
            loop.run_until_complete(bot_app.shutdown())
        loop.close()
        logger.info("👋 बॉट बंद हुआ")

if __name__ == "__main__":
    main()
