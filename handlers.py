# ===== handlers.py =====
import logging
import json
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

class Handlers:
    def __init__(self, config, db):
        self.config = config
        self.db = db
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        args = context.args
        
        referrer_id = None
        if args and args[0].startswith('ref_'):
            try:
                referrer_id = int(args[0].replace('ref_', ''))
                if referrer_id == user.id:
                    referrer_id = None
            except:
                pass
        
        user_data = {
            'user_id': user.id,
            'first_name': user.first_name,
            'username': user.username,
            'referrer_id': referrer_id
        }
        
        is_new = self.db.add_user(user_data)
        
        welcome_text = (
            f"🎬 **Welcome to FilmyFund, {user.first_name}!**\n\n"
            f"💰 **Earn Money Daily**\n"
            f"• Get ₹{self.config.CHANNEL_JOIN_BONUS} welcome bonus\n"
            f"• Earn ₹0.10+ per referral every day\n"
            f"• Spin wheel to win up to ₹5\n"
            f"• Daily bonuses & rewards\n\n"
            f"👇 **Click below to open the app!**"
        )
        
        keyboard = [[
            InlineKeyboardButton(
                "📱 OPEN MINI APP",
                web_app=WebAppInfo(url=f"{self.config.WEBAPP_URL}/?user_id={user.id}")
            )
        ]]
        
        if is_new and referrer_id:
            welcome_text += f"\n\n✅ You were referred by user {referrer_id}!"
            
            referrer = self.db.get_user(referrer_id)
            if referrer:
                self.db.add_balance(referrer_id, self.config.REFERRAL_BONUS)
                self.db.add_transaction(referrer_id, 'referral_bonus', self.config.REFERRAL_BONUS, 
                                       f"Referral bonus for user {user.id}")
                
                try:
                    await context.bot.send_message(
                        chat_id=referrer_id,
                        text=f"🎉 **New Referral!**\n\n"
                             f"User {user.first_name} joined using your link!\n"
                             f"💰 You earned ₹{self.config.REFERRAL_BONUS} bonus!"
                    )
                except:
                    pass
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def open_app(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        
        keyboard = [[
            InlineKeyboardButton(
                "📱 OPEN MINI APP",
                web_app=WebAppInfo(url=f"{self.config.WEBAPP_URL}/?user_id={user.id}")
            )
        ]]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Click below to open the FilmyFund Mini App:",
            reply_markup=reply_markup
        )
    
    async def handle_webapp_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            web_app_data = update.effective_message.web_app_data
            if not web_app_data:
                return
            
            user = update.effective_user
            data = json.loads(web_app_data.data)
            action = data.get('action')
            
            logger.info(f"WebApp action from user {user.id}: {action}")
            
            if action == 'spin':
                await self.process_spin(update, context, data)
            elif action == 'daily':
                await self.process_daily_bonus(update, context, data)
            elif action == 'channel_join':
                await self.process_channel_join(update, context, data)
            elif action == 'save_payment':
                await self.process_save_payment(update, context, data)
            elif action == 'withdraw':
                await self.process_withdraw(update, context, data)
            elif action == 'report_issue':
                await self.process_report_issue(update, context, data)
            elif action == 'missions':
                await self.process_missions(update, context, data)
            
        except Exception as e:
            logger.error(f"WebApp data error: {e}")
            await update.effective_message.reply_text(
                text=json.dumps({'error': str(e), 'success': False})
            )
    
    async def process_spin(self, update, context, data):
        user_id = data.get('user_id')
        result = self.db.process_spin(user_id)
        
        if result:
            response = {
                'prize': result['prize'],
                'prize_name': result['prize_name'],
                'remaining_spins': result['remaining_spins']
            }
            await update.effective_message.reply_text(text=json.dumps(response))
    
    async def process_daily_bonus(self, update, context, data):
        user_id = data.get('user_id')
        result = self.db.claim_daily_bonus(user_id)
        
        if result:
            response = {
                'bonus': result['bonus'],
                'streak': result['streak'],
                'success': True
            }
            await update.effective_message.reply_text(text=json.dumps(response))
    
    async def process_channel_join(self, update, context, data):
        user_id = data.get('user_id')
        user = self.db.get_user(user_id)
        
        if user and not user.get('channel_joined'):
            self.db.add_balance(user_id, self.config.CHANNEL_JOIN_BONUS)
            self.db.update_user(user_id, {'channel_joined': True})
            self.db.add_transaction(user_id, 'channel_bonus', 
                                  self.config.CHANNEL_JOIN_BONUS, 
                                  "Channel join bonus")
            
            response = {'success': True, 'bonus': self.config.CHANNEL_JOIN_BONUS}
        else:
            response = {'success': False, 'message': 'Already claimed or invalid'}
        
        await update.effective_message.reply_text(text=json.dumps(response))
    
    async def process_save_payment(self, update, context, data):
        user_id = data.get('user_id')
        method = data.get('method')
        details = data.get('details')
        
        self.db.update_user(user_id, {
            'payment_method': method,
            'payment_details': details
        })
        
        await update.effective_message.reply_text(text=json.dumps({'success': True}))
    
    async def process_withdraw(self, update, context, data):
        user_id = data.get('user_id')
        amount = data.get('amount')
        method = data.get('method')
        details = data.get('details')
        
        result = self.db.process_withdrawal(user_id, amount, method, details)
        await update.effective_message.reply_text(text=json.dumps(result))
    
    async def process_report_issue(self, update, context, data):
        user_id = data.get('user_id')
        issue = data.get('issue')
        
        self.db.add_issue_report(user_id, issue)
        await update.effective_message.reply_text(text=json.dumps({'success': True}))
    
    async def process_missions(self, update, context, data):
        user_id = data.get('user_id')
        missions = self.db.get_user_missions(user_id)
        await update.effective_message.reply_text(text=json.dumps(missions))
    
    async def check_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        user = self.db.get_user(user_id)
        
        if user:
            text = (
                f"💰 **Your Balance**\n\n"
                f"Available: ₹{user.get('balance', 0):.2f}\n"
                f"Total Earned: ₹{user.get('total_earned', 0):.2f}\n"
                f"Spins: {user.get('spins', 3)} 🎰\n\n"
                f"Use /app to open the Mini App!"
            )
        else:
            text = "Please use /start first"
        
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    
    async def show_referrals(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        user = self.db.get_user(user_id)
        
        if user:
            ref_link = f"https://t.me/{self.config.BOT_USERNAME}?start=ref_{user_id}"
            text = (
                f"👥 **Your Referrals**\n\n"
                f"Total: {user.get('total_refs', 0)}\n"
                f"Active: {user.get('active_refs', 0)}\n"
                f"Monthly: {user.get('monthly_refs', 0)}\n\n"
                f"🔗 **Your Referral Link:**\n"
                f"`{ref_link}`\n\n"
                f"Share this link with friends!"
            )
        else:
            text = "Please use /start first"
        
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    
    async def daily_bonus_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        keyboard = [[
            InlineKeyboardButton(
                "🎁 CLAIM DAILY BONUS",
                web_app=WebAppInfo(url=f"{self.config.WEBAPP_URL}/?user_id={user_id}")
            )
        ]]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Click below to claim your daily bonus in the Mini App:",
            reply_markup=reply_markup
        )
    
    async def withdraw_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        keyboard = [[
            InlineKeyboardButton(
                "💳 WITHDRAW EARNINGS",
                web_app=WebAppInfo(url=f"{self.config.WEBAPP_URL}/?user_id={user_id}")
            )
        ]]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"Minimum withdrawal: ₹{self.config.MIN_WITHDRAWAL}\n"
            "Click below to withdraw in the Mini App:",
            reply_markup=reply_markup
        )
    
    async def help_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = (
            "❓ **FilmyFund Help**\n\n"
            "**Commands:**\n"
            "/start - Start the bot\n"
            "/app - Open Mini App\n"
            "/balance - Check balance\n"
            "/referrals - View referrals\n"
            "/daily - Daily bonus\n"
            "/withdraw - Withdraw earnings\n"
            "/help - This message\n\n"
            "**How to Earn:**\n"
            "1️⃣ Join our channel (₹{channel_bonus} bonus)\n"
            "2️⃣ Refer friends (earn daily)\n"
            "3️⃣ Spin wheel for prizes\n"
            "4️⃣ Daily streak bonuses\n\n"
            "**Support:** @{support_username}"
        ).format(
            channel_bonus=self.config.CHANNEL_JOIN_BONUS,
            support_username=self.config.SUPPORT_USERNAME.replace('@', '')
        )
        
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data.startswith('approve_'):
            withdrawal_id = data.replace('approve_', '')
            self.db.update_withdrawal_status(withdrawal_id, 'approved')
            await query.edit_message_text("✅ Withdrawal approved!")
        
        elif data.startswith('reject_'):
            withdrawal_id = data.replace('reject_', '')
            self.db.update_withdrawal_status(withdrawal_id, 'rejected')
            await query.edit_message_text("❌ Withdrawal rejected!")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        text = update.message.text
        
        self.db.increment_search_count(user_id)
        
        user = self.db.get_user(user_id)
        
        if not user:
            await update.message.reply_text("Please use /start first")
            return
        
        if text.lower() in ['hi', 'hello', 'hey']:
            await update.message.reply_text(f"Hello {user.get('first_name', 'User')}! Use /app to earn money!")
        else:
            await update.message.reply_text("Use the Mini App to earn money! Click /app")
