# ===== admin.py =====
import logging
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

class AdminHandlers:
    def __init__(self, config, db, handlers):
        self.config = config
        self.db = db
        self.handlers = handlers
    
    async def admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if user_id not in self.config.ADMIN_IDS:
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
        
        keyboard = [
            [InlineKeyboardButton("📊 USER STATS", callback_data="admin_user_stats")],
            [InlineKeyboardButton("📢 BROADCAST", callback_data="admin_broadcast")],
            [InlineKeyboardButton("💰 WITHDRAWALS", callback_data="admin_withdrawals")],
            [InlineKeyboardButton("🏆 RESET LEADERBOARD", callback_data="admin_reset_leaderboard")],
            [InlineKeyboardButton("📈 PROCESS DAILY EARNINGS", callback_data="admin_daily_earnings")],
            [InlineKeyboardButton("📋 SYSTEM LOGS", callback_data="admin_logs")],
            [InlineKeyboardButton("❌ CLOSE", callback_data="admin_close")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Get quick stats
        total_users = self.db.users.count_documents({})
        pending_withdrawals = self.db.withdrawals.count_documents({'status': 'pending'})
        active_today = self.db.daily_searches.count_documents({'date': datetime.now().date().isoformat()})
        
        text = (
            "👑 **Admin Panel**\n\n"
            f"📊 **Quick Stats:**\n"
            f"• Total Users: {total_users}\n"
            f"• Active Today: {active_today}\n"
            f"• Pending Withdrawals: {pending_withdrawals}\n\n"
            f"Select an option below:"
        )
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    
    async def handle_admin_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "admin_user_stats":
            await self.user_stats_menu(query, context)
        elif data == "admin_broadcast":
            await self.broadcast_menu(query, context)
        elif data == "admin_withdrawals":
            await self.withdrawals_menu(query, context)
        elif data == "admin_reset_leaderboard":
            await self.reset_leaderboard(query, context)
        elif data == "admin_daily_earnings":
            await self.process_daily_earnings(query, context)
        elif data == "admin_logs":
            await self.show_logs(query, context)
        elif data == "admin_close":
            await query.edit_message_text("🔒 Admin panel closed.")
        elif data.startswith("user_stats_"):
            user_id = int(data.replace("user_stats_", ""))
            await self.show_user_stats(query, context, user_id)
        elif data == "back_to_admin":
            await self.back_to_admin(query, context)
    
    async def user_stats_menu(self, query, context):
        keyboard = [
            [InlineKeyboardButton("🔍 GET USER BY ID", callback_data="admin_get_user")],
            [InlineKeyboardButton("📊 OVERALL STATS", callback_data="admin_overall_stats")],
            [InlineKeyboardButton("◀️ BACK", callback_data="back_to_admin")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "📊 **User Statistics**\n\n"
            "Choose an option:",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def broadcast_menu(self, query, context):
        context.user_data['admin_action'] = 'broadcast'
        keyboard = [[InlineKeyboardButton("◀️ BACK", callback_data="back_to_admin")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📢 **Broadcast Message**\n\n"
            "Send me the message you want to broadcast to all users.\n"
            "(You can send text, photo, or any media)",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def withdrawals_menu(self, query, context):
        withdrawals = self.db.get_pending_withdrawals()
        
        if not withdrawals:
            await query.edit_message_text(
                "✅ No pending withdrawals.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ BACK", callback_data="back_to_admin")
                ]])
            )
            return
        
        for w in withdrawals[:5]:
            user = self.db.get_user(w['user_id'])
            user_name = user.get('first_name', 'Unknown') if user else 'Unknown'
            
            text = (
                f"💰 **Withdrawal Request**\n\n"
                f"ID: `{w['_id'][-8:]}`\n"
                f"User: {user_name} (ID: {w['user_id']})\n"
                f"Amount: ₹{w['amount']:.2f}\n"
                f"Method: {w['method']}\n"
                f"Details: {w['details']}\n"
                f"Date: {w['request_date']}\n\n"
                f"Approve or Reject?"
            )
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ Approve", callback_data=f"approve_{w['_id']}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"reject_{w['_id']}")
                ],
                [InlineKeyboardButton("◀️ BACK", callback_data="back_to_admin")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        
        if len(withdrawals) > 5:
            await query.message.reply_text(f"⚠️ {len(withdrawals)-5} more pending...")
    
    async def reset_leaderboard(self, query, context):
        rewards = self.db.reset_weekly_leaderboard()
        
        text = "🏆 **Leaderboard Reset**\n\n"
        if rewards:
            text += "Rewards given:\n"
            for r in rewards:
                text += f"• User {r['user_id']}: Rank #{r['rank']} - ₹{r['reward']}\n"
        else:
            text += "No rewards given this week."
        
        keyboard = [[InlineKeyboardButton("◀️ BACK", callback_data="back_to_admin")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    
    async def process_daily_earnings(self, query, context):
        count = self.db.process_daily_referral_earnings()
        
        text = f"✅ **Daily Earnings Processed**\n\nProcessed earnings for {count} active referrals."
        
        keyboard = [[InlineKeyboardButton("◀️ BACK", callback_data="back_to_admin")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    
    async def show_logs(self, query, context):
        # Get recent transactions
        recent = list(self.db.transactions.find().sort('timestamp', -1).limit(10))
        
        text = "📋 **Recent Transactions**\n\n"
        for t in recent:
            text += f"• {t['timestamp'][:10]}: User {t['user_id']} - ₹{t['amount']} ({t['type']})\n"
        
        keyboard = [[InlineKeyboardButton("◀️ BACK", callback_data="back_to_admin")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    
    async def back_to_admin(self, query, context):
        keyboard = [
            [InlineKeyboardButton("📊 USER STATS", callback_data="admin_user_stats")],
            [InlineKeyboardButton("📢 BROADCAST", callback_data="admin_broadcast")],
            [InlineKeyboardButton("💰 WITHDRAWALS", callback_data="admin_withdrawals")],
            [InlineKeyboardButton("🏆 RESET LEADERBOARD", callback_data="admin_reset_leaderboard")],
            [InlineKeyboardButton("📈 PROCESS DAILY EARNINGS", callback_data="admin_daily_earnings")],
            [InlineKeyboardButton("📋 SYSTEM LOGS", callback_data="admin_logs")],
            [InlineKeyboardButton("❌ CLOSE", callback_data="admin_close")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        total_users = self.db.users.count_documents({})
        pending_withdrawals = self.db.withdrawals.count_documents({'status': 'pending'})
        active_today = self.db.daily_searches.count_documents({'date': datetime.now().date().isoformat()})
        
        text = (
            "👑 **Admin Panel**\n\n"
            f"📊 **Quick Stats:**\n"
            f"• Total Users: {total_users}\n"
            f"• Active Today: {active_today}\n"
            f"• Pending Withdrawals: {pending_withdrawals}\n\n"
            f"Select an option below:"
        )
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    
    async def show_user_stats(self, query, context, target_id):
        user = self.db.get_user(target_id)
        
        if not user:
            await query.edit_message_text(
                f"❌ User {target_id} not found",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ BACK", callback_data="admin_user_stats")
                ]])
            )
            return
        
        # Calculate daily earning
        daily_earning = user.get('active_refs', 0) * self.config.DAILY_REFERRAL_EARNING
        
        text = (
            f"👤 **User Details**\n\n"
            f"ID: `{user['user_id']}`\n"
            f"Name: {user.get('first_name', 'N/A')}\n"
            f"Username: @{user.get('username', 'N/A')}\n\n"
            f"💰 **Financial**\n"
            f"Balance: ₹{user.get('balance', 0):.2f}\n"
            f"Total Earned: ₹{user.get('total_earned', 0):.2f}\n\n"
            f"👥 **Referrals**\n"
            f"Total: {user.get('total_refs', 0)}\n"
            f"Active: {user.get('active_refs', 0)}\n"
            f"Pending: {user.get('pending_refs', 0)}\n"
            f"Daily Earnings: ₹{daily_earning:.2f}\n\n"
            f"📊 **Activity**\n"
            f"Tier: {self.config.get_tier_name(user.get('tier', 1))}\n"
            f"Searches: {user.get('total_searches', 0)}\n"
            f"Joined: {user.get('join_date', 'Unknown')[:10]}\n"
            f"Last Active: {user.get('last_active', 'Unknown')[:10]}"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("➕ ADD MONEY", callback_data=f"add_money_{target_id}"),
                InlineKeyboardButton("➖ REMOVE MONEY", callback_data=f"remove_money_{target_id}")
            ],
            [
                InlineKeyboardButton("🔄 CLEAR DATA", callback_data=f"clear_data_{target_id}"),
                InlineKeyboardButton("🔄 CLEAR EARNINGS", callback_data=f"clear_earnings_{target_id}")
            ],
            [InlineKeyboardButton("◀️ BACK", callback_data="admin_user_stats")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    
    async def handle_admin_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin messages (for broadcast, etc.)"""
        user_id = update.effective_user.id
        
        if user_id not in self.config.ADMIN_IDS:
            return
        
        if context.user_data.get('admin_action') == 'broadcast':
            # Handle broadcast
            message = update.message
            users = self.db.users.find({}, {'user_id': 1})
            
            sent = 0
            failed = 0
            
            status_msg = await update.message.reply_text("📢 Broadcasting...")
            
            for user in users:
                try:
                    if message.text:
                        await context.bot.send_message(
                            chat_id=user['user_id'],
                            text=f"📢 **Broadcast Message**\n\n{message.text}",
                            parse_mode=ParseMode.MARKDOWN
                        )
                    elif message.photo:
                        await context.bot.send_photo(
                            chat_id=user['user_id'],
                            photo=message.photo[-1].file_id,
                            caption=f"📢 **Broadcast**\n\n{message.caption}" if message.caption else "📢 **Broadcast**"
                        )
                    sent += 1
                except Exception as e:
                    failed += 1
                    logger.error(f"Broadcast failed to {user['user_id']}: {e}")
                
                await asyncio.sleep(0.05)  # Avoid flood
            
            await status_msg.edit_text(
                f"✅ **Broadcast Complete**\n\n"
                f"• Sent: {sent}\n"
                f"• Failed: {failed}"
            )
            
            context.user_data['admin_action'] = None
