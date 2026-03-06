# ===== admin.py (COMPLETE FIXED - USER DETAILS BUTTON WORKS) =====

import logging
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from bson.objectid import ObjectId

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
        
        if user_id not in self.config.ADMIN_IDS:
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
        
        total_users = self.db.users.count_documents({})
        pending_withdrawals = self.db.withdrawals.count_documents({'status': 'pending'})
        active_today = self.db.daily_searches.count_documents({'date': datetime.now().date().isoformat()})
        total_searches = self.db.search_logs.count_documents({})
        
        total_balance = 0
        if self.db.users.count_documents({}) > 0:
            result = self.db.users.aggregate([
                {'$group': {'_id': None, 'total': {'$sum': '$balance'}}}
            ]).next()
            total_balance = result.get('total', 0) if result else 0
        
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
        
        text = (
            "👑 **Admin Panel**\n\n"
            f"📊 **Quick Stats:**\n"
            f"• Total Users: {total_users}\n"
            f"• Active Today: {active_today}\n"
            f"• Pending Withdrawals: {pending_withdrawals}\n"
            f"• Total Searches: {total_searches}\n"
            f"• Total Balance: ₹{total_balance:.2f}\n\n"
            f"Select an option below:"
        )
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    
    # ========== CALLBACK HANDLER ==========
    
    async def handle_admin_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all admin callback queries - FIXED: User detail button works"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = update.effective_user.id
        
        if user_id not in self.config.ADMIN_IDS:
            await query.edit_message_text("❌ Unauthorized")
            return
        
        logger.info(f"Admin callback: {data}")
        
        # ===== MAIN MENU OPTIONS =====
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
            
        # ===== USER STATS SUBMENU =====
        elif data == "admin_overall_stats":
            await self.show_overall_stats(query, context)
            
        elif data == "admin_top_users":
            await self.show_top_users(query, context)
            
        # ===== USER SPECIFIC ACTIONS =====
        elif data.startswith("user_stats_"):
            try:
                target_id = int(data.replace("user_stats_", ""))
                await self.show_user_stats(query, context, target_id)
            except Exception as e:
                logger.error(f"Error parsing user_stats callback: {e}")
                await query.edit_message_text(
                    "❌ Error loading user details",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("◀️ BACK", callback_data="admin_user_stats")
                    ]])
                )
        
        elif data.startswith("money_action_"):
            try:
                target_id = int(data.replace("money_action_", ""))
                await self.money_action_prompt(query, context, target_id)
            except Exception as e:
                logger.error(f"Error parsing money_action callback: {e}")
        
        elif data.startswith("clear_data_"):
            try:
                target_id = int(data.replace("clear_data_", ""))
                await self.clear_data_options(query, context, target_id)
            except Exception as e:
                logger.error(f"Error parsing clear_data callback: {e}")
        
        elif data == "clear_all_data":
            target_id = context.user_data.get('clearing_user')
            if target_id:
                context.user_data['clear_type'] = 'all'
                await self.confirm_clear_data(query, context, target_id)
            else:
                await query.edit_message_text("❌ Session expired")
        
        elif data == "clear_earnings_only":
            target_id = context.user_data.get('clearing_user')
            if target_id:
                context.user_data['clear_type'] = 'earning'
                await self.confirm_clear_data(query, context, target_id)
            else:
                await query.edit_message_text("❌ Session expired")
        
        elif data.startswith("confirm_clear_"):
            try:
                target_id = int(data.replace("confirm_clear_", ""))
                clear_type = context.user_data.get('clear_type', 'all')
                await self.clear_user_data(query, context, target_id, clear_type)
            except Exception as e:
                logger.error(f"Error parsing confirm_clear callback: {e}")
        
        elif data.startswith("cancel_clear_"):
            try:
                target_id = int(data.replace("cancel_clear_", ""))
                await self.show_user_stats(query, context, target_id)
            except Exception as e:
                logger.error(f"Error parsing cancel_clear callback: {e}")
        
        elif data.startswith("flag_user_"):
            try:
                target_id = int(data.replace("flag_user_", ""))
                await self.flag_user(query, context, target_id)
            except Exception as e:
                logger.error(f"Error parsing flag_user callback: {e}")
            
        elif data.startswith("unflag_user_"):
            try:
                target_id = int(data.replace("unflag_user_", ""))
                await self.unflag_user(query, context, target_id)
            except Exception as e:
                logger.error(f"Error parsing unflag_user callback: {e}")
            
        elif data.startswith("block_withdraw_"):
            try:
                target_id = int(data.replace("block_withdraw_", ""))
                await self.block_withdrawals(query, context, target_id)
            except Exception as e:
                logger.error(f"Error parsing block_withdraw callback: {e}")
            
        elif data.startswith("unblock_withdraw_"):
            try:
                target_id = int(data.replace("unblock_withdraw_", ""))
                await self.unblock_withdrawals(query, context, target_id)
            except Exception as e:
                logger.error(f"Error parsing unblock_withdraw callback: {e}")
            
        elif data.startswith("user_history_"):
            try:
                target_id = int(data.replace("user_history_", ""))
                await self.show_user_full_history(query, context, target_id)
            except Exception as e:
                logger.error(f"Error parsing user_history callback: {e}")
            
        # ===== WITHDRAWAL ACTIONS =====
        elif data.startswith("approve_"):
            withdrawal_id = data.replace("approve_", "")
            await self.approve_withdrawal(query, context, withdrawal_id)
            
        elif data.startswith("reject_"):
            withdrawal_id = data.replace("reject_", "")
            await self.reject_withdrawal(query, context, withdrawal_id)
    
    # ========== USER STATS MENU ==========
    
    async def user_stats_menu(self, query, context):
        """User statistics menu"""
        total_users = self.db.users.count_documents({})
        active_today = self.db.daily_searches.count_documents({'date': datetime.now().date().isoformat()})
        users_with_balance = self.db.users.count_documents({'balance': {'$gt': 0}})
        total_refs = self.db.referrals.count_documents({})
        active_refs = self.db.referrals.count_documents({'is_active': True})
        
        keyboard = [
            [InlineKeyboardButton("🔍 GET USER BY ID", callback_data="admin_search_user")],
            [InlineKeyboardButton("📊 OVERALL STATS", callback_data="admin_overall_stats")],
            [InlineKeyboardButton("📈 TOP USERS", callback_data="admin_top_users")],
            [InlineKeyboardButton("◀️ BACK", callback_data="back_to_admin")]
        ]
        
        text = (
            "📊 **User Statistics**\n\n"
            f"• Total Users: {total_users}\n"
            f"• Active Today: {active_today}\n"
            f"• Users with Balance: {users_with_balance}\n"
            f"• Total Referrals: {total_refs}\n"
            f"• Active Referrals: {active_refs}\n\n"
            "Choose an option:"
        )
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    
    async def show_overall_stats(self, query, context):
        """Show overall statistics"""
        total_users = self.db.users.count_documents({})
        active_today = self.db.daily_searches.count_documents({'date': datetime.now().date().isoformat()})
        
        week_ago = (datetime.now() - timedelta(days=7)).date().isoformat()
        active_week = self.db.daily_searches.distinct('user_id', {
            'date': {'$gte': week_ago}
        })
        
        total_balance = 0
        if self.db.users.count_documents({}) > 0:
            result = self.db.users.aggregate([
                {'$group': {'_id': None, 'total': {'$sum': '$balance'}}}
            ]).next()
            total_balance = result.get('total', 0) if result else 0
        
        total_withdrawn = 0
        if self.db.withdrawals.count_documents({'status': 'completed'}) > 0:
            result = self.db.withdrawals.aggregate([
                {'$match': {'status': 'completed'}},
                {'$group': {'_id': None, 'total': {'$sum': '$amount'}}}
            ]).next()
            total_withdrawn = result.get('total', 0) if result else 0
        
        text = (
            "📊 **Detailed Statistics**\n\n"
            f"👥 **Users:**\n"
            f"• Total: {total_users}\n"
            f"• Active Today: {active_today}\n"
            f"• Active this Week: {len(active_week)}\n\n"
            f"💰 **Financial:**\n"
            f"• Total Balance: ₹{total_balance:.2f}\n"
            f"• Total Withdrawn: ₹{total_withdrawn:.2f}\n"
            f"• Platform Balance: ₹{(total_balance - total_withdrawn):.2f}\n\n"
            f"📈 **Referrals:**\n"
            f"• Total: {self.db.referrals.count_documents({})}\n"
            f"• Active: {self.db.referrals.count_documents({'is_active': True})}\n"
            f"• Inactive: {self.db.referrals.count_documents({'is_active': False})}"
        )
        
        keyboard = [[InlineKeyboardButton("◀️ BACK", callback_data="admin_user_stats")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    async def show_top_users(self, query, context):
        """Show top users by different metrics"""
        top_balance = list(self.db.users.find(
            {'balance': {'$gt': 0}},
            {'first_name': 1, 'balance': 1}
        ).sort('balance', -1).limit(5))
        
        top_refs = list(self.db.users.find(
            {'active_refs': {'$gt': 0}},
            {'first_name': 1, 'active_refs': 1}
        ).sort('active_refs', -1).limit(5))
        
        top_searches = list(self.db.users.find(
            {'total_searches': {'$gt': 0}},
            {'first_name': 1, 'total_searches': 1}
        ).sort('total_searches', -1).limit(5))
        
        text = "📈 **Top Users**\n\n"
        
        text += "💰 **By Balance:**\n"
        for i, u in enumerate(top_balance, 1):
            text += f"{i}. {u.get('first_name', 'User')}: ₹{u['balance']:.2f}\n"
        
        text += "\n👥 **By Active Referrals:**\n"
        for i, u in enumerate(top_refs, 1):
            text += f"{i}. {u.get('first_name', 'User')}: {u['active_refs']}\n"
        
        text += "\n🔍 **By Searches:**\n"
        for i, u in enumerate(top_searches, 1):
            text += f"{i}. {u.get('first_name', 'User')}: {u['total_searches']}\n"
        
        keyboard = [[InlineKeyboardButton("◀️ BACK", callback_data="admin_user_stats")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
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
        """Show detailed stats for a specific user - FIXED: User detail button works"""
        user = self.db.get_user(target_id)
        
        if not user:
            await query.edit_message_text(
                f"❌ User {target_id} not found",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ BACK", callback_data="admin_user_stats")
                ]])
            )
            return
        
        withdrawals = list(self.db.withdrawals.find(
            {'user_id': target_id}
        ).sort('request_date', -1).limit(5))
        
        referrals = list(self.db.referrals.find(
            {'referrer_id': target_id}
        ).sort('join_date', -1).limit(5))
        
        referred_by = self.db.referrals.find_one({'referred_id': target_id})
        
        daily_earning = user.get('active_refs', 0) * self.config.DAILY_REFERRAL_EARNING
        
        suspicious = user.get('suspicious_activity', False)
        blocked = user.get('withdrawal_blocked', False)
        
        if blocked:
            status = "🔴 **BLOCKED**"
            status_emoji = "🔴"
        elif suspicious:
            status = "⚠️ **FLAGGED**"
            status_emoji = "⚠️"
        else:
            status = "✅ **CLEAN**"
            status_emoji = "✅"
        
        notify_ref = user.get('notify_referrals', True)
        notify_earn = user.get('notify_earnings', True)
        notify_wd = user.get('notify_withdrawals', True)
        
        text = (
            f"👤 **User Details** {status_emoji}\n"
            f"Status: {status}\n\n"
            f"**Basic Info:**\n"
            f"ID: `{user['user_id']}`\n"
            f"Name: {user.get('first_name', 'N/A')}\n"
            f"Username: @{user.get('username', 'N/A')}\n"
            f"Joined: {user.get('join_date', 'Unknown')[:10]}\n\n"
            f"💰 **Financial**\n"
            f"Balance: ₹{user.get('balance', 0):.2f}\n"
            f"Total Earned: ₹{user.get('total_earned', 0):.2f}\n\n"
            f"👥 **Referrals**\n"
            f"Total: {user.get('total_refs', 0)}\n"
            f"Active: {user.get('active_refs', 0)}\n"
            f"Pending: {user.get('pending_refs', 0)}\n"
            f"Daily Earnings: ₹{daily_earning:.2f}\n"
        )
        
        if referred_by:
            text += f"Referred By: {referred_by['referrer_id']}\n"
        
        text += f"\n📊 **Activity**\n"
        text += f"Tier: {self.config.get_tier_name(user.get('tier', 1))}\n"
        text += f"Searches: {user.get('total_searches', 0)}\n"
        text += f"Last Active: {user.get('last_active', 'Unknown')[:10]}\n\n"
        
        text += f"🔔 **Notifications**\n"
        text += f"• Referrals: {'✅ ON' if notify_ref else '❌ OFF'}\n"
        text += f"• Earnings: {'✅ ON' if notify_earn else '❌ OFF'}\n"
        text += f"• Withdrawals: {'✅ ON' if notify_wd else '❌ OFF'}\n\n"
        
        if withdrawals:
            text += "📜 **Recent Withdrawals:**\n"
            for w in withdrawals[:3]:
                w_id = str(w['_id'])[-6:]
                status_sym = "✅" if w['status'] == 'completed' else "❌" if w['status'] == 'rejected' else "⏳"
                text += f"• {status_sym} ₹{w['amount']} - {w['status']} ({w['request_date'][:10]})\n"
            text += "\n"
        
        if referrals:
            text += "👥 **Recent Referrals:**\n"
            for r in referrals[:3]:
                status_emoji = "✅" if r.get('is_active') else "⏳"
                text += f"• {status_emoji} User {r['referred_id']} - {r['join_date'][:10]}\n"
        
        keyboard = [
            [
                InlineKeyboardButton("💰 +/– MONEY", callback_data=f"money_action_{target_id}"),
                InlineKeyboardButton("🗑️ CLEAR DATA", callback_data=f"clear_data_{target_id}")
            ],
            [
                InlineKeyboardButton("🚫 FLAG", callback_data=f"flag_user_{target_id}"),
                InlineKeyboardButton("✅ UNFLAG", callback_data=f"unflag_user_{target_id}")
            ],
            [
                InlineKeyboardButton("🔴 BLOCK WD", callback_data=f"block_withdraw_{target_id}"),
                InlineKeyboardButton("🟢 UNBLOCK WD", callback_data=f"unblock_withdraw_{target_id}")
            ],
            [
                InlineKeyboardButton("📜 FULL HISTORY", callback_data=f"user_history_{target_id}")
            ],
            [InlineKeyboardButton("◀️ BACK", callback_data="admin_user_stats")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if len(text) > 4000:
            text = text[:3500] + "...\n(Truncated)"
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    
    # ========== MONEY ACTION PROMPT ==========
    
    async def money_action_prompt(self, query, context, target_id):
        """Prompt for money addition/removal"""
        context.user_data['admin_action'] = f"money_{target_id}"
        
        keyboard = [[InlineKeyboardButton("◀️ CANCEL", callback_data=f"user_stats_{target_id}")]]
        
        await query.edit_message_text(
            f"💰 **Money Action for User {target_id}**\n\n"
            f"Reply to this message with:\n"
            f"• `+100` to add ₹100\n"
            f"• `-50` to remove ₹50\n\n"
            f"**Example:** `+200` or `-150`\n\n"
            f"Current Balance: ₹{self.db.get_user(target_id).get('balance', 0):.2f}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ========== CLEAR DATA OPTIONS ==========
    
    async def clear_data_options(self, query, context, target_id):
        """Show clear data options"""
        context.user_data['clearing_user'] = target_id
        
        keyboard = [
            [InlineKeyboardButton("🗑️ ALL DATA", callback_data="clear_all_data")],
            [InlineKeyboardButton("💰 ONLY EARNINGS", callback_data="clear_earnings_only")],
            [InlineKeyboardButton("◀️ CANCEL", callback_data=f"user_stats_{target_id}")]
        ]
        
        await query.edit_message_text(
            f"⚠️ **CLEAR USER DATA**\n\n"
            f"User: `{target_id}`\n\n"
            f"**Choose what to clear:**\n\n"
            f"• **ALL DATA**: Complete user deletion (user, referrals, transactions, withdrawals)\n"
            f"• **ONLY EARNINGS**: Reset balance & earnings to 0 (keep user & referrals)\n\n"
            f"⚠️ This action cannot be undone!",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ========== CONFIRM CLEAR DATA ==========
    
    async def confirm_clear_data(self, query, context, target_id):
        """Final confirmation before clearing"""
        clear_type = context.user_data.get('clear_type', 'all')
        
        if clear_type == 'all':
            msg = "🗑️ **Confirm Delete ALL Data**\n\nReply with `all type` to confirm"
        else:
            msg = "💰 **Confirm Clear Earnings**\n\nReply with `earning` to confirm"
        
        keyboard = [[InlineKeyboardButton("◀️ CANCEL", callback_data=f"user_stats_{target_id}")]]
        
        await query.edit_message_text(
            msg,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ========== USER MANAGEMENT FUNCTIONS ==========
    
    async def flag_user(self, query, context, target_id):
        """Flag user for suspicious activity"""
        self.db.users.update_one(
            {'user_id': target_id},
            {'$set': {'suspicious_activity': True}}
        )
        self.db.user_cache.pop(f"user_{target_id}", None)
        await query.answer("✅ User flagged")
        await self.show_user_stats(query, context, target_id)
    
    async def unflag_user(self, query, context, target_id):
        """Remove flag from user"""
        self.db.users.update_one(
            {'user_id': target_id},
            {'$set': {'suspicious_activity': False}}
        )
        self.db.user_cache.pop(f"user_{target_id}", None)
        await query.answer("✅ User unflagged")
        await self.show_user_stats(query, context, target_id)
    
    async def block_withdrawals(self, query, context, target_id):
        """Block user from withdrawing"""
        self.db.users.update_one(
            {'user_id': target_id},
            {'$set': {'withdrawal_blocked': True}}
        )
        self.db.user_cache.pop(f"user_{target_id}", None)
        await query.answer("🔴 Withdrawals blocked")
        await self.show_user_stats(query, context, target_id)
    
    async def unblock_withdrawals(self, query, context, target_id):
        """Unblock user withdrawals"""
        self.db.users.update_one(
            {'user_id': target_id},
            {'$set': {'withdrawal_blocked': False}}
        )
        self.db.user_cache.pop(f"user_{target_id}", None)
        await query.answer("🟢 Withdrawals unblocked")
        await self.show_user_stats(query, context, target_id)
    
    async def show_user_full_history(self, query, context, target_id):
        """Show complete user history"""
        transactions = list(self.db.transactions.find(
            {'user_id': target_id}
        ).sort('timestamp', -1).limit(20))
        
        withdrawals = list(self.db.withdrawals.find(
            {'user_id': target_id}
        ).sort('request_date', -1).limit(20))
        
        text = f"📜 **Full History for User {target_id}**\n\n"
        
        text += "**Recent Transactions:**\n"
        for t in transactions[:10]:
            text += f"• {t['timestamp'][:10]}: {t['type']} - ₹{t['amount']}\n"
        
        text += "\n**All Withdrawals:**\n"
        for w in withdrawals[:10]:
            text += f"• {w['request_date'][:10]}: ₹{w['amount']} - {w['status']}\n"
        
        keyboard = [[InlineKeyboardButton("◀️ BACK", callback_data=f"user_stats_{target_id}")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ========== PROCESS MONEY ACTION ==========
    
    async def process_money_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE, target_id):
        """Process money addition/removal from message"""
        try:
            text = update.message.text.strip()
            
            if not (text.startswith('+') or text.startswith('-')):
                await update.message.reply_text(
                    "❌ **Invalid Format**\n\nUse + or - prefix.\nExample: `+100` or `-50`",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            try:
                amount = float(text)
            except ValueError:
                await update.message.reply_text("❌ Invalid number format")
                return
            
            if amount == 0:
                await update.message.reply_text("❌ Amount cannot be zero")
                return
            
            user = self.db.get_user(target_id)
            if not user:
                await update.message.reply_text(f"❌ User {target_id} not found")
                return
            
            if amount < 0 and abs(amount) > user.get('balance', 0):
                await update.message.reply_text(
                    f"❌ User has only ₹{user['balance']:.2f}. Cannot remove ₹{abs(amount):.2f}"
                )
                return
            
            old_balance = user.get('balance', 0)
            new_balance = old_balance + amount
            
            self.db.users.update_one(
                {'user_id': target_id},
                {'$inc': {'balance': amount}}
            )
            
            if amount > 0:
                self.db.add_transaction(
                    target_id, 
                    'admin_add', 
                    amount, 
                    f"Admin added ₹{amount:.2f}"
                )
                action_text = f"added ₹{amount:.2f} to"
                user_msg = f"✅ Admin added ₹{amount:.2f} to your balance!"
            else:
                self.db.add_transaction(
                    target_id, 
                    'admin_remove', 
                    amount, 
                    f"Admin removed ₹{abs(amount):.2f}"
                )
                action_text = f"removed ₹{abs(amount):.2f} from"
                user_msg = f"⚠️ Admin removed ₹{abs(amount):.2f} from your balance"
            
            self.db.user_cache.pop(f"user_{target_id}", None)
            
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=user_msg
                )
            except Exception as e:
                logger.error(f"Could not notify user {target_id}: {e}")
            
            await update.message.reply_text(
                f"✅ **Success!**\n\n"
                f"{action_text} user {target_id}\n"
                f"Old Balance: ₹{old_balance:.2f}\n"
                f"New Balance: ₹{new_balance:.2f}",
                parse_mode=ParseMode.MARKDOWN
            )
            
            context.user_data['admin_action'] = None
            
            keyboard = [[InlineKeyboardButton("👤 VIEW USER", callback_data=f"user_stats_{target_id}")]]
            await update.message.reply_text(
                "Click below to view updated user details:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            logger.error(f"Money action error: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    # ========== CLEAR USER DATA ==========
    
    async def clear_user_data(self, query, context, target_id, clear_type='all'):
        """Clear user data based on type"""
        try:
            if clear_type == 'all':
                self.db.users.delete_one({'user_id': target_id})
                self.db.transactions.delete_many({'user_id': target_id})
                self.db.withdrawals.delete_many({'user_id': target_id})
                self.db.referrals.delete_many({'$or': [
                    {'referrer_id': target_id},
                    {'referred_id': target_id}
                ]})
                self.db.daily_searches.delete_many({'user_id': target_id})
                self.db.search_logs.delete_many({'user_id': target_id})
                
                message = f"✅ **All data cleared** for user `{target_id}`"
                
            elif clear_type == 'earning':
                self.db.users.update_one(
                    {'user_id': target_id},
                    {'$set': {
                        'balance': 0,
                        'total_earned': 0
                    }}
                )
                
                self.db.transactions.delete_many({'user_id': target_id})
                
                message = f"✅ **Earnings cleared** for user `{target_id}`\nBalance reset to ₹0"
            
            self.db.user_cache.pop(f"user_{target_id}", None)
            
            self.db.log_system_event('user_data_cleared', f"User {target_id} - Type: {clear_type}")
            
            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ BACK TO ADMIN", callback_data="admin_user_stats")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logger.error(f"Clear data error: {e}")
            await query.edit_message_text(f"❌ Error clearing data: {str(e)}")
        
        context.user_data['clear_type'] = None
        context.user_data['clearing_user'] = None
    
    # ========== CLEAR DATA FROM MESSAGE ==========
    
    async def clear_user_data_from_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE, target_id, clear_type):
        """Clear user data when confirmed via message"""
        try:
            if clear_type == 'all':
                self.db.users.delete_one({'user_id': target_id})
                self.db.transactions.delete_many({'user_id': target_id})
                self.db.withdrawals.delete_many({'user_id': target_id})
                self.db.referrals.delete_many({'$or': [
                    {'referrer_id': target_id},
                    {'referred_id': target_id}
                ]})
                self.db.daily_searches.delete_many({'user_id': target_id})
                self.db.search_logs.delete_many({'user_id': target_id})
                
                message = f"✅ **All data cleared** for user `{target_id}`"
                
            elif clear_type == 'earning':
                self.db.users.update_one(
                    {'user_id': target_id},
                    {'$set': {
                        'balance': 0,
                        'total_earned': 0
                    }}
                )
                
                self.db.transactions.delete_many({'user_id': target_id})
                
                message = f"✅ **Earnings cleared** for user `{target_id}`\nBalance reset to ₹0"
            
            self.db.user_cache.pop(f"user_{target_id}", None)
            
            self.db.log_system_event('user_data_cleared', f"User {target_id} - Type: {clear_type}")
            
            await update.message.reply_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ BACK TO ADMIN", callback_data="admin_user_stats")
                ]])
            )
            
        except Exception as e:
            logger.error(f"Clear data error: {e}")
            await update.message.reply_text(f"❌ Error clearing data: {str(e)}")
        
        context.user_data['admin_action'] = None
        context.user_data['clear_type'] = None
        context.user_data['clearing_user'] = None
    
    # ========== BROADCAST ==========
    
    async def broadcast_menu(self, query, context):
        """Broadcast message menu"""
        context.user_data['admin_action'] = 'broadcast'
        
        keyboard = [[InlineKeyboardButton("◀️ BACK", callback_data="back_to_admin")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        total_users = self.db.users.count_documents({})
        
        await query.edit_message_text(
            f"📢 **Broadcast Message**\n\n"
            f"Total users: {total_users}\n\n"
            f"Send me the message you want to broadcast.\n"
            f"(Text, photo, video, or any media)",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ========== PROCESS BROADCAST ==========
    
    async def process_broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process broadcast message"""
        message = update.message
        users = list(self.db.users.find({}, {'user_id': 1}))
        
        sent = 0
        failed = 0
        
        status_msg = await update.message.reply_text(f"📢 Broadcasting to {len(users)} users...")
        
        for user in users:
            try:
                if message.text:
                    await context.bot.send_message(
                        chat_id=user['user_id'],
                        text=message.text
                    )
                elif message.photo:
                    await context.bot.send_photo(
                        chat_id=user['user_id'],
                        photo=message.photo[-1].file_id,
                        caption=message.caption
                    )
                sent += 1
            except Exception as e:
                failed += 1
                logger.error(f"Broadcast failed: {e}")
            
            await asyncio.sleep(0.05)
        
        await status_msg.edit_text(f"✅ Broadcast: {sent} sent, {failed} failed")
        context.user_data['admin_action'] = None
        self.db.log_system_event('broadcast', f"Sent to {sent} users")
    
    # ========== PROCESS SEARCH USER ==========
    
    async def process_search_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process user search"""
        try:
            target_id = int(update.message.text.strip())
            user = self.db.get_user(target_id)
            
            if user:
                keyboard = [[InlineKeyboardButton("👤 VIEW DETAILS", callback_data=f"user_stats_{target_id}")]]
                await update.message.reply_text(
                    f"✅ User {target_id} found! Click below to view details.",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                await update.message.reply_text(f"❌ User {target_id} not found")
                
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID. Please enter a numeric ID.")
        except Exception as e:
            logger.error(f"Search user error: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")
        
        context.user_data['admin_action'] = None
    
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
        
        for i, w in enumerate(withdrawals[:5], 1):
            user = self.db.get_user(w['user_id'])
            user_name = user.get('first_name', 'Unknown')[:10] if user else 'Unknown'
            text += f"{i}. {user_name}: ₹{w['amount']} - {w['method']}\n"
            text += f"   ID: `{str(w['_id'])[-8:]}`\n\n"
        
        keyboard = []
        for w in withdrawals[:3]:
            keyboard.append([
                InlineKeyboardButton(f"✅ Approve {str(w['_id'])[-6:]}", callback_data=f"approve_{w['_id']}"),
                InlineKeyboardButton(f"❌ Reject {str(w['_id'])[-6:]}", callback_data=f"reject_{w['_id']}")
            ])
        
        keyboard.append([InlineKeyboardButton("◀️ BACK", callback_data="back_to_admin")])
        
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    async def approve_withdrawal(self, query, context, withdrawal_id):
        """Approve a withdrawal"""
        try:
            withdrawal = self.db.withdrawals.find_one({'_id': ObjectId(withdrawal_id)})
        except:
            withdrawal = None
        
        if not withdrawal:
            await query.edit_message_text("❌ Withdrawal not found")
            return
        
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
        
        self.db.add_transaction(
            withdrawal['user_id'],
            'withdrawal_approved',
            -withdrawal['amount'],
            f"Withdrawal approved #{withdrawal_id[-8:]}"
        )
        
        try:
            await context.bot.send_message(
                chat_id=withdrawal['user_id'],
                text=(
                    f"✅ **Withdrawal Approved!**\n\n"
                    f"Amount: ₹{withdrawal['amount']:.2f}\n"
                    f"Method: {withdrawal['method']}\n\n"
                    f"Your withdrawal has been approved and will be processed shortly."
                ),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Could not notify user: {e}")
        
        await query.edit_message_text(
            f"✅ Withdrawal ₹{withdrawal['amount']:.2f} approved!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ BACK TO WITHDRAWALS", callback_data="admin_withdrawals")
            ]])
        )
        
        self.db.log_system_event('withdrawal_approved', f"User {withdrawal['user_id']}: ₹{withdrawal['amount']}")
    
    async def reject_withdrawal(self, query, context, withdrawal_id):
        """Reject a withdrawal"""
        try:
            withdrawal = self.db.withdrawals.find_one({'_id': ObjectId(withdrawal_id)})
        except:
            withdrawal = None
        
        if not withdrawal:
            await query.edit_message_text("❌ Withdrawal not found")
            return
        
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
        
        self.db.add_balance(
            withdrawal['user_id'],
            withdrawal['amount'],
            f"Refund for rejected withdrawal"
        )
        
        try:
            await context.bot.send_message(
                chat_id=withdrawal['user_id'],
                text=(
                    f"❌ **Withdrawal Rejected**\n\n"
                    f"Amount: ₹{withdrawal['amount']:.2f}\n"
                    f"Method: {withdrawal['method']}\n\n"
                    f"Your withdrawal was rejected. Amount refunded.\n"
                    f"Contact support: {self.config.SUPPORT_USERNAME}"
                ),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Could not notify user: {e}")
        
        await query.edit_message_text(
            f"❌ Withdrawal ₹{withdrawal['amount']:.2f} rejected!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ BACK TO WITHDRAWALS", callback_data="admin_withdrawals")
            ]])
        )
        
        self.db.log_system_event('withdrawal_rejected', f"User {withdrawal['user_id']}: ₹{withdrawal['amount']}")
    
    # ========== LEADERBOARD RESET ==========
    
    async def reset_leaderboard(self, query, context):
        """Reset weekly leaderboard and give rewards"""
        top_users = list(self.db.users.find(
            {'active_refs': {'$gt': 0}, 'suspicious_activity': False}
        ).sort('active_refs', -1).limit(10))
        
        rewards = []
        
        for i, user in enumerate(top_users):
            rank = i + 1
            reward = 0
            
            if rank == 1 and user.get('active_refs', 0) >= 50:
                reward = 200
            elif rank == 2 and user.get('active_refs', 0) >= 50:
                reward = 200
            elif rank == 3 and user.get('active_refs', 0) >= 50:
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
                    'reward': reward,
                    'active_refs': user.get('active_refs', 0)
                })
        
        self.db.users.update_many({}, {'$set': {'weekly_searches': 0}})
        
        text = "🏆 **Leaderboard Reset**\n\n"
        if rewards:
            text += "Rewards given:\n"
            for r in rewards:
                text += f"• {r['name']}: Rank #{r['rank']} - ₹{r['reward']} ({r['active_refs']} refs)\n"
        else:
            text += "No rewards given this week."
        
        keyboard = [[InlineKeyboardButton("◀️ BACK", callback_data="back_to_admin")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        
        self.db.log_system_event('leaderboard_reset', f"Given {len(rewards)} rewards")
    
    # ========== DAILY EARNINGS ==========
    
    async def process_daily_earnings(self, query, context):
        """Manually process daily earnings"""
        count = self.db.process_daily_referral_earnings()
        
        text = f"✅ **Daily Earnings Processed**\n\nProcessed earnings for {count} active referrals."
        
        keyboard = [[InlineKeyboardButton("◀️ BACK", callback_data="back_to_admin")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ========== SYSTEM LOGS ==========
    
    async def show_logs(self, query, context):
        """Show system logs"""
        events = list(self.db.system_stats.find().sort('timestamp', -1).limit(10))
        
        recent_tx = list(self.db.transactions.find().sort('timestamp', -1).limit(5))
        
        recent_users = list(self.db.users.find().sort('join_date', -1).limit(5))
        
        text = "📋 **System Logs**\n\n"
        
        text += "**Recent Events:**\n"
        for e in events:
            text += f"• {e['timestamp'][:16]}: {e['event_type']}\n"
        
        text += "\n**New Users:**\n"
        for u in recent_users:
            text += f"• {u['join_date'][:10]}: {u.get('first_name', 'User')}\n"
        
        keyboard = [[InlineKeyboardButton("◀️ BACK", callback_data="back_to_admin")]]
        
        if len(text) > 4000:
            text = text[:3500] + "...\n(Truncated)"
        
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ========== BACK TO ADMIN ==========
    
    async def back_to_admin(self, query, context):
        """Return to main admin panel"""
        context.user_data['admin_action'] = None
        context.user_data['clear_type'] = None
        context.user_data['clearing_user'] = None
        
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
        
        total_users = self.db.users.count_documents({})
        pending = self.db.withdrawals.count_documents({'status': 'pending'})
        
        text = (
            "👑 **Admin Panel**\n\n"
            f"📊 Users: {total_users} | Pending WD: {pending}"
        )
        
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ========== HANDLE ADMIN MESSAGES ==========
    
    async def handle_admin_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin messages"""
        user_id = update.effective_user.id
        
        if user_id not in self.config.ADMIN_IDS:
            return
        
        action = context.user_data.get('admin_action')
        if not action:
            return
        
        if action == 'broadcast':
            await self.process_broadcast(update, context)
        
        elif action.startswith('money_'):
            try:
                target_id = int(action.replace('money_', ''))
                await self.process_money_action(update, context, target_id)
            except Exception as e:
                logger.error(f"Money action error: {e}")
                await update.message.reply_text("❌ Error processing money action")
        
        elif action.startswith('confirm_clear_'):
            try:
                target_id = int(action.replace('confirm_clear_', ''))
                clear_text = update.message.text.strip().lower()
                
                if clear_text == 'all type':
                    await self.clear_user_data_from_message(update, context, target_id, 'all')
                elif clear_text == 'earning':
                    await self.clear_user_data_from_message(update, context, target_id, 'earning')
                else:
                    await update.message.reply_text(
                        "❌ **Invalid Option**\n\nPlease type:\n• `all type` - Delete all data\n• `earning` - Clear only earnings",
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("◀️ BACK TO USER", callback_data=f"user_stats_{target_id}")
                        ]])
                    )
            except Exception as e:
                logger.error(f"Clear data error: {e}")
        
        elif action == 'search_user':
            await self.process_search_user(update, context)
