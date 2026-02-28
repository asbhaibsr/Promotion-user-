# database.py
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError
from datetime import datetime, timedelta
import logging
from config import Config
from utils import get_tier_from_refs

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.client = MongoClient(Config.MONGO_URI)
        self.db = self.client.movie_bot
        
        # कलेक्शन
        self.users = self.db.users
        self.referrals = self.db.referrals
        self.withdrawals = self.db.withdrawals
        self.transactions = self.db.transactions
        self.blocked_users = self.db.blocked_users
        self.ads = self.db.ads
        self.channel_joins = self.db.channel_joins
        self.spins = self.db.spins
        self.missions = self.db.missions
        self.broadcast_queue = self.db.broadcast_queue
        self.analytics = self.db.analytics
        
        # इंडेक्स बनाएं (परफॉर्मेंस के लिए)
        self._create_indexes()
        
        logger.info("✅ डेटाबेस कनेक्टेड")
    
    def _create_indexes(self):
        """इंडेक्स क्रिएट करें"""
        self.users.create_index("user_id", unique=True)
        self.users.create_index([("balance", DESCENDING)])
        self.users.create_index([("joined", DESCENDING)])
        
        self.referrals.create_index([("referrer", ASCENDING), ("user", ASCENDING)], unique=True)
        self.referrals.create_index("user", unique=True)
        self.referrals.create_index("last_paid")
        
        self.withdrawals.create_index([("status", ASCENDING), ("requested", DESCENDING)])
        
        self.channel_joins.create_index([("user_id", ASCENDING), ("channel", ASCENDING)], unique=True)
        
        self.spins.create_index([("user_id", ASCENDING), ("timestamp", DESCENDING)])
        
        logger.info("✅ इंडेक्स बन गए")
    
    # ========== यूजर फंक्शन्स ==========
    
    def get_user(self, user_id):
        """यूजर डेटा प्राप्त करें"""
        return self.users.find_one({"user_id": user_id})
    
    def create_user(self, user_id, username, full_name, referrer=None):
        """नया यूजर बनाएं"""
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
            "blocked_reason": None,
            "language": "hi",
            "settings": {
                "notifications": True,
                "daily_reminder": True
            }
        }
        
        try:
            self.users.insert_one(user)
            
            # रेफरल लॉजिक
            if referrer and referrer != user_id:
                ref_user = self.get_user(referrer)
                if ref_user and not ref_user.get("is_blocked", False):
                    self.referrals.insert_one({
                        "referrer": referrer,
                        "user": user_id,
                        "joined": datetime.now(),
                        "active": False,
                        "first_search": None,
                        "last_paid": None,
                        "total_earned": 0.0
                    })
                    
                    # रेफरर को नोटिफिकेशन (बाद में हैंडल होगा)
            
            return user
            
        except DuplicateKeyError:
            return self.get_user(user_id)
    
    def update_user(self, user_id, updates):
        """यूजर अपडेट करें"""
        updates["last_active"] = datetime.now()
        return self.users.update_one(
            {"user_id": user_id},
            {"$set": updates}
        )
    
    def update_balance(self, user_id, amount, transaction_type=None, details=None):
        """बैलेंस अपडेट करें (ट्रांजैक्शन के साथ)"""
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
        """यूजर स्टैट्स प्राप्त करें"""
        user = self.get_user(user_id)
        if not user:
            return None
        
        ref_count = self.referrals.count_documents({"referrer": user_id})
        active_refs = self.referrals.count_documents({"referrer": user_id, "active": True})
        pending_refs = ref_count - active_refs
        
        # टीयर कैलकुलेट करें
        tier = get_tier_from_refs(active_refs)
        
        return {
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
            "channel_joined": user.get("channel_joined", False)
        }
    
    # ========== रेफरल फंक्शन्स ==========
    
    def activate_referral(self, user_id):
        """रेफरल एक्टिवेट करें (पहली सर्च पर)"""
        ref = self.referrals.find_one({"user": user_id})
        if ref and not ref["active"]:
            self.referrals.update_one(
                {"user": user_id},
                {"$set": {"active": True, "first_search": datetime.now()}}
            )
            
            # रेफरर अपडेट करें
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
        return None
    
    def pay_referrer(self, user_id):
        """रेफरर को रोजाना पेमेंट"""
        ref = self.referrals.find_one({"user": user_id, "active": True})
        if not ref:
            return None
        
        # 24 घंटे का कूलडाउन चेक करें
        if ref.get("last_paid"):
            if datetime.now() - ref["last_paid"] < Config.REFERRAL_COOLDOWN:
                return None
        
        referrer = self.get_user(ref["referrer"])
        if not referrer or referrer.get("is_blocked", False):
            return None
        
        # टीयर के हिसाब से रेट
        tier = referrer.get("tier", 1)
        rate = Config.TIERS[tier]["rate"]
        
        # पेमेंट करें
        self.update_balance(
            ref["referrer"],
            rate,
            "referral_earning",
            f"रेफरल {user_id} से कमाई"
        )
        
        self.referrals.update_one(
            {"user": user_id},
            {"$set": {"last_paid": datetime.now()}}
        )
        
        return rate
    
    # ========== डेली बोनस ==========
    
    def claim_daily(self, user_id):
        """डेली बोनस क्लेम करें"""
        user = self.get_user(user_id)
        if not user:
            return None
        
        today = datetime.now().date()
        last = user.get("last_daily")
        
        if last and last.date() == today:
            return None
        
        # स्ट्रीक कैलकुलेट करें
        if last and last.date() == today - timedelta(days=1):
            streak = user.get("daily_streak", 0) + 1
        else:
            streak = 1
        
        # बोनस कैलकुलेट करें
        bonus = Config.DAILY_BONUS_BASE + (streak * Config.DAILY_BONUS_INCREMENT)
        
        self.users.update_one(
            {"user_id": user_id},
            {
                "$set": {"last_daily": datetime.now(), "daily_streak": streak},
                "$inc": {"balance": bonus, "total_earned": bonus}
            }
        )
        
        # ट्रांजैक्शन लॉग करें
        self.transactions.insert_one({
            "user_id": user_id,
            "amount": bonus,
            "type": "daily_bonus",
            "details": f"डेली बोनस (स्ट्रीक: {streak})",
            "timestamp": datetime.now()
        })
        
        return {
            "bonus": round(bonus, 2),
            "streak": streak,
            "balance": round(user["balance"] + bonus, 2)
        }
    
    # ========== स्पिन फंक्शन्स ==========
    
    def can_spin(self, user_id):
        """चेक करें कि स्पिन कर सकता है या नहीं"""
        user = self.get_user(user_id)
        if not user:
            return False, "यूजर नहीं मिला"
        
        if user["spins"] <= 0:
            return False, "कोई स्पिन नहीं बची"
        
        # कूलडाउन चेक करें (वैकल्पिक)
        last_spin = user.get("last_spin")
        if last_spin and Config.SPIN_COOLDOWN:
            if datetime.now() - last_spin < Config.SPIN_COOLDOWN:
                remaining = Config.SPIN_COOLDOWN - (datetime.now() - last_spin)
                minutes = int(remaining.total_seconds() / 60)
                return False, f"अगला स्पिन {minutes} मिनट बाद"
        
        return True, "स्पिन कर सकते हैं"
    
    def spin_wheel(self, user_id):
        """स्पिन व्हील"""
        can, msg = self.can_spin(user_id)
        if not can:
            return {"error": msg}
        
        import random
        prize = random.choices(Config.SPIN_PRIZES, weights=Config.SPIN_WEIGHTS)[0]
        
        self.users.update_one(
            {"user_id": user_id},
            {
                "$inc": {"spins": -1, "balance": prize, "total_earned": prize},
                "$set": {"last_spin": datetime.now()}
            }
        )
        
        # स्पिन हिस्ट्री
        self.spins.insert_one({
            "user_id": user_id,
            "prize": prize,
            "timestamp": datetime.now()
        })
        
        # ट्रांजैक्शन
        if prize > 0:
            self.transactions.insert_one({
                "user_id": user_id,
                "amount": prize,
                "type": "spin",
                "details": f"स्पिन जीत: ₹{prize}",
                "timestamp": datetime.now()
            })
        
        return {"prize": prize}
    
    # ========== चैनल जॉइन ==========
    
    def has_joined_channel(self, user_id, channel):
        """चैनल जॉइन किया है या नहीं"""
        return self.channel_joins.find_one({
            "user_id": user_id,
            "channel": channel
        }) is not None
    
    def mark_channel_joined(self, user_id, channel):
        """चैनल जॉइन मार्क करें और बोनस दें"""
        if self.has_joined_channel(user_id, channel):
            return False
        
        self.channel_joins.insert_one({
            "user_id": user_id,
            "channel": channel,
            "joined_at": datetime.now(),
            "bonus": Config.CHANNEL_BONUS
        })
        
        # बोनस दें
        self.update_balance(user_id, Config.CHANNEL_BONUS, "channel_bonus", f"चैनल {channel} जॉइन बोनस")
        
        # चैनल जॉइन स्टेटस अपडेट करें
        self.users.update_one(
            {"user_id": user_id},
            {"$set": {"channel_joined": True}}
        )
        
        return True
    
    # ========== विड्रॉल फंक्शन्स ==========
    
    def create_withdrawal(self, user_id, amount, method, details):
        """विड्रॉल रिक्वेस्ट बनाएं"""
        user = self.get_user(user_id)
        if not user:
            return False, "यूजर नहीं मिला"
        
        if user["balance"] < amount:
            return False, "अपर्याप्त बैलेंस"
        
        if amount < Config.MIN_WITHDRAWAL:
            return False, f"न्यूनतम विड्रॉल ₹{Config.MIN_WITHDRAWAL} है"
        
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
        
        # बैलेंस डिडक्ट करें
        self.users.update_one(
            {"user_id": user_id},
            {"$inc": {"balance": -amount}}
        )
        
        self.transactions.insert_one({
            "user_id": user_id,
            "amount": -amount,
            "type": "withdrawal",
            "details": f"विड्रॉल रिक्वेस्ट ₹{amount}",
            "timestamp": datetime.now()
        })
        
        return True, "विड्रॉल रिक्वेस्ट सबमिट हो गई"
    
    # ========== मिशन फंक्शन्स ==========
    
    def update_mission(self, user_id, mission_type):
        """मिशन अपडेट करें"""
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
        
        # मिशन कंप्लीट हुआ?
        config = Config.MISSIONS.get(mission_type)
        if config and mission["count"] >= config["target"] and not mission.get("completed"):
            self.missions.update_one(
                {"_id": mission["_id"]},
                {"$set": {"completed": True}}
            )
            
            # रिवॉर्ड दें
            self.update_balance(user_id, config["reward"], "mission", f"मिशन {mission_type} पूरा")
            self.users.update_one(
                {"user_id": user_id},
                {"$inc": {"spins": config["spins"]}}
            )
            
            return {
                "completed": True,
                "reward": config["reward"],
                "spins": config["spins"]
            }
        
        return {"count": mission["count"]}
    
    # ========== एडमिन फंक्शन्स ==========
    
    def get_all_users(self, filter_blocked=False):
        """सभी यूजर्स प्राप्त करें"""
        query = {"is_blocked": False} if filter_blocked else {}
        return list(self.users.find(query))
    
    def get_blocked_users(self):
        """ब्लॉक यूजर्स प्राप्त करें"""
        return list(self.users.find({"is_blocked": True}))
    
    def block_user(self, user_id, reason=None):
        """यूजर ब्लॉक करें"""
        return self.users.update_one(
            {"user_id": user_id},
            {"$set": {"is_blocked": True, "blocked_reason": reason}}
        )
    
    def unblock_user(self, user_id):
        """यूजर अनब्लॉक करें"""
        return self.users.update_one(
            {"user_id": user_id},
            {"$set": {"is_blocked": False, "blocked_reason": None}}
        )
    
    def clear_junk_users(self):
        """ब्लॉक/डिलीट यूजर्स का डेटा साफ करें"""
        blocked = self.get_blocked_users()
        count = 0
        
        for user in blocked:
            user_id = user["user_id"]
            
            # रेफरल डिलीट करें
            self.referrals.delete_many({"referrer": user_id})
            self.referrals.delete_many({"user": user_id})
            
            # ट्रांजैक्शन डिलीट करें
            self.transactions.delete_many({"user_id": user_id})
            
            # स्पिन हिस्ट्री डिलीट करें
            self.spins.delete_many({"user_id": user_id})
            
            # मिशन डिलीट करें
            self.missions.delete_many({"user_id": user_id})
            
            # चैनल जॉइन डिलीट करें
            self.channel_joins.delete_many({"user_id": user_id})
            
            # यूजर डिलीट करें
            self.users.delete_one({"user_id": user_id})
            
            count += 1
        
        return count
    
    def get_stats(self):
        """ग्लोबल स्टैट्स प्राप्त करें"""
        return {
            "total_users": self.users.count_documents({}),
            "active_users": self.users.count_documents({"is_blocked": False}),
            "blocked_users": self.users.count_documents({"is_blocked": True}),
            "total_withdrawals": self.withdrawals.count_documents({"status": "completed"}),
            "pending_withdrawals": self.withdrawals.count_documents({"status": "pending"}),
            "total_earned": sum(u.get("total_earned", 0) for u in self.users.find({}, {"total_earned": 1})),
            "total_paid": sum(w.get("amount", 0) for w in self.withdrawals.find({"status": "completed"})),
            "today_users": self.users.count_documents({"joined": {"$gte": datetime.now().replace(hour=0, minute=0, second=0)}})
        }
    
    # ========== एड्स फंक्शन्स ==========
    
    def create_ad(self, title, description, image_url, link_url, price_per_view):
        """एड बनाएं"""
        ad = {
            "title": title,
            "description": description,
            "image_url": image_url,
            "link_url": link_url,
            "price_per_view": price_per_view,
            "views": 0,
            "clicks": 0,
            "active": True,
            "created_at": datetime.now()
        }
        return self.ads.insert_one(ad)
    
    def get_active_ads(self):
        """एक्टिव एड्स प्राप्त करें"""
        return list(self.ads.find({"active": True}))
    
    def record_ad_view(self, ad_id, user_id):
        """एड व्यू रिकॉर्ड करें"""
        self.ads.update_one(
            {"_id": ad_id},
            {"$inc": {"views": 1}}
        )
        self.update_balance(user_id, Config.AD_PRICE_PER_VIEW, "ad_view", "एड देखने की कमाई")
    
    # ========== ब्रॉडकास्ट फंक्शन्स ==========
    
    def add_to_broadcast_queue(self, message, users):
        """ब्रॉडकास्ट क्यू में मैसेज जोड़ें"""
        queue_item = {
            "message": message,
            "total_users": len(users),
            "processed": 0,
            "failed": 0,
            "status": "pending",
            "created_at": datetime.now()
        }
        return self.broadcast_queue.insert_one(queue_item)
    
    # ========== लीडरबोर्ड ==========
    
    def get_leaderboard(self, limit=10):
        """लीडरबोर्ड प्राप्त करें"""
        pipeline = [
            {"$match": {"is_blocked": False, "active_referrals": {"$gt": 0}}},
            {"$sort": {"active_referrals": -1, "total_earned": -1}},
            {"$limit": limit},
            {"$project": {
                "user_id": 1,
                "full_name": 1,
                "username": 1,
                "active_referrals": 1,
                "balance": 1,
                "tier": 1
            }}
        ]
        return list(self.users.aggregate(pipeline))
    
    def get_monthly_leaderboard(self):
        """मंथली लीडरबोर्ड"""
        start_of_month = datetime.now().replace(day=1, hour=0, minute=0, second=0)
        
        pipeline = [
            {"$match": {
                "is_blocked": False,
                "monthly_referrals": {"$gt": 0}
            }},
            {"$sort": {"monthly_referrals": -1}},
            {"$limit": 10}
        ]
        return list(self.users.aggregate(pipeline))
    
    # ========== क्लीनअप फंक्शन्स ==========
    
    def cleanup_old_data(self, days=30):
        """पुराना डेटा साफ करें"""
        cutoff = datetime.now() - timedelta(days=days)
        
        # पुराने ट्रांजैक्शन आर्काइव करें
        self.transactions.delete_many({"timestamp": {"$lt": cutoff}})
        
        # पुराने स्पिन हिस्ट्री डिलीट करें
        self.spins.delete_many({"timestamp": {"$lt": cutoff}})
        
        # 7 दिन से पुराने मिशन डिलीट करें
        week_ago = datetime.now() - timedelta(days=7)
        self.missions.delete_many({"date": {"$lt": week_ago.date().isoformat()}})
        
        return True

# ग्लोबल डेटाबेस इंस्टेंस
db = Database()
