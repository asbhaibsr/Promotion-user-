from pymongo import MongoClient
from datetime import datetime, timedelta
from config import MONGO_URI, TIERS, DAILY_BONUS_BASE, MIN_WITHDRAWAL

client = MongoClient(MONGO_URI)
db = client.movie_bot

users = db.users
referrals = db.referrals
withdrawals = db.withdrawals

# === USER FUNCTIONS ===
def get_user(user_id):
    return users.find_one({"user_id": user_id})

def create_user(user_id, username, full_name, referrer=None):
    user = {
        "user_id": user_id,
        "username": username,
        "full_name": full_name,
        "balance": 0.0,
        "spins": 3,
        "tier": 1,
        "total_referrals": 0,
        "active_referrals": 0,
        "monthly_referrals": 0,
        "joined": datetime.now(),
        "last_daily": None,
        "daily_streak": 0,
        "missions": {},
        "payment_method": None,
        "payment_details": None,
        "welcome_bonus": False
    }
    users.insert_one(user)
    
    # Referral logic
    if referrer and referrer != user_id:
        ref = users.find_one({"user_id": referrer})
        if ref:
            referrals.insert_one({
                "referrer": referrer,
                "user": user_id,
                "joined": datetime.now(),
                "active": False,
                "first_search": None,
                "last_paid": None
            })
    return user

def update_balance(user_id, amount):
    users.update_one(
        {"user_id": user_id},
        {"$inc": {"balance": amount}}
    )
    user = get_user(user_id)
    return user["balance"] if user else 0

# === REFERRAL FUNCTIONS ===
def activate_referral(user_id):
    ref = referrals.find_one({"user": user_id})
    if ref and not ref["active"]:
        referrals.update_one(
            {"user": user_id},
            {"$set": {"active": True, "first_search": datetime.now()}}
        )
        # Update referrer stats
        users.update_one(
            {"user_id": ref["referrer"]},
            {"$inc": {"active_referrals": 1, "monthly_referrals": 1, "spins": 1}}
        )
        return ref["referrer"]
    return None

def pay_referrer(user_id):
    """रोजाना रेफरल पेमेंट"""
    ref = referrals.find_one({"user": user_id, "active": True})
    if not ref:
        return None
    
    today = datetime.now().date()
    if ref.get("last_paid") and ref["last_paid"].date() == today:
        return None
    
    referrer = users.find_one({"user_id": ref["referrer"]})
    if not referrer:
        return None
    
    # टियर के हिसाब से रेट
    tier = referrer.get("tier", 1)
    rate = TIERS[tier]["rate"]
    
    # पेमेंट करो
    users.update_one(
        {"user_id": ref["referrer"]},
        {"$inc": {"balance": rate}}
    )
    
    referrals.update_one(
        {"user": user_id},
        {"$set": {"last_paid": datetime.now()}}
    )
    
    return rate

# === DAILY FUNCTIONS ===
def claim_daily(user_id):
    user = users.find_one({"user_id": user_id})
    if not user:
        return None
    
    today = datetime.now().date()
    last = user.get("last_daily")
    
    if last and last.date() == today:
        return None
    
    streak = 1
    if last and last.date() == today - timedelta(days=1):
        streak = user.get("daily_streak", 0) + 1
    else:
        streak = 1
    
    bonus = DAILY_BONUS_BASE + (streak * 0.02)
    
    users.update_one(
        {"user_id": user_id},
        {
            "$set": {"last_daily": datetime.now(), "daily_streak": streak},
            "$inc": {"balance": bonus}
        }
    )
    
    updated_user = get_user(user_id)
    return {
        "bonus": bonus, 
        "streak": streak, 
        "balance": updated_user["balance"] if updated_user else user["balance"] + bonus
    }

# === WITHDRAWAL ===
def create_withdrawal(user_id, amount, method, details):
    user = users.find_one({"user_id": user_id})
    if not user or user["balance"] < amount or amount < MIN_WITHDRAWAL:
        return False
    
    withdrawal = {
        "user_id": user_id,
        "amount": amount,
        "method": method,
        "details": details,
        "status": "pending",
        "requested": datetime.now()
    }
    withdrawals.insert_one(withdrawal)
    
    users.update_one(
        {"user_id": user_id},
        {"$set": {"balance": 0}}
    )
    return True

# === LEADERBOARD ===
def get_leaderboard():
    return list(users.find(
        {"active_referrals": {"$gt": 0}}
    ).sort("active_referrals", -1).limit(10))

# === STATS ===
def get_user_stats(user_id):
    user = users.find_one({"user_id": user_id})
    if not user:
        return None
    
    ref_count = referrals.count_documents({"referrer": user_id})
    active_refs = referrals.count_documents({"referrer": user_id, "active": True})
    
    return {
        "balance": user.get("balance", 0),
        "spins": user.get("spins", 0),
        "tier": user.get("tier", 1),
        "total_refs": ref_count,
        "active_refs": active_refs,
        "monthly_refs": user.get("monthly_referrals", 0)
    }

# === MISSION UPDATE ===
def check_missions(user_id, mission_type):
    user = users.find_one({"user_id": user_id})
    if not user:
        return
    
    missions = user.get("missions", {})
    today = datetime.now().date().isoformat()
    
    if missions.get("date") != today:
        missions = {"date": today, "searches": 0, "search_done": False}
    
    if mission_type == "search":
        count = missions.get("searches", 0) + 1
        missions["searches"] = count
        if count >= 3 and not missions.get("search_done"):
            users.update_one(
                {"user_id": user_id},
                {"$inc": {"balance": 0.15, "spins": 1}}
            )
            missions["search_done"] = True
    
    users.update_one(
        {"user_id": user_id},
        {"$set": {"missions": missions}}
    )
