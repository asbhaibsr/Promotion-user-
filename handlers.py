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
        logger.info("✅ Handlers initialized")
    
    # ========== MAIN COMMANDS ==========
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command handler"""
        try:
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
                'first_name': user.first_name or "User",
                'username': user.username,
                'referrer_id': referrer_id
            }
            
            # Add to database
            is_new = self.db.add_user(user_data)
            
            if is_new:
                logger.info(f"✅ New user: {user.id} ({user.first_name}) referred by: {referrer_id}")
            else:
                logger.info(f"👋 Returning user: {user.id}")
            
            # Create welcome message
            welcome_text = (
                f"🎬 **Welcome to FilmyFund, {user.first_name}!**\n\n"
                f"💰 **Earn Money Daily**\n"
                f"• Refer friends → earn ₹{self.config.DAILY_REFERRAL_EARNING} per active referral daily\n"
                f"• Join channel → ₹{self.config.CHANNEL_JOIN_BONUS} bonus\n"
                f"• Daily bonus with streak → up to ₹0.20\n"
                f"• Search movies → activate referrals\n\n"
                f"📌 **How to Start:**\n"
                f"1️⃣ Join the movie group below\n"
                f"2️⃣ Search any movie name\n"
                f"3️⃣ Bot automatically detects!\n\n"
                f"👇 **Click below to begin!**"
            )
            
            # Create keyboard
            keyboard = [
                [InlineKeyboardButton(
                    "📱 OPEN MINI APP",
                    web_app=WebAppInfo(url=f"{self.config.WEBAPP_URL}/?user_id={user.id}")
                )],
                [InlineKeyboardButton(
                    "🎬 JOIN MOVIE GROUP (MUST)",
                    url=self.config.MOVIE_GROUP_LINK
                )],
                [InlineKeyboardButton(
                    f"📢 JOIN CHANNEL (₹{self.config.CHANNEL_JOIN_BONUS} BONUS)",
                    url=self.config.CHANNEL_LINK
                )]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Send welcome
            await update.message.reply_text(
                welcome_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Send referral link
            ref_link = f"https://t.me/{self.config.BOT_USERNAME}?start=ref_{user.id}"
            
            ref_text = (
                f"🔗 **Your Referral Link:**\n"
                f"`{ref_link}`\n\n"
                f"📢 **Share this link with friends!**\n\n"
                f"⚠️ **Important Rules:**\n"
                f"• Friends must join movie group\n"
                f"• Friends must search movies\n"
                f"• Fake searches = No withdrawal\n"
                f"• Admin verifies all withdrawals"
            )
            
            await update.message.reply_text(
                ref_text,
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logger.error(f"Start command error: {e}")
            await update.message.reply_text("❌ Error starting bot. Please try again.")
    
    async def open_app(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Open Mini App command"""
        try:
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
            
        except Exception as e:
            logger.error(f"Open app error: {e}")
    
    async def check_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check balance command"""
        try:
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
            
        except Exception as e:
            logger.error(f"Balance error: {e}")
    
    async def show_referrals(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show referrals command"""
        try:
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
            
        except Exception as e:
            logger.error(f"Referrals error: {e}")
    
    async def withdraw_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Withdraw command"""
        try:
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
            
        except Exception as e:
            logger.error(f"Withdraw cmd error: {e}")
    
    async def help_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Help command"""
        try:
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
            
        except Exception as e:
            logger.error(f"Help error: {e}")
    
    async def admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin panel command"""
        if update.effective_user.id not in self.config.ADMIN_IDS:
            await update.message.reply_text("❌ Unauthorized")
            return
        
        try:
            stats = self.db.get_system_stats()
            await update.message.reply_text(
                f"👑 **Admin Panel**\n\n"
                f"Total Users: {stats.get('total_users', 0)}\n"
                f"Active Today: {stats.get('active_today', 0)}\n"
                f"Pending Withdrawals: {stats.get('pending_withdrawals', 0)}\n"
                f"Total Searches: {stats.get('total_searches', 0)}",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Admin panel error: {e}")
    
    # ========== MESSAGE HANDLER ==========
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all messages - AUTOMATIC GROUP VERIFICATION"""
        try:
            user = update.effective_user
            chat = update.effective_chat
            message = update.message
            
            if not user or not message:
                return
            
            user_id = user.id
            chat_id = str(chat.id)
            message_text = message.text or ""
            
            # CRITICAL: Check if this is the movie group
            is_movie_group = False
            
            # Multiple checks for group identification
            if chat_id == self.config.MOVIE_GROUP_ID:
                is_movie_group = True
            elif chat_id.endswith('3193018012'):  # Your group ID suffix
                is_movie_group = True
            elif chat.username and chat.username in self.config.MOVIE_GROUP_LINK:
                is_movie_group = True
            
            # If it's the movie group and message has text (search)
            if is_movie_group and message_text and len(message_text.strip()) > 1:
                logger.info(f"🔍 Movie search detected: User {user_id} in group {chat_id}")
                
                # Record search
                result = self.db.record_search(user_id)
                
                if result:
                    # Send private confirmation
                    try:
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=(
                                "✅ **Search Recorded!**\n\n"
                                f"• Your search: '{message_text[:50]}...'\n"
                                "• Your referrer will earn today\n"
                                "• Keep searching daily\n"
                                "• Fake searches = No withdrawal\n\n"
                                f"📱 Open Mini App: {self.config.WEBAPP_URL}/?user_id={user_id}"
                            ),
                            parse_mode=ParseMode.MARKDOWN
                        )
                    except Exception as e:
                        logger.error(f"Could not send confirmation to user {user_id}: {e}")
                    
                    # Send group reply
                    try:
                        await message.reply_text(
                            "✅ **Search Recorded!**",
                            parse_mode=ParseMode.MARKDOWN
                        )
                    except:
                        pass
                    
                    logger.info(f"✅ Search recorded for user {user_id}")
                else:
                    logger.warning(f"❌ Search NOT recorded for user {user_id} (anti-cheat)")
            
            # Handle private messages
            elif chat.type == 'private':
                if message_text.lower() in ['hi', 'hello', 'hey']:
                    await message.reply_text(
                        "Welcome! Use /start to begin earning!\n"
                        f"Or open Mini App: {self.config.WEBAPP_URL}/?user_id={user_id}"
                    )
                elif message_text.lower() not in ['/start', '/app', '/balance', '/referrals', '/withdraw', '/help']:
                    await message.reply_text(
                        "Use /app to open the Mini App and start earning!"
                    )
                    
        except Exception as e:
            logger.error(f"Message handler error: {e}")
    
    # ========== WEBAPP DATA HANDLER ==========
    
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
            
            response = {'success': False, 'message': 'Unknown action'}
            
            if action == 'channel_verified':
                response = await self.process_channel_verification(data)
            elif action == 'daily_bonus':
                response = await self.process_daily_bonus(data)
            elif action == 'withdraw':
                response = await self.process_withdraw(data)
            elif action == 'report_issue':
                response = await self.process_report_issue(data)
            elif action == 'get_missions':
                response = await self.process_missions(data)
            
            await update.effective_message.reply_text(text=json.dumps(response))
            
        except Exception as e:
            logger.error(f"WebApp data error: {e}")
            await update.effective_message.reply_text(
                text=json.dumps({'success': False, 'message': str(e)})
            )
    
    # ========== WEBAPP PROCESSORS ==========
    
    async def process_channel_verification(self, data):
        """Process channel join verification"""
        user_id = data.get('user_id')
        channel_id = data.get('channel_id')
        
        result = self.db.mark_channel_join(user_id, channel_id)
        
        if result:
            user = self.db.get_user(user_id)
            return {
                'success': True,
                'message': f'Channel joined! ₹{self.config.CHANNEL_JOIN_BONUS} bonus added!',
                'user_data': {
                    'balance': user.get('balance', 0),
                    'channel_joined': True
                }
            }
        else:
            return {
                'success': False,
                'message': 'Already claimed bonus or invalid channel!'
            }
    
    async def process_daily_bonus(self, data):
        """Process daily bonus claim"""
        user_id = data.get('user_id')
        result = self.db.claim_daily_bonus(user_id)
        
        if result:
            return {
                'bonus': result['bonus'],
                'streak': result['streak'],
                'success': True
            }
        else:
            return {
                'success': False,
                'message': 'Already claimed today or try again later'
            }
    
    async def process_withdraw(self, data):
        """Process withdrawal request"""
        user_id = data.get('user_id')
        amount = data.get('amount')
        method = data.get('method')
        details = data.get('details')
        
        result = self.db.process_withdrawal(user_id, amount, method, details)
        return result
    
    async def process_report_issue(self, data):
        """Process issue report"""
        user_id = data.get('user_id')
        issue = data.get('issue')
        
        # Add issue to database
        try:
            self.db.issues.insert_one({
                'user_id': user_id,
                'issue': issue,
                'report_date': datetime.now().isoformat(),
                'status': 'pending'
            })
        except:
            pass
        
        return {'success': True, 'message': 'Issue reported. Admin will contact you.'}
    
    async def process_missions(self, data):
        """Get user missions"""
        user_id = data.get('user_id')
        user = self.db.get_user(user_id)
        
        if not user:
            return {}
        
        # Simple mission response
        missions = {}
        for i in range(1, 6):
            missions[f'mission_{i}'] = {
                'name': f'Mission {i}',
                'completed': i <= 2,
                'reward': i * 5
            }
        
        return missions
