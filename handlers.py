# handlers.py - Advanced Bot Handlers

import logging
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import Config
from database import db
from utils import is_admin, format_balance, escape_markdown

logger = logging.getLogger(__name__)

class BotHandlers:
    
    @staticmethod
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command handler"""
        user = update.effective_user
        
        # Check for referral
        referrer = None
        if context.args and context.args[0].startswith("ref_"):
            try:
                referrer = int(context.args[0].replace("ref_", ""))
                logger.info(f"🔗 Referral click: {referrer} -> {user.id}")
            except:
                pass
        
        # Create or get user
        db_user = db.get_user(user.id)
        if not db_user:
            db_user = db.create_user(user.id, user.username or "", user.first_name, referrer)
            db.update_balance(user.id, Config.WELCOME_BONUS, "welcome", "Welcome Bonus")
            
            # Send welcome bonus message
            await update.message.reply_text(
                f"🎉 *WELCOME BONUS!*\n"
                f"You got ₹{Config.WELCOME_BONUS} credited to your account!",
                parse_mode='Markdown'
            )
            
            # Notify referrer if exists
            if referrer and referrer != user.id:
                try:
                    ref_user = db.get_user(referrer)
                    if ref_user:
                        await context.bot.send_message(
                            referrer,
                            f"🎉 *New Referral!*\n\n"
                            f"👤 {user.first_name} joined using your link!\n"
                            f"✅ They need to search in group to activate.",
                            parse_mode='Markdown'
                        )
                except Exception as e:
                    logger.error(f"Referrer notification failed: {e}")
        
        # Get user stats
        stats = db.get_user_stats(user.id)
        
        # Create welcome message with animations
        welcome_msg = (
            f"✨ *WELCOME TO FILMYFUND* ✨\n\n"
            f"👋 *Hello {escape_markdown(user.first_name)}!*\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💰 *Balance:* `{format_balance(stats['balance'])}`\n"
            f"🎰 *Spins:* `{stats['spins']}`\n"
            f"👑 *Tier:* `{stats['tier_name']}`\n"
            f"👥 *Active Referrals:* `{stats['active_refs']}`\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"🎯 *How to Earn?*\n"
            f"• 🔍 Search movies in group → Daily ₹\n"
            f"• 👥 Refer friends → Lifetime earnings\n"
            f"• 🎡 Spin wheel → Win up to ₹5\n"
            f"• 📅 Daily bonus → Streak rewards\n\n"
            f"👇 *Open Mini App to Start!*"
        )
        
        # Create keyboard
        keyboard = [
            [
                InlineKeyboardButton(
                    "🚀 OPEN MINI APP 🚀",
                    web_app={"url": f"{Config.WEB_APP_URL}/?user={user.id}"}
                )
            ],
            [
                InlineKeyboardButton("📢 Join Channel", url=Config.CHANNEL_LINK),
                InlineKeyboardButton("👥 Refer & Earn", callback_data="show_ref_link")
            ]
        ]
        
        if is_admin(user.id):
            keyboard.append([
                InlineKeyboardButton("👑 ADMIN PANEL", callback_data="admin_panel")
            ])
        
        # Send message
        await update.message.reply_text(
            welcome_msg,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        logger.info(f"✅ User {user.id} started bot")
    
    @staticmethod
    async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check if bot is active in group"""
        if not update.message or not update.message.chat:
            return
        
        chat = update.message.chat
        
        if chat.type not in ['group', 'supergroup']:
            await update.message.reply_text("❌ This command only works in groups!")
            return
        
        # Check if user is admin
        user_id = update.effective_user.id
        if not is_admin(user_id):
            await update.message.reply_text("❌ Only admins can use this command!")
            return
        
        await update.message.reply_text(
            "✅ *I am active in this group!*\n\n"
            "Users can search movies here to activate referrals.\n"
            "Each search contributes to daily missions.",
            parse_mode='Markdown'
        )
        
        logger.info(f"✅ Check command used in group {chat.id}")
    
    @staticmethod
    async def group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Track group messages for referral activation"""
        if not update.message or not update.message.text:
            return
        
        user = update.effective_user
        if not user or user.is_bot:
            return
        
        # Only track if message is longer than 2 chars (likely a search)
        if len(update.message.text) > 2:
            logger.info(f"📝 Search in group: {user.id} -> {update.message.text[:30]}...")
            
            # Track search and get referrer if activated
            referrer = db.track_search(user.id)
            
            # Notify referrer if first search
            if referrer:
                try:
                    await context.bot.send_message(
                        referrer,
                        f"🎉 *Referral Activated!*\n\n"
                        f"👤 {user.first_name} did their first search!\n"
                        f"✅ You got +1 Spin as bonus!\n\n"
                        f"Now you'll earn daily from their activity!",
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Referrer notification failed: {e}")
            
            # Process daily payment for this user's referrer
            amount = db.process_daily_referral_payment(user.id)
            if amount:
                ref_doc = db.referrals.find_one({"user": user.id})
                if ref_doc:
                    try:
                        referrer_name = user.first_name
                        await context.bot.send_message(
                            ref_doc["referrer"],
                            f"💰 *Daily Referral Earnings!*\n\n"
                            f"From {referrer_name}: `{format_balance(amount)}`\n"
                            f"Keep searching to earn more!",
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        logger.error(f"Payment notification failed: {e}")
            
            # Update mission
            db.update_mission(user.id, "daily_search")
    
    @staticmethod
    async def web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle mini app data - ALL ACTIONS WORKING"""
        if not update.effective_message or not update.effective_message.web_app_data:
            return
        
        data = update.effective_message.web_app_data.data
        logger.info(f"📱 WebApp Data received: {data[:100]}...")
        
        try:
            payload = json.loads(data)
            action = payload.get("action")
            user_id = payload.get("user_id")
            
            if not user_id:
                await update.effective_message.reply_text(json.dumps({"error": "User ID not found"}))
                return
            
            # ===== GET USER DATA =====
            if action == "get_data":
                stats = db.get_user_stats(user_id)
                if stats:
                    # Add config data
                    stats.update({
                        "channel": Config.CHANNEL_USERNAME,
                        "channel_link": Config.CHANNEL_LINK,
                        "channel_bonus": Config.CHANNEL_BONUS,
                        "min_withdrawal": Config.MIN_WITHDRAWAL,
                        "daily_base": Config.DAILY_BONUS_BASE,
                        "daily_increment": Config.DAILY_BONUS_INCREMENT,
                        "welcome_bonus": Config.WELCOME_BONUS,
                        "spin_prizes": Config.SPIN_PRIZES,
                        "bot_username": Config.BOT_USERNAME
                    })
                    await update.effective_message.reply_text(json.dumps(stats))
                else:
                    await update.effective_message.reply_text(json.dumps({"error": "User not found"}))
            
            # ===== SPIN WHEEL =====
            elif action == "spin":
                result = db.spin_wheel(user_id)
                await update.effective_message.reply_text(json.dumps(result))
                logger.info(f"🎡 User {user_id} spun: {result.get('prize', 0)}")
            
            # ===== DAILY BONUS =====
            elif action == "daily":
                result = db.claim_daily(user_id)
                if result:
                    await update.effective_message.reply_text(json.dumps(result))
                    logger.info(f"📅 User {user_id} claimed daily: {result['bonus']}")
                else:
                    await update.effective_message.reply_text(json.dumps({"error": "Already claimed today"}))
            
            # ===== SAVE PAYMENT =====
            elif action == "save_payment":
                method = payload.get("method", "upi")
                details = payload.get("details", "")
                
                db.update_user(user_id, {
                    "payment_method": method,
                    "payment_details": details
                })
                
                await update.effective_message.reply_text(json.dumps({
                    "success": True,
                    "method": method,
                    "details": details
                }))
                logger.info(f"💳 User {user_id} saved payment details: {method}")
            
            # ===== WITHDRAW =====
            elif action == "withdraw":
                amount = float(payload.get("amount", 0))
                method = payload.get("method")
                details = payload.get("details")
                
                success, msg = db.create_withdrawal(user_id, amount, method, details)
                
                if success:
                    # Notify all admins
                    for admin_id in Config.ADMIN_IDS:
                        try:
                            user = db.get_user(user_id)
                            name = user.get("full_name", "User") if user else "User"
                            
                            await context.bot.send_message(
                                admin_id,
                                f"💰 *New Withdrawal Request!*\n\n"
                                f"👤 User: {name}\n"
                                f"🆔 ID: `{user_id}`\n"
                                f"💵 Amount: `{format_balance(amount)}`\n"
                                f"🏦 Method: `{method.upper()}`\n"
                                f"📝 Details: `{details}`\n\n"
                                f"Use /process_{payload.get('withdrawal_id', '')} to process",
                                parse_mode='Markdown'
                            )
                        except Exception as e:
                            logger.error(f"Admin notification failed: {e}")
                
                await update.effective_message.reply_text(json.dumps({
                    "success": success, 
                    "message": msg
                }))
                logger.info(f"💰 User {user_id} requested withdrawal: ₹{amount}")
            
            # ===== LEADERBOARD =====
            elif action == "leaderboard":
                lb = db.get_current_leaderboard()
                result = []
                for idx, user in enumerate(lb, 1):
                    result.append({
                        "rank": idx,
                        "name": user.get("full_name", "User")[:20],
                        "refs": user.get("monthly_referrals", 0),
                        "balance": user.get("balance", 0),
                        "tier": user.get("tier", 1)
                    })
                await update.effective_message.reply_text(json.dumps(result))
            
            # ===== TOP EARNERS =====
            elif action == "top_earners":
                top = db.get_balance_leaderboard()
                result = []
                for idx, user in enumerate(top, 1):
                    result.append({
                        "rank": idx,
                        "name": user.get("full_name", "User")[:20],
                        "balance": user.get("balance", 0)
                    })
                await update.effective_message.reply_text(json.dumps(result))
            
            # ===== CHANNEL JOIN =====
            elif action == "channel_join":
                joined = db.mark_channel_joined(user_id, Config.CHANNEL_USERNAME)
                await update.effective_message.reply_text(json.dumps({
                    "success": joined,
                    "bonus": Config.CHANNEL_BONUS if joined else 0
                }))
            
            # ===== MISSIONS =====
            elif action == "missions":
                missions = db.get_missions(user_id)
                await update.effective_message.reply_text(json.dumps(missions))
            
            # ===== REFERRAL INFO =====
            elif action == "referral_info":
                stats = db.get_user_stats(user_id)
                if stats:
                    await update.effective_message.reply_text(json.dumps({
                        "total_refs": stats["total_refs"],
                        "active_refs": stats["active_refs"],
                        "ref_earnings": stats["ref_earnings"],
                        "referral_link": stats["referral_link"]
                    }))
            
            # ===== REPORT ISSUE =====
            elif action == "report_issue":
                issue = payload.get("issue", "")
                
                db.save_report(user_id, issue)
                
                # Notify admins
                for admin_id in Config.ADMIN_IDS:
                    try:
                        user = db.get_user(user_id)
                        name = user.get("full_name", "User") if user else "User"
                        
                        await context.bot.send_message(
                            admin_id,
                            f"⚠️ *NEW USER REPORT!*\n\n"
                            f"👤 User: {name}\n"
                            f"🆔 ID: `{user_id}`\n"
                            f"📝 Issue: `{issue}`",
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        logger.error(f"Admin notification failed: {e}")
                
                await update.effective_message.reply_text(json.dumps({"success": True}))
                logger.info(f"📝 Report from user {user_id}: {issue[:50]}...")
            
            # ===== CHECK SEARCH STATUS =====
            elif action == "check_search":
                today = datetime.now().date().isoformat()
                searches = db.group_activity.count_documents({
                    "user_id": user_id,
                    "date": today
                })
                await update.effective_message.reply_text(json.dumps({
                    "searches": searches
                }))
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON Decode Error: {e}")
            await update.effective_message.reply_text(json.dumps({"error": "Invalid data format"}))
        
        except Exception as e:
            logger.error(f"WebApp Data Error: {e}")
            await update.effective_message.reply_text(json.dumps({"error": str(e)}))
    
    @staticmethod
    async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "show_ref_link":
            user_id = query.from_user.id
            stats = db.get_user_stats(user_id)
            
            if stats:
                await query.edit_message_text(
                    f"🔗 *Your Referral Link*\n\n"
                    f"`{stats['referral_link']}`\n\n"
                    f"👥 Total: {stats['total_refs']}\n"
                    f"✅ Active: {stats['active_refs']}\n"
                    f"💰 Earnings: {format_balance(stats['ref_earnings'])}\n\n"
                    f"Share this link with friends!\n"
                    f"They get ₹{Config.WELCOME_BONUS} on joining!",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Back", callback_data="back_to_start")
                    ]])
                )
        
        elif data == "back_to_start":
            # Re-show start message
            user = query.from_user
            stats = db.get_user_stats(user.id)
            
            welcome_msg = (
                f"✨ *WELCOME BACK* ✨\n\n"
                f"👋 *Hello {escape_markdown(user.first_name)}!*\n\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"💰 *Balance:* `{format_balance(stats['balance'])}`\n"
                f"🎰 *Spins:* `{stats['spins']}`\n"
                f"👑 *Tier:* `{stats['tier_name']}`\n"
                f"👥 *Active:* `{stats['active_refs']}`\n"
                f"━━━━━━━━━━━━━━━━━━"
            )
            
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
            
            await query.edit_message_text(
                welcome_msg,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
    
    @staticmethod
    async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Global error handler"""
        logger.error(f"Error in update {update}: {context.error}")
        
        try:
            if update and update.effective_message:
                await update.effective_message.reply_text(
                    "❌ *Technical Error*\n"
                    "Please try again later.\n"
                    "If problem persists, contact support.",
                    parse_mode='Markdown'
                )
        except:
            pass
