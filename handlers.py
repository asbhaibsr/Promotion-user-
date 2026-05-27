# ═══════════════════════════════════════════════════════════
# EarnZone / FilmyFund — Telegram Mini App
# Owner   : @asbhaibsr
# ⚠️  Unauthorized modification or redistribution prohibited.
# © 2025 @asbhaibsr — All Rights Reserved
# ═══════════════════════════════════════════════════════════

# ===== handlers.py — LOG CHANNEL VERIFY COMPLETELY FIXED =====
#
# ASLI PROBLEM THI:
#   1. bot_app.run_polling() mein channel_post allowed_updates nahi tha
#   2. Handler filter sahi nahi tha channel posts ke liye
#   3. ID parsing Unicode small caps handle nahi karta tha properly
#
# FIXES:
#   ✅ Log channel pe #VerifyComplete → referral activate
#   ✅ Log channel pe #FileSent → referral activate  
#   ✅ Log channel pe #NewUser → SIRF log, activate NAHI
#   ✅ Unicode ID parse (ɪᴅ - 7142838312)
#   ✅ Normal ID parse (ID - 7142838312)
#   ✅ Bracket ID parse (As Name (7142838312))
#   ✅ Referrer ko notify — jab referred user group pe aaye
#   ✅ Referral active hone pe dono users ko message

import logging
import re
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.error import Forbidden, BadRequest
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

# ⚠️ APNA LOG CHANNEL ID YAHAN DAALO
LOG_CHANNEL_ID = -1002352329534


class Handlers:
    def __init__(self, config, db):
        self.config = config
        self.db = db
        self.bot = None
        self._group_notified = {}  # user_id -> last_notify_timestamp
        logger.info("✅ Handlers initialized")

    # ══════════════════════════════════════════════════════════════
    # START COMMAND
    # ══════════════════════════════════════════════════════════════

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
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
                'first_name': user.first_name or "User",
                'username': user.username,
                'referrer_id': referrer_id
            }

            add_result = self.db.add_user(user_data)

            # ── Duplicate user ──
            if isinstance(add_result, dict) and add_result.get('already_on_bot'):
                info = add_result
                uname = info.get('username', '')
                uname_txt = f"@{uname}" if uname else "No username"
                orig_ref_id = info.get('original_referrer_id')

                if referrer_id:
                    orig_txt = ""
                    if orig_ref_id and orig_ref_id != referrer_id:
                        orig_ref_user = self.db.get_user(orig_ref_id)
                        if orig_ref_user:
                            orig_name = orig_ref_user.get('first_name', 'Someone')
                            orig_txt = f"\n⚠️ Inhe pehle se {orig_name} ne refer kiya hua hai."
                    try:
                        await context.bot.send_message(
                            chat_id=referrer_id,
                            text=(
                                f"⚠️ Ye User Pehle Se Hai!\n\n"
                                f"👤 {info.get('first_name', 'User')} pehle se FilmyFund use kar raha hai\n\n"
                                f"❌ Ye aapke refer mein count NAHI hoga\n\n"
                                f"💡 Tip: Naye log dhundho jo abhi tak join nahi kiye!\n"
                                f"Jitne zyada naye refer — utni zyada KAMAI! 💰"
                            )
                        )
                    except Exception as e:
                        logger.error(f"Notify referrer duplicate: {e}")

                keyboard = [
                    [InlineKeyboardButton("💰 App Kholo — Paise Kamao!",
                        web_app=WebAppInfo(url=f"{self.config.WEBAPP_URL}/?user_id={user.id}"))],
                    [InlineKeyboardButton("🎬 Movie Group", url=self.config.MOVIE_GROUP_LINK)],
                    [InlineKeyboardButton("📢 Sabhi Groups Join Karo", url="https://t.me/addlist/tN-IEpLgpUQzMGY1")]
                ]
                await update.message.reply_text(
                    f"👋 Wapas Aaye {user.first_name}!\n\n"
                    f"💰 Aaj ka Bonus abhi baaki hai!\n"
                    f"🎯 Missions complete karo — points pao!\n"
                    f"📺 Ads dekho — aur kamao!\n\n"
                    f"⬇️ App kholo aur shuru karo!",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                return

            is_new = bool(add_result)

            if is_new:
                self.db.add_live_activity('join', user.id, 0, "Joined the bot")

                # Log to channel
                if self.config.LOG_CHANNEL_ID:
                    try:
                        referrer_name = "Direct"
                        if referrer_id:
                            ref_user = self.db.get_user(referrer_id)
                            if ref_user:
                                rname = ref_user.get('first_name', '')
                                rusername = ref_user.get('username', '')
                                referrer_name = f"{rname} (@{rusername})" if rusername else rname
                        await context.bot.send_message(
                            chat_id=self.config.LOG_CHANNEL_ID,
                            text=(
                                f"👤 NEW USER JOINED\n\n"
                                f"Name: {user.first_name}\n"
                                f"ID: {user.id}\n"
                                f"Username: @{user.username if user.username else 'N/A'}\n"
                                f"Referred by: {referrer_name}\n"
                                f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                            )
                        )
                    except Exception as e:
                        logger.error(f"Log channel new user error: {e}")

                # Notify admins
                for admin_id in self.config.ADMIN_IDS:
                    try:
                        kb = [[InlineKeyboardButton("👤 VIEW USER", callback_data=f"user_details_{user.id}")]]
                        await context.bot.send_message(
                            chat_id=admin_id,
                            text=(
                                f"👤 New User! {user.first_name}\n"
                                f"ID: {user.id}\nRef by: {referrer_id or 'Direct'}"
                            ),
                            reply_markup=InlineKeyboardMarkup(kb)
                        )
                    except:
                        pass

                # Notify referrer
                if referrer_id:
                    try:
                        referrer = self.db.get_user(referrer_id)
                        if referrer and referrer.get('notify_referrals', True):
                            await context.bot.send_message(
                                chat_id=referrer_id,
                                text=(
                                    f"🔔 {user.first_name} Join Ho Gaya!\n\n"
                                    f"✅ Aapka referral link kaam kar gaya!\n\n"
                                    f"⏳ Abhi sirf EK kaam baaki hai:\n"
                                    f"👉 Inhe Movie Group pe movie search karni hai\n"
                                    f"👉 Movie bot ka link khola aur 10 sec wait karo\n\n"
                                    f"Bas itna karte hi:\n"
                                    f"🎟 +3 Passes TURANT milenge!\n"
                                    f"💰 +{int(float(self.config.REFERRAL_BONUS)*100)} pts account mein!\n\n"
                                    f"🔥 Abhi inhe message karo — time mat kho!"
                                )
                            )
                    except Exception as e:
                        logger.error(f"Notify referrer on join: {e}")

            # Welcome message
            ref_link = f"https://t.me/{self.config.BOT_USERNAME}?start=ref_{user.id}"
            movie_group = getattr(self.config, 'MOVIE_GROUP_LINK', 'https://t.me/all_movies_webseries_is_here')

            if referrer_id and is_new:
                welcome_text = (
                    f"🤑 {user.first_name}, Paise Kamana Shuru Karo!\n\n"
                    f"✅ Referral se aaye — BONUS ACTIVE!\n\n"
                    f"━━━ SIRF 3 KAAM ━━━\n\n"
                    f"1️⃣ 👇 MOVIE GROUP join karo\n"
                    f"2️⃣ Koi bhi movie search karo\n"
                    f"    (jaise: Pushpa 2, Stree 2)\n"
                    f"3️⃣ Link aaya → kholo → 10 sec ruko ✅\n\n"
                    f"━━━ REWARD ━━━\n"
                    f"🎁 +50 pts TURANT!\n"
                    f"💰 Roz search = +30 pts\n"
                    f"🎮 Games khelo = aur kamao\n"
                    f"👥 Dosto ko refer karo = DOUBLE KAMAI\n\n"
                    f"🔥 1000+ log roz paise kama rahe hain!"
                )
                keyboard = [
                    [InlineKeyboardButton("🎬 MOVIE GROUP — ABHI JOIN KARO!", url=movie_group)],
                    [InlineKeyboardButton("💰 App Kholo — Earning Shuru!", web_app=WebAppInfo(url=f"{self.config.WEBAPP_URL}/?user_id={user.id}"))],
                    [InlineKeyboardButton("📢 Sabhi Groups Join Karo", url="https://t.me/addlist/tN-IEpLgpUQzMGY1")]
                ]
                await update.message.reply_text(
                    welcome_text, reply_markup=InlineKeyboardMarkup(keyboard)
                )
                # 2hr auto reminder
                try:
                    import asyncio
                    async def _remind_2hr():
                        await asyncio.sleep(7200)
                        try:
                            if not self.db.referrals.find_one({'referred_id': user.id, 'is_active': True}):
                                kb = [[InlineKeyboardButton("🎬 ABHI Movie Search Karo!", url=movie_group)]]
                                await context.bot.send_message(
                                    chat_id=user.id,
                                    text=(
                                        f"⚠️ {user.first_name}, Bonus Ud Jayega!\n\n"
                                        f"😱 +50 pts abhi bhi aapke liye wait kar raha hai!\n\n"
                                        f"Bas EK kaam:\n"
                                        f"👇 Movie Group pe koi movie search karo\n"
                                        f"👇 Link kholo, 10 sec ruko — HO GAYA!\n\n"
                                        f"⏰ Abhi karo — kal mat sochna!"
                                    ),
                                    reply_markup=InlineKeyboardMarkup(kb)
                                )
                        except Exception as e:
                            logger.error(f"2hr reminder: {e}")
                    asyncio.ensure_future(_remind_2hr())
                except:
                    pass
            else:
                keyboard = [
                    [InlineKeyboardButton("🤑 App Kholo — Paise Kamao!",
                        web_app=WebAppInfo(url=f"{self.config.WEBAPP_URL}/?user_id={user.id}"))],
                    [InlineKeyboardButton("🎬 Movie Group Join Karo", url=movie_group)],
                    [InlineKeyboardButton("📢 Sabhi Groups Join Karo", url="https://t.me/addlist/tN-IEpLgpUQzMGY1")]
                ]
                await update.message.reply_text(
                    f"💰 {user.first_name}, Paise Kamana Shuru Karo!\n\n"
                    f"🎬 Movie dekho → Paise kamao\n"
                    f"👥 Dosto ko refer karo → Aur paise kamao\n"
                    f"🎮 Games khelo → Aur bhi paise kamao\n\n"
                    f"🔥 1000+ log roz kama rahe hain FilmyFund se!\n\n"
                    f"⬇️ App kholo aur ABHI shuru karo!",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

            if is_new:
                await update.message.reply_text(
                    f"🔗 Aapka Personal Earning Link:\n"
                    f"{ref_link}\n\n"
                    f"━━━ EK REFER = KITNA MILEGA? ━━━\n"
                    f"🎟 +3 Passes (Games khelne ke liye)\n"
                    f"💰 +{int(float(self.config.REFERRAL_BONUS)*100)} pts balance mein!\n"
                    f"📅 Roz +30 pts — jab tak woh search karta rahe!\n\n"
                    f"👇 Copy karo aur apne dosto ko bhejo!\n"
                    f"Jitne zyada refer — UTNI ZYADA KAMAI! 🚀"
                )

        except Exception as e:
            logger.error(f"Start error: {e}", exc_info=True)
            try:
                await update.message.reply_text("❌ Error. /start dobara try karo.")
            except:
                pass

    # ══════════════════════════════════════════════════════════════
    # GROUP MESSAGE — Sirf referrer ko notify karo
    # ══════════════════════════════════════════════════════════════

    async def handle_group_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Movie group pe message aaya — referrer ko notify karo ki user aa gaya.
        VERIFY/ACTIVATE sirf log channel se hoga.
        """
        try:
            message = update.message or update.channel_post
            if not message:
                return
            user = update.effective_user
            if not user or user.is_bot:
                return
            chat = update.effective_chat
            if not chat or chat.type not in ['group', 'supergroup']:
                return

            # Sirf configured movie group pe
            if self.config.MOVIE_GROUP_ID:
                try:
                    if str(chat.id) != str(self.config.MOVIE_GROUP_ID):
                        return
                except:
                    pass

            msg_text = message.text or message.caption or ""
            if len(msg_text.strip()) < 2:
                return

            user_id = user.id
            referral = self.db.referrals.find_one({'referred_id': user_id})
            if not referral:
                return

            referrer_id = referral.get('referrer_id')
            is_active = referral.get('is_active', False)

            # Pending referral — referrer ko ek baar notify karo
            if not is_active and referrer_id:
                now_ts = datetime.now().timestamp()
                last_notified = self._group_notified.get(user_id, 0)
                if now_ts - last_notified > 21600:  # 6 hr cooldown
                    self._group_notified[user_id] = now_ts
                    try:
                        referrer = self.db.get_user(referrer_id)
                        if referrer and referrer.get('notify_referrals', True):
                            await context.bot.send_message(
                                chat_id=referrer_id,
                                text=(
                                    f"👀 {user.first_name} Movie Group Pe Aa Gaya!\n\n"
                                    f"✅ Movie search bhi kar di!\n\n"
                                    f"⏳ Sirf shortlink baaki hai...\n"
                                    f"Jaise hi link khola — TURANT active!\n\n"
                                    f"🎟 Aapko milenge: 3 Passes + {int(float(self.config.REFERRAL_BONUS)*100)} pts\n\n"
                                    f"🔥 Inhe ek message karo — jaldi karo!"
                                )
                            )
                    except Exception as e:
                        logger.error(f"Group notify referrer {referrer_id}: {e}")
        except Exception as e:
            logger.error(f"Group message handler: {e}")

    # ══════════════════════════════════════════════════════════════
    # LOG CHANNEL HANDLER — MAIN VERIFY LOGIC
    # ══════════════════════════════════════════════════════════════

    async def handle_log_channel_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Log channel pe movie bot ka message aata hai → bot verify karta hai.

        SUPPORTED FORMATS:
        ─────────────────────────────────────────────────────────────
        FORMAT 1 — #VerifyComplete (shortlink puri hui):
          ✅ #VerifyComplete
          ɪᴅ - 7142838312
          Nᴀᴍᴇ - ʀɪᴛɪᴋᴀ
          sʜᴏʀᴛʟɪɴᴋ - softurl.in
          ᴛɪᴍᴇ - 05 Apr 16:03 IST

        FORMAT 2 — #FileSent (file bheji = movie search done):
          #FileSent — File pahunch gayi! ✈️
          As Bʜᴀɪ Bsʀ (7315805581)
          Kill 2023 Hindi ORG 480p ...
          358.7 MB
          Premium: ✅ VIP
          05 Apr 15:55 IST

        FORMAT 3 — #NewUser (SIRF info, activate NAHI):
          #NewUser ID - 7346280916 Nᴀᴍᴇ - Abhinav
        ─────────────────────────────────────────────────────────────

        RULE: Sirf #VerifyComplete aur #FileSent pe activate karo.
              #NewUser pe kuch mat karo.
        """
        try:
            # Channel post ya regular message dono handle karo
            message = update.channel_post or update.message
            if not message:
                logger.debug("handle_log_channel_message: no message object")
                return

            chat_id = message.chat.id

            # ── STRICT chat ID check ──
            if chat_id != LOG_CHANNEL_ID:
                logger.debug(f"Ignoring chat_id={chat_id}, want {LOG_CHANNEL_ID}")
                return

            text = (message.text or message.caption or "").strip()
            if not text:
                return

            # ── Detailed log karo ──
            logger.info(f"═══ LOG CHANNEL MSG RECEIVED ═══")
            logger.info(f"Chat: {chat_id} | Len: {len(text)}")
            logger.info(f"Text preview: {text[:200]}")
            logger.info(f"═══════════════════════════════")

            # ── Message type detect ──
            text_upper = text.upper()
            has_verify   = '#VERIFYCOMPLETE' in text_upper or 'VERIFYCOMPLETE' in text_upper
            has_filesent = '#FILESENT' in text_upper or 'FILESENT' in text_upper
            has_newuser  = '#NEWUSER' in text_upper
            has_vshort   = '#VERIFYSHORTLINK' in text_upper or 'VERIFYSHORTLINK' in text_upper
            has_slv      = 'SHORTLINK VERIFIED' in text_upper
            # #ShortlinkShown = sirf shortlink MILI hai, puri NAHI hui — IGNORE karo
            has_shortlink_shown = '#SHORTLINKSHOWN' in text_upper

            logger.info(f"Detect: VerifyComplete={has_verify} FileSent={has_filesent} NewUser={has_newuser} VerifyShort={has_vshort} ShortlinkShown(ignored)={has_shortlink_shown}")

            # ── Ignore list — koi action nahi ──
            if has_newuser or has_shortlink_shown:
                uid, name = self._parse_user_id_and_name(text)
                logger.info(f"IGNORED: #NewUser or #ShortlinkShown — ID={uid} — NO ACTION")
                return

            # ── Verify messages — SIRF in pe activate karo ──
            if has_verify or has_filesent or has_vshort or has_slv:
                uid, name = self._parse_user_id_and_name(text)
                logger.info(f"VERIFY MSG parsed: uid={uid} name={name}")

                if not uid:
                    logger.warning(f"⚠️ Could not parse user_id from:\n{text}")
                    return

                msg_type = (
                    'VerifyComplete'  if has_verify else
                    'FileSent'        if has_filesent else
                    'Verifyshortlink' if has_vshort else
                    'ShortlinkVerified'
                )
                logger.info(f"✅ Processing: type={msg_type} uid={uid} name={name}")
                await self._activate_and_notify(uid, name, context)

            else:
                logger.info(f"ℹ️ No action needed: {text[:60]}")

        except Exception as e:
            logger.error(f"handle_log_channel_message ERROR: {e}", exc_info=True)

    # ══════════════════════════════════════════════════════════════
    # USER ID + NAME PARSER — All formats
    # ══════════════════════════════════════════════════════════════

    def _parse_user_id_and_name(self, text: str):
        """
        Log channel message se user_id aur name extract karo.

        Supported formats:
          • "ID - 1234567890"           (ASCII normal)
          • "ɪᴅ - 1234567890"           (Unicode small caps)
          • "ID: 1234567890"            (colon format)
          • "As SomeName (1234567890)"  (#FileSent format)
          • "👤 SomeName (1234567890)"  (emoji format)
          • Fallback: any 7-15 digit number in text

        Returns (user_id: int | None, name: str)
        """
        user_id = None
        name = "User"

        lines = text.split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # ── Method 0: "👤 12345 | Name" format (#ShortlinkShown) ──
            if '👤' in line and '|' in line:
                # Format: "👤 677930179 | Smile :)"
                m0 = re.search(r'👤\s*(\d{5,15})\s*\|\s*(.+)', line)
                if m0:
                    try:
                        user_id = int(m0.group(1))
                        name_part = m0.group(2).strip()
                        if name_part:
                            name = name_part[:50]
                        logger.debug(f"ID parsed (👤|pipe format): {user_id} name={name}")
                    except:
                        pass

            # ── Method 1: Normal "ID - 12345" or "ID: 12345" ──
            m = re.match(r'^ID\s*[-:]\s*(\d{5,15})', line, re.IGNORECASE)
            if m:
                try:
                    user_id = int(m.group(1))
                    logger.debug(f"ID parsed (normal): {user_id} from '{line}'")
                except:
                    pass

            # ── Method 2: Unicode small caps "ɪᴅ - 12345" ──
            # ɪ = U+026A, ᴅ = U+1D05 (both look like ID)
            if not user_id:
                # Normalize Unicode to ASCII-like
                normalized = line.replace('ɪ', 'I').replace('ᴅ', 'D').replace('ɴ', 'N')
                m2 = re.match(r'^ID\s*[-:–—]\s*(\d{5,15})', normalized, re.IGNORECASE)
                if m2:
                    try:
                        user_id = int(m2.group(1))
                        logger.debug(f"ID parsed (unicode norm): {user_id} from '{line}'")
                    except:
                        pass

            # ── Method 3: "As SomeName (12345)" — #FileSent format ──
            if not user_id:
                m3 = re.search(r'\((\d{5,15})\)', line)
                if m3:
                    try:
                        candidate = int(m3.group(1))
                        if candidate > 10000:  # valid Telegram ID range
                            user_id = candidate
                            # Extract name: everything before "("
                            name_part = re.sub(r'\(.*\)', '', line)
                            # Remove "As " prefix if present
                            name_part = re.sub(r'^As\s+', '', name_part.strip())
                            # Remove emoji prefixes
                            name_part = re.sub(r'^[👤📤✅#\s]+', '', name_part).strip()
                            if name_part:
                                name = name_part[:50]
                            logger.debug(f"ID parsed (bracket): {user_id} from '{line}'")
                    except:
                        pass

            # ── Name parsing: "Nᴀᴍᴇ - SomeName" or "Name - SomeName" ──
            norm_line = line.replace('ᴀ', 'A').replace('ᴍ', 'M').replace('ᴇ', 'E').replace('ɴ', 'N')
            nm = re.match(r'^NAME\s*[-:–—]\s*(.+)', norm_line, re.IGNORECASE)
            if nm:
                candidate_name = nm.group(1).strip()
                if candidate_name and not re.search(r'^\d+$', candidate_name):
                    name = candidate_name[:50]

        # ── Fallback: any standalone 7-15 digit number ──
        if not user_id:
            # Find all 7-15 digit numbers not surrounded by more digits
            candidates = re.findall(r'(?<!\d)(\d{7,15})(?!\d)', text)
            for c in candidates:
                try:
                    n = int(c)
                    # Basic Telegram user ID sanity check (not year/time like 2023, 1503 etc)
                    if n > 1_000_000:
                        user_id = n
                        logger.debug(f"ID parsed (fallback): {user_id}")
                        break
                except:
                    pass

        logger.info(f"_parse_user_id_and_name → uid={user_id} name={name}")
        return user_id, name

    # ══════════════════════════════════════════════════════════════
    # ACTIVATE REFERRAL + NOTIFY
    # ══════════════════════════════════════════════════════════════

    async def _activate_and_notify(self, user_id: int, name: str, context):
        """
        Referral activate karo ya daily search record karo.
        Dono cases mein relevant users ko notify karo.
        """
        # 1. Check user exists in DB
        user = self.db.get_user(user_id)
        if not user:
            logger.warning(f"User {user_id} DB mein nahi — bot se /start nahi kiya hoga")
            return

        # 2. Referral activate karne ki koshish karo
        result = self.db.activate_referral_by_log_channel(user_id)
        logger.info(f"activate_referral_by_log_channel({user_id}) → {result}")

        if result and result.get('activated'):
            # ── First time activation ──
            referrer_id   = result.get('referrer_id')
            referrer_name = result.get('referrer_name', 'Unknown')

            logger.info(f"✅ REFERRAL ACTIVATED: user={user_id} ({name}) → referrer={referrer_id}")

            # Referrer ko khushkhabri (improved message)
            if referrer_id:
                try:
                    ref_pts = int(float(self.config.REFERRAL_BONUS) * 100)
                    daily_pts = int(float(self.config.DAILY_REFERRAL_EARNING) * 100)
                    await context.bot.send_message(
                        chat_id=referrer_id,
                        text=(
                            f"🎉🎉 REFERRAL ACTIVE HO GAYA! 🎉🎉\n\n"
                            f"👤 {name} ne shortlink complete kar li!\n\n"
                            f"━━━ AAPKO MILA ━━━\n"
                            f"🎟 +3 Passes — abhi account mein!\n"
                            f"💰 +{ref_pts} pts — abhi balance mein!\n\n"
                            f"━━━ DAILY INCOME ━━━\n"
                            f"📅 Ab jab bhi {name} movie search karega:\n"
                            f"💵 +{daily_pts} pts ROZI aapko milta rahega!\n\n"
                            f"🚀 Aur refer karo — aur kamao!\n"
                            f"💡 App kholo aur balance check karo!"
                        )
                    )
                    logger.info(f"Referrer {referrer_id} notified of activation")
                except Exception as e:
                    logger.error(f"Notify referrer {referrer_id} FAILED: {e}")

            # Referred user ko bhi batao (improved with movie group button)
            try:
                movie_link = getattr(self.config, 'MOVIE_GROUP_LINK', 'https://t.me/all_movies_webseries_is_here')
                keyboard = [
                    [InlineKeyboardButton(
                        "💰 Earning Shuru Karo!",
                        web_app=WebAppInfo(url=f"{self.config.WEBAPP_URL}/?user_id={user_id}")
                    )],
                    [InlineKeyboardButton("🎬 Movie Group Join Karo", url=movie_link)]
                ]
                await context.bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"🥳 CONGRATULATIONS {name.upper()}!\n\n"
                        f"✅ Aap verify ho gaye!\n"
                        f"💰 Earning SHURU!\n\n"
                        f"━━━ ROZ KYA KARNA HAI? ━━━\n\n"
                        f"🎬 Movie Group pe movie search karo\n"
                        f"   → +30 pts TURANT!\n\n"
                        f"🎁 Daily Bonus claim karo\n"
                        f"   → FREE pts roz!\n\n"
                        f"📺 Ads dekho\n"
                        f"   → +10 pts har ad!\n\n"
                        f"🎯 Missions complete karo\n"
                        f"   → +100 se +500 pts!\n\n"
                        f"👥 Dosto ko refer karo\n"
                        f"   → Inki kamai = Aapki kamai!\n\n"
                        f"🔥 Abhi App kholo — paise wait kar rahe hain!"
                    ),
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                logger.info(f"User {user_id} notified of verification")
            except Forbidden:
                logger.warning(f"User {user_id} ne bot block kar diya — marking blocked")
                try:
                    self.db.mark_user_blocked(user_id)
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"Notify user {user_id} FAILED: {e}")

        else:
            # ── Already active — daily search record karo ──
            reason = result.get('reason', 'unknown') if result else 'no_result'
            logger.info(f"Referral already active for {user_id} (reason={reason}) — recording daily search")

            search = self.db.record_daily_search(user_id)
            logger.info(f"record_daily_search({user_id}) → {search}")

            # Movie search mission progress update (m_search5)
            try:
                self.db._update_single_mission_progress(user_id, 'm_search5', 1)
                logger.info(f"m_search5 mission updated for user {user_id}")
            except Exception as me:
                logger.error(f"Mission update error: {me}")

            if search.get('success'):
                referrer_id = search.get('referrer_id')
                earning     = search.get('earning', self.config.DAILY_REFERRAL_EARNING)
                logger.info(f"✅ Daily search credited: user={user_id} ref={referrer_id} +₹{earning}")

                if referrer_id:
                    try:
                        await context.bot.send_message(
                            chat_id=referrer_id,
                            text=(
                                f"💵 Daily Kamai Aayi!\n\n"
                                f"👤 {name} ne aaj movie search ki!\n"
                                f"💰 +{int(float(earning)*100)} pts aapke account mein!\n\n"
                                f"📈 Jitne zyada active refers — utni zyada ROZI!\n"
                                f"💡 Aur dosto ko refer karo = aur kamai!"
                            )
                        )
                    except Exception as e:
                        logger.error(f"Daily earning notify referrer {referrer_id}: {e}")

            elif search.get('reason') == 'already_credited_today':
                logger.info(f"Already credited today for {user_id}")
            else:
                logger.info(f"No active referral for {user_id}: {search.get('reason', '')}")

    # ══════════════════════════════════════════════════════════════
    # OTHER COMMANDS
    # ══════════════════════════════════════════════════════════════

    async def open_app(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        keyboard = [[InlineKeyboardButton(
            "🤑 App Kholo — Paise Kamao!",
            web_app=WebAppInfo(url=f"{self.config.WEBAPP_URL}/?user_id={user.id}")
        )]]
        await update.message.reply_text(
            f"💰 {user.first_name}, aaj ka bonus abhi baaki hai!\n"
            f"⬇️ App kholo aur ABHI kamao!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def check_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user_id = update.effective_user.id
            user = self.db.get_user(user_id)
            if user:
                daily_potential = user.get('active_refs', 0) * self.config.DAILY_REFERRAL_EARNING
                bal_pts = int(user.get('balance', 0) * 100)
                total_pts = int(user.get('total_earned', 0) * 100)
                today_pts = int(user.get('today_earned', 0) * 100)
                daily_pts = int(float(daily_potential) * 100)
                text = (
                    f"💰 Aapka Balance\n\n"
                    f"🏦 Available: {bal_pts} pts\n"
                    f"📊 Total Kamaya: {total_pts} pts\n"
                    f"📅 Aaj Kamaya: {today_pts} pts\n\n"
                    f"━━━ REFERRALS ━━━\n"
                    f"✅ Active: {user.get('active_refs', 0)} log\n"
                    f"⏳ Pending: {user.get('pending_refs', 0)} log\n"
                    f"💵 Roz Milta Hai: {daily_pts} pts\n\n"
                    f"🏆 Level: {self.config.get_tier_name(user.get('tier', 1))}\n\n"
                    f"👉 Aur refer karo = aur kamao!"
                )
            else:
                text = "❌ Pehle /start karo!"
            await update.message.reply_text(text)
        except Exception as e:
            logger.error(f"Balance: {e}")

    async def show_referrals(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user_id = update.effective_user.id
            user = self.db.get_user(user_id)
            if user:
                ref_link = f"https://t.me/{self.config.BOT_USERNAME}?start=ref_{user_id}"
                daily_pts = int(user.get('active_refs', 0) * float(self.config.DAILY_REFERRAL_EARNING) * 100)
                ref_pts = int(float(self.config.REFERRAL_BONUS) * 100)
                text = (
                    f"👥 Aapke Referrals\n\n"
                    f"✅ Active: {user.get('active_refs', 0)} log\n"
                    f"⏳ Pending: {user.get('pending_refs', 0)} log\n"
                    f"📊 Total: {user.get('total_refs', 0)} log\n\n"
                    f"💵 Roz Mil Raha Hai: {daily_pts} pts\n\n"
                    f"━━━ EK REFER SE MILTA HAI ━━━\n"
                    f"🎟 3 Passes + {ref_pts} pts TURANT!\n"
                    f"📅 Roz 30 pts — jab tak woh search kare!\n\n"
                    f"🔗 Aapka Link:\n{ref_link}\n\n"
                    f"📤 Copy karo aur ABHI share karo!"
                )
            else:
                text = "❌ Pehle /start karo!"
            await update.message.reply_text(text)
        except Exception as e:
            logger.error(f"Referrals: {e}")

    async def withdraw_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user_id = update.effective_user.id
            user = self.db.get_user(user_id)
            if not user:
                await update.message.reply_text("❌ Pehle /start karo!")
                return
            balance = user.get('balance', 0)
            bal_pts = int(balance * 100)
            min_pts = int(self.config.MIN_WITHDRAWAL * 100)
            if balance < self.config.MIN_WITHDRAWAL:
                need_pts = min_pts - bal_pts
                await update.message.reply_text(
                    f"😅 Balance Thoda Kam Hai!\n\n"
                    f"💰 Aapke paas: {bal_pts} pts\n"
                    f"🎯 Minimum chahiye: {min_pts} pts\n"
                    f"📈 Aur chahiye: sirf {need_pts} pts!\n\n"
                    f"━━━ JALDI KAMAO ━━━\n"
                    f"🎬 Movie search karo → +30 pts\n"
                    f"👥 1 refer karo → +{int(float(self.config.REFERRAL_BONUS)*100)} pts\n"
                    f"🎯 Missions karo → +100 se +500 pts\n\n"
                    f"🔥 Bas thoda aur — phir withdrawal!"
                )
                return
            keyboard = [[InlineKeyboardButton(
                "💸 ABHI WITHDRAW KARO!",
                web_app=WebAppInfo(url=f"{self.config.WEBAPP_URL}/?user_id={user_id}&page=withdraw")
            )]]
            await update.message.reply_text(
                f"🎉 Withdrawal Ke Liye Ready!\n\n"
                f"💰 Aapka Balance: {bal_pts} pts\n\n"
                f"⬇️ Neeche click karo aur paise NIKALO!",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Withdraw cmd: {e}")

    async def help_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            text = (
                "❓ FilmyFund — Help\n\n"
                "━━━ COMMANDS ━━━\n"
                "/start — Bot shuru karo\n"
                "/app — App kholo\n"
                "/balance — Balance dekho\n"
                "/referrals — Referrals dekho\n"
                "/withdraw — Paise nikalo\n"
                "/help — Ye message\n\n"
                "━━━ PAISE KAISE KAMAYEIN? ━━━\n"
                "1️⃣ Apna referral link share karo\n"
                "2️⃣ Dost join kare\n"
                "3️⃣ Woh Movie Group pe movie search kare\n"
                "4️⃣ Movie bot ka link khola → 10 sec ruka\n"
                "5️⃣ DONE! Referral active — roz paise aate rahenge!\n\n"
                "━━━ RULES ━━━\n"
                "⚠️ Sirf shortlink ke baad active hoga\n"
                "⚠️ 1 user = 1 search per day\n"
                "⚠️ Fake kaam = account band\n\n"
                f"🆘 Support: {self.config.SUPPORT_USERNAME}"
            )
            await update.message.reply_text(text)
        except Exception as e:
            logger.error(f"Help: {e}")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user = update.effective_user
            chat = update.effective_chat
            message = update.message
            if not user or not message:
                return
            message_text = message.text or ""
            if chat.type == 'private' and message_text.lower() in ['hi', 'hello', 'hey', 'hii', 'helo']:
                keyboard = [[InlineKeyboardButton(
                    "🤑 App Kholo — Paise Kamao!",
                    web_app=WebAppInfo(url=f"{self.config.WEBAPP_URL}/?user_id={user.id}")
                )]]
                await message.reply_text(
                    f"👋 {user.first_name}!\n\n"
                    f"💰 FilmyFund pe aaj bhi paise wait kar rahe hain!\n"
                    f"⬇️ App kholo aur kamao!",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
        except Exception as e:
            logger.error(f"handle_message: {e}")

    async def handle_webapp_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            web_app_data = update.effective_message.web_app_data
            if not web_app_data:
                return
            data = json.loads(web_app_data.data)
            action = data.get('action')
            response = {'success': False, 'message': 'Unknown action'}
            if action == 'support':
                response = await self.process_support_message(data, context)
            await update.effective_message.reply_text(text=json.dumps(response))
        except Exception as e:
            logger.error(f"WebApp data: {e}")

    async def process_support_message(self, data, context=None):
        try:
            user_id = data.get('user_id')
            message = data.get('message')
            if not user_id or not message:
                return {'success': False, 'message': 'Missing data'}
            msg_id = self.db.add_support_message(user_id, message)
            if msg_id:
                if context:
                    for admin_id in self.config.ADMIN_IDS:
                        try:
                            kb = [[InlineKeyboardButton("📩 VIEW", callback_data=f"view_support_{msg_id}")]]
                            await context.bot.send_message(
                                chat_id=admin_id,
                                text=f"📩 New Support\n\nUser: {user_id}\nMsg: {message[:100]}",
                                reply_markup=InlineKeyboardMarkup(kb)
                            )
                        except:
                            pass
                return {'success': True, 'message': 'Sent!'}
            return {'success': False, 'message': 'Failed'}
        except Exception as e:
            logger.error(f"Support message: {e}")
            return {'success': False, 'message': str(e)}

    async def send_daily_reminders(self, context):
        try:
            pending_users = self.db.get_pending_reminders()
            if not pending_users:
                return
            sent = 0
            webapp_url = self.config.WEBAPP_URL
            for u in pending_users:
                uid = u['user_id']
                name = u.get('first_name', 'User')
                try:
                    kb = [[InlineKeyboardButton("🤑 App Kholo — Abhi Kamao!",
                        web_app=WebAppInfo(url=f"{webapp_url}/?user_id={uid}"))]]
                    await context.bot.send_message(
                        chat_id=uid,
                        text=(
                            f"🔔 {name}, Aaj Ka Kaam Baaki Hai!\n\n"
                            f"😱 Aaj ke FREE points abhi bhi available hain!\n\n"
                            f"✅ Daily Bonus claim karo → FREE pts!\n"
                            f"🎬 Movie search karo → +30 pts!\n"
                            f"📺 Ads dekho → +10 pts har ad!\n"
                            f"🎯 Missions karo → +500 pts tak!\n\n"
                            f"⚠️ Streak toot gayi toh bonus band!\n\n"
                            f"⬇️ ABHI App kholo!"
                        ),
                        reply_markup=InlineKeyboardMarkup(kb)
                    )
                    self.db.mark_user_reminded(uid)
                    sent += 1
                    import asyncio
                    await asyncio.sleep(0.05)
                except Exception as e:
                    logger.error(f"Reminder {uid}: {e}")
            logger.info(f"Reminders sent: {sent}")
        except Exception as e:
            logger.error(f"send_daily_reminders: {e}")
