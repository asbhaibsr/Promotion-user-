# ===== admin.py =====
import logging
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
        """Admin panel command"""
        user_id = update.effective_user.id
        
        # Check if user is admin
        if user_id not in self.config.ADMIN_IDS:
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
        
        text = (
            "👑 **Admin Panel**\n\n"
            "**Commands:**\n"
            "/stats - View bot statistics\n"
            "/broadcast [message] - Send message to all users\n"
            "/addbalance [user_id] [amount] - Add balance to user\n"
            "/setbonus [amount] - Set daily bonus amount\n"
            "/withdrawals - View pending withdrawals\n"
        )
        
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    
    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """View bot statistics"""
        user_id = update.effective_user.id
        
        # Check if user is admin
        if user_id not in self.config.ADMIN_IDS:
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
        
        # Get stats from database
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        # Total users
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        # Users joined today
        today = datetime.now().date().isoformat()
        cursor.execute("SELECT COUNT(*) FROM users WHERE date(join_date) = ?", (today,))
        today_users = cursor.fetchone()[0]
        
        # Active users (last 24h)
        yesterday = (datetime.now() - timedelta(days=1)).isoformat()
        cursor.execute("SELECT COUNT(*) FROM users WHERE last_active > ?", (yesterday,))
        active_users = cursor.fetchone()[0]
        
        # Total balance
        cursor.execute("SELECT SUM(balance) FROM users")
        total_balance = cursor.fetchone()[0] or 0
        
        # Pending withdrawals
        cursor.execute("SELECT COUNT(*), SUM(amount) FROM withdrawals WHERE status = 'pending'")
        pending_count, pending_amount = cursor.fetchone()
        pending_count = pending_count or 0
        pending_amount = pending_amount or 0
        
        conn.close()
        
        text = (
            "📊 **Bot Statistics**\n\n"
            f"**Users:**\n"
            f"• Total: {total_users}\n"
            f"• Joined today: {today_users}\n"
            f"• Active (24h): {active_users}\n\n"
            f"**Financial:**\n"
            f"• Total balance: ₹{total_balance:.2f}\n"
            f"• Pending withdrawals: {pending_count}\n"
            f"• Withdrawal amount: ₹{pending_amount:.2f}\n\n"
        )
        
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    
    async def broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send message to all users"""
        user_id = update.effective_user.id
        
        # Check if user is admin
        if user_id not in self.config.ADMIN_IDS:
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
        
        # Get message
        if not context.args:
            await update.message.reply_text("Usage: /broadcast [message]")
            return
        
        message = ' '.join(context.args)
        
        # Get all users
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        users = cursor.fetchall()
        conn.close()
        
        sent_count = 0
        failed_count = 0
        
        status_msg = await update.message.reply_text(f"📢 Broadcasting to {len(users)} users...")
        
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
            
            # Small delay to avoid rate limits
            await asyncio.sleep(0.05)
        
        await status_msg.edit_text(
            f"✅ **Broadcast Complete**\n\n"
            f"• Sent: {sent_count}\n"
            f"• Failed: {failed_count}"
        )
    
    async def add_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Add balance to user"""
        user_id = update.effective_user.id
        
        # Check if user is admin
        if user_id not in self.config.ADMIN_IDS:
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
        
        # Parse arguments
        if len(context.args) < 2:
            await update.message.reply_text("Usage: /addbalance [user_id] [amount]")
            return
        
        try:
            target_id = int(context.args[0])
            amount = float(context.args[1])
        except ValueError:
            await update.message.reply_text("❌ Invalid user_id or amount")
            return
        
        # Check if user exists
        user = self.db.get_user(target_id)
        if not user:
            await update.message.reply_text(f"❌ User {target_id} not found")
            return
        
        # Add balance
        self.db.add_balance(target_id, amount, f"Admin added ₹{amount}")
        
        # Notify user
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
    
    async def set_daily_bonus(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Set daily bonus amount"""
        user_id = update.effective_user.id
        
        # Check if user is admin
        if user_id not in self.config.ADMIN_IDS:
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
        
        if not context.args:
            await update.message.reply_text(f"Current daily bonus: ₹{self.config.DAILY_BONUS}")
            return
        
        try:
            new_bonus = float(context.args[0])
            self.config.DAILY_BONUS = new_bonus
            await update.message.reply_text(f"✅ Daily bonus set to ₹{new_bonus}")
        except ValueError:
            await update.message.reply_text("❌ Invalid amount")
    
    async def withdrawals(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """View pending withdrawals"""
        user_id = update.effective_user.id
        
        # Check if user is admin
        if user_id not in self.config.ADMIN_IDS:
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
        
        # Get pending withdrawals
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT w.*, u.first_name, u.username 
            FROM withdrawals w
            JOIN users u ON u.user_id = w.user_id
            WHERE w.status = 'pending'
            ORDER BY w.request_date ASC
            LIMIT 10
        ''')
        withdrawals = cursor.fetchall()
        conn.close()
        
        if not withdrawals:
            await update.message.reply_text("✅ No pending withdrawals")
            return
        
        for w in withdrawals:
            text = (
                f"💰 **Withdrawal Request**\n\n"
                f"ID: `{w['id']}`\n"
                f"User: {w['first_name']} (@{w['username'] or 'N/A'})\n"
                f"Amount: ₹{w['amount']:.2f}\n"
                f"Method: {w['method']}\n"
                f"Details: {w['details']}\n"
                f"Date: {w['request_date']}\n\n"
                f"Approve or Reject?"
            )
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ Approve", callback_data=f"approve_{w['id']}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"reject_{w['id']}")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
