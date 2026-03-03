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
        
        # Extract referrer from start param
        referrer_id = None
        if args and args[0].startswith('ref_'):
            try:
                referrer_id = int(args[0].replace('ref_', ''))
                if referrer_id == user.id:
                    referrer_id = None  # Self referral not allowed
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
        
        # Create welcome message with buttons
        welcome_text = (
            f"🎬 **Welcome to FilmyFund, {user.first_name}!**\n\n"
            f"💰 **Earn Money Daily**\n"
            f"• Refer friends → earn ₹{self.config.DAILY_REFERRAL_EARNING} per active referral daily\n"
            f"• First search bonus → ₹0.30\n"
            f"• Daily bonus with streak → up to ₹0.20\n"
            f"• Complete missions → earn up to ₹25\n"
            f"• Weekly leaderboard → win ₹200\n\n"
            f"👇 **Click below to start earning!**"
        )
        
        # Main button to open Mini App
        keyboard = [[
            InlineKeyboardButton(
                "📱 OPEN MINI APP & EARN",
                web_app=WebAppInfo(url=f"{self.config.WEBAPP_URL}/?user_id={user.id}")
            )
        ]]
        
        # Add join group button
        keyboard.append([
            InlineKeyboardButton(
                "🎬 JOIN MOVIE GROUP",
                url=self.config.MOVIE_GROUP_LINK
            )
        ])
        
        # If referred, show message
        if is_new and referrer_id:
            welcome_text += f"\n\n✅ You were referred by a friend! Complete first search to activate your referral!"
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Send welcome message
        await update.message.reply_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Send referral link separately
        ref_link = f"https://t.me/{self.config.BOT_USERNAME}?start=ref_{user.id}"
        await update.message.reply_text(
            f"🔗 **Your Referral Link:**\n`{ref_link}`\n\n"
            f"Share this link with friends! When they join and search, you'll earn daily!",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def handle_webapp_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all Mini App actions"""
        try:
            web_app_data = update.effective_message.web_app_data
            if not web_app_data:
                return
            
            user = update.effective_user
            data = json.loads(web_app_data.data)
            action = data.get('action')
            
            logger.info(f"📱 WebApp action from {user.id}: {action}")
            
            # Route to appropriate handler
            if action == 'search_verified':
                await self.process_search_verification(update, context, data)
            elif action == 'daily_bonus':
                await self.process_daily_bonus(update, context, data)
            elif action == 'channel_join':
                await self.process_channel_join(update, context, data)
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
    
    async def process_search_verification(self, update, context, data):
        """Process when user verifies they searched in group"""
        user_id = data.get('user_id')
        
        # Record the search
        self.db.record_search(user_id)
        
        # Get updated user data
        user = self.db.get_user(user_id)
        
        response = {
            'success': True,
            'message': 'Search verified!',
            'user_data': {
                'balance': user.get('balance', 0),
                'total_searches': user.get('total_searches', 0),
                'active_refs': user.get('active_refs', 0),
                'tier': user.get('tier', 1)
            }
        }
        
        await update.effective_message.reply_text(text=json.dumps(response))
        
        # Send confirmation message to user
        await context.bot.send_message(
            chat_id=user_id,
            text="✅ **Search Verified!**\n\n"
                 "Your referrer will now earn daily from your activity!\n"
                 "Keep searching daily to help them earn more!",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def process_daily_bonus(self, update, context, data):
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
    
    async def process_channel_join(self, update, context, data):
        user_id = data.get('user_id')
        channel_id = data.get('channel_id', 'main')
        
        # Verify if user actually joined (can be done via bot)
        try:
            member = await context.bot.get_chat_member(
                chat_id=self.config.CHANNELS['main']['id'],
                user_id=user_id
            )
            
            if member.status in ['member', 'administrator', 'creator']:
                result = self.db.mark_channel_join(user_id, channel_id)
                response = {
                    'success': True,
                    'bonus': self.config.CHANNELS['main']['bonus']
                }
            else:
                response = {
                    'success': False,
                    'message': 'Please join the channel first'
                }
        except Exception as e:
            logger.error(f"Channel verification error: {e}")
            response = {
                'success': False,
                'message': 'Could not verify. Please try again.'
            }
        
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
        
        # Forward to admin (optional)
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
                f"Active Referrals: {user.get('active_refs', 0)}\n"
                f"Pending: {user.get('pending_refs', 0)}\n"
                f"Tier: {self.config.get_tier_name(user.get('tier', 1))}\n\n"
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
            
            # Calculate daily earnings
            daily_earning = user.get('active_refs', 0) * self.config.DAILY_REFERRAL_EARNING
            
            text = (
                f"👥 **Your Referrals**\n\n"
                f"Total: {user.get('total_refs', 0)}\n"
                f"Active: {user.get('active_refs', 0)} (Earning daily)\n"
                f"Pending: {user.get('pending_refs', 0)} (Need to search)\n\n"
                f"💰 **Daily Earnings:** ₹{daily_earning:.2f}\n"
                f"📈 **Tier:** {self.config.get_tier_name(user.get('tier', 1))}\n\n"
                f"🔗 **Your Referral Link:**\n"
                f"`{ref_link}`\n\n"
                f"Share this link! When friends join and search, you'll earn daily!"
            )
        else:
            text = "Please use /start first"
        
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    
    async def help_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = (
            "❓ **FilmyFund Help**\n\n"
            "**Commands:**\n"
            "/start - Start the bot\n"
            "/app - Open Mini App\n"
            "/balance - Check balance\n"
            "/referrals - View referrals\n"
            "/help - This message\n\n"
            "**How to Earn:**\n"
            "1️⃣ **Refer Friends**\n"
            "   - Share your referral link\n"
            "   - Friend joins → ₹5 welcome bonus (one-time)\n"
            "   - Friend searches → You earn ₹0.30 daily forever!\n\n"
            "2️⃣ **Daily Bonus**\n"
            "   - Claim daily to build streak\n"
            "   - Higher streak = higher bonus\n\n"
            "3️⃣ **Complete Missions**\n"
            "   - Earn extra rewards\n\n"
            "4️⃣ **Weekly Leaderboard**\n"
            "   - Top 3 with 50+ active → ₹200 each\n"
            "   - Rank 4-10 with 25+ active → ₹50 each\n\n"
            "**Support:** @{support_username}"
        ).format(
            support_username=self.config.SUPPORT_USERNAME.replace('@', '')
        )
        
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular messages"""
        user_id = update.effective_user.id
        text = update.message.text
        
        # Check if it's a movie search in group
        if update.effective_chat.type in ['group', 'supergroup']:
            # This is a group message - could be movie search
            # You can implement keyword detection here
            if any(word in text.lower() for word in ['movie', 'film', 'bollywood', 'hollywood']):
                self.db.record_search(user_id)
                await update.message.reply_text("✅ Search recorded! Your referrer will earn today!")
        
        # Simple response for private chat
        elif update.effective_chat.type == 'private':
            if text.lower() in ['hi', 'hello', 'hey']:
                await update.message.reply_text(f"Hello! Use /app to start earning money!")
            else:
                await update.message.reply_text("Use /app to open the Mini App and start earning!")
