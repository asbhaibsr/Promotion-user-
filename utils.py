# ===== utils.py (UPDATED) =====

import logging
import random
import string
from datetime import datetime, timedelta
import re

logger = logging.getLogger(__name__)

class Utils:
    def __init__(self, config, db):
        self.config = config
        self.db = db
        logger.info("✅ Utils initialized")

    def validate_upi_id(self, upi_id):
        try:
            if not upi_id or not isinstance(upi_id, str):
                return False
            pattern = r'^[a-zA-Z0-9._-]+@[a-zA-Z0-9]+$'
            return bool(re.match(pattern, upi_id.strip()))
        except Exception as e:
            logger.error(f"Error validating UPI: {e}")
            return False

    def validate_bank_details(self, details):
        try:
            if not details:
                return False
            parts = details.split('|')
            return len(parts) >= 3 and all(parts)
        except Exception as e:
            logger.error(f"Error validating bank details: {e}")
            return False

    def format_number(self, num):
        try:
            num = float(num)
            return "{:,.2f}".format(num)
        except:
            return str(num)

    def time_ago(self, timestamp):
        if not timestamp:
            return "Never"
        try:
            if isinstance(timestamp, str):
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            else:
                dt = timestamp
            now = datetime.now()
            diff = now - dt
            if diff.days > 0:
                return f"{diff.days}d ago"
            elif diff.seconds > 3600:
                return f"{diff.seconds // 3600}h ago"
            elif diff.seconds > 60:
                return f"{diff.seconds // 60}min ago"
            else:
                return "just now"
        except Exception as e:
            logger.error(f"Error parsing time: {e}")
            return "recently"

    def calculate_tier_progress(self, user):
        try:
            if not user:
                return 0, "0/0"
            current_tier = user.get('tier', 1)
            active_refs = user.get('active_refs', 0)
            max_tier = max(self.config.TIERS.keys())
            if current_tier >= max_tier:
                return 100, "MAX TIER"
            next_tier = current_tier + 1
            required = self.config.TIERS[next_tier]['required_refs']
            if required == 0:
                return 100, "MAX"
            progress = min(100, (active_refs / required) * 100)
            return progress, f"{active_refs}/{required}"
        except Exception as e:
            logger.error(f"Error calculating tier progress: {e}")
            return 0, "0/0"

    def get_daily_bonus_amount(self, streak):
        """
        UPDATED: 0.05 per streak day, max 0.30
        (was 0.02/max 0.15 before)
        """
        try:
            base = self.config.DAILY_BONUS  # 0.05
            bonus = min(streak * 0.05, 0.30)
            return base + bonus
        except Exception as e:
            logger.error(f"Error calculating bonus: {e}")
            return 0.05

    def is_valid_amount(self, amount):
        try:
            amount = float(amount)
            return amount > 0 and amount <= 1000000
        except:
            return False

    def sanitize_text(self, text):
        if not text:
            return ""
        try:
            text = str(text)
            chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
            for char in chars:
                text = text.replace(char, f'\\{char}')
            return text
        except Exception as e:
            logger.error(f"Error sanitizing text: {e}")
            return str(text)

    def get_tier_emoji(self, tier):
        try:
            emojis = {1: "🥉", 2: "🥈", 3: "🥇", 4: "👑", 5: "💎"}
            return emojis.get(int(tier), "🎯")
        except:
            return "🎯"

    def format_currency(self, amount):
        try:
            amount = float(amount)
            return f"₹{amount:.2f}"
        except:
            return "₹0.00"

    def get_referral_link(self, user_id):
        try:
            return f"https://t.me/{self.config.BOT_USERNAME}?start=ref_{user_id}"
        except:
            return f"https://t.me/yourbot?start=ref_{user_id}"

    def validate_withdrawal_method(self, method, details):
        try:
            if method == "UPI":
                return self.validate_upi_id(details)
            elif method == "Bank":
                return self.validate_bank_details(details)
            else:
                return False
        except Exception as e:
            logger.error(f"Error validating withdrawal: {e}")
            return False

    def get_user_rank(self, user_id):
        try:
            users = list(self.db.users.find(
                {'suspicious_activity': False},
                {'user_id': 1, 'active_refs': 1}
            ).sort('active_refs', -1))
            for i, user in enumerate(users):
                if user['user_id'] == int(user_id):
                    return i + 1
            return len(users) + 1
        except Exception as e:
            logger.error(f"Error getting user rank: {e}")
            return 0

    def parse_command(self, text):
        try:
            if not text or not text.startswith('/'):
                return None, []
            parts = text.strip().split()
            command = parts[0].lower()
            args = parts[1:] if len(parts) > 1 else []
            return command, args
        except Exception as e:
            logger.error(f"Error parsing command: {e}")
            return None, []

    def is_suspicious_activity(self, user_id):
        try:
            recent = list(self.db.search_logs.find(
                {'user_id': int(user_id)}
            ).sort('timestamp', -1).limit(10))
            if len(recent) < 5:
                return False
            timestamps = [datetime.fromisoformat(r['timestamp']) for r in recent]
            time_diffs = [(timestamps[i] - timestamps[i+1]).total_seconds()
                         for i in range(len(timestamps)-1)]
            avg_time = sum(time_diffs) / len(time_diffs)
            if avg_time < 30:
                logger.warning(f"Suspicious activity: User {user_id} searching too fast")
                return True
            return False
        except Exception as e:
            logger.error(f"Error checking suspicious activity: {e}")
            return False

    def calculate_referral_earnings(self, user_id, days=30):
        try:
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()
            pipeline = [
                {'$match': {
                    'referrer_id': int(user_id),
                    'last_earning_date': {'$gte': cutoff}
                }},
                {'$group': {'_id': None, 'total': {'$sum': '$earnings'}}}
            ]
            result = list(self.db.referrals.aggregate(pipeline))
            return result[0].get('total', 0) if result else 0
        except Exception as e:
            logger.error(f"Error calculating referral earnings: {e}")
            return 0
