# ===== handlers.py (FIXED COMPLETE) =====
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
        """Start command handler - FIXED referral system"""
        try:
            user = update.effective_user
            args = context.args
            
            # Extract referrer from start param
            referrer_id = None
            if args and args[0].startswith('ref_'):
                try:
                    referrer_id = int(args[0].replace('ref_', ''))
                    # Prevent self-referral
                    if referrer_id == user.id:
                        referrer_id = None
                        logger.info(f"User {user.id} tried to self-refer")
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
                if referrer_id:
                    logger.info(f"✅ New user: {user.id} referred by: {referrer_id}")
                else:
                    logger.info(f"✅ New user: {user.id} (direct)")
            else:
                logger.info(f"👋 Returning user: {user.id}")
            
            # Create welcome message
            welcome_text = (
                f"🎬 **Welcome to FilmyFund, {user.first_name}!**\n\n"
                f"💰 **How You Earn:**\n"
                f"• Refer friends → earn ₹{self.config.DAILY_REFERRAL_EARNING} per active referral DAILY\n"
                f"• When friends search movies, YOU get paid\n"
                f"• Join channel → ₹{self.config.CHANNEL_JOIN_BONUS} instant bonus\n"
                f"• Daily bonus with streak → up to ₹0.20\n\n"
                f"📌 **IMPORTANT:**\n"
                f"❌ You DON'T earn by searching yourself\n"
                f"✅ You earn when YOUR REFERRALS search\n"
                f"🔍 Your referrals must search in the movie group\n\n"
                f"👇 **Click below to begin!**"
            )
            
            # Create keyboard
            keyboard = [
                [InlineKeyboardButton(
                    "📱 OPEN MINI APP",
                    web_app=WebAppInfo(url=f"{self.config.WEBAPP_URL}/?user_id={user.id}")
                )],
                [InlineKeyboardButton(
                    "🎬 JOIN MOVIE GROUP",
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
                f"⚠️ **Rules:**\n"
                f"• Friends must join movie group\n"
                f"• Friends must search movies (any movie name)\n"
                f"• You earn ₹{self.config.DAILY_REFERRAL_EARNING} daily per active friend\n"
                f"• Fake searches = No withdrawal for anyone\n"
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
                # Calculate daily earning potential
                daily_potential = user.get('active_refs', 0) * self.config.DAILY_REFERRAL_EARNING
                
                text = (
                    f"💰 **Your Balance**\n\n"
                    f"Available: ₹{user.get('balance', 0):.2f}\n"
                    f"Total Earned: ₹{user.get('total_earned', 0):.2f}\n\n"
                    f"👥 **Referrals**\n"
                    f"Active: {user.get('active_refs', 0)}\n"
                    f"Pending: {user.get('pending_refs', 0)}\n"
                    f"Daily Potential: ₹{daily_potential:.2f}\n\n"
                    f"🏆 **Tier:** {self.config.get_tier_name(user.get('tier', 1))}"
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
                    f"💰 **Daily Earnings:** ₹{daily_earning:.2f}\n"
                    f"📊 **Monthly Potential:** ₹{daily_earning * 30:.2f}\n\n"
                    f"🔗 **Your Link:**\n`{ref_link}`\n\n"
                    f"💡 **Tip:** Share this link with friends to earn more!"
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
                    f"Your balance: ₹{balance:.2f}\n\n"
                    f"Earn more by referring friends!"
                )
                return
            
            # Check for suspicious activity
            if user.get('suspicious_activity'):
                await update.message.reply_text(
                    "❌ Your account is under review.\n"
                    "Contact support for more information."
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
                "❓ **Help & FAQ**\n\n"
                "**Commands:**\n"
                "/start - Start the bot\n"
                "/app - Open Mini App\n"
                "/balance - Check balance\n"
                "/referrals - View referrals\n"
                "/withdraw - Withdraw earnings\n"
                "/help - This message\n\n"
                "**How to Earn:**\n"
                "1️⃣ Share your referral link with friends\n"
                "2️⃣ Friends join and search movies in group\n"
                "3️⃣ You earn ₹{self.config.DAILY_REFERRAL_EARNING} per active friend daily\n"
                "4️⃣ Claim daily bonus for extra earnings\n\n"
                "**⚠️ Important Rules:**\n"
                "• You DON'T earn from your own searches\n"
                "• You ONLY earn from your referrals' searches\n"
                "• Fake searches = No withdrawal (banned)\n"
                "• Admin checks all withdrawals\n\n"
                f"**Support:** {self.config.SUPPORT_USERNAME}"
            )
            
            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            logger.error(f"Help error: {e}")
    
    # ========== MESSAGE HANDLER ==========
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all messages - AUTOMATIC GROUP VERIFICATION - FIXED"""
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
            elif chat_id.endswith(str(abs(int(self.config.MOVIE_GROUP_ID)))):  # Compare numeric part
                is_movie_group = True
            elif chat.username and chat.username in str(self.config.MOVIE_GROUP_LINK):
                is_movie_group = True
            
            # If it's the movie group and message has text (search)
            if is_movie_group and message_text and len(message_text.strip()) > 1:
                logger.info(f"🔍 Movie search detected: User {user_id} in group {chat_id}")
                
                # Record search - this ONLY affects referrer earnings, NOT user balance
                result = self.db.record_search(user_id)
                
                if result:
                    # Send private confirmation to the user (searcher)
                    try:
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=(
                                "✅ **Search Recorded!**\n\n"
                                f"• Movie: '{message_text[:30]}...'\n"
                                "• This helps your referrer earn\n"
                                "• You DON'T earn from your own searches\n"
                                "• To earn: refer friends using /referrals\n\n"
                                f"📱 Open Mini App: {self.config.WEBAPP_URL}/?user_id={user_id}"
                            ),
                            parse_mode=ParseMode.MARKDOWN
                        )
                    except Exception as e:
                        logger.error(f"Could not send confirmation to user {user_id}: {e}")
                    
                    # NO GROUP REPLY - FIXED: No message in group
                    logger.info(f"✅ Search recorded for user {user_id} (no group reply)")
                else:
                    logger.warning(f"❌ Search NOT recorded for user {user_id} (anti-cheat)")
                    # Notify user privately if search failed
                    try:
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=(
                                "❌ **Search Not Recorded**\n\n"
                                "Possible reasons:\n"
                                "• Daily search limit reached\n"
                                "• Searching too fast (spam)\n"
                                "• Account under review\n\n"
                                "Please try again later."
                            ),
                            parse_mode=ParseMode.MARKDOWN
                        )
                    except:
                        pass
            
            # Handle private messages
            elif chat.type == 'private':
                if message_text.lower() in ['hi', 'hello', 'hey']:
                    await message.reply_text(
                        "Welcome! Use /start to begin earning!\n"
                        f"Or open Mini App: {self.config.WEBAPP_URL}/?user_id={user_id}"
                    )
                elif message_text.lower() not in ['/start', '/app', '/balance', '/referrals', '/withdraw', '/help']:
                    await message.reply_text(
                        "Use /app to open the Mini App and check your earnings!"
                    )
                    
        except Exception as e:
            logger.error(f"Message handler error: {e}")
    
    # ========== WEBAPP DATA HANDLER ==========
    
    async def handle_webapp_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle Mini App actions - FIXED"""
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
            
            # Send response back to webapp
            await update.effective_message.reply_text(text=json.dumps(response))
            
        except Exception as e:
            logger.error(f"WebApp data error: {e}")
            await update.effective_message.reply_text(
                text=json.dumps({'success': False, 'message': str(e)})
            )
    
    # ========== WEBAPP PROCESSORS ==========
    
    async def process_channel_verification(self, data):
        """Process channel join verification - FIXED"""
        try:
            user_id = data.get('user_id')
            channel_id = data.get('channel_id')
            
            if not user_id or not channel_id:
                return {'success': False, 'message': 'Invalid data'}
            
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
        except Exception as e:
            logger.error(f"Channel verification error: {e}")
            return {'success': False, 'message': 'Verification failed'}
    
    async def process_daily_bonus(self, data):
        """Process daily bonus claim - FIXED"""
        try:
            user_id = data.get('user_id')
            result = self.db.claim_daily_bonus(user_id)
            
            if result and result.get('success'):
                return {
                    'success': True,
                    'bonus': result['bonus'],
                    'streak': result['streak'],
                    'message': f'Claimed ₹{result["bonus"]:.2f} (Streak: {result["streak"]})'
                }
            else:
                return {
                    'success': False,
                    'message': 'Already claimed today or try again later'
                }
        except Exception as e:
            logger.error(f"Daily bonus error: {e}")
            return {'success': False, 'message': 'Failed to claim'}
    
    async def process_withdraw(self, data):
        """Process withdrawal request - FIXED"""
        try:
            user_id = data.get('user_id')
            amount = data.get('amount')
            method = data.get('method')
            details = data.get('details')
            
            result = self.db.process_withdrawal(user_id, amount, method, details)
            return result
        except Exception as e:
            logger.error(f"Withdrawal error: {e}")
            return {'success': False, 'message': 'Withdrawal failed'}
    
    async def process_report_issue(self, data):
        """Process issue report"""
        try:
            user_id = data.get('user_id')
            issue = data.get('issue')
            
            # Add issue to database
            self.db.issues.insert_one({
                'user_id': user_id,
                'issue': issue,
                'report_date': datetime.now().isoformat(),
                'status': 'pending'
            })
            
            return {'success': True, 'message': 'Issue reported. Admin will contact you.'}
        except Exception as e:
            logger.error(f"Report issue error: {e}")
            return {'success': False, 'message': 'Failed to report'}
    
    async def process_missions(self, data):
        """Get user missions"""
        try:
            user_id = data.get('user_id')
            user = self.db.get_user(user_id)
            
            if not user:
                return {}
            
            # Calculate mission progress
            missions = {
                'mission_1': {
                    'name': 'Make 1 Active Referral',
                    'completed': user.get('active_refs', 0) >= 1,
                    'progress': min(user.get('active_refs', 0), 1),
                    'total': 1,
                    'reward': 5.0
                },
                'mission_2': {
                    'name': 'Make 5 Active Referrals',
                    'completed': user.get('active_refs', 0) >= 5,
                    'progress': min(user.get('active_refs', 0), 5),
                    'total': 5,
                    'reward': 25.0
                },
                'mission_3': {
                    'name': 'Reach Silver Tier',
                    'completed': user.get('active_refs', 0) >= 10,
                    'progress': min(user.get('active_refs', 0), 10),
                    'total': 10,
                    'reward': 50.0
                },
                'mission_4': {
                    'name': 'Reach Gold Tier',
                    'completed': user.get('active_refs', 0) >= 30,
                    'progress': min(user.get('active_refs', 0), 30),
                    'total': 30,
                    'reward': 100.0
                },
                'mission_5': {
                    'name': 'Reach Diamond Tier',
                    'completed': user.get('active_refs', 0) >= 100,
                    'progress': min(user.get('active_refs', 0), 100),
                    'total': 100,
                    'reward': 500.0
                }
            }
            
            return {
                'success': True,
                'missions': missions,
                'total_completed': sum(1 for m in missions.values() if m['completed'])
            }
        except Exception as e:
            logger.error(f"Missions error: {e}")
            return {}
