# database.py - MongoDB डेटाबेस

from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError
from datetime import datetime, timedelta
import logging
from config import Config
import random

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.client = MongoClient(Config.MONGO_URI)
        self.db = self.client.movie_bot_advanced
        
        # कलेक्शन
        self.users = self.db.users
        self.referrals = self.db.referrals
        self.withdrawals = self.db.withdrawals
        self.transactions = self.db.transactions
        self.channel_joins = self.db.channel_joins
        self.spins = self.db.spins
        self.missions = self.db.missions
        self.group_activity = self.db.group_activity
        self.monthly_leaderboard = self.db.monthly_leaderboard
        self.reports = self.db.reports
        
        self._create_indexes()
        logger.info("✅ Advanced Database Connected")
    
    def _create_indexes(self):
        self.users.create_index("user_id", unique=True)
        self.users.create_index([("balance", DESCENDING)])
        self.users.create_index([("monthly_referrals", DESCENDING)])
        self.referrals.create_index([("referrer", ASCENDING), ("user", ASCENDING)], unique=True)
        self.referrals.create_index("user", unique=True)
        self.group_activity.create_index([("user_id", ASCENDING), ("date", ASCENDING)], unique=True)
        logger.info("✅ Indexes Created")
    
    # ========== USER FUNCTIONS ==========
    
    def get_user(self, user_id):
        return self.users.find_one({"user_id": user_id})
    
    def create_user(self, user_id, username, full_name, photo_url=None, referrer=None):
        user = {
            "user_id": user_id,
            "username": username,
            "full_name": full_name,
            "photo_url": photo_url,
            "balance": 0.0,
            "total_earned": 0.0,
            "spins": Config.INITIAL_SPINS,
            "tier": 1,
            "total_referrals": 0,
            "active_referrals": 0,
            "monthly_referrals": 0,
            "joined": datetime.now(),
            "last_active": datetime.now(),
            "last_daily": None,
            "daily_streak": 0,
            "last_spin": None,
            "payment_method": None,
            "payment_details": None,
            "welcome_bonus": False,
            "channel_joined": False,
            "is_blocked": False,
            "total_searches": 0,
            "last_search_date": None,
            "search_streak": 0
        }
        
        try:
            self.users.insert_one(user)
            
            if referrer and referrer != user_id:
                ref_user = self.get_user(referrer)
                if ref_user and not ref_user.get("is_blocked", False):
                    self.referrals.insert_one({
                        "referrer": referrer,
                        "user": user_id,
                        "joined": datetime.now(),
                        "active": False,
                        "first_search": None,
                        "last_active": None
                    })
            
            return user
            
        except DuplicateKeyError:
            return self.get_user(user_id)
    
    def update_user(self, user_id, updates):
        updates["last_active"] = datetime.now()
        return self.users.update_one(
            {"user_id": user_id},
            {"$set": updates}
        )
    
    def update_balance(self, user_id, amount, transaction_type=None, details=None):
        result = self.users.update_one(
            {"user_id": user_id},
            {"$inc": {"balance": amount, "total_earned": max(0, amount)}}
        )
        
        if result.modified_count > 0 and transaction_type:
            self.transactions.insert_one({
                "user_id": user_id,
                "amount": amount,
                "type": transaction_type,
                "details": details,
                "timestamp": datetime.now()
            })
        
        user = self.get_user(user_id)
        return user["balance"] if user else 0
    
    def get_user_stats(self, user_id):
        user = self.get_user(user_id)
        if not user:
            return None
        
        ref_count = self.referrals.count_documents({"referrer": user_id})
        active_refs = self.referrals.count_documents({"referrer": user_id, "active": True})
        pending_refs = ref_count - active_refs
        
        tier = self._get_tier_from_refs(active_refs)
        
        return {
            "user_id": user_id,
            "full_name": user.get("full_name", "User"),
            "username": user.get("username", ""),
            "photo_url": user.get("photo_url"),
            "balance": round(user.get("balance", 0), 2),
            "total_earned": round(user.get("total_earned", 0), 2),
            "spins": user.get("spins", 0),
            "tier": tier,
            "tier_name": Config.TIERS[tier]["name"],
            "tier_rate": Config.TIERS[tier]["rate"],
            "total_refs": ref_count,
            "active_refs": active_refs,
            "pending_refs": pending_refs,
            "monthly_refs": user.get("monthly_referrals", 0),
            "daily_streak": user.get("daily_streak", 0),
            "channel_joined": user.get("channel_joined", False),
            "total_searches": user.get("total_searches", 0),
            "search_streak": user.get("search_streak", 0),
            "referral_link": f"https://t.me/LinkProviderRobot?start=ref_{user_id}"
        }
    
    def _get_tier_from_refs(self, refs):
        for tier, config in sorted(Config.TIERS.items(), key=lambda x: x[1]["min_refs"], reverse=True):
            if refs >= config["min_refs"]:
                return tier
        return 1
    
    # ========== REFERRAL SYSTEM ==========
    
    def track_search(self, user_id):
        """Track user search in group - activates referral"""
        user = self.get_user(user_id)
        if not user:
            return None
        
        today = datetime.now().date()
        last_search = user.get("last_search_date")
        
        # Update search streak
        if last_search and last_search.date() == today - timedelta(days=1):
            streak = user.get("search_streak", 0) + 1
        else:
            streak = 1
        
        self.users.update_one(
            {"user_id": user_id},
            {
                "$inc": {"total_searches": 1},
                "$set": {
                    "last_search_date": datetime.now(),
                    "search_streak": streak
                }
            }
        )
        
        # Record daily activity
        today_str = today.isoformat()
        try:
            self.group_activity.insert_one({
                "user_id": user_id,
                "date": today_str,
                "timestamp": datetime.now()
            })
        except DuplicateKeyError:
            pass  # Already recorded today
        
        # Activate referral if not active
        ref = self.referrals.find_one({"user": user_id})
        if ref and not ref.get("active"):
            self.referrals.update_one(
                {"user": user_id},
                {"$set": {"active": True, "first_search": datetime.now(), "last_active": datetime.now()}}
            )
            
            # Update referrer stats
            self.users.update_one(
                {"user_id": ref["referrer"]},
                {
                    "$inc": {
                        "active_referrals": 1,
                        "monthly_referrals": 1,
                        "spins": Config.REFERRAL_BONUS
                    }
                }
            )
            
            return ref["referrer"]
        
        # Update last active for existing referral
        if ref:
            self.referrals.update_one(
                {"user": user_id},
                {"$set": {"last_active": datetime.now()}}
            )
        
        return None
    
    def process_daily_referral_payment(self, user_id):
        """Pay referrer daily (once per day)"""
        ref = self.referrals.find_one({"user": user_id, "active": True})
        if not ref:
            return None
        
        today = datetime.now().date()
        
        # Check if already paid today
        if ref.get("last_paid") and ref["last_paid"].date() == today:
            return None
        
        # Check if user searched today
        today_activity = self.group_activity.find_one({
            "user_id": user_id,
            "date": today.isoformat()
        })
        
        if not today_activity:
            return None  # No search today, no payment
        
        referrer = self.get_user(ref["referrer"])
        if not referrer or referrer.get("is_blocked", False):
            return None
        
        tier = referrer.get("tier", 1)
        rate = Config.TIERS[tier]["rate"]
        
        # Pay referrer
        self.update_balance(
            ref["referrer"],
            rate,
            "referral_daily",
            f"Daily earnings from referral {user_id}"
        )
        
        self.referrals.update_one(
            {"user": user_id},
            {"$set": {"last_paid": datetime.now()}}
        )
        
        return rate
    
    # ========== DAILY BONUS ==========
    
    def claim_daily(self, user_id):
        user = self.get_user(user_id)
        if not user:
            return None
        
        today = datetime.now().date()
        last = user.get("last_daily")
        
        if last and last.date() == today:
            return None
        
        if last and last.date() == today - timedelta(days=1):
            streak = user.get("daily_streak", 0) + 1
        else:
            streak = 1
        
        bonus = Config.DAILY_BONUS_BASE + (streak * Config.DAILY_BONUS_INCREMENT)
        
        self.users.update_one(
            {"user_id": user_id},
            {
                "$set": {"last_daily": datetime.now(), "daily_streak": streak},
                "$inc": {"balance": bonus, "total_earned": bonus}
            }
        )
        
        self.transactions.insert_one({
            "user_id": user_id,
            "amount": bonus,
            "type": "daily_bonus",
            "details": f"Daily Bonus (Streak: {streak})",
            "timestamp": datetime.now()
        })
        
        # Update mission
        self.update_mission(user_id, "daily_bonus")
        
        return {
            "bonus": round(bonus, 2),
            "streak": streak,
            "balance": round(user["balance"] + bonus, 2)
        }
    
    # ========== SPIN WHEEL ==========
    
    def can_spin(self, user_id):
        user = self.get_user(user_id)
        if not user:
            return False, "User not found"
        
        if user["spins"] <= 0:
            return False, "No spins left"
        
        last_spin = user.get("last_spin")
        if last_spin and Config.SPIN_COOLDOWN:
            if datetime.now() - last_spin < Config.SPIN_COOLDOWN:
                remaining = Config.SPIN_COOLDOWN - (datetime.now() - last_spin)
                minutes = int(remaining.total_seconds() / 60)
                return False, f"Next spin in {minutes} minutes"
        
        return True, "OK"
    
    def spin_wheel(self, user_id):
        can, msg = self.can_spin(user_id)
        if not can:
            return {"error": msg}
        
        prize_data = random.choices(Config.SPIN_PRIZES, weights=Config.SPIN_WEIGHTS)[0]
        prize = prize_data["value"]
        
        self.users.update_one(
            {"user_id": user_id},
            {
                "$inc": {"spins": -1, "balance": prize, "total_earned": prize},
                "$set": {"last_spin": datetime.now()}
            }
        )
        
        self.spins.insert_one({
            "user_id": user_id,
            "prize": prize,
            "prize_name": prize_data["name"],
            "timestamp": datetime.now()
        })
        
        if prize > 0:
            self.transactions.insert_one({
                "user_id": user_id,
                "amount": prize,
                "type": "spin",
                "details": f"Spin Won: ₹{prize} - {prize_data['name']}",
                "timestamp": datetime.now()
            })
        
        return {
            "prize": prize,
            "prize_name": prize_data["name"],
            "prize_emoji": prize_data["emoji"],
            "color": prize_data["color"],
            "remaining_spins": user["spins"] - 1
        }
    
    # ========== CHANNEL JOIN ==========
    
    def mark_channel_joined(self, user_id, channel):
        if self.channel_joins.find_one({"user_id": user_id, "channel": channel}):
            return False
        
        self.channel_joins.insert_one({
            "user_id": user_id,
            "channel": channel,
            "joined_at": datetime.now()
        })
        
        self.update_balance(user_id, Config.CHANNEL_BONUS, "channel_bonus", f"Channel {channel} join bonus")
        
        self.users.update_one(
            {"user_id": user_id},
            {"$set": {"channel_joined": True}}
        )
        
        return True
    
    # ========== WITHDRAWAL ==========
    
    def create_withdrawal(self, user_id, amount, method, details):
        user = self.get_user(user_id)
        if not user:
            return False, "User not found"
        
        if user["balance"] < amount:
            return False, "Insufficient balance"
        
        if amount < Config.MIN_WITHDRAWAL:
            return False, f"Minimum withdrawal ₹{Config.MIN_WITHDRAWAL}"
        
        withdrawal = {
            "user_id": user_id,
            "amount": amount,
            "method": method,
            "details": details,
            "status": "pending",
            "requested": datetime.now(),
            "processed": None
        }
        
        self.withdrawals.insert_one(withdrawal)
        
        self.users.update_one(
            {"user_id": user_id},
            {"$inc": {"balance": -amount}}
        )
        
        self.transactions.insert_one({
            "user_id": user_id,
            "amount": -amount,
            "type": "withdrawal",
            "details": f"Withdrawal request ₹{amount}",
            "timestamp": datetime.now()
        })
        
        return True, "Withdrawal request submitted"
    
    # ========== MISSIONS ==========
    
    def update_mission(self, user_id, mission_type):
        today = datetime.now().date().isoformat()
        
        mission = self.missions.find_one({
            "user_id": user_id,
            "type": mission_type,
            "date": today
        })
        
        if not mission:
            mission = {
                "user_id": user_id,
                "type": mission_type,
                "date": today,
                "count": 1,
                "completed": False
            }
            self.missions.insert_one(mission)
        else:
            self.missions.update_one(
                {"_id": mission["_id"]},
                {"$inc": {"count": 1}}
            )
            mission["count"] += 1
        
        config = Config.MISSIONS.get(mission_type)
        if config and mission["count"] >= config["target"] and not mission.get("completed"):
            self.missions.update_one(
                {"_id": mission["_id"]},
                {"$set": {"completed": True}}
            )
            
            self.update_balance(user_id, config["reward"], "mission", f"Mission {mission_type} completed")
            self.users.update_one(
                {"user_id": user_id},
                {"$inc": {"spins": config["spins"]}}
            )
            
            return {
                "completed": True,
                "reward": config["reward"],
                "spins": config["spins"],
                "name": config["name"]
            }
        
        return {"count": mission["count"], "completed": mission.get("completed", False)}
    
    def get_missions(self, user_id):
        today = datetime.now().date().isoformat()
        missions = {}
        
        for mission_type, config in Config.MISSIONS.items():
            mission = self.missions.find_one({
                "user_id": user_id,
                "type": mission_type,
                "date": today
            })
            
            missions[mission_type] = {
                "count": mission["count"] if mission else 0,
                "completed": mission["completed"] if mission else False,
                "target": config["target"],
                "reward": config["reward"],
                "spins": config["spins"],
                "name": config["name"],
                "icon": config["icon"]
            }
        
        return missions
    
    # ========== LEADERBOARD ==========
    
    def get_current_leaderboard(self, limit=10):
        """Get current month's leaderboard with user photos"""
        pipeline = [
            {"$match": {"is_blocked": False, "monthly_referrals": {"$gt": 0}}},
            {"$sort": {"monthly_referrals": -1}},
            {"$limit": limit},
            {"$project": {
                "user_id": 1,
                "full_name": 1,
                "username": 1,
                "photo_url": 1,
                "monthly_referrals": 1,
                "balance": 1,
                "tier": 1,
                "active_referrals": 1
            }}
        ]
        return list(self.users.aggregate(pipeline))
    
    # ========== ADMIN FUNCTIONS ==========
    
    def get_stats(self):
        total_users = self.users.count_documents({})
        active_today = self.group_activity.count_documents({
            "date": datetime.now().date().isoformat()
        })
        
        return {
            "total_users": total_users,
            "active_users": self.users.count_documents({"is_blocked": False}),
            "blocked_users": self.users.count_documents({"is_blocked": True}),
            "active_today": active_today,
            "pending_withdrawals": self.withdrawals.count_documents({"status": "pending"}),
            "total_earned": sum(u.get("total_earned", 0) for u in self.users.find({}, {"total_earned": 1})),
            "total_paid": sum(w.get("amount", 0) for w in self.withdrawals.find({"status": "completed"})),
            "today_users": self.users.count_documents({"joined": {"$gte": datetime.now().replace(hour=0, minute=0, second=0)}})
        }
    
    def get_all_users(self, filter_blocked=False):
        query = {"is_blocked": False} if filter_blocked else {}
        return list(self.users.find(query))
    
    # ========== CLEAR DATA ==========
    
    def clear_user_earnings(self, user_id):
        """Clear only earnings data for a user"""
        self.users.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "balance": 0,
                    "total_earned": 0,
                    "spins": Config.INITIAL_SPINS,
                    "total_referrals": 0,
                    "active_referrals": 0,
                    "monthly_referrals": 0,
                    "daily_streak": 0,
                    "total_searches": 0,
                    "search_streak": 0,
                    "last_daily": None,
                    "last_spin": None
                }
            }
        )
        
        # Clear related collections
        self.transactions.delete_many({"user_id": user_id})
        self.spins.delete_many({"user_id": user_id})
        self.missions.delete_many({"user_id": user_id})
        self.group_activity.delete_many({"user_id": user_id})
        
        return True
    
    def clear_all_user_data(self, user_id):
        """Clear ALL data for a user (full reset)"""
        # Delete user completely
        self.users.delete_one({"user_id": user_id})
        
        # Clear all related collections
        self.referrals.delete_many({"referrer": user_id})
        self.referrals.delete_many({"user": user_id})
        self.transactions.delete_many({"user_id": user_id})
        self.withdrawals.delete_many({"user_id": user_id})
        self.spins.delete_many({"user_id": user_id})
        self.missions.delete_many({"user_id": user_id})
        self.channel_joins.delete_many({"user_id": user_id})
        self.group_activity.delete_many({"user_id": user_id})
        
        return True
    
    # ========== REPORTS ==========
    
    def save_report(self, user_id, issue):
        """Save user report"""
        report = {
            "user_id": user_id,
            "issue": issue,
            "timestamp": datetime.now(),
            "status": "pending"
        }
        self.reports.insert_one(report)
        return report


# Global database instance
db = Database()
