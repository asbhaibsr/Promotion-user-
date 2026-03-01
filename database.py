# database.py - Advanced MongoDB with Caching

from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError
from datetime import datetime, timedelta
import logging
import random
from config import Config
from functools import lru_cache
from bson.objectid import ObjectId

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        try:
            self.client = MongoClient(
                Config.MONGO_URI, 
                serverSelectionTimeoutMS=5000,
                maxPoolSize=50
            )
            self.db = self.client.movie_bot_advanced
            
            # Test connection
            self.client.admin.command('ping')
            logger.info("✅ MongoDB Connected Successfully")
        except Exception as e:
            logger.error(f"❌ MongoDB Connection Failed: {e}")
            raise e
        
        # Collections
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
        self.settings = self.db.settings
        self.notifications = self.db.notifications
        
        self._create_indexes()
        logger.info("✅ Database Ready")
    
    def _create_indexes(self):
        # Users indexes
        self.users.create_index("user_id", unique=True)
        self.users.create_index([("balance", DESCENDING)])
        self.users.create_index([("total_earned", DESCENDING)])
        self.users.create_index([("monthly_referrals", DESCENDING)])
        self.users.create_index("last_active")
        self.users.create_index("joined")
        
        # Referrals indexes
        self.referrals.create_index(
            [("referrer", ASCENDING), ("user", ASCENDING)], 
            unique=True
        )
        self.referrals.create_index("user", unique=True)
        self.referrals.create_index([("referrer", ASCENDING), ("active", ASCENDING)])
        self.referrals.create_index("first_search")
        
        # Withdrawals indexes
        self.withdrawals.create_index([("user_id", ASCENDING), ("requested", DESCENDING)])
        self.withdrawals.create_index("status")
        
        # Activity indexes
        self.group_activity.create_index(
            [("user_id", ASCENDING), ("date", ASCENDING)], 
            unique=True
        )
        self.group_activity.create_index("date")
        
        # Missions indexes
        self.missions.create_index(
            [("user_id", ASCENDING), ("type", ASCENDING), ("date", ASCENDING)],
            unique=True
        )
        
        # Channel joins
        self.channel_joins.create_index(
            [("user_id", ASCENDING), ("channel", ASCENDING)],
            unique=True
        )
        
        # TTL indexes
        self.notifications.create_index("created_at", expireAfterSeconds=604800)  # 7 days
        self.spins.create_index("timestamp", expireAfterSeconds=2592000)  # 30 days
    
    # ========== USER FUNCTIONS ==========
    
    def get_user(self, user_id):
        """Get user by ID with caching"""
        try:
            return self.users.find_one({"user_id": user_id})
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}")
            return None
    
    def create_user(self, user_id, username, full_name, referrer=None):
        """Create new user with complete profile"""
        try:
            user = {
                "user_id": user_id,
                "username": username,
                "full_name": full_name,
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
                "search_streak": 0,
                "total_spins": 0,
                "total_spin_wins": 0,
                "best_spin_win": 0,
                "last_withdrawal": None,
                "total_withdrawn": 0,
                "referral_code": f"REF{user_id}{random.randint(100,999)}",
                "device_info": {},
                "preferences": {
                    "notifications": True,
                    "language": "en"
                }
            }
            
            self.users.insert_one(user)
            
            # Process referral if valid
            if referrer and referrer != user_id:
                ref_user = self.get_user(referrer)
                if ref_user and not ref_user.get("is_blocked", False):
                    self.referrals.insert_one({
                        "referrer": referrer,
                        "user": user_id,
                        "joined": datetime.now(),
                        "active": False,
                        "first_search": None,
                        "last_active": None,
                        "earnings": 0.0
                    })
                    
                    # Update referrer stats
                    self.users.update_one(
                        {"user_id": referrer},
                        {"$inc": {"total_referrals": 1}}
                    )
            
            return user
            
        except DuplicateKeyError:
            return self.get_user(user_id)
        except Exception as e:
            logger.error(f"Error creating user {user_id}: {e}")
            return None
    
    def update_user(self, user_id, updates):
        """Update user with timestamp"""
        try:
            updates["last_active"] = datetime.now()
            return self.users.update_one(
                {"user_id": user_id},
                {"$set": updates}
            )
        except Exception as e:
            logger.error(f"Error updating user {user_id}: {e}")
            return None
    
    def update_balance(self, user_id, amount, transaction_type=None, details=None):
        """Update user balance with transaction logging"""
        try:
            # Update balance
            result = self.users.update_one(
                {"user_id": user_id},
                {"$inc": {"balance": amount, "total_earned": max(0, amount)}}
            )
            
            if result.modified_count > 0 and transaction_type:
                # Log transaction
                self.transactions.insert_one({
                    "user_id": user_id,
                    "amount": amount,
                    "type": transaction_type,
                    "details": details,
                    "balance_after": self.get_user(user_id)["balance"],
                    "timestamp": datetime.now()
                })
            
            # Update tier based on new balance/referrals
            self._update_user_tier(user_id)
            
            user = self.get_user(user_id)
            return user["balance"] if user else 0
        except Exception as e:
            logger.error(f"Error updating balance for {user_id}: {e}")
            return 0
    
    def _update_user_tier(self, user_id):
        """Update user tier based on active referrals"""
        user = self.get_user(user_id)
        if not user:
            return
        
        active_refs = self.referrals.count_documents({
            "referrer": user_id, 
            "active": True
        })
        
        new_tier = 1
        for tier, config in sorted(Config.TIERS.items(), key=lambda x: x[1]["min_refs"], reverse=True):
            if active_refs >= config["min_refs"]:
                new_tier = tier
                break
        
        if new_tier != user.get("tier", 1):
            self.users.update_one(
                {"user_id": user_id},
                {"$set": {"tier": new_tier}}
            )
            
            # Add tier upgrade bonus
            tier_bonus = Config.TIERS[new_tier]["bonus"]
            if tier_bonus > 0:
                self.update_balance(
                    user_id, 
                    tier_bonus, 
                    "tier_upgrade", 
                    f"Upgraded to {Config.TIERS[new_tier]['name']}"
                )
    
    def get_user_stats(self, user_id):
        """Get comprehensive user stats"""
        user = self.get_user(user_id)
        if not user:
            return None
        
        # Referral stats
        ref_count = self.referrals.count_documents({"referrer": user_id})
        active_refs = self.referrals.count_documents({
            "referrer": user_id, 
            "active": True
        })
        pending_refs = ref_count - active_refs
        
        # Referral earnings
        pipeline = [
            {"$match": {"referrer": user_id}},
            {"$group": {"_id": None, "total": {"$sum": "$earnings"}}}
        ]
        ref_earnings = list(self.referrals.aggregate(pipeline))
        ref_earnings = ref_earnings[0]["total"] if ref_earnings else 0
        
        # Withdrawal stats
        total_withdrawn = sum(
            w.get("amount", 0) for w in self.withdrawals.find({
                "user_id": user_id,
                "status": "completed"
            })
        )
        
        pending_withdrawal = self.withdrawals.count_documents({
            "user_id": user_id,
            "status": "pending"
        })
        
        # Mission stats
        today = datetime.now().date().isoformat()
        missions_completed = self.missions.count_documents({
            "user_id": user_id,
            "date": today,
            "completed": True
        })
        
        # Current tier
        tier = user.get("tier", 1)
        tier_info = Config.TIERS[tier]
        
        # Next tier
        next_tier = tier + 1 if tier < max(Config.TIERS.keys()) else tier
        next_tier_info = Config.TIERS.get(next_tier, tier_info)
        refs_needed = max(0, next_tier_info["min_refs"] - active_refs)
        
        return {
            "balance": round(user.get("balance", 0), 2),
            "total_earned": round(user.get("total_earned", 0), 2),
            "spins": user.get("spins", 0),
            "tier": tier,
            "tier_name": tier_info["name"],
            "tier_rate": tier_info["rate"],
            "tier_color": tier_info["color"],
            "next_tier": next_tier if next_tier != tier else None,
            "next_tier_name": next_tier_info["name"] if next_tier != tier else None,
            "refs_needed": refs_needed if next_tier != tier else 0,
            "total_refs": ref_count,
            "active_refs": active_refs,
            "pending_refs": pending_refs,
            "ref_earnings": round(ref_earnings, 2),
            "monthly_refs": user.get("monthly_referrals", 0),
            "daily_streak": user.get("daily_streak", 0),
            "channel_joined": user.get("channel_joined", False),
            "total_searches": user.get("total_searches", 0),
            "total_spins": user.get("total_spins", 0),
            "total_spin_wins": user.get("total_spin_wins", 0),
            "best_spin_win": user.get("best_spin_win", 0),
            "total_withdrawn": round(total_withdrawn, 2),
            "pending_withdrawal": pending_withdrawal,
            "missions_completed": missions_completed,
            "referral_link": f"https://t.me/{Config.BOT_USERNAME}?start=ref_{user_id}",
            "joined": user.get("joined").isoformat() if user.get("joined") else None,
            "last_active": user.get("last_active").isoformat() if user.get("last_active") else None
        }
    
    # ========== SEARCH TRACKING ==========
    
    def track_search(self, user_id):
        """Track user search in group - returns referrer if activated"""
        today = datetime.now().date().isoformat()
        
        # Update group activity
        try:
            self.group_activity.update_one(
                {"user_id": user_id, "date": today},
                {"$inc": {"count": 1}},
                upsert=True
            )
        except DuplicateKeyError:
            self.group_activity.update_one(
                {"user_id": user_id, "date": today},
                {"$inc": {"count": 1}}
            )
        
        # Update user search stats
        user = self.get_user(user_id)
        if user:
            self.users.update_one(
                {"user_id": user_id},
                {
                    "$inc": {"total_searches": 1},
                    "$set": {"last_search_date": today}
                }
            )
        
        # Check if this activates a referral
        referral = self.referrals.find_one({"user": user_id, "active": False})
        if referral:
            # Mark as active
            self.referrals.update_one(
                {"_id": referral["_id"]},
                {
                    "$set": {
                        "active": True,
                        "first_search": datetime.now()
                    }
                }
            )
            
            # Update referrer stats
            self.users.update_one(
                {"user_id": referral["referrer"]},
                {
                    "$inc": {
                        "active_referrals": 1,
                        "monthly_referrals": 1,
                        "spins": Config.REFERRAL_BONUS
                    }
                }
            )
            
            # Send notification to bot (handled in handler)
            return referral["referrer"]
        
        return None
    
    def process_daily_referral_payment(self, user_id):
        """Process daily payment for active referrals"""
        today = datetime.now().date()
        
        # Get all active referrals for this user
        referrals = list(self.referrals.find({
            "user": user_id,
            "active": True
        }))
        
        if not referrals:
            return 0
        
        # Get user tier rate
        user = self.get_user(user_id)
        tier = user.get("tier", 1)
        rate = Config.TIERS[tier]["rate"]
        
        total_payment = 0
        for ref in referrals:
            # Check if already paid today
            last_paid = ref.get("last_paid")
            if last_paid and last_paid.date() == today:
                continue
            
            amount = rate
            total_payment += amount
            
            # Update referral earnings
            self.referrals.update_one(
                {"_id": ref["_id"]},
                {
                    "$inc": {"earnings": amount},
                    "$set": {"last_paid": datetime.now()}
                }
            )
        
        if total_payment > 0:
            # Add to user balance
            self.update_balance(
                user_id,
                total_payment,
                "referral_daily",
                f"Daily earnings from {len(referrals)} referrals"
            )
            
            return total_payment
        
        return 0
    
    # ========== SPIN WHEEL ==========
    
    def spin_wheel(self, user_id):
        """Process spin wheel with probability"""
        user = self.get_user(user_id)
        if not user:
            return {"error": "User not found"}
        
        if user["spins"] <= 0:
            return {"error": "No spins left"}
        
        # Check cooldown
        last_spin = user.get("last_spin")
        if last_spin and (datetime.now() - last_spin) < Config.SPIN_COOLDOWN:
            remaining = Config.SPIN_COOLDOWN - (datetime.now() - last_spin)
            minutes = remaining.seconds // 60
            return {"error": f"Wait {minutes} minutes"}
        
        # Select prize based on weights
        weights = [p["weight"] for p in Config.SPIN_PRIZES]
        prize_data = random.choices(Config.SPIN_PRIZES, weights=weights)[0]
        prize = prize_data["value"]
        
        # Log spin
        self.spins.insert_one({
            "user_id": user_id,
            "prize": prize,
            "timestamp": datetime.now()
        })
        
        # Update user
        update_data = {
            "$inc": {
                "spins": -1, 
                "balance": prize, 
                "total_earned": prize,
                "total_spins": 1
            },
            "$set": {"last_spin": datetime.now()}
        }
        
        if prize > 0:
            update_data["$inc"]["total_spin_wins"] = 1
            if prize > user.get("best_spin_win", 0):
                update_data["$set"]["best_spin_win"] = prize
        
        self.users.update_one({"user_id": user_id}, update_data)
        
        # Update spin mission
        self.update_mission(user_id, "spin_master")
        
        return {
            "prize": prize,
            "prize_name": prize_data["name"],
            "remaining_spins": user["spins"] - 1,
            "color": prize_data["color"]
        }
    
    # ========== DAILY BONUS ==========
    
    def claim_daily(self, user_id):
        """Claim daily bonus with streak"""
        user = self.get_user(user_id)
        if not user:
            return None
        
        today = datetime.now().date()
        last = user.get("last_daily")
        
        if last and last.date() == today:
            return None
        
        # Calculate streak
        if last and last.date() == today - timedelta(days=1):
            streak = user.get("daily_streak", 0) + 1
        else:
            streak = 1
        
        # Calculate bonus
        bonus = Config.DAILY_BONUS_BASE + (streak * Config.DAILY_BONUS_INCREMENT)
        
        # Update user
        self.users.update_one(
            {"user_id": user_id},
            {
                "$set": {"last_daily": datetime.now(), "daily_streak": streak},
                "$inc": {"balance": bonus, "total_earned": bonus}
            }
        )
        
        # Update mission
        self.update_mission(user_id, "daily_bonus")
        
        return {
            "bonus": round(bonus, 2),
            "streak": streak,
            "balance": round(user["balance"] + bonus, 2)
        }
    
    # ========== CHANNEL JOIN ==========
    
    def mark_channel_joined(self, user_id, channel):
        """Mark user as joined channel and give bonus"""
        if self.channel_joins.find_one({"user_id": user_id, "channel": channel}):
            return False
        
        self.channel_joins.insert_one({
            "user_id": user_id,
            "channel": channel,
            "joined_at": datetime.now()
        })
        
        self.update_balance(
            user_id, 
            Config.CHANNEL_BONUS, 
            "channel_bonus", 
            f"Channel {channel} join bonus"
        )
        
        self.users.update_one(
            {"user_id": user_id},
            {"$set": {"channel_joined": True}}
        )
        
        return True
    
    # ========== WITHDRAWAL ==========
    
    def create_withdrawal(self, user_id, amount, method, details):
        """Create withdrawal request"""
        user = self.get_user(user_id)
        if not user:
            return False, "User not found"
        
        if user["balance"] < amount:
            return False, "Insufficient balance"
        
        if amount < Config.MIN_WITHDRAWAL:
            return False, f"Minimum withdrawal ₹{Config.MIN_WITHDRAWAL}"
        
        # Check for pending withdrawals
        pending = self.withdrawals.count_documents({
            "user_id": user_id,
            "status": "pending"
        })
        
        if pending > 0:
            return False, "You already have a pending request"
        
        # Create withdrawal
        withdrawal = {
            "user_id": user_id,
            "amount": amount,
            "method": method,
            "details": details,
            "status": "pending",
            "requested": datetime.now(),
            "processed": None,
            "transaction_id": f"WD{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(100,999)}"
        }
        
        self.withdrawals.insert_one(withdrawal)
        
        # Deduct from balance
        self.users.update_one(
            {"user_id": user_id},
            {
                "$inc": {"balance": -amount},
                "$set": {"last_withdrawal": datetime.now()}
            }
        )
        
        return True, "Withdrawal request submitted"
    
    def process_withdrawal(self, withdrawal_id, status, admin_id=None):
        """Process withdrawal (admin function)"""
        result = self.withdrawals.update_one(
            {"_id": ObjectId(withdrawal_id)},
            {
                "$set": {
                    "status": status,
                    "processed": datetime.now(),
                    "processed_by": admin_id
                }
            }
        )
        
        if result.modified_count > 0:
            withdrawal = self.withdrawals.find_one({"_id": ObjectId(withdrawal_id)})
            if status == "completed":
                self.users.update_one(
                    {"user_id": withdrawal["user_id"]},
                    {"$inc": {"total_withdrawn": withdrawal["amount"]}}
                )
            elif status == "rejected":
                # Refund amount
                self.update_balance(
                    withdrawal["user_id"],
                    withdrawal["amount"],
                    "withdrawal_refund",
                    "Withdrawal rejected - refund"
                )
            
            return True
        
        return False
    
    # ========== MISSIONS ==========
    
    def update_mission(self, user_id, mission_type):
        """Update mission progress"""
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
                "completed": False,
                "completed_at": None
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
                {
                    "$set": {
                        "completed": True,
                        "completed_at": datetime.now()
                    }
                }
            )
            
            # Give rewards
            self.update_balance(
                user_id, 
                config["reward"], 
                "mission", 
                f"Mission {mission_type} completed"
            )
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
        
        return {
            "count": mission["count"], 
            "completed": mission.get("completed", False),
            "target": config["target"] if config else 0
        }
    
    def get_missions(self, user_id):
        """Get all missions for user"""
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
                "icon": config["icon"],
                "desc": config["desc"]
            }
        
        return missions
    
    # ========== LEADERBOARD ==========
    
    def get_current_leaderboard(self, limit=10):
        """Get current month leaderboard"""
        pipeline = [
            {"$match": {
                "is_blocked": False, 
                "monthly_referrals": {"$gt": 0}
            }},
            {"$sort": {"monthly_referrals": -1}},
            {"$limit": limit},
            {"$project": {
                "user_id": 1,
                "full_name": 1,
                "monthly_referrals": 1,
                "balance": 1,
                "active_referrals": 1,
                "tier": 1
            }}
        ]
        return list(self.users.aggregate(pipeline))
    
    def get_balance_leaderboard(self, limit=10):
        """Get top earners by balance"""
        pipeline = [
            {"$match": {"is_blocked": False}},
            {"$sort": {"balance": -1}},
            {"$limit": limit},
            {"$project": {
                "user_id": 1,
                "full_name": 1,
                "balance": 1,
                "tier": 1
            }}
        ]
        return list(self.users.aggregate(pipeline))
    
    # ========== ADMIN FUNCTIONS ==========
    
    def get_stats(self):
        """Get comprehensive stats"""
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        total_users = self.users.count_documents({})
        active_today = self.group_activity.count_documents({
            "date": now.date().isoformat()
        })
        
        # Referral stats
        total_referrals = self.referrals.count_documents({})
        active_referrals = self.referrals.count_documents({"active": True})
        
        # Financial stats
        total_earned = sum(
            u.get("total_earned", 0) for u in self.users.find({}, {"total_earned": 1})
        )
        total_paid = sum(
            w.get("amount", 0) for w in self.withdrawals.find({"status": "completed"})
        )
        pending_withdrawals = self.withdrawals.count_documents({"status": "pending"})
        pending_amount = sum(
            w.get("amount", 0) for w in self.withdrawals.find({"status": "pending"})
        )
        
        # Today's stats
        today_users = self.users.count_documents({"joined": {"$gte": today_start}})
        today_earned = sum(
            t.get("amount", 0) for t in self.transactions.find({
                "timestamp": {"$gte": today_start},
                "amount": {"$gt": 0}
            })
        )
        
        # Spin stats
        total_spins = self.spins.count_documents({})
        today_spins = self.spins.count_documents({"timestamp": {"$gte": today_start}})
        
        # Tier distribution
        tier_dist = {}
        for tier in Config.TIERS.keys():
            tier_dist[tier] = self.users.count_documents({"tier": tier})
        
        return {
            "total_users": total_users,
            "active_users": self.users.count_documents({"is_blocked": False}),
            "blocked_users": self.users.count_documents({"is_blocked": True}),
            "active_today": active_today,
            "total_referrals": total_referrals,
            "active_referrals": active_referrals,
            "pending_withdrawals": pending_withdrawals,
            "pending_amount": round(pending_amount, 2),
            "total_earned": round(total_earned, 2),
            "total_paid": round(total_paid, 2),
            "today_users": today_users,
            "today_earned": round(today_earned, 2),
            "total_spins": total_spins,
            "today_spins": today_spins,
            "tier_distribution": tier_dist
        }
    
    def get_all_users(self, filter_blocked=False, limit=None):
        """Get all users with optional filter"""
        query = {"is_blocked": False} if filter_blocked else {}
        
        if limit:
            return list(self.users.find(query).limit(limit))
        return list(self.users.find(query))
    
    def clear_user_earnings(self, user_id):
        """Clear user earnings but keep account"""
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
                    "total_spins": 0,
                    "total_spin_wins": 0,
                    "best_spin_win": 0,
                    "last_daily": None,
                    "last_spin": None
                }
            }
        )
        
        # Clear referrals
        self.referrals.delete_many({"referrer": user_id})
        
        return True
    
    def clear_all_user_data(self, user_id):
        """Completely delete user and all data"""
        self.users.delete_one({"user_id": user_id})
        self.referrals.delete_many({"referrer": user_id})
        self.referrals.delete_many({"user": user_id})
        self.transactions.delete_many({"user_id": user_id})
        self.withdrawals.delete_many({"user_id": user_id})
        self.spins.delete_many({"user_id": user_id})
        self.missions.delete_many({"user_id": user_id})
        self.channel_joins.delete_many({"user_id": user_id})
        self.group_activity.delete_many({"user_id": user_id})
        return True
    
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
    
    # ========== MONTHLY RESET ==========
    
    def reset_monthly_referrals(self):
        """Reset monthly referrals and give rewards"""
        # Get top referrers
        top_users = list(self.users.find(
            {"monthly_referrals": {"$gt": 0}},
            {"user_id": 1, "monthly_referrals": 1, "full_name": 1}
        ).sort("monthly_referrals", -1).limit(10))
        
        # Give rewards
        rewards_given = []
        for idx, user in enumerate(top_users, 1):
            reward_config = Config.LEADERBOARD_REWARDS.get(idx)
            if reward_config and user["monthly_referrals"] >= reward_config["min_refs"]:
                reward = reward_config["reward"]
                self.update_balance(
                    user["user_id"],
                    reward,
                    "leaderboard",
                    f"Rank #{idx} in monthly leaderboard"
                )
                rewards_given.append({
                    "user_id": user["user_id"],
                    "rank": idx,
                    "reward": reward
                })
        
        # Reset monthly referrals for all users
        self.users.update_many(
            {},
            {"$set": {"monthly_referrals": 0}}
        )
        
        return rewards_given


# Global database instance
db = Database()
