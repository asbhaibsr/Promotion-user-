# handlers.py - बॉट के सारे कमांड हैंडलर्स

import logging
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import Config
from database import db
from utils import is_admin, format_balance

logger = logging.getLogger(__name__)

class BotHandlers:
    
    @staticmethod
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        
        # Check for referral
        referrer = None
        if context.args and context.args[0].startswith("ref_"):
            try:
                referrer = int(context.args[0].replace("ref_", ""))
                logger.info(f"🔗 Referral: {referrer} -> {user.id}")
            except:
                pass
        
        # Create or get user
        db_user = db.get_user(user.id)
        if not db_user:
            db.create_user(user.id, user.username or "", user.first_name, referrer)
            db.update_balance(user.id, Config.WELCOME_BONUS, "welcome", "Welcome Bonus")
            
            await update.message.reply_text(
                f"🎉 *WELCOME BONUS!*\n"
                f"You got ₹{Config.WELCOME_BONUS}!",
                parse_mode='Markdown'
            )
        
        # Get user stats
        stats = db.get_user_stats(user.id)
        
        # Mini App Button
        keyboard = [[
            InlineKeyboardButton(
                "🚀 OPEN MINI APP 🚀",
                web_app={"url": f"{Config.WEB_APP_URL}/?user={user.id}"}
            )
        ]]
        
        if is_admin(user.id):
            keyboard.append([
                InlineKeyboardButton("👑 ADMIN PANEL", callback_data="admin_panel")
            ])
        
        welcome_msg = (
            f"✨ *Hello {user.first_name}!* ✨\n\n"
            f"💰 *Balance:* `{format_balance(stats['balance'])}`\n"
            f"🎰 *Spins:* `{stats['spins']}`\n"
            f"👑 *Tier:* `{stats['tier_name']}`\n"
            f"👥 *Active Referrals:* `{stats['active_refs']}`\n\n"
            f"🎯 *Today's Missions*\n"
            f"• 3 Searches → ₹0.15 + 1 Spin\n"
            f"• 2 Referrals → ₹0.50 + 1 Spin\n"
            f"• Daily Bonus → ₹0.10 + 1 Spin\n\n"
            f"👇 *Open Mini App to Start Earning!*"
        )
        
        await update.message.reply_text(
            welcome_msg,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        logger.info(f"✅ User {user.id} started bot")
    
    @staticmethod
    async def group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Track group messages for referral activation"""
        if not update.message or not update.message.text:
            return
        
        user = update.effective_user
        if not user or user.is_bot:
            return
        
        # Track search in group
        if len(update.message.text) > 2:
            logger.info(f"📝 Search: {user.id} -> {update.message.text[:30]}...")
            
            # Activate referral if first search
            referrer = db.track_search(user.id)
            if referrer:
                try:
                    await context.bot.send_message(
                        referrer,
                        f"🎉 *Referral Activated!*\n"
                        f"{user.first_name} did first search!\n"
                        f"✅ +1 Spin Added!",
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Referrer notification failed: {e}")
            
            # Process daily payment
            amount = db.process_daily_referral_payment(user.id)
            if amount:
                ref_doc = db.referrals.find_one({"user": user.id})
                if ref_doc:
                    try:
                        await context.bot.send_message(
                            ref_doc["referrer"],
                            f"💰 *Daily Referral Earnings!*\n"
                            f"From {user.first_name}: `{format_balance(amount)}`",
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        logger.error(f"Payment notification failed: {e}")
            
            # Update mission
            db.update_mission(user.id, "daily_search")
    
    @staticmethod
    async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check if bot is active in group"""
        if not update.message or not update.message.chat:
            return
        
        chat = update.message.chat
        
        if chat.type not in ['group', 'supergroup']:
            await update.message.reply_text("This command only works in groups!")
            return
        
        await update.message.reply_text(
            "✅ *I am active in this group!*\n\n"
            "Users can search movies here to activate referrals.",
            parse_mode='Markdown'
        )
        
        logger.info(f"✅ Check command used in group {chat.id}")
    
    @staticmethod
    async def web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle mini app data"""
        if not update.effective_message or not update.effective_message.web_app_data:
            return
        
        data = update.effective_message.web_app_data.data
        logger.info(f"📱 WebApp Data: {data[:100]}...")
        
        try:
            payload = json.loads(data)
            action = payload.get("action")
            user_id = payload.get("user_id")
            
            if not user_id:
                await update.effective_message.reply_text(json.dumps({"error": "User ID not found"}))
                return
            
            if action == "get_data":
                stats = db.get_user_stats(user_id)
                if stats:
                    stats.update({
                        "movie_group": Config.MOVIE_GROUP_LINK,
                        "new_group": Config.NEW_MOVIE_GROUP_LINK,
                        "channel": Config.CHANNEL_USERNAME,
                        "channel_link": Config.CHANNEL_LINK,
                        "channel_bonus": Config.CHANNEL_BONUS,
                        "min_withdrawal": Config.MIN_WITHDRAWAL
                    })
                    await update.effective_message.reply_text(json.dumps(stats))
                else:
                    await update.effective_message.reply_text(json.dumps({"error": "User not found"}))
            
            elif action == "spin":
                result = db.spin_wheel(user_id)
                await update.effective_message.reply_text(json.dumps(result))
                logger.info(f"🎡 User {user_id} spun: {result.get('prize', 0)}")
            
            elif action == "daily":
                result = db.claim_daily(user_id)
                if result:
                    await update.effective_message.reply_text(json.dumps(result))
                    logger.info(f"📅 User {user_id} claimed daily: {result['bonus']}")
                else:
                    await update.effective_message.reply_text(json.dumps({"error": "Already claimed today"}))
            
            elif action == "save_payment":
                method = payload.get("method")
                details = payload.get("details")
                
                db.update_user(user_id, {
                    "payment_method": method,
                    "payment_details": details
                })
                
                await update.effective_message.reply_text(json.dumps({"success": True}))
                logger.info(f"💳 User {user_id} saved payment details")
            
            elif action == "withdraw":
                amount = float(payload.get("amount", 0))
                method = payload.get("method")
                details = payload.get("details")
                
                success, msg = db.create_withdrawal(user_id, amount, method, details)
                
                if success:
                    for admin_id in Config.ADMIN_IDS:
                        try:
                            await context.bot.send_message(
                                admin_id,
                                f"💰 *New Withdrawal Request!*\n\n"
                                f"👤 User: `{user_id}`\n"
                                f"💵 Amount: `{format_balance(amount)}`\n"
                                f"🏦 Method: `{method.upper()}`\n"
                                f"📝 Details: `{details}`",
                                parse_mode='Markdown'
                            )
                        except:
                            pass
                
                await update.effective_message.reply_text(json.dumps({"success": success, "message": msg}))
                logger.info(f"💰 User {user_id} requested withdrawal: ₹{amount}")
            
            elif action == "leaderboard":
                lb = db.get_current_leaderboard()
                result = []
                for idx, user in enumerate(lb, 1):
                    result.append({
                        "rank": idx,
                        "name": user.get("full_name", "User")[:20],
                        "refs": user.get("monthly_referrals", 0),
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
                missions = db.get_missions(user_id)
                await update.effective_message.reply_text(json.dumps(missions))
            
            elif action == "report_issue":
                issue = payload.get("issue")
                for admin_id in Config.ADMIN_IDS:
                    try:
                        await context.bot.send_message(
                            admin_id,
                            f"⚠️ *User Report!*\n\n"
                            f"👤 User: `{user_id}`\n"
                            f"📝 Issue: `{issue}`",
                            parse_mode='Markdown'
                        )
                    except:
                        pass
                await update.effective_message.reply_text(json.dumps({"success": True}))
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON Decode Error: {e}")
            await update.effective_message.reply_text(json.dumps({"error": "Invalid data"}))
        
        except Exception as e:
            logger.error(f"WebApp Data Error: {e}")
            await update.effective_message.reply_text(json.dumps({"error": str(e)}))
    
    @staticmethod
    async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Global error handler"""
        logger.error(f"Error in update {update}: {context.error}")
        
        try:
            if update and update.effective_message:
                await update.effective_message.reply_text(
                    "❌ *Technical Error*\n"
                    "Please try again later.",
                    parse_mode='Markdown'
                )
        except:
            pass
