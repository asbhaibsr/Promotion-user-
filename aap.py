from flask import Flask, render_template, request, jsonify
from database import *
import json

app = Flask(__name__)

@app.route('/')
def index():
    user_id = request.args.get('user', '0')
    try:
        user_id = int(user_id)
    except:
        user_id = 0
    
    return render_template('index.html', user_id=user_id)

@app.route('/api/user/<int:user_id>')
def api_user(user_id):
    stats = get_user_stats(user_id)
    if not stats:
        return jsonify({"error": "User not found"})
    return jsonify(stats)

@app.route('/api/leaderboard')
def api_leaderboard():
    lb = get_leaderboard()
    result = []
    for u in lb:
        result.append({
            "name": u.get("full_name", "User")[:15],
            "refs": u.get("active_referrals", 0),
            "balance": u.get("balance", 0)
        })
    return jsonify(result)

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    from telegram import Update
    from main import app as bot_app
    
    update = Update.de_json(request.get_json(force=True), bot_app.bot)
    bot_app.process_update(update)
    return 'OK', 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)
