# ===== admin.py =====
import logging
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

class AdminHandlers:
    def __init__(self, config, db):
        self.config = config
        self.db = db
        logger.info("✅ Admin handlers initialized")
    
    # ========== MAIN ADMIN PANEL ==========
    
    async def admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Main admin panel command (/admin)"""
        user_id = update.effective_user.id
        
        # Check if user is admin
        if user_id not in self.config.ADMIN_IDS:
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
        
        # Create main menu keyboard
        keyboard = [
            [InlineKeyboardButton("📊 USER STATS", callback_data="admin_user_stats")],
            [InlineKeyboardButton("📢 BROADCAST", callback_data="admin_broadcast")],
            [InlineKeyboardButton("💰 WITHDRAWALS", callback_data="admin_withdrawals")],
            [InlineKeyboardButton("🏆 RESET LEADERBOARD", callback_data="admin_reset_leaderboard")],
            [InlineKeyboardButton("📈 PROCESS DAILY EARNINGS", callback_data="admin_daily_earnings")],
            [InlineKeyboardButton("📋 SYSTEM LOGS", callback_data="admin_logs")],
            [InlineKeyboardButton("🔍 SEARCH USER", callback_data="admin_search_user")],
            [InlineKeyboardButton("❌ CLOSE", callback_data="admin_close")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Get quick stats
        total_users = self.db.users.count_documents({})
        pending_withdrawals = self.db.withdrawals.count_documents({'status': 'pending'})
        active_today = self.db.daily_searches.count_documents({'date': datetime.now().date().isoformat()})
        total_searches = self.db.search_logs.count_documents({})
        
        text = (
            "👑 **Admin Panel**\n\n"
            f"📊 **Quick Stats:**\n"
            f"• Total Users: {total_users}\n"
            f"• Active Today: {active_today}\n"
            f"• Pending Withdrawals: {pending_withdrawals}\n"
            f"• Total Searches: {total_searches}\n\n"
            f"Select an option below:"
        )
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    
    # ========== CALLBACK HANDLER ==========
    
    async def handle_admin_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all admin callback queries"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = update.effective_user.id
        
        # Verify admin
        if user_id not in self.config.ADMIN_IDS:
            await query.edit_message_text("❌ Unauthorized")
            return
        
        # Route callbacks
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
        elif data == "admin_search_user":
            await self.search_user_prompt(query, context)
        elif data == "admin_close":
            await query.edit_message_text("🔒 Admin panel closed.")
        elif data == "back_to_admin":
            await self.back_to_admin(query, context)
        elif data.startswith("user_stats_"):
            target_id = int(data.replace("user_stats_", ""))
            await self.show_user_stats(query, context, target_id)
        elif data.startswith("approve_"):
            withdrawal_id = data.replace("approve_", "")
            await self.approve_withdrawal(query, context, withdrawal_id)
        elif data.startswith("reject_"):
            withdrawal_id = data.replace("reject_", "")
            await self.reject_withdrawal(query, context, withdrawal_id)
        elif data.startswith("add_money_"):
            target_id = int(data.replace("add_money_", ""))
            context.user_data['admin_action'] = f"add_money_{target_id}"
            await query.edit_message_text(
                f"💰 Enter amount to add for user {target_id}:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ CANCEL", callback_data=f"user_stats_{target_id}")
                ]])
            )
        elif data.startswith("remove_money_"):
            target_id = int(data.replace("remove_money_", ""))
            context.user_data['admin_action'] = f"remove_money_{target_id}"
            await query.edit_message_text(
                f"💰 Enter amount to remove from user {target_id}:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ CANCEL", callback_data=f"user_stats_{target_id}")
                ]])
            )
        elif data.startswith("clear_data_"):
            target_id = int(data.replace("clear_data_", ""))
            await self.confirm_clear_data(query, context, target_id)
        elif data.startswith("confirm_clear_"):
            target_id = int(data.replace("confirm_clear_", ""))
            await self.clear_user_data(query, context, target_id)
        elif data.startswith("cancel_clear_"):
            target_id = int(data.replace("cancel_clear_", ""))
            await self.show_user_stats(query, context, target_id)
    
    # ========== USER STATS MENU ==========
    
    async def user_stats_menu(self, query, context):
        """User statistics menu"""
        keyboard = [
            [InlineKeyboardButton("🔍 GET USER BY ID", callback_data="admin_search_user")],
            [InlineKeyboardButton("📊 OVERALL STATS", callback_data="admin_overall_stats")],
            [InlineKeyboardButton("📈 TOP USERS", callback_data="admin_top_users")],
            [InlineKeyboardButton("◀️ BACK", callback_data="back_to_admin")]
        ]
        
        # Get some quick stats
        total_users = self.db.users.count_documents({})
        active_today = self.db.daily_searches.count_documents({'date': datetime.now().date().isoformat()})
        users_with_balance = self.db.users.count_documents({'balance': {'$gt': 0}})
        
        text = (
            "📊 **User Statistics**\n\n"
            f"• Total Users: {total_users}\n"
            f"• Active Today: {active_today}\n"
            f"• Users with Balance: {users_with_balance}\n\n"
            "Choose an option:"
        )
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    
    # ========== SEARCH USER ==========
    
    async def search_user_prompt(self, query, context):
        """Prompt for user ID to search"""
        context.user_data['admin_action'] = 'search_user'
        
        keyboard = [[InlineKeyboardButton("◀️ BACK", callback_data="admin_user_stats")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🔍 **Search User**\n\n"
            "Please enter the user ID to search:",
            reply_markup=reply_markup
        )
    
    # ========== SHOW USER STATS ==========
    
    async def show_user_stats(self, query, context, target_id):
        """Show detailed stats for a specific user"""
        user = self.db.get_user(target_id)
        
        if not user:
            await query.edit_message_text(
                f"❌ User {target_id} not found",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ BACK", callback_data="admin_user_stats")
                ]])
            )
            return
        
        # Get withdrawal history
        withdrawals = self.db.get_user_withdrawals(target_id, 3)
        
        # Calculate daily earning
        daily_earning = user.get('active_refs', 0) * self.config.DAILY_REFERRAL_EARNING
        
        # Check if suspicious
        suspicious = user.get('suspicious_activity', False)
        blocked = user.get('withdrawal_blocked', False)
        
        status = "✅ Clean" if not suspicious and not blocked else "⚠️ **FLAGGED**" if suspicious else "🔴 **BLOCKED**"
        
        text = (
            f"👤 **User Details**\n"
            f"Status: {status}\n\n"
            f"**Basic Info:**\n"
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
            f"Last Active: {user.get('last_active', 'Unknown')[:10]}\n\n"
        )
        
        # Add recent withdrawals
        if withdrawals:
            text += "📜 **Recent Withdrawals:**\n"
            for w in withdrawals[:3]:
                text += f"• ₹{w['amount']} - {w['status']} ({w['request_date'][:10]})\n"
        
        # Create action buttons
        keyboard = [
            [
                InlineKeyboardButton("➕ ADD", callback_data=f"add_money_{target_id}"),
                InlineKeyboardButton("➖ REMOVE", callback_data=f"remove_money_{target_id}")
            ],
            [
                InlineKeyboardButton("🚫 FLAG USER", callback_data=f"flag_user_{target_id}"),
                InlineKeyboardButton("✅ UNFLAG", callback_data=f"unflag_user_{target_id}")
            ],
            [
                InlineKeyboardButton("📜 FULL HISTORY", callback_data=f"user_history_{target_id}"),
                InlineKeyboardButton("🗑️ CLEAR DATA", callback_data=f"clear_data_{target_id}")
            ],
            [InlineKeyboardButton("◀️ BACK", callback_data="admin_user_stats")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    
    # ========== BROADCAST ==========
    
    async def broadcast_menu(self, query, context):
        """Broadcast message menu"""
        context.user_data['admin_action'] = 'broadcast'
        
        keyboard = [[InlineKeyboardButton("◀️ BACK", callback_data="back_to_admin")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Get user count
        total_users = self.db.users.count_documents({})
        
        await query.edit_message_text(
            f"📢 **Broadcast Message**\n\n"
            f"Total users: {total_users}\n\n"
            f"Send me the message you want to broadcast to all users.\n"
            f"(You can send text, photo, video, or any media)",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ========== WITHDRAWALS ==========
    
    async def withdrawals_menu(self, query, context):
        """Show pending withdrawals"""
        withdrawals = list(self.db.withdrawals.find(
            {'status': 'pending'}
        ).sort('request_date', 1).limit(10))
        
        if not withdrawals:
            await query.edit_message_text(
                "✅ No pending withdrawals.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ BACK", callback_data="back_to_admin")
                ]])
            )
            return
        
        text = f"💰 **Pending Withdrawals** ({len(withdrawals)})\n\n"
        
        for w in withdrawals:
            user = self.db.get_user(w['user_id'])
            user_name = user.get('first_name', 'Unknown')[:15] if user else 'Unknown'
            
            text += (
                f"ID: `{str(w['_id'])[-8:]}`\n"
                f"User: {user_name} ({w['user_id']})\n"
                f"Amount: ₹{w['amount']}\n"
                f"Method: {w['method']}\n"
                f"Date: {w['request_date'][:10]}\n"
                f"[Approve](command: approve_{w['_id']}) | [Reject](command: reject_{w['_id']})\n\n"
            )
        
        # Since markdown links don't work in Telegram, we'll use buttons
        # We'll show first withdrawal with buttons
        first = withdrawals[0]
        user_first = self.db.get_user(first['user_id'])
        user_name_first = user_first.get('first_name', 'Unknown') if user_first else 'Unknown'
        
        detail_text = (
            f"💰 **Withdrawal Request**\n\n"
            f"ID: `{str(first['_id'])[-8:]}`\n"
            f"User: {user_name_first} (ID: {first['user_id']})\n"
            f"Amount: ₹{first['amount']:.2f}\n"
            f"Method: {first['method']}\n"
            f"Details: {first['details']}\n"
            f"Date: {first['request_date']}\n\n"
            f"Approve or Reject?"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_{first['_id']}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_{first['_id']}")
            ],
            [InlineKeyboardButton("◀️ BACK", callback_data="back_to_admin")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(detail_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        
        # If more than 1, show count
        if len(withdrawals) > 1:
            await query.message.reply_text(f"⚠️ {len(withdrawals)-1} more pending withdrawals...")
    
    async def approve_withdrawal(self, query, context, withdrawal_id):
        """Approve a withdrawal"""
        try:
            from bson.objectid import ObjectId
            withdrawal = self.db.withdrawals.find_one({'_id': ObjectId(withdrawal_id)})
        except:
            withdrawal = None
        
        if not withdrawal:
            await query.edit_message_text("❌ Withdrawal not found")
            return
        
        # Update status
        self.db.withdrawals.update_one(
            {'_id': ObjectId(withdrawal_id)},
            {
                '$set': {
                    'status': 'completed',
                    'processed_date': datetime.now().isoformat(),
                    'admin_id': query.from_user.id
                }
            }
        )
        
        # Notify user
        try:
            await context.bot.send_message(
                chat_id=withdrawal['user_id'],
                text=(
                    f"✅ **Withdrawal Approved!**\n\n"
                    f"Amount: ₹{withdrawal['amount']}\n"
                    f"Method: {withdrawal['method']}\n\n"
                    f"Your withdrawal has been approved and will be processed shortly."
                ),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Could not notify user: {e}")
        
        await query.edit_message_text(
            f"✅ Withdrawal ₹{withdrawal['amount']} approved!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ BACK TO WITHDRAWALS", callback_data="admin_withdrawals")
            ]])
        )
    
    async def reject_withdrawal(self, query, context, withdrawal_id):
        """Reject a withdrawal"""
        try:
            from bson.objectid import ObjectId
            withdrawal = self.db.withdrawals.find_one({'_id': ObjectId(withdrawal_id)})
        except:
            withdrawal = None
        
        if not withdrawal:
            await query.edit_message_text("❌ Withdrawal not found")
            return
        
        # Update status
        self.db.withdrawals.update_one(
            {'_id': ObjectId(withdrawal_id)},
            {
                '$set': {
                    'status': 'rejected',
                    'processed_date': datetime.now().isoformat(),
                    'admin_id': query.from_user.id
                }
            }
        )
        
        # Refund balance
        self.db.add_balance(
            withdrawal['user_id'],
            withdrawal['amount'],
            f"Refund for rejected withdrawal"
        )
        
        # Notify user
        try:
            await context.bot.send_message(
                chat_id=withdrawal['user_id'],
                text=(
                    f"❌ **Withdrawal Rejected**\n\n"
                    f"Amount: ₹{withdrawal['amount']}\n\n"
                    f"Your withdrawal request was rejected. Please contact support for more information."
                ),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Could not notify user: {e}")
        
        await query.edit_message_text(
            f"❌ Withdrawal ₹{withdrawal['amount']} rejected and refunded!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ BACK TO WITHDRAWALS", callback_data="admin_withdrawals")
            ]])
        )
    
    # ========== LEADERBOARD RESET ==========
    
    async def reset_leaderboard(self, query, context):
        """Reset weekly leaderboard and give rewards"""
        # Get top 10 users
        top_users = list(self.db.users.find(
            {'weekly_searches': {'$gt': 0}, 'suspicious_activity': False}
        ).sort('weekly_searches', -1).limit(10))
        
        rewards = []
        
        for i, user in enumerate(top_users):
            rank = i + 1
            reward = 0
            
            # Calculate reward
            if rank <= 3 and user.get('active_refs', 0) >= 50:
                reward = 200
            elif rank <= 10 and user.get('active_refs', 0) >= 25:
                reward = 50
            
            if reward > 0:
                self.db.add_balance(
                    user['user_id'],
                    reward,
                    f"Weekly leaderboard rank #{rank}"
                )
                rewards.append({
                    'user_id': user['user_id'],
                    'name': user.get('first_name', 'User'),
                    'rank': rank,
                    'reward': reward
                })
        
        # Reset weekly searches
        self.db.users.update_many({}, {'$set': {'weekly_searches': 0}})
        
        text = "🏆 **Leaderboard Reset**\n\n"
        if rewards:
            text += "Rewards given:\n"
            for r in rewards:
                text += f"• {r['name']}: Rank #{r['rank']} - ₹{r['reward']}\n"
        else:
            text += "No rewards given this week."
        
        keyboard = [[InlineKeyboardButton("◀️ BACK", callback_data="back_to_admin")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    
    # ========== DAILY EARNINGS ==========
    
    async def process_daily_earnings(self, query, context):
        """Manually process daily earnings"""
        count = self.db.process_daily_referral_earnings()
        
        text = f"✅ **Daily Earnings Processed**\n\nProcessed earnings for {count} active referrals."
        
        keyboard = [[InlineKeyboardButton("◀️ BACK", callback_data="back_to_admin")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    
    # ========== SYSTEM LOGS ==========
    
    async def show_logs(self, query, context):
        """Show system logs"""
        # Get recent transactions
        recent_tx = list(self.db.transactions.find().sort('timestamp', -1).limit(5))
        
        # Get recent withdrawals
        recent_wd = list(self.db.withdrawals.find().sort('request_date', -1).limit(5))
        
        # Get recent users
        recent_users = list(self.db.users.find().sort('join_date', -1).limit(5))
        
        text = "📋 **System Logs**\n\n"
        
        text += "**Recent Transactions:**\n"
        for t in recent_tx:
            text += f"• {t['timestamp'][:10]}: User {t['user_id']} - ₹{t['amount']} ({t['type']})\n"
        
        text += "\n**Recent Withdrawals:**\n"
        for w in recent_wd:
            text += f"• {w['request_date'][:10]}: ₹{w['amount']} - {w['status']}\n"
        
        text += "\n**New Users:**\n"
        for u in recent_users:
            text += f"• {u['join_date'][:10]}: {u.get('first_name', 'User')}\n"
        
        keyboard = [[InlineKeyboardButton("◀️ BACK", callback_data="back_to_admin")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Split if too long
        if len(text) > 4000:
            text = text[:4000] + "...\n(Truncated)"
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    
    # ========== CLEAR USER DATA ==========
    
    async def confirm_clear_data(self, query, context, target_id):
        """Confirm clearing user data"""
        keyboard = [
            [
                InlineKeyboardButton("✅ YES, CLEAR", callback_data=f"confirm_clear_{target_id}"),
                InlineKeyboardButton("❌ NO", callback_data=f"cancel_clear_{target_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"⚠️ **WARNING**\n\n"
            f"Are you sure you want to clear ALL data for user {target_id}?\n"
            f"This will reset balance, referrals, and search history.\n\n"
            f"This action cannot be undone!",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def clear_user_data(self, query, context, target_id):
        """Clear all user data"""
        # Delete user data
        self.db.users.delete_one({'user_id': target_id})
        self.db.transactions.delete_many({'user_id': target_id})
        self.db.withdrawals.delete_many({'user_id': target_id})
        self.db.referrals.delete_many({'$or': [
            {'referrer_id': target_id},
            {'referred_id': target_id}
        ]})
        self.db.daily_searches.delete_many({'user_id': target_id})
        self.db.search_logs.delete_many({'user_id': target_id})
        
        await query.edit_message_text(
            f"✅ All data cleared for user {target_id}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ BACK", callback_data="admin_user_stats")
            ]])
        )
    
    # ========== BACK TO ADMIN ==========
    
    async def back_to_admin(self, query, context):
        """Return to main admin panel"""
        context.user_data['admin_action'] = None
        
        keyboard = [
            [InlineKeyboardButton("📊 USER STATS", callback_data="admin_user_stats")],
            [InlineKeyboardButton("📢 BROADCAST", callback_data="admin_broadcast")],
            [InlineKeyboardButton("💰 WITHDRAWALS", callback_data="admin_withdrawals")],
            [InlineKeyboardButton("🏆 RESET LEADERBOARD", callback_data="admin_reset_leaderboard")],
            [InlineKeyboardButton("📈 PROCESS DAILY EARNINGS", callback_data="admin_daily_earnings")],
            [InlineKeyboardButton("📋 SYSTEM LOGS", callback_data="admin_logs")],
            [InlineKeyboardButton("🔍 SEARCH USER", callback_data="admin_search_user")],
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
    
    # ========== HANDLE ADMIN MESSAGES ==========
    
    async def handle_admin_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin messages (for broadcast, add money, etc.)"""
        user_id = update.effective_user.id
        
        # Check if admin
        if user_id not in self.config.ADMIN_IDS:
            return
        
        # Check what action we're in
        action = context.user_data.get('admin_action')
        
        if not action:
            return
        
        # Handle broadcast
        if action == 'broadcast':
            await self.process_broadcast(update, context)
        
        # Handle add money
        elif action.startswith('add_money_'):
            target_id = int(action.replace('add_money_', ''))
            await self.process_add_money(update, context, target_id)
        
        # Handle remove money
        elif action.startswith('remove_money_'):
            target_id = int(action.replace('remove_money_', ''))
            await self.process_remove_money(update, context, target_id)
        
        # Handle search user
        elif action == 'search_user':
            await self.process_search_user(update, context)
    
    async def process_broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process broadcast message"""
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
                elif message.video:
                    await context.bot.send_video(
                        chat_id=user['user_id'],
                        video=message.video.file_id,
                        caption=f"📢 **Broadcast**\n\n{message.caption}" if message.caption else "📢 **Broadcast**"
                    )
                elif message.document:
                    await context.bot.send_document(
                        chat_id=user['user_id'],
                        document=message.document.file_id,
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
    
    async def process_add_money(self, update: Update, context: ContextTypes.DEFAULT_TYPE, target_id):
        """Add money to user"""
        try:
            amount = float(update.message.text.strip())
            
            if amount <= 0:
                await update.message.reply_text("❌ Amount must be positive")
                return
            
            # Add balance
            self.db.add_balance(target_id, amount, f"Admin added ₹{amount}")
            
            # Notify user
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=(
                        f"✅ **Money Added by Admin**\n\n"
                        f"Amount: +₹{amount:.2f}\n"
                        f"Your new balance: ₹{(self.db.get_user(target_id) or {}).get('balance', 0):.2f}"
                    ),
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                pass
            
            await update.message.reply_text(f"✅ Added ₹{amount:.2f} to user {target_id}")
            
            # Show updated user stats
            user = self.db.get_user(target_id)
            if user:
                await self.show_user_stats_to_admin(update, context, target_id)
            
        except ValueError:
            await update.message.reply_text("❌ Invalid amount. Please enter a number.")
        
        context.user_data['admin_action'] = None
    
    async def process_remove_money(self, update: Update, context: ContextTypes.DEFAULT_TYPE, target_id):
        """Remove money from user"""
        try:
            amount = float(update.message.text.strip())
            
            if amount <= 0:
                await update.message.reply_text("❌ Amount must be positive")
                return
            
            user = self.db.get_user(target_id)
            if not user:
                await update.message.reply_text("❌ User not found")
                return
            
            if user.get('balance', 0) < amount:
                await update.message.reply_text(f"❌ User only has ₹{user.get('balance', 0):.2f}")
                return
            
            # Remove balance
            self.db.users.update_one(
                {'user_id': target_id},
                {'$inc': {'balance': -amount}}
            )
            
            self.db.add_transaction(
                target_id,
                'admin_deduct',
                -amount,
                f"Admin removed ₹{amount}"
            )
            
            # Notify user
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=(
                        f"⚠️ **Money Deducted by Admin**\n\n"
                        f"Amount: -₹{amount:.2f}\n"
                        f"Your new balance: ₹{(self.db.get_user(target_id) or {}).get('balance', 0):.2f}"
                    ),
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                pass
            
            await update.message.reply_text(f"✅ Removed ₹{amount:.2f} from user {target_id}")
            
            # Show updated user stats
            user = self.db.get_user(target_id)
            if user:
                await self.show_user_stats_to_admin(update, context, target_id)
            
        except ValueError:
            await update.message.reply_text("❌ Invalid amount. Please enter a number.")
        
        context.user_data['admin_action'] = None
    
    async def process_search_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process user search"""
        try:
            target_id = int(update.message.text.strip())
            user = self.db.get_user(target_id)
            
            if user:
                await self.show_user_stats_to_admin(update, context, target_id)
            else:
                await update.message.reply_text(f"❌ User {target_id} not found")
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID. Please enter a number.")
        
        context.user_data['admin_action'] = None
    
    async def show_user_stats_to_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE, target_id):
        """Show user stats as a new message (not edit)"""
        user = self.db.get_user(target_id)
        
        if not user:
            await update.message.reply_text(f"❌ User {target_id} not found")
            return
        
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
            [InlineKeyboardButton("◀️ BACK TO ADMIN", callback_data="back_to_admin")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
