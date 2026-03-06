# ===== handlers.py (COMPLETE FIXED - DAILY BONUS ADDED, CORRECT REF LINK) =====

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
        """Start command handler - FIXED: Correct referral link format"""
        try:
            user = update.effective_user
            args = context.args
            
            referrer_id = None
            if args and args[0].startswith('ref_'):
                try:
                    referrer_id = int(args[0].replace('ref_', ''))
                    if referrer_id == user.id:
                        referrer_id = None
                        logger.info(f"User {user.id} tried to self-refer")
                except:
                    pass
            
            user_data = {
                'user_id': user.id,
                'first_name': user.first_name or "User",
                'username': user.username,
                'referrer_id': referrer_id
            }
            
            is_new = self.db.add_user(user_data)
            
            if is_new:
                if referrer_id:
                    logger.info(f"✅ New user: {user.id} referred by: {referrer_id}")
                    
                    try:
                        referrer = self.db.get_user(referrer_id)
                        if referrer:
                            notify = referrer.get('notify_referrals', True)
                            if notify:
                                await context.bot.send_message(
                                    chat_id=referrer_id,
                                    text=(
                                        f"🎉 **New Referral!**\n\n"
                                        f"{user.first_name} just joined using your link!\n\n"
                                        f"🔍 Ask them to:\n"
                                        f"1️⃣ Join movie group\n"
                                        f"2️⃣ Search any movie\n"
                                        f"3️⃣ Complete shortlinks\n\n"
                                        f"You'll earn when they search! 🚀"
                                    ),
                                    parse_mode=ParseMode.MARKDOWN
                                )
                    except Exception as e:
                        logger.error(f"Failed to notify referrer: {e}")
                else:
                    logger.info(f"✅ New user: {user.id} (direct)")
            else:
                logger.info(f"👋 Returning user: {user.id}")
            
            welcome_text = (
                f"🎬 **Welcome {user.first_name}!**\n\n"
                f"👇 Click below to start earning:"
            )
            
            keyboard = [
                [InlineKeyboardButton(
                    "📱 OPEN MINI APP",
                    web_app=WebAppInfo(url=f"{self.config.WEBAPP_URL}/?user_id={user.id}")
                )],
                [InlineKeyboardButton(
                    "🎬 JOIN MOVIE GROUP",
                    url=self.config.MOVIE_GROUP_LINK
                )]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                welcome_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            
            # FIXED: Correct referral link format with your bot username
            ref_link = f"https://t.me/{self.config.BOT_USERNAME}?start=ref_{user.id}"
            
            ref_text = (
                f"🔗 **Your Referral Link:**\n"
                f"`{ref_link}`\n\n"
                f"📢 Share this with friends to earn!"
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
                # FIXED: Correct referral link format
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
                "3️⃣ Friends must complete shortlinks\n"
                "4️⃣ You earn ₹0.30 per active friend daily\n\n"
                "**⚠️ Important Rules:**\n"
                "• You DON'T earn from your own searches\n"
                "• You ONLY earn from your referrals' searches\n"
                "• Referrals MUST complete shortlinks\n"
                "• Fake searches = No withdrawal (banned)\n"
                "• Admin checks all withdrawals\n\n"
                f"**Support:** {self.config.SUPPORT_USERNAME}"
            )
            
            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            logger.error(f"Help error: {e}")
    
    # ========== MESSAGE HANDLER ==========
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all messages"""
        try:
            user = update.effective_user
            chat = update.effective_chat
            message = update.message
            
            if not user or not message:
                return
            
            user_id = user.id
            chat_id = str(chat.id)
            message_text = message.text or ""
            
            is_movie_group = False
            
            if chat_id == self.config.MOVIE_GROUP_ID:
                is_movie_group = True
            elif chat_id.endswith(str(abs(int(self.config.MOVIE_GROUP_ID)))) if self.config.MOVIE_GROUP_ID else False:
                is_movie_group = True
            elif chat.username and self.config.MOVIE_GROUP_LINK and chat.username in str(self.config.MOVIE_GROUP_LINK):
                is_movie_group = True
            
            if is_movie_group and message_text and len(message_text.strip()) > 1:
                logger.info(f"🔍 Movie search detected: User {user_id} in group {chat_id}")
                
                result = self.db.record_search(user_id)
                
                if result and result.get('success'):
                    try:
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=(
                                "✅ **Search Recorded!**\n\n"
                                f"• Movie: '{message_text[:30]}...'\n\n"
                                "⚠️ **IMPORTANT WARNING:**\n"
                                "• You MUST complete the shortlinks in group\n"
                                "• Without shortlinks, your referrer's withdrawals will be blocked\n"
                                "• And you won't be able to withdraw either!\n\n"
                                "👉 Go to group and click on any link\n"
                                "👉 Complete the steps (just wait 5-10 seconds)\n"
                                "👉 Do this daily to keep earnings active\n\n"
                                f"📱 Open Mini App: {self.config.WEBAPP_URL}/?user_id={user_id}"
                            ),
                            parse_mode=ParseMode.MARKDOWN
                        )
                    except Exception as e:
                        logger.error(f"Could not send confirmation to user {user_id}: {e}")
                    
                    logger.info(f"✅ Search recorded for user {user_id}")
                else:
                    logger.warning(f"❌ Search NOT recorded for user {user_id}")
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
            elif action == 'toggle_notification':
                response = await self.process_toggle_notification(data)
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
        """Process daily bonus claim"""
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
        """Process withdrawal request"""
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
    
    async def process_toggle_notification(self, data):
        """Toggle notification settings"""
        try:
            user_id = data.get('user_id')
            setting = data.get('setting')
            value = data.get('value')
            
            self.db.users.update_one(
                {'user_id': user_id},
                {'$set': {f'notify_{setting}': value}}
            )
            
            return {'success': True, 'message': 'Settings updated'}
        except Exception as e:
            logger.error(f"Toggle notification error: {e}")
            return {'success': False, 'message': 'Failed to update'}
    
    async def process_missions(self, data):
        """Get user missions"""
        try:
            user_id = data.get('user_id')
            user = self.db.get_user(user_id)
            
            if not user:
                return {}
            
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
