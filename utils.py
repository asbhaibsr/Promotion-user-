# utils.py - हेल्पर फंक्शन्स

def is_admin(user_id):
    from config import Config
    return user_id in Config.ADMIN_IDS

def format_balance(amount):
    return f"₹{amount:.2f}"
