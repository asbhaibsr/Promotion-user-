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
        
        text = (
            "👑 **Admin Panel**\n\n"
            "**Commands:**\n"
            "/stats - View bot statistics\n"
            "/broadcast [message] - Send message to all users\n"
            "/addbalance [user_id] [amount] - Add balance to user\n"
            "/withdrawals - View pending withdrawals\n"
        )
        
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    
    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if user_id not in self.config.ADMIN_IDS:
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
        
        total_users = self.db.users.count_documents({})
        today = datetime.now().date().isoformat()
        today_users = self.db.users.count_documents({'join_date': {'$regex': f'^{today}'}})
        
        yesterday = (datetime.now() - timedelta(days=1)).isoformat()
        active_users = self.db.users.count_documents({'last_active': {'$gt': yesterday}})
        
        pipeline = [{'$group': {'_id': None, 'total': {'$sum': '$balance'}}}]
        result = list(self.db.users.aggregate(pipeline))
        total_balance = result[0]['total'] if result else 0
        
        pending_count = self.db.withdrawals.count_documents({'status': 'pending'})
        
        text = (
            "📊 **Bot Statistics**\n\n"
            f"**Users:**\n"
            f"• Total: {total_users}\n"
            f"• Joined today: {today_users}\n"
            f"• Active (24h): {active_users}\n\n"
            f"**Financial:**\n"
            f"• Total balance: ₹{total_balance:.2f}\n"
            f"• Pending withdrawals: {pending_count}\n"
        )
        
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    
    async def broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if user_id not in self.config.ADMIN_IDS:
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /broadcast [message]")
            return
        
        message = ' '.join(context.args)
        
        users = self.db.users.find({}, {'user_id': 1})
        
        sent_count = 0
        failed_count = 0
        
        status_msg = await update.message.reply_text(f"📢 Broadcasting...")
        
        for user in users:
            try:
                await context.bot.send_message(
                    chat_id=user['user_id'],
                    text=f"📢 **Broadcast Message**\n\n{message}",
                    parse_mode=ParseMode.MARKDOWN
                )
                sent_count += 1
            except Exception as e:
                failed_count += 1
                logger.error(f"Broadcast failed to {user['user_id']}: {e}")
            
            await asyncio.sleep(0.05)
        
        await status_msg.edit_text(
            f"✅ **Broadcast Complete**\n\n"
            f"• Sent: {sent_count}\n"
            f"• Failed: {failed_count}"
        )
    
    async def add_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if user_id not in self.config.ADMIN_IDS:
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text("Usage: /addbalance [user_id] [amount]")
            return
        
        try:
            target_id = int(context.args[0])
            amount = float(context.args[1])
        except ValueError:
            await update.message.reply_text("❌ Invalid user_id or amount")
            return
        
        user = self.db.get_user(target_id)
        if not user:
            await update.message.reply_text(f"❌ User {target_id} not found")
            return
        
        self.db.add_balance(target_id, amount, f"Admin added ₹{amount}")
        
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=f"🎉 **Balance Added!**\n\n"
                     f"Admin added ₹{amount:.2f} to your balance!\n"
                     f"New balance: ₹{(user['balance'] + amount):.2f}"
            )
        except:
            pass
        
        await update.message.reply_text(
            f"✅ Added ₹{amount:.2f} to user {target_id}\n"
            f"New balance: ₹{(user['balance'] + amount):.2f}"
        )
    
    async def withdrawals(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if user_id not in self.config.ADMIN_IDS:
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
        
        withdrawals = self.db.get_pending_withdrawals()
        
        if not withdrawals:
            await update.message.reply_text("✅ No pending withdrawals")
            return
        
        for w in withdrawals[:5]:
            user = self.db.get_user(w['user_id'])
            text = (
                f"💰 **Withdrawal Request**\n\n"
                f"ID: `{w['_id']}`\n"
                f"User: {user.get('first_name', 'Unknown')} (@{user.get('username', 'N/A')})\n"
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
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
