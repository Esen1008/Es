#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import random
import threading
import time
import sqlite3
import schedule
import re
from contextlib import contextmanager
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ConversationHandler, filters

TOKEN = os.environ.get('TOKEN', '8859045300:AAGdLExTMf6cpGnJlDPJrz3GJ3VVlE1_51M')
WAITING_USERNAME = 1
DB_PATH = "game_data.db"
db_lock = threading.Lock()

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with db_lock, get_db() as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT UNIQUE,
                balance REAL DEFAULT 0,
                total_games INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                profit REAL DEFAULT 0,
                turnover REAL DEFAULT 0,
                rebate REAL DEFAULT 0,
                claimed_rebate REAL DEFAULT 0,
                last_signin TEXT,
                signin_streak INTEGER DEFAULT 0,
                daily_profit REAL DEFAULT 0,
                weekly_profit REAL DEFAULT 0,
                monthly_profit REAL DEFAULT 0,
                last_reset TEXT DEFAULT CURRENT_DATE
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS gift_shop (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                emoji TEXT,
                price INTEGER,
                description TEXT
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS gifts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user INTEGER,
                to_user INTEGER,
                gift_type TEXT,
                price INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS red_packets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER,
                chat_id INTEGER,
                total_amount REAL,
                total_count INTEGER,
                remain_amount REAL,
                remain_count INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expired_at TIMESTAMP
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS red_packet_claims (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                packet_id INTEGER,
                user_id INTEGER,
                amount REAL,
                claimed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(packet_id, user_id)
            )
        ''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_username ON users(username)')
        conn.commit()
        init_gift_shop()

def init_gift_shop():
    with db_lock, get_db() as conn:
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM gift_shop')
        if c.fetchone()[0] == 0:
            gifts = [
                ('玫瑰花', '🌹', 88, '表达爱意'),
                ('巧克力', '🍫', 188, '甜蜜礼物'),
                ('蛋糕', '🎂', 288, '庆祝胜利'),
                ('香槟', '🥂', 388, '庆祝时刻'),
                ('钻石', '💎', 888, '珍贵礼物'),
                ('皇冠', '👑', 1888, '尊贵象征'),
                ('跑车', '🏎️', 5888, '豪华跑车'),
                ('游艇', '🛥️', 8888, '私人游艇'),
            ]
            c.executemany('INSERT INTO gift_shop (name, emoji, price, description) VALUES (?, ?, ?, ?)', gifts)
            conn.commit()

def get_user(user_id):
    with db_lock, get_db() as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        r = c.fetchone()
        return dict(r) if r else None

def create_user(user_id, username=None):
    with db_lock, get_db() as conn:
        c = conn.cursor()
        c.execute('INSERT INTO users (user_id, username, balance, last_reset) VALUES (?, ?, ?, ?)',
                  (user_id, username, 0, datetime.now().strftime("%Y-%m-%d")))
        conn.commit()

def update_user(user_id, data):
    if not data:
        return
    with db_lock, get_db() as conn:
        c = conn.cursor()
        set_clause = ', '.join([f"{k} = ?" for k in data.keys()])
        values = list(data.values()) + [user_id]
        c.execute(f'UPDATE users SET {set_clause} WHERE user_id = ?', values)
        conn.commit()

def get_user_data(user_id):
    user = get_user(user_id)
    if not user:
        create_user(user_id)
        user = get_user(user_id)
    return user

def save_user_data(user_id, data):
    update_user(user_id, data)

def get_top_users(period='daily', limit=10):
    field = {'daily': 'daily_profit', 'weekly': 'weekly_profit', 'monthly': 'monthly_profit'}.get(period, 'daily_profit')
    with db_lock, get_db() as conn:
        c = conn.cursor()
        c.execute(f'''
            SELECT user_id, username, {field} as profit
            FROM users
            WHERE username IS NOT NULL AND {field} != 0
            ORDER BY {field} DESC
            LIMIT ?
        ''', (limit,))
        return [dict(r) for r in c.fetchall()]

def shuffle_cards():
    suits = ['♠', '♥', '♦', '♣']
    ranks = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
    values = {r: min(i + 1, 10) for i, r in enumerate(ranks)}
    deck = [(f"{s}{r}", values[r]) for s in suits for r in ranks]
    random.shuffle(deck)
    return deck

def check_special(cards):
    vals = [c[1] for c in cards]
    total = sum(vals)
    if all(v <= 5 for v in vals) and total <= 10:
        return "五小牛 ⭐", 6
    for v in set(vals):
        if vals.count(v) >= 4:
            return "炸弹牛 💣", 6
    if all(v >= 11 for v in vals):
        return "五花牛 🌸", 5
    flower_count = sum(1 for v in vals if v >= 11)
    if flower_count >= 4:
        return "四花牛 🌺", 4
    counts = [vals.count(v) for v in set(vals)]
    if 3 in counts and 2 in counts:
        return "葫芦牛 🍀", 4
    return None, 0

def calc_niu(cards):
    vals = [c[1] for c in cards]
    special, mult = check_special(cards)
    if special:
        return special, mult
    total = sum(vals)
    for i in range(5):
        for j in range(i+1, 5):
            for k in range(j+1, 5):
                if (vals[i] + vals[j] + vals[k]) % 10 == 0:
                    niu = (total - vals[i] - vals[j] - vals[k]) % 10
                    if niu == 0:
                        return "牛牛 🐂", 3
                    mult = 3 if niu >= 8 else 2 if niu >= 6 else 1
                    return f"牛{niu}", mult
    return "没牛 😢", 0

def show_cards(cards):
    return ' '.join(c[0] for c in cards)

def get_vip_level(turnover):
    levels = [(500000000, "VIP 10 👑"), (100000000, "VIP 9 💎"), (50000000, "VIP 8 💎"),
              (10000000, "VIP 7 💎"), (5000000, "VIP 6 💎"), (1000000, "VIP 5 💎"),
              (500000, "VIP 4 💎"), (100000, "VIP 3 💎"), (50000, "VIP 2 💎"), (10000, "VIP 1 💎")]
    for threshold, level in levels:
        if turnover >= threshold:
            return level
    return "普通会员"

def get_rebate_rate(turnover):
    rates = [(10000000, 0.015), (5000000, 0.012), (1000000, 0.01),
             (500000, 0.008), (100000, 0.006), (10000, 0.005)]
    for threshold, rate in rates:
        if turnover >= threshold:
            return rate
    return 0.003

def get_main_menu(user):
    user_id = user['user_id']
    username = user.get('username', f"玩家{str(user_id)[:6]}")
    vip = get_vip_level(user['turnover'])
    rebate = user.get('rebate', 0)
    kb = [
        [InlineKeyboardButton("🎲 牛牛游戏", callback_data="play")],
        [InlineKeyboardButton("🏆 排行榜", callback_data="rank")],
        [InlineKeyboardButton("💰 钱包", callback_data="wallet")],
        [InlineKeyboardButton("📈 战绩", callback_data="stats")],
        [InlineKeyboardButton("📅 每日签到", callback_data="signin")],
        [InlineKeyboardButton("🧧 领取返佣", callback_data="claim_rebate")],
    ]
    text = f"🏰 皇家至尊娱乐城\n👤 {username}\n💎 {vip}\n💰 余额: {user['balance']:.2f}元\n🧧 返佣: {rebate:.2f}元\n📊 总游戏: {user['total_games']}局"
    return text, kb

async def start(update, context):
    user_id = update.effective_user.id
    user = get_user_data(user_id)
    if user.get('username') is None:
        await update.message.reply_text("🎉 欢迎！\n请设置用户名（最多10个字）")
        return WAITING_USERNAME
    text, kb = get_main_menu(user)
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))
    return ConversationHandler.END

async def handle_username(update, context):
    user_id = update.effective_user.id
    username = update.message.text.strip()
    if len(username) > 10:
        await update.message.reply_text("❌ 不能超过10个字")
        return WAITING_USERNAME
    user = get_user_data(user_id)
    user['username'] = username
    save_user_data(user_id, user)
    await update.message.reply_text(f"✅ 注册成功！\n👤 昵称: {username}\n发送 /start 开始！")
    return ConversationHandler.END

async def cancel(update, context):
    await update.message.reply_text("已取消")
    return ConversationHandler.END

async def setname(update, context):
    user_id = update.effective_user.id
    if len(context.args) == 0:
        await update.message.reply_text("用法: /setname 新昵称")
        return
    username = ' '.join(context.args)
    if len(username) > 10:
        await update.message.reply_text("❌ 不能超过10个字")
        return
    user = get_user_data(user_id)
    user['username'] = username
    save_user_data(user_id, user)
    await update.message.reply_text(f"✅ 已修改为: {username}")

async def handle_group_message(update, context):
    if not update.message or not update.message.text:
        return
    user_id = update.message.from_user.id
    text = update.message.text.strip()
    if not text.startswith('/'):
        return
    parts = text.split()
    command = parts[0].lower()

    if command == '/xz':
        if len(parts) < 2:
            await update.message.reply_text("用法: /xz 金额")
            return
        try:
            bet = float(parts[1])
            if bet < 10:
                await update.message.reply_text("最低10元")
                return
            if bet > 10000:
                await update.message.reply_text("最高10000元")
                return
            await play_game_group(update, context, bet)
        except ValueError:
            await update.message.reply_text("请输入有效数字")

    elif command == '/phb':
        await show_group_ranking(update, context)

    elif command == '/hb':
        if len(parts) < 3:
            await update.message.reply_text("用法: /hb 总金额 个数")
            return
        try:
            total = float(parts[1])
            count = int(parts[2])
            if total < 10:
                await update.message.reply_text("最低10元")
                return
            if count < 1 or count > 100:
                await update.message.reply_text("个数1-100")
                return
            await create_red_packet(update, context, total, count)
        except ValueError:
            await update.message.reply_text("请输入有效数字")

async def play_game_group(update, context, bet):
    user_id = update.message.from_user.id
    user = get_user_data(user_id)
    if user['balance'] < bet:
        await update.message.reply_text(f"余额不足！当前: {user['balance']:.2f}元")
        return
    user['balance'] -= bet
    deck = shuffle_cards()
    p_hand = deck[:5]
    d_hand = deck[5:10]
    p_name, p_mult = calc_niu(p_hand)
    d_name, d_mult = calc_niu(d_hand)
    result_text = ""
    win_amount = 0
    if p_mult > d_mult:
        win_amount = bet * p_mult
        user['balance'] += win_amount
        user['wins'] += 1
        user['profit'] += win_amount - bet
        user['daily_profit'] += win_amount - bet
        result_text = f"🎉 赢了！+{win_amount:.0f}元"
    elif p_mult < d_mult:
        user['losses'] += 1
        user['profit'] -= bet
        user['daily_profit'] -= bet
        result_text = f"💔 输了！-{bet:.0f}元"
    else:
        user['balance'] += bet
        result_text = "🤝 平局"
    user['total_games'] += 1
    user['turnover'] += bet
    rebate_rate = get_rebate_rate(user['turnover'])
    rebate_amount = bet * rebate_rate
    user['rebate'] = user.get('rebate', 0) + rebate_amount
    save_user_data(user_id, user)
    msg = f"🎲 下注 {bet:.0f}元\n🎴 你: {show_cards(p_hand)} → {p_name}\n🎴 庄: {show_cards(d_hand)} → {d_name}\n{result_text}\n💰 余额: {user['balance']:.2f}元"
    await update.message.reply_text(msg)

async def show_group_ranking(update, context):
    with db_lock, get_db() as conn:
        c = conn.cursor()
        c.execute('SELECT username, daily_profit FROM users WHERE username IS NOT NULL ORDER BY daily_profit DESC LIMIT 10')
        results = c.fetchall()
    if not results:
        await update.message.reply_text("暂无数据")
        return
    msg = "🏆 今日排行榜 (12:00刷新)\n\n"
    medals = ['🥇', '🥈', '🥉']
    for i, row in enumerate(results, 1):
        medal = medals[i-1] if i <= 3 else f"{i}."
        sign = '+' if row['daily_profit'] >= 0 else ''
        msg += f"{medal} {row['username']}  {sign}{row['daily_profit']:.0f}元\n"
    await update.message.reply_text(msg)

async def create_red_packet(update, context, total, count):
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    user = get_user_data(user_id)
    if user['balance'] < total:
        await update.message.reply_text(f"余额不足！需要 {total}元")
        return
    user['balance'] -= total
    save_user_data(user_id, user)
    with db_lock, get_db() as conn:
        c = conn.cursor()
        c.execute('INSERT INTO red_packets (sender_id, chat_id, total_amount, total_count, remain_amount, remain_count, expired_at) VALUES (?, ?, ?, ?, ?, ?, datetime("now", "+24 hours"))',
                  (user_id, chat_id, total, count, total, count))
        packet_id = c.lastrowid
        conn.commit()
    msg = f"🧧 发红包！\n💰 {total}元\n📦 {count}个\n点击领取！"
    kb = [[InlineKeyboardButton("🧧 抢红包", callback_data=f"redpacket_{packet_id}")]]
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb))

async def claim_red_packet(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    packet_id = int(query.data.split('_')[1])
    with db_lock, get_db() as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM red_packets WHERE id = ?', (packet_id,))
        packet = c.fetchone()
        if not packet:
            await query.edit_message_text("红包不存在")
            return
        c.execute('SELECT * FROM red_packet_claims WHERE packet_id = ? AND user_id = ?', (packet_id, user_id))
        if c.fetchone():
            await query.answer("已领过")
            return
        if packet['remain_count'] <= 0:
            await query.edit_message_text("已抢完")
            return
        if packet['remain_count'] == 1:
            amount = packet['remain_amount']
        else:
            max_amount = packet['remain_amount'] / packet['remain_count'] * 2
            amount = round(random.uniform(0.01, min(max_amount, packet['remain_amount'])), 2)
        c.execute('UPDATE red_packets SET remain_amount = remain_amount - ?, remain_count = remain_count - 1 WHERE id = ?', (amount, packet_id))
        c.execute('INSERT INTO red_packet_claims (packet_id, user_id, amount) VALUES (?, ?, ?)', (packet_id, user_id, amount))
        conn.commit()
    user = get_user_data(user_id)
    user['balance'] += amount
    save_user_data(user_id, user)
    await query.edit_message_text(f"🧧 抢到 {amount:.2f}元！\n💰 余额: {user['balance']:.2f}元")

async def button(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    user = get_user_data(user_id)
    data = query.data

    if data.startswith('redpacket_'):
        await claim_red_packet(update, context)
        return

    if data == "back":
        text, kb = get_main_menu(user)
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))
        return

    if data == "play":
        if user['balance'] < 10:
            await query.edit_message_text("余额不足，最低10元\n去签到领1.88元")
            return
        kb = [[InlineKeyboardButton("10", callback_data="bet_10"), InlineKeyboardButton("50", callback_data="bet_50")],
              [InlineKeyboardButton("100", callback_data="bet_100"), InlineKeyboardButton("500", callback_data="bet_500")],
              [InlineKeyboardButton("🔙 返回", callback_data="back")]]
        await query.edit_message_text(f"下注金额\n💰 余额: {user['balance']:.2f}元", reply_markup=InlineKeyboardMarkup(kb))
        return

    if data.startswith("bet_"):
        bet = float(data.split("_")[1])
        if bet > user['balance']:
            await query.edit_message_text("余额不足")
            return
        user['balance'] -= bet
        deck = shuffle_cards()
        p_hand = deck[:5]
        d_hand = deck[5:10]
        p_name, p_mult = calc_niu(p_hand)
        d_name, d_mult = calc_niu(d_hand)
        result_text = ""
        win_amount = 0
        if p_mult > d_mult:
            win_amount = bet * p_mult
            user['balance'] += win_amount
            user['wins'] += 1
            user['profit'] += win_amount - bet
            user['daily_profit'] += win_amount - bet
            result_text = f"🎉 赢了！+{win_amount:.0f}元"
        elif p_mult < d_mult:
            user['losses'] += 1
            user['profit'] -= bet
            user['daily_profit'] -= bet
            result_text = f"💔 输了！-{bet:.0f}元"
        else:
            user['balance'] += bet
            result_text = "🤝 平局"
        user['total_games'] += 1
        user['turnover'] += bet
        rebate_rate = get_rebate_rate(user['turnover'])
        rebate_amount = bet * rebate_rate
        user['rebate'] = user.get('rebate', 0) + rebate_amount
        save_user_data(user_id, user)
        text = f"🎴 你: {show_cards(p_hand)} → {p_name}\n🎴 庄: {show_cards(d_hand)} → {d_name}\n{result_text}\n💰 余额: {user['balance']:.2f}元"
        kb = [[InlineKeyboardButton("🔄 再来", callback_data="play")], [InlineKeyboardButton("🔙 返回", callback_data="back")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))
        return

    if data == "wallet":
        text = f"💰 钱包\n余额: {user['balance']:.2f}元\n盈利: {user['profit']:.2f}元\n总流水: {user['turnover']:.2f}元\n未领取返佣: {user.get('rebate', 0):.2f}元"
        kb = [[InlineKeyboardButton("🔙 返回", callback_data="back")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))
        return

    if data == "stats":
        wr = (user['wins'] / user['total_games'] * 100) if user['total_games'] > 0 else 0
        text = f"📈 战绩\n总局: {user['total_games']}\n胜: {user['wins']} 负: {user['losses']}\n胜率: {wr:.1f}%\n总盈利: {user['profit']:.2f}元"
        kb = [[InlineKeyboardButton("🔙 返回", callback_data="back")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))
        return

    if data == "signin":
        today = datetime.now().strftime("%Y-%m-%d")
        if user.get('last_signin') == today:
            kb = [[InlineKeyboardButton("🔙 返回", callback_data="back")]]
            await query.edit_message_text(f"今天已签到！连续: {user.get('signin_streak', 0)}天", reply_markup=InlineKeyboardMarkup(kb))
            return
        reward = 1.88
        user['balance'] += reward
        user['last_signin'] = today
        user['signin_streak'] = user.get('signin_streak', 0) + 1
        save_user_data(user_id, user)
        kb = [[InlineKeyboardButton("🔙 返回", callback_data="back")]]
        text = f"✅ 签到成功！+{reward:.2f}元\n连续: {user['signin_streak']}天\n💰 余额: {user['balance']:.2f}元"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))
        return

    if data == "claim_rebate":
        rebate = user.get('rebate', 0)
        if rebate <= 0:
            await query.edit_message_text("没有可领取的返佣")
            return
        user['balance'] += rebate
        user['claimed_rebate'] = user.get('claimed_rebate', 0) + rebate
        user['rebate'] = 0
        save_user_data(user_id, user)
        text = f"✅ 领取返佣 {rebate:.2f}元\n💰 余额: {user['balance']:.2f}元"
        kb = [[InlineKeyboardButton("🔙 返回", callback_data="back")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))
        return

    if data == "rank":
        kb = [[InlineKeyboardButton("📅 日榜", callback_data="rank_daily")],
              [InlineKeyboardButton("📆 周榜", callback_data="rank_weekly")],
              [InlineKeyboardButton("📊 月榜", callback_data="rank_monthly")],
              [InlineKeyboardButton("🔙 返回", callback_data="back")]]
        await query.edit_message_text("🏆 排行榜", reply_markup=InlineKeyboardMarkup(kb))
        return

    if data.startswith("rank_"):
        period = data.split("_")[1]
        names = {'daily': '日榜', 'weekly': '周榜', 'monthly': '月榜'}
        rankings = get_top_users(period)
        text = f"🏆 {names.get(period, '')}\n\n"
        if rankings:
            medals = ['🥇', '🥈', '🥉']
            for i, row in enumerate(rankings, 1):
                medal = medals[i-1] if i <= 3 else f"{i}."
                text += f"{medal} {row['username']}  {row['profit']:+.2f}元\n"
        else:
            text += "暂无数据"
        kb = [[InlineKeyboardButton("🔄 刷新", callback_data=f"rank_{period}")], [InlineKeyboardButton("🔙 返回", callback_data="rank")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))
        return

class WebHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, format, *args):
        pass

def run_web_server():
    try:
        server = HTTPServer(('0.0.0.0', int(os.environ.get('PORT', 8080))), WebHandler)
        server.serve_forever()
    except:
        pass

def reset_daily_ranking():
    with db_lock, get_db() as conn:
        c = conn.cursor()
        c.execute('UPDATE users SET daily_profit = 0')
        conn.commit()
    print(f"📊 排行榜已刷新 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

def schedule_daily_reset():
    schedule.every().day.at("12:00").do(reset_daily_ranking)
    while True:
        schedule.run_pending()
        time.sleep(60)

def main():
    init_db()
    threading.Thread(target=run_web_server, daemon=True).start()
    threading.Thread(target=schedule_daily_reset, daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={WAITING_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_username)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("setname", setname))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, handle_group_message))
    print("=" * 50)
    print("🤖 皇家至尊娱乐城 Bot 已启动！")
    print("📊 使用SQLite数据库")
    print("👥 支持群聊模式")
    print("=" * 50)
    print("\n📌 群聊命令:")
    print("  /xz 100     - 下注")
    print("  /phb        - 排行榜")
    print("  /hb 1000 5  - 发红包")
    print("=" * 50)
    app.run_polling()

if __name__ == "__main__":
    main()
