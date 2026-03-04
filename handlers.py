# ===== handlers.py =====
import logging
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

class Handlers:
    def __init__(self, config, db):
        self.config = config
        self.db = db
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command handler"""
        user = update.effective_user
        args = context.args
        
        # Extract referrer from start param
        referrer_id = None
        if args and args[0].startswith('ref_'):
            try:
                referrer_id = int(args[0].replace('ref_', ''))
                if referrer_id == user.id:
                    referrer_id = None
            except:
                pass
        
        # User data for database
        user_data = {
            'user_id': user.id,
            'first_name': user.first_name,
            'username': user.username,
            'referrer_id': referrer_id
        }
        
        # Add to database
        is_new = self.db.add_user(user_data)
        
        # Create welcome message
        welcome_text = (
            f"🎬 **Welcome to FilmyFund, {user.first_name}!**\n\n"
            f"💰 **Earn Money Daily**\n"
            f"• Refer friends → earn ₹{self.config.DAILY_REFERRAL_EARNING} per active referral daily\n"
            f"• Join channel → ₹{self.config.CHANNELS['main']['bonus']} bonus\n"
            f"• Daily bonus with streak → up to ₹0.20\n"
            f"• Complete missions → earn up to ₹25\n\n"
            f"👇 **Click below to start earning!**"
        )
        
        # Main button to open Mini App
        keyboard = [[
            InlineKeyboardButton(
                "📱 OPEN MINI APP",
                web_app=WebAppInfo(url=f"{self.config.WEBAPP_URL}/?user_id={user.id}")
            )
        ]]
        
        # Add join movie group button
        keyboard.append([
            InlineKeyboardButton(
                "🎬 JOIN MOVIE GROUP",
                url=self.config.MOVIE_GROUP_LINK
            )
        ])
        
        # Add join channel button
        keyboard.append([
            InlineKeyboardButton(
                f"📢 JOIN CHANNEL (₹{self.config.CHANNELS['main']['bonus']} BONUS)",
                url=self.config.CHANNELS['main']['link']
            )
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Send welcome message
        await update.message.reply_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Send referral link
        ref_link = f"https://t.me/{self.config.BOT_USERNAME}?start=ref_{user.id}"
        await update.message.reply_text(
            f"🔗 **Your Referral Link:**\n`{ref_link}`\n\n"
            f"Share this link with friends! When they join and search, you'll earn daily!\n\n"
            f"⚠️ **Important:**\n"
            f"• Go to movie group and search any movie\n"
            f"• Bot will automatically detect your search\n"
            f"• Fake searches = No withdrawal",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def open_app(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Open Mini App command"""
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
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all messages - AUTOMATIC GROUP VERIFICATION"""
        user_id = update.effective_user.id
        chat_id = str(update.effective_chat.id)
        
        # Check if this is the movie group
        if chat_id == self.config.MOVIE_GROUP_ID or chat_id.endswith('3193018012'):
            # This is a message in the movie group
            # Check if it's a movie search (any text message)
            if update.message.text and len(update.message.text) > 1:
                # Record the search automatically
                result = self.db.record_search(user_id)
                
                if result:
                    # Send confirmation
                    await update.message.reply_text(
                        "✅ **Search Recorded!**\n\n"
                        "• Your referrer will earn today\n"
                        "• Keep searching daily\n"
                        "• Fake searches = No withdrawal",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    
                    logger.info(f"✅ Search recorded for user {user_id} in movie group")
        
        # Handle private chat messages
        elif update.effective_chat.type == 'private':
            text = update.message.text.lower()
            if text in ['hi', 'hello', 'hey', 'start']:
                await update.message.reply_text(
                    "Welcome! Use /start to begin earning!"
                )
            else:
                await update.message.reply_text(
                    "Use /app to open the Mini App and start earning!"
                )
    
    async def handle_webapp_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle Mini App actions"""
        try:
            web_app_data = update.effective_message.web_app_data
            if not web_app_data:
                return
            
            user = update.effective_user
            data = json.loads(web_app_data.data)
            action = data.get('action')
            
            logger.info(f"📱 WebApp action from {user.id}: {action}")
            
            if action == 'channel_verified':
                await self.process_channel_verification(update, context, data)
            elif action == 'daily_bonus':
                await self.process_daily_bonus(update, context, data)
            elif action == 'save_payment':
                await self.process_save_payment(update, context, data)
            elif action == 'withdraw':
                await self.process_withdraw(update, context, data)
            elif action == 'report_issue':
                await self.process_report_issue(update, context, data)
            elif action == 'get_missions':
                await self.process_missions(update, context, data)
            
        except Exception as e:
            logger.error(f"WebApp data error: {e}")
            await update.effective_message.reply_text(
                text=json.dumps({'error': str(e), 'success': False})
            )
    
    async def process_channel_verification(self, update, context, data):
        """Process channel join verification"""
        user_id = data.get('user_id')
        channel_id = data.get('channel_id')
        
        result = self.db.mark_channel_join(user_id, channel_id)
        
        if result:
            user = self.db.get_user(user_id)
            response = {
                'success': True,
                'message': f'Channel joined! ₹{self.config.CHANNELS["main"]["bonus"]} bonus added!',
                'user_data': {
                    'balance': user.get('balance', 0),
                    'channel_joined': True
                }
            }
        else:
            response = {
                'success': False,
                'message': 'Already claimed bonus!'
            }
        
        await update.effective_message.reply_text(text=json.dumps(response))
    
    async def process_daily_bonus(self, update, context, data):
        """Process daily bonus claim"""
        user_id = data.get('user_id')
        result = self.db.claim_daily_bonus(user_id)
        
        if result:
            response = {
                'bonus': result['bonus'],
                'streak': result['streak'],
                'success': True
            }
        else:
            response = {
                'success': False,
                'message': 'Already claimed today'
            }
        
        await update.effective_message.reply_text(text=json.dumps(response))
    
    async def process_save_payment(self, update, context, data):
        """Save user payment details"""
        user_id = data.get('user_id')
        method = data.get('method')
        details = data.get('details')
        
        self.db.users.update_one(
            {'user_id': user_id},
            {'$set': {
                'payment_method': method,
                'payment_details': details
            }}
        )
        
        await update.effective_message.reply_text(
            text=json.dumps({'success': True, 'message': 'Payment details saved!'})
        )
    
    async def process_withdraw(self, update, context, data):
        """Process withdrawal request"""
        user_id = data.get('user_id')
        amount = data.get('amount')
        method = data.get('method')
        details = data.get('details')
        
        result = self.db.process_withdrawal(user_id, amount, method, details)
        
        if result.get('success'):
            user = self.db.get_user(user_id)
            user_name = user.get('first_name', 'Unknown')
            
            # Notify admins
            for admin_id in self.config.ADMIN_IDS:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=f"💰 **New Withdrawal Request**\n\n"
                             f"User: {user_name} (ID: {user_id})\n"
                             f"Amount: ₹{amount}\n"
                             f"Method: {method}\n"
                             f"Details: {details}\n"
                             f"Request ID: {result.get('id', 'N/A')}",
                        parse_mode=ParseMode.MARKDOWN
                    )
                except:
                    pass
        
        await update.effective_message.reply_text(text=json.dumps(result))
    
    async def process_report_issue(self, update, context, data):
        """Process issue report"""
        user_id = data.get('user_id')
        issue = data.get('issue')
        
        self.db.add_issue_report(user_id, issue)
        
        # Notify admins
        for admin_id in self.config.ADMIN_IDS:
            try:
                user = self.db.get_user(user_id)
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"⚠️ **New Issue Report**\n\n"
                         f"User: {user.get('first_name')} (ID: {user_id})\n"
                         f"Issue: {issue}",
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                pass
        
        await update.effective_message.reply_text(text=json.dumps({'success': True}))
    
    async def process_missions(self, update, context, data):
        """Get user missions"""
        user_id = data.get('user_id')
        missions = self.db.get_user_missions(user_id)
        await update.effective_message.reply_text(text=json.dumps(missions))
    
    async def check_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check balance command"""
        user_id = update.effective_user.id
        user = self.db.get_user(user_id)
        
        if user:
            text = (
                f"💰 **Your Balance**\n\n"
                f"Available: ₹{user.get('balance', 0):.2f}\n"
                f"Total Earned: ₹{user.get('total_earned', 0):.2f}\n"
                f"Active Referrals: {user.get('active_refs', 0)}\n"
                f"Tier: {self.config.get_tier_name(user.get('tier', 1))}"
            )
        else:
            text = "Please use /start first"
        
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    
    async def show_referrals(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show referrals command"""
        user_id = update.effective_user.id
        user = self.db.get_user(user_id)
        
        if user:
            ref_link = f"https://t.me/{self.config.BOT_USERNAME}?start=ref_{user_id}"
            daily_earning = user.get('active_refs', 0) * self.config.DAILY_REFERRAL_EARNING
            
            text = (
                f"👥 **Your Referrals**\n\n"
                f"Total: {user.get('total_refs', 0)}\n"
                f"Active: {user.get('active_refs', 0)}\n"
                f"Pending: {user.get('pending_refs', 0)}\n\n"
                f"💰 **Daily Earnings:** ₹{daily_earning:.2f}\n\n"
                f"🔗 **Your Link:**\n`{ref_link}`"
            )
        else:
            text = "Please use /start first"
        
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    
    async def withdraw_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Withdraw command"""
        user_id = update.effective_user.id
        user = self.db.get_user(user_id)
        
        if not user:
            await update.message.reply_text("Please use /start first")
            return
        
        balance = user.get('balance', 0)
        
        if balance < self.config.MIN_WITHDRAWAL:
            await update.message.reply_text(
                f"❌ Minimum withdrawal is ₹{self.config.MIN_WITHDRAWAL}\n"
                f"Your balance: ₹{balance:.2f}"
            )
            return
        
        keyboard = [[
            InlineKeyboardButton(
                "💸 WITHDRAW NOW",
                web_app=WebAppInfo(url=f"{self.config.WEBAPP_URL}/?user_id={user_id}&page=withdraw")
            )
        ]]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"💰 Your balance: ₹{balance:.2f}\n"
            f"Click below to withdraw:",
            reply_markup=reply_markup
        )
    
    async def help_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Help command"""
        text = (
            "❓ **Help**\n\n"
            "**Commands:**\n"
            "/start - Start the bot\n"
            "/app - Open Mini App\n"
            "/balance - Check balance\n"
            "/referrals - View referrals\n"
            "/withdraw - Withdraw earnings\n"
            "/help - This message\n\n"
            "**How to Earn:**\n"
            "1️⃣ Join movie group and search movies\n"
            "2️⃣ Share your referral link\n"
            "3️⃣ Claim daily bonus\n"
            "4️⃣ Join channel for bonus\n\n"
            "⚠️ **Anti-Cheat Warning:**\n"
            "• Fake searches = No withdrawal\n"
            "• Admin checks all withdrawals\n"
            "• Only real searches count\n\n"
            f"**Support:** {self.config.SUPPORT_USERNAME}"
        )
        
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
