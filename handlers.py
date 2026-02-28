# handlers.py
import logging
import json
import random
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import Config
from database import db
from utils import (
    get_referral_link, format_balance, get_tier_name,
    check_channel_membership, is_admin, escape_markdown
)

logger = logging.getLogger(__name__)

class BotHandlers:
    
    @staticmethod
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """स्टार्ट कमांड हैंडलर"""
        user = update.effective_user
        
        # रेफरल चेक करें
        referrer = None
        if context.args and context.args[0].startswith("ref_"):
            try:
                referrer = int(context.args[0].replace("ref_", ""))
            except:
                pass
        
        # यूजर बनाएं या प्राप्त करें
        db_user = db.get_user(user.id)
        if not db_user:
            db.create_user(user.id, user.username or "", user.first_name, referrer)
            
            # वेलकम बोनस
            db.update_balance(user.id, Config.WELCOME_BONUS, "welcome", "वेलकम बोनस")
            db.users.update_one({"user_id": user.id}, {"$set": {"welcome_bonus": True}})
            
            await update.message.reply_text(
                f"🎉 *वेलकम बोनस!*\n"
                f"आपको ₹{Config.WELCOME_BONUS} मिले!",
                parse_mode='Markdown'
            )
        
        # चैनल जॉइन चेक करें
        try:
            is_member = await check_channel_membership(context.bot, user.id, Config.CHANNEL_USERNAME)
            if is_member and not db_user.get("channel_joined", False):
                db.mark_channel_joined(user.id, Config.CHANNEL_USERNAME)
                await update.message.reply_text(
                    f"🎁 *चैनल जॉइन बोनस!*\n"
                    f"आपको ₹{Config.CHANNEL_BONUS} मिले!",
                    parse_mode='Markdown'
                )
        except Exception as e:
            logger.error(f"चैनल चेक एरर: {e}")
        
        # यूजर स्टैट्स
        stats = db.get_user_stats(user.id)
        
        # मिनी ऐप बटन
        keyboard = [[
            InlineKeyboardButton(
                "🚀 *मिनी ऐप खोलें* 🚀",
                web_app={"url": f"{Config.WEB_APP_URL}/?user={user.id}&lang=hi"}
            )
        ]]
        
        # अगर एडमिन है तो एडमिन बटन
        if is_admin(user.id):
            keyboard.append([
                InlineKeyboardButton("👑 *एडमिन पैनल*", callback_data="admin_panel")
            ])
        
        welcome_msg = (
            f"✨ *नमस्ते {user.first_name}!* ✨\n\n"
            f"💰 *बैलेंस:* `{format_balance(stats['balance'])}`\n"
            f"🎰 *स्पिन:* `{stats['spins']}`\n"
            f"👑 *टीयर:* `{stats['tier_name']}`\n"
            f"👥 *एक्टिव रेफरल:* `{stats['active_refs']}`\n\n"
            f"🎯 *आज के मिशन*\n"
            f"• 3 सर्च करें → ₹0.15 + 1 स्पिन\n"
            f"• 2 रेफर करें → ₹0.50 + 1 स्पिन\n"
            f"• डेली बोनस → ₹0.10 + 1 स्पिन\n\n"
            f"👇 *मिनी ऐप खोलें और कमाई शुरू करें!*"
        )
        
        await update.message.reply_text(
            welcome_msg,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        logger.info(f"✅ यूजर {user.id} ने बॉट स्टार्ट किया")
    
    @staticmethod
    async def group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ग्रुप मैसेज हैंडलर (मूवी सर्च)"""
        if not update.message or not update.message.text:
            return
        
        user = update.effective_user
        if not user or user.is_bot:
            return
        
        # सिर्फ टेक्स्ट मैसेज को ट्रैक करें
        if len(update.message.text) > 5:  # मिनिमम लेंथ
            logger.info(f"📝 सर्च: {user.id} -> {update.message.text[:30]}...")
            
            # रेफरल एक्टिवेट करें
            referrer = db.activate_referral(user.id)
            if referrer:
                try:
                    await context.bot.send_message(
                        referrer,
                        f"🎉 *रेफरल एक्टिव!*\n"
                        f"{user.first_name} ने पहली सर्च की!\n"
                        f"✅ +1 स्पिन मिला!",
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"रेफरर नोटिफिकेशन फेल: {e}")
            
            # रेफरर को पेमेंट
            amount = db.pay_referrer(user.id)
            if amount:
                ref_doc = db.referrals.find_one({"user": user.id})
                if ref_doc:
                    try:
                        await context.bot.send_message(
                            ref_doc["referrer"],
                            f"💰 *डेली रेफरल कमाई!*\n"
                            f"{user.first_name} से: `{format_balance(amount)}`",
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        logger.error(f"पेमेंट नोटिफिकेशन फेल: {e}")
            
            # मिशन अपडेट
            db.update_mission(user.id, "daily_search")
    
    @staticmethod
    async def web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """मिनी ऐप से डेटा हैंडल करें"""
        if not update.effective_message or not update.effective_message.web_app_data:
            return
        
        data = update.effective_message.web_app_data.data
        logger.info(f"📱 वेबऐप डेटा: {data[:100]}...")
        
        try:
            payload = json.loads(data)
            action = payload.get("action")
            user_id = payload.get("user_id")
            
            if not user_id:
                await update.effective_message.reply_text(json.dumps({"error": "यूजर आईडी नहीं मिली"}))
                return
            
            if action == "get_data":
                stats = db.get_user_stats(user_id)
                if stats:
                    stats.update({
                        "movie_group": Config.MOVIE_GROUP_LINK,
                        "new_group": Config.NEW_MOVIE_GROUP_LINK,
                        "all_groups": Config.ALL_GROUPS_LINK,
                        "channel": Config.CHANNEL_USERNAME,
                        "channel_bonus": Config.CHANNEL_BONUS
                    })
                    await update.effective_message.reply_text(json.dumps(stats))
                else:
                    await update.effective_message.reply_text(json.dumps({"error": "यूजर नहीं मिला"}))
            
            elif action == "spin":
                result = db.spin_wheel(user_id)
                await update.effective_message.reply_text(json.dumps(result))
                logger.info(f"🎡 यूजर {user_id} ने स्पिन किया: {result.get('prize', 0)}")
            
            elif action == "daily":
                result = db.claim_daily(user_id)
                if result:
                    await update.effective_message.reply_text(json.dumps(result))
                    logger.info(f"📅 यूजर {user_id} ने डेली बोनस क्लेम किया: {result['bonus']}")
                else:
                    await update.effective_message.reply_text(json.dumps({"error": "आज क्लेम कर चुके हैं"}))
            
            elif action == "save_payment":
                method = payload.get("method")
                details = payload.get("details")
                
                db.update_user(user_id, {
                    "payment_method": method,
                    "payment_details": details
                })
                
                await update.effective_message.reply_text(json.dumps({"success": True}))
                logger.info(f"💳 यूजर {user_id} ने पेमेंट डिटेल्स सेव की")
            
            elif action == "withdraw":
                amount = float(payload.get("amount", 0))
                method = payload.get("method")
                details = payload.get("details")
                
                success, msg = db.create_withdrawal(user_id, amount, method, details)
                
                if success:
                    # एडमिन को नोटिफिकेशन
                    for admin_id in Config.ADMIN_IDS:
                        try:
                            await context.bot.send_message(
                                admin_id,
                                f"💰 *नई विड्रॉल रिक्वेस्ट!*\n\n"
                                f"👤 यूजर: `{user_id}`\n"
                                f"💵 रकम: `{format_balance(amount)}`\n"
                                f"🏦 तरीका: `{method.upper()}`\n"
                                f"📝 डिटेल्स: `{details}`",
                                parse_mode='Markdown'
                            )
                        except:
                            pass
                
                await update.effective_message.reply_text(json.dumps({"success": success, "message": msg}))
                logger.info(f"💰 यूजर {user_id} ने विड्रॉल रिक्वेस्ट की: ₹{amount}")
            
            elif action == "leaderboard":
                lb = db.get_leaderboard()
                result = []
                for idx, user in enumerate(lb, 1):
                    result.append({
                        "rank": idx,
                        "name": user.get("full_name", "यूजर")[:20],
                        "refs": user.get("active_referrals", 0),
                        "balance": user.get("balance", 0)
                    })
                await update.effective_message.reply_text(json.dumps(result))
            
            elif action == "channel_join":
                joined = db.mark_channel_joined(user_id, Config.CHANNEL_USERNAME)
                await update.effective_message.reply_text(json.dumps({
                    "success": joined,
                    "bonus": Config.CHANNEL_BONUS if joined else 0
                }))
            
            elif action == "missions":
                missions = {}
                for mission_type in Config.MISSIONS.keys():
                    today = datetime.now().date().isoformat()
                    mission = db.missions.find_one({
                        "user_id": user_id,
                        "type": mission_type,
                        "date": today
                    })
                    missions[mission_type] = {
                        "count": mission["count"] if mission else 0,
                        "completed": mission["completed"] if mission else False
                    }
                await update.effective_message.reply_text(json.dumps(missions))
            
            elif action == "ad_view":
                ad_id = payload.get("ad_id")
                if ad_id and Config.ENABLE_ADS:
                    db.record_ad_view(ad_id, user_id)
                    await update.effective_message.reply_text(json.dumps({"success": True}))
            
            elif action == "get_ads":
                if Config.ENABLE_ADS:
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
                    await update.effective_message.reply_text(json.dumps(result))
                else:
                    await update.effective_message.reply_text(json.dumps([]))
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON डीकोड एरर: {e}")
            await update.effective_message.reply_text(json.dumps({"error": "इनवैलिड डेटा"}))
        
        except Exception as e:
            logger.error(f"वेबऐप डेटा एरर: {e}")
            await update.effective_message.reply_text(json.dumps({"error": str(e)}))
    
    @staticmethod
    async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ग्लोबल एरर हैंडलर"""
        logger.error(f"अपडेट {update} में एरर: {context.error}")
        
        try:
            if update and update.effective_message:
                await update.effective_message.reply_text(
                    "❌ *टेक्निकल एरर*\n"
                    "कृपया बाद में प्रयास करें।",
                    parse_mode='Markdown'
                )
        except:
            pass
