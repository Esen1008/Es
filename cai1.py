import os
import random
import sqlite3
import json
import re
from datetime import datetime, timedelta

# ========== 配置 ==========
TOKEN = os.environ.get("8859045300:AAGdLExTMf6cpGnJlDPJrz3GJ3VVlE1_51M", "8859045300:AAGdLExTMf6cpGnJlDPJrz3GJ3VVlE1_51M")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "8446215864"))
客服 = "@xiaoyun_1210"

# ========== 导入 telegram ==========
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters

# ========== 游戏开关 ==========
game_enabled = True
limit_enabled = False
limit_percent = 0

# ========== 数据库初始化 ==========
def init_db():
    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT UNIQUE,
        balance INTEGER DEFAULT 0,
        total_water INTEGER DEFAULT 0,
        month_water INTEGER DEFAULT 0,
        vip_level INTEGER DEFAULT 0,
        vip_claimed TEXT DEFAULT '[]',
        last_period_result TEXT DEFAULT '',
        notifications_on INTEGER DEFAULT 1,
        rebate_claimed TEXT DEFAULT '[]',
        signin_day INTEGER DEFAULT 0,
        signin_last TEXT DEFAULT '',
        signin_claimed TEXT DEFAULT '[]',
        total_recharge INTEGER DEFAULT 0,
        withdrawable_water INTEGER DEFAULT 0,
        first_recharge_claimed TEXT DEFAULT '[]',
        rebate_claimed_today INTEGER DEFAULT 0,
        rebate_last_date TEXT DEFAULT '',
        username_set INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS bet_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        period INTEGER,
        bet_type TEXT,
        amount INTEGER,
        win_amount INTEGER,
        result_number INTEGER,
        bet_time TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS period_results (
        period INTEGER PRIMARY KEY,
        result INTEGER,
        result_time TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS system_state (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')
    c.execute('INSERT OR IGNORE INTO system_state (key, value) VALUES ("current_period", "1")')
    c.execute('''CREATE TABLE IF NOT EXISTS withdraw_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount INTEGER,
        method TEXT,
        account_info TEXT,
        status TEXT DEFAULT 'pending',
        request_time TEXT,
        type TEXT DEFAULT '提现'
    )''')
    conn.commit()
    conn.close()

def get_saved_period():
    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    c.execute('SELECT value FROM system_state WHERE key="current_period"')
    row = c.fetchone()
    conn.close()
    return int(row[0]) if row else 1

def save_period(period):
    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    c.execute('UPDATE system_state SET value=? WHERE key="current_period"', (str(period),))
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    c.execute('SELECT balance, total_water, month_water, vip_level, vip_claimed, last_period_result, notifications_on, rebate_claimed, signin_day, signin_last, signin_claimed, total_recharge, withdrawable_water, first_recharge_claimed, rebate_claimed_today, rebate_last_date, username, username_set FROM users WHERE user_id=?', (user_id,))
    row = c.fetchone()
    if row:
        return {
            'balance': row[0],
            'total_water': row[1],
            'month_water': row[2],
            'vip_level': row[3],
            'vip_claimed': json.loads(row[4]),
            'last_period_result': row[5] or '',
            'notifications_on': row[6] if row[6] is not None else 1,
            'rebate_claimed': json.loads(row[7]) if row[7] else [],
            'signin_day': row[8] or 0,
            'signin_last': row[9] or '',
            'signin_claimed': json.loads(row[10]) if row[10] else [],
            'total_recharge': row[11] or 0,
            'withdrawable_water': row[12] or 0,
            'first_recharge_claimed': json.loads(row[13]) if row[13] else [],
            'rebate_claimed_today': row[14] or 0,
            'rebate_last_date': row[15] or '',
            'username': row[16],
            'username_set': row[17] or 0
        }
    c.execute('INSERT INTO users (user_id, vip_claimed, last_period_result, notifications_on, rebate_claimed, signin_claimed, first_recharge_claimed, rebate_claimed_today, rebate_last_date, username_set) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', 
              (user_id, '[]', '', 1, '[]', '[]', '[]', 0, '', 0))
    conn.commit()
    conn.close()
    return {'balance': 0, 'total_water': 0, 'month_water': 0, 'vip_level': 0, 'vip_claimed': [], 'last_period_result': '', 'notifications_on': 1, 'rebate_claimed': [], 'signin_day': 0, 'signin_last': '', 'signin_claimed': [], 'total_recharge': 0, 'withdrawable_water': 0, 'first_recharge_claimed': [], 'rebate_claimed_today': 0, 'rebate_last_date': '', 'username': None, 'username_set': 0}

def update_user(user_id, **kwargs):
    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    fields = []
    values = []
    for key, val in kwargs.items():
        if key in ['vip_claimed', 'rebate_claimed', 'signin_claimed', 'first_recharge_claimed']:
            val = json.dumps(val)
        fields.append(f'{key}=?')
        values.append(val)
    values.append(user_id)
    c.execute(f'UPDATE users SET {", ".join(fields)} WHERE user_id=?', values)
    conn.commit()
    conn.close()

def add_balance(user_id, amount):
    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    c.execute('UPDATE users SET balance = balance + ? WHERE user_id=?', (amount, user_id))
    conn.commit()
    conn.close()

def get_user_by_username(username):
    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    c.execute('SELECT user_id FROM users WHERE username=?', (username,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def get_username(user_id):
    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    c.execute('SELECT username FROM users WHERE user_id=?', (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def save_bet_history(user_id, period, bet_type, amount, win_amount, result_number):
    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    bet_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute('''INSERT INTO bet_history (user_id, period, bet_type, amount, win_amount, result_number, bet_time)
                 VALUES (?, ?, ?, ?, ?, ?, ?)''',
              (user_id, period, bet_type, amount, win_amount, result_number, bet_time))
    c.execute('SELECT COUNT(*) FROM bet_history WHERE user_id=?', (user_id,))
    count = c.fetchone()[0]
    if count > 100:
        delete_count = count - 100
        c.execute('''DELETE FROM bet_history 
                     WHERE user_id=? AND id IN (
                         SELECT id FROM bet_history 
                         WHERE user_id=? 
                         ORDER BY id ASC 
                         LIMIT ?
                     )''', (user_id, user_id, delete_count))
    conn.commit()
    conn.close()

def save_period_result(period, result):
    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    result_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute('INSERT OR REPLACE INTO period_results (period, result, result_time) VALUES (?, ?, ?)',
              (period, result, result_time))
    c.execute('SELECT COUNT(*) FROM period_results')
    count = c.fetchone()[0]
    if count > 100:
        c.execute('''DELETE FROM period_results 
                     WHERE period IN (
                         SELECT period FROM period_results 
                         ORDER BY period ASC 
                         LIMIT ?
                     )''', (count - 100,))
    conn.commit()
    conn.close()

def get_period_results(limit=100):
    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    c.execute('''SELECT period, result, result_time 
                 FROM period_results 
                 ORDER BY period DESC 
                 LIMIT ?''', (limit,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_bet_history(user_id, limit=10):
    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    c.execute('''SELECT period, bet_type, amount, win_amount, result_number, bet_time
                 FROM bet_history 
                 WHERE user_id=? 
                 ORDER BY period DESC, id DESC 
                 LIMIT ?''', (user_id, limit))
    rows = c.fetchall()
    conn.close()
    return rows

def get_all_bet_history(user_id):
    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    c.execute('''SELECT period, bet_type, amount, win_amount, result_number, bet_time
                 FROM bet_history 
                 WHERE user_id=? 
                 ORDER BY period DESC, id DESC''', (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_vip_config():
    return {
        0: {'water': 0.003, 'monthly': 0, 'upgrade': 0, 'keep': 0, 'reward': 0},
        1: {'water': 0.004, 'monthly': 30, 'upgrade': 10000, 'keep': 3000, 'reward': 50},
        2: {'water': 0.0055, 'monthly': 80, 'upgrade': 30000, 'keep': 6000, 'reward': 150},
        3: {'water': 0.007, 'monthly': 180, 'upgrade': 80000, 'keep': 12000, 'reward': 400},
        4: {'water': 0.009, 'monthly': 400, 'upgrade': 200000, 'keep': 25000, 'reward': 900},
        5: {'water': 0.011, 'monthly': 900, 'upgrade': 500000, 'keep': 50000, 'reward': 1800},
        6: {'water': 0.0135, 'monthly': 1800, 'upgrade': 1000000, 'keep': 80000, 'reward': 3500},
        7: {'water': 0.0165, 'monthly': 3500, 'upgrade': 2000000, 'keep': 120000, 'reward': 6500},
        8: {'water': 0.02, 'monthly': 6500, 'upgrade': 4000000, 'keep': 180000, 'reward': 12000},
        9: {'water': 0.0245, 'monthly': 11000, 'upgrade': 7000000, 'keep': 260000, 'reward': 20000},
        10: {'water': 0.03, 'monthly': 18000, 'upgrade': 10000000, 'keep': 350000, 'reward': 35000},
    }

# ========== 游戏状态 ==========
current_period = 1
betting_open = True
bets = {}

def get_result_text(number):
    return '大' if number >= 4 else '小'

def check_vip_upgrade(user_id):
    user = get_user(user_id)
    total = user['total_water']
    current_vip = user['vip_level']
    vip_config = get_vip_config()
    new_vip = current_vip
    for level in range(10, current_vip, -1):
        if total >= vip_config[level]['upgrade']:
            new_vip = level
            break
    if new_vip > current_vip:
        claimed = user['vip_claimed']
        rewards = []
        for lv in range(current_vip + 1, new_vip + 1):
            if str(lv) not in claimed:
                rewards.append(lv)
        update_user(user_id, vip_level=new_vip)
        return new_vip, rewards
    return current_vip, []

def get_bet_result_text(user_id, period, result_number):
    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    c.execute('''SELECT bet_type, amount, win_amount 
                 FROM bet_history 
                 WHERE user_id=? AND period=? 
                 ORDER BY id ASC''', (user_id, period))
    rows = c.fetchall()
    conn.close()

    if not rows:
        return None

    text = f"🎲 第{period}期 开奖结果：{result_number}（{get_result_text(result_number)}）\n\n"
    text += "你的下注：\n"
    total_win = 0
    for bet_type, amount, win_amount in rows:
        if win_amount > 0:
            text += f"✅ 押{bet_type} {amount}积分 → 赢 +{win_amount}积分\n"
            total_win += win_amount
        else:
            text += f"❌ 押{bet_type} {amount}积分 → 输 {win_amount}积分\n"
            total_win += win_amount
    text += f"\n本局净赚：{'+' if total_win > 0 else ''}{total_win}积分"
    user = get_user(user_id)
    text += f"\n当前余额：{user['balance']} 积分"
    return text

# ========== 真实控盘逻辑 ==========
def get_controlled_result():
    """动态控盘，让大/小比例长期稳定在50/50，玩家无法察觉"""
    global bets

    # 1. 统计当前下注倾向
    big_count = 0
    small_count = 0
    for uid, user_bets in bets.items():
        for bet in user_bets:
            if bet['type'] == '大':
                big_count += bet['amount']
            elif bet['type'] == '小':
                small_count += bet['amount']

    total_bet = big_count + small_count
    if total_bet == 0:
        # 没人下注大小，真随机
        return random.randint(1, 6)

    # 2. 获取最近100期开奖结果
    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    c.execute('SELECT result FROM period_results ORDER BY period DESC LIMIT 100')
    rows = c.fetchall()
    conn.close()

    if rows:
        recent = [r[0] for r in rows]
        big_recent = sum(1 for r in recent if r >= 4)
        recent_big_ratio = big_recent / len(recent)
    else:
        recent_big_ratio = 0.5

    # 3. 计算开大概率（核心算法）
    target = 0.5
    history_correction = (recent_big_ratio - target) * 0.3
    bet_ratio = big_count / total_bet
    bet_correction = (bet_ratio - target) * 0.1

    final_big_prob = target - history_correction - bet_correction
    final_big_prob = max(0.45, min(0.55, final_big_prob))

    # 4. 开奖
    if random.random() < final_big_prob:
        return random.choice([4, 5, 6])
    else:
        return random.choice([1, 2, 3])

# ========== 检查用户名 ==========
def check_username_valid(username):
    return re.match(r'^[a-zA-Z0-9]{3,20}$', username) is not None

def is_username_taken(username):
    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    c.execute('SELECT 1 FROM users WHERE username=?', (username,))
    row = c.fetchone()
    conn.close()
    return row is not None

# ========== 显示主菜单 ==========
def show_menu(chat_id, context):
    global current_period, betting_open, game_enabled, limit_enabled, limit_percent

    user = get_user(chat_id)
    if user.get('username_set', 0) == 0:
        context.bot.send_message(chat_id, "请先设置用户名：\n仅限英文+数字，3-20位")
        return

    notif_status = "🟢 已开启" if user.get('notifications_on', 1) else "🔴 已关闭"

    keyboard = [
        [InlineKeyboardButton("🎲 开始下注", callback_data='bet_guide')],
        [InlineKeyboardButton("💰 钱包", callback_data='wallet')],
        [InlineKeyboardButton("👑 VIP等级", callback_data='vip')],
        [InlineKeyboardButton("📊 开奖记录", callback_data='global_history')],
        [InlineKeyboardButton("🎁 VIP福利专区", callback_data='vip_rewards')],
        [InlineKeyboardButton("📋 转账记录", callback_data='transfer_history')],
        [InlineKeyboardButton("🔥 限时福利", callback_data='limited_offers')],
        [InlineKeyboardButton("⚠️ 风控规则", callback_data='rules')],
    ]

    if user.get('notifications_on', 1):
        keyboard.append([InlineKeyboardButton("🔕 关闭播报", callback_data='toggle_notif')])
    else:
        keyboard.append([InlineKeyboardButton("🔔 开启播报", callback_data='toggle_notif')])

    if chat_id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("⚙️ 管理面板", callback_data='admin')])

    status_text = "🟢 运行中" if game_enabled else "🔴 已关闭"

    text = f"🎰 欢迎来到骰子赌场！\n"
    text += f"当前第 {current_period} 期\n"
    text += f"{'📝 下注中' if betting_open else '🔒 已封盘'}\n"
    text += f"游戏状态：{status_text}\n"
    text += f"播报状态：{notif_status}"
    if limit_enabled:
        text += f"\n🔥 限时福利：充值+{limit_percent}%"
    text += f"\n\n使用 /bet 金额 类型 下注\n"
    text += f"示例：/bet 100 大\n"
    text += f"      /bet 50 大 1\n"
    text += f"      /bet 100 1 2 3 4 5 6"

    context.bot.send_message(chat_id, text, reply_markup=InlineKeyboardMarkup(keyboard))

# ========== 注册用户名 ==========
def handle_username_input(update, context):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    user = get_user(user_id)
    if user.get('username_set', 0) == 1:
        return

    if not check_username_valid(text):
        update.message.reply_text("❌ 用户名格式错误\n仅限英文+数字，3-20位\n请输入其他用户名：")
        return

    if is_username_taken(text):
        update.message.reply_text(f"❌ 用户名 {text} 已被占用\n请输入其他用户名：")
        return

    update_user(user_id, username=text, username_set=1)
    update.message.reply_text(f"✅ 注册成功！\n用户名：{text}\n\n欢迎来到骰子赌场！")
    show_menu(user_id, context)

# ========== 处理提现金额输入 ==========
def handle_withdraw_amount(update, context):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if 'withdraw_method' not in context.user_data:
        return

    try:
        amount = int(text)
        if amount <= 0:
            update.message.reply_text("❌ 请输入正整数的金额")
            return

        user = get_user(user_id)
        if amount > user['balance']:
            update.message.reply_text(f"❌ 余额不足！当前余额：{user['balance']} 积分")
            return

        context.user_data['withdraw_amount'] = amount

        method = context.user_data.get('withdraw_method')
        keyboard = [
            [InlineKeyboardButton("✅ 确认提现", callback_data='withdraw_confirm')],
            [InlineKeyboardButton("🔙 取消", callback_data='withdraw')]
        ]
        update.message.reply_text(
            f"📋 提现确认\n\n"
            f"方式：{method}\n"
            f"金额：{amount} 积分\n\n"
            f"点击确认提交申请",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except:
        update.message.reply_text("❌ 请输入有效的整数金额")

# ========== 命令 ==========
def start(update, context):
    chat_id = update.effective_chat.id
    user = get_user(chat_id)
    if user.get('username_set', 0) == 0:
        update.message.reply_text("🎰 欢迎来到骰子赌场！\n\n请先设置你的用户名（仅限英文+数字，3-20位）：\n\n示例：xiaoyun123")
        return
    show_menu(chat_id, context)

def bet_command(update, context):
    global current_period, betting_open, game_enabled

    user_id = update.effective_user.id
    args = context.args

    user = get_user(user_id)
    if user.get('username_set', 0) == 0:
        update.message.reply_text("请先设置用户名：/start")
        return

    if not game_enabled:
        update.message.reply_text("🔴 游戏已关闭，请联系管理员开启")
        return

    if not betting_open:
        update.message.reply_text("🔒 当前已封盘，请等待下一期")
        return

    # 检查最后10秒锁盘
    now = datetime.now()
    seconds = now.second
    remaining = 60 - seconds
    if remaining <= 10:
        update.message.reply_text("🔒 已封盘，最后10秒不可下注，请等待下一期")
        return

    if len(args) < 2:
        update.message.reply_text(
            "❌ 用法：/bet 金额 类型1 类型2 ...\n"
            "示例：/bet 100 大\n"
            "      /bet 50 大 1\n"
            "      /bet 100 1 2 3 4 5 6\n"
            "类型：大 / 小 / 1-6"
        )
        return

    try:
        amount = int(args[0])
    except:
        update.message.reply_text("❌ 金额必须是数字")
        return

    if amount < 1:
        update.message.reply_text("❌ 最低下注1积分")
        return

    types = args[1:]
    if '大' in types and '小' in types:
        update.message.reply_text("❌ 不能同时押大和小（对冲）")
        return

    valid_types = ['大', '小', '1', '2', '3', '4', '5', '6']
    for t in types:
        if t not in valid_types:
            update.message.reply_text(f"❌ 无效类型：{t}")
            return

    user = get_user(user_id)
    total_bet = amount * len(types)
    if user['balance'] < total_bet:
        update.message.reply_text(f"❌ 余额不足！需要 {total_bet} 积分，当前余额：{user['balance']} 积分")
        return

    add_balance(user_id, -total_bet)
    if user_id not in bets:
        bets[user_id] = []
    for t in types:
        bets[user_id].append({'type': t, 'amount': amount})

    update_user(user_id, last_period_result='', withdrawable_water=user['withdrawable_water'] + total_bet)

    types_text = '、'.join(types)
    keyboard = [
        [InlineKeyboardButton("🎲 继续下注", callback_data='bet_guide')],
        [InlineKeyboardButton("📊 开奖记录", callback_data='global_history')],
        [InlineKeyboardButton("🏠 返回主菜单", callback_data='back')]
    ]
    update.message.reply_text(
        f"✅ 下注成功！\n"
        f"第{current_period}期 | 押{types_text} | 各{amount}积分\n"
        f"总下注：{total_bet}积分\n"
        f"当前余额：{user['balance'] - total_bet} 积分\n"
        f"\n⏳ 等待开奖...",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ========== button_handler ==========
def button_handler(update, context):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    data = query.data

    # ---------- 切换播报 ----------
    if data == 'toggle_notif':
        user = get_user(user_id)
        current = user.get('notifications_on', 1)
        new_status = 0 if current else 1
        update_user(user_id, notifications_on=new_status)
        status_text = "🟢 已开启" if new_status else "🔴 已关闭"
        keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='back')]]
        query.edit_message_text(
            f"🔔 播报{status_text}\n\n"
            f"开启后你会收到每期开奖通知\n"
            f"关闭后不会收到任何播报",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # ---------- 开始下注 ----------
    if data == 'bet_guide':
        user = get_user(user_id)

        now = datetime.now()
        seconds = now.second
        remaining = 60 - seconds
        if remaining < 0:
            remaining = 0

        is_locked = remaining <= 10
        status_text = "🔒 已封盘，等待开奖..." if is_locked else f"⏳ 剩余时间：{remaining}秒"

        text = f"🎲 第 {current_period} 期\n"
        text += f"{status_text}\n\n"

        if is_locked:
            text += "⚠️ 下注已锁定，请等待下一期\n\n"
        else:
            text += "请使用命令下注：/bet 金额 类型1 类型2 ...\n\n"
            text += "类型：大 / 小 / 1-6\n"
            text += "示例：/bet 100 大  /bet 50 大 1\n\n"

        if user.get('last_period_result', '') and betting_open and not is_locked:
            text += f"📋 上一期结果：\n{user['last_period_result']}\n\n"
            update_user(user_id, last_period_result='')

        text += f"当前余额：{user['balance']} 积分"

        keyboard = []
        if not is_locked:
            keyboard.append([InlineKeyboardButton("🏠 返回主菜单", callback_data='back')])
        else:
            keyboard.append([InlineKeyboardButton("🔄 刷新状态", callback_data='bet_guide')])
            keyboard.append([InlineKeyboardButton("🏠 返回主菜单", callback_data='back')])

        query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # ---------- 全局开奖记录 ----------
    if data == 'global_history':
        rows = get_period_results(100)
        if not rows:
            keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='back')]]
            query.edit_message_text("📊 暂无开奖记录", reply_markup=InlineKeyboardMarkup(keyboard))
            return
        text = "📊 最近100期开奖记录\n\n"
        for period, result, result_time in rows:
            result_text = get_result_text(result)
            time_str = result_time.split(' ')[1] if ' ' in result_time else result_time
            text += f"第{period}期：{result}（{result_text}）| {time_str}\n"
        keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='back')]]
        query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # ---------- 转账记录 ----------
    if data == 'transfer_history':
        keyboard = [
            [InlineKeyboardButton("🎲 下注记录", callback_data='history')],
            [InlineKeyboardButton("💳 充值/提现记录", callback_data='fund_history')],
            [InlineKeyboardButton("🔙 返回", callback_data='back')]
        ]
        query.edit_message_text("📋 转账记录\n\n请选择查看：", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # ---------- 充值/提现记录 ----------
    if data == 'fund_history':
        conn = sqlite3.connect('data.db')
        c = conn.cursor()
        c.execute('''SELECT amount, method, status, request_time, type 
                     FROM withdraw_requests 
                     WHERE user_id=? 
                     ORDER BY request_time DESC 
                     LIMIT 20''', (user_id,))
        rows = c.fetchall()
        conn.close()

        if not rows:
            keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='transfer_history')]]
            query.edit_message_text("📋 暂无充值/提现记录", reply_markup=InlineKeyboardMarkup(keyboard))
            return

        text = "💳 充值/提现记录\n\n"
        for amount, method, status, request_time, req_type in rows:
            time_str = request_time.split(' ')[1] if ' ' in request_time else request_time
            status_icon = "✅" if status == 'approved' else "❌" if status == 'rejected' else "⏳"
            type_icon = "📥" if req_type == '充值' else "📤"
            text += f"{type_icon} {req_type} {amount}积分 | {method}\n"
            text += f"   {time_str} {status_icon} {status}\n\n"

        keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='transfer_history')]]
        query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # ---------- 下注记录 ----------
    if data == 'history':
        history = get_bet_history(user_id, 10)
        if not history:
            keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='transfer_history')]]
            query.edit_message_text("📋 暂无下注记录", reply_markup=InlineKeyboardMarkup(keyboard))
            return
        text = "📋 我的下注记录（最近10条）\n\n"
        last_period = None
        for period, bet_type, amount, win_amount, result_number, bet_time in history:
            if period != last_period:
                last_period = period
                result_text = get_result_text(result_number)
                time_str = bet_time.split(' ')[1] if ' ' in bet_time else bet_time
                text += f"\n第{period}期 | {result_number}（{result_text}）| {time_str}\n"
            if win_amount > 0:
                text += f"  • {bet_type} ✅ +{win_amount}\n"
            else:
                text += f"  • {bet_type} ❌ {win_amount}\n"
        keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='transfer_history')]]
        query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # ---------- 钱包（包含领取反水） ----------
    if data == 'wallet':
        user = get_user(user_id)
        recharge_needed = user['total_recharge']
        water_done = user['withdrawable_water']
        can_withdraw = water_done >= recharge_needed and recharge_needed > 0

        vip_config = get_vip_config()
        config = vip_config[user['vip_level']]

        today = datetime.now().strftime('%Y-%m-%d')
        rebate_claimed_today = user.get('rebate_claimed_today', 0)
        rebate_last_date = user.get('rebate_last_date', '')

        if rebate_last_date != today:
            rebate_claimed_today = 0
            update_user(user_id, rebate_claimed_today=0, rebate_last_date=today)

        total_rebate = int(user['month_water'] * config['water'])
        available_rebate = total_rebate - rebate_claimed_today
        if available_rebate < 0:
            available_rebate = 0

        text = f"💰 我的钱包\n\n"
        text += f"余额：{user['balance']} 积分\n"
        text += f"可提现：{user['balance'] if can_withdraw else 0} 积分\n"
        text += f"流水进度：{water_done} / {recharge_needed}"
        if recharge_needed == 0:
            text += "（无需刷流水）"
        elif water_done >= recharge_needed:
            text += " ✅ 已达标"
        else:
            text += f"（还需 {recharge_needed - water_done} 积分）"

        text += f"\n\n━━━ 🎁 领取反水 ━━━\n"
        text += f"反水比例：{config['water']*100}%\n"
        text += f"本月流水：{user['month_water']}\n"
        text += f"已领取反水：{rebate_claimed_today}\n"
        text += f"可领取反水：{available_rebate} 积分"

        keyboard = []
        if available_rebate > 0:
            keyboard.append([InlineKeyboardButton("📥 领取反水", callback_data='claim_rebate')])
        keyboard.append([InlineKeyboardButton("💳 充值", callback_data='recharge')])
        keyboard.append([InlineKeyboardButton("🏦 提现", callback_data='withdraw')])
        keyboard.append([InlineKeyboardButton("🔙 返回", callback_data='back')])
        query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # ---------- 领取反水 ----------
    if data == 'claim_rebate':
        user = get_user(user_id)
        vip_config = get_vip_config()
        config = vip_config[user['vip_level']]

        today = datetime.now().strftime('%Y-%m-%d')
        rebate_claimed_today = user.get('rebate_claimed_today', 0)
        rebate_last_date = user.get('rebate_last_date', '')

        if rebate_last_date != today:
            rebate_claimed_today = 0
            update_user(user_id, rebate_claimed_today=0, rebate_last_date=today)

        total_rebate = int(user['month_water'] * config['water'])
        available_rebate = total_rebate - rebate_claimed_today

        if available_rebate <= 0:
            keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='wallet')]]
            query.edit_message_text("❌ 暂无反水可领取", reply_markup=InlineKeyboardMarkup(keyboard))
            return

        add_balance(user_id, available_rebate)
        update_user(user_id, rebate_claimed_today=rebate_claimed_today + available_rebate, rebate_last_date=today)

        keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='wallet')]]
        query.edit_message_text(
            f"🎉 领取成功！\n"
            f"+{available_rebate} 积分\n"
            f"💰 新余额：{get_user(user_id)['balance']} 积分",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # ---------- 充值 ----------
    if data == 'recharge':
        keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='wallet')]]
        text = f"💳 充值中心\n\n📞 请联系客服充值\n客服：{客服}\n\n充值流程：\n1. 联系客服 {客服}\n2. 告知充值金额和支付方式\n3. 客服确认后，积分自动到账"
        if limit_enabled:
            text += f"\n\n🔥 今日限时福利：充值额外+{limit_percent}%！\n（联系客服时告知，客服手动添加）"
        query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # ---------- 提现 ----------
    if data == 'withdraw':
        user = get_user(user_id)
        recharge_needed = user['total_recharge']
        water_done = user['withdrawable_water']
        can_withdraw = water_done >= recharge_needed and recharge_needed > 0

        if not can_withdraw:
            keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='wallet')]]
            text = "❌ 流水未达标\n\n"
            text += f"流水进度：{water_done} / {recharge_needed}"
            if recharge_needed == 0:
                text += "\n你还没有充值记录，无需刷流水"
            query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            return

        if user['balance'] <= 0:
            keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='wallet')]]
            query.edit_message_text("❌ 余额为0，无法提现", reply_markup=InlineKeyboardMarkup(keyboard))
            return

        keyboard = [
            [InlineKeyboardButton("💎 USDT", callback_data='withdraw_usdt')],
            [InlineKeyboardButton("📱 TNG", callback_data='withdraw_tng')],
            [InlineKeyboardButton("🏦 银行转账", callback_data='withdraw_bank')],
            [InlineKeyboardButton("🛍️ Shopee Pay", callback_data='withdraw_shopeepay')],
            [InlineKeyboardButton("🔙 返回", callback_data='wallet')]
        ]
        text = f"🏦 提现中心\n\n请选择提现方式：\n\n可提现余额：{user['balance']} 积分"
        query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data.startswith('withdraw_'):
        method_map = {
            'withdraw_usdt': 'USDT',
            'withdraw_tng': 'TNG',
            'withdraw_bank': '银行转账',
            'withdraw_shopeepay': 'Shopee Pay'
        }
        method = method_map.get(data, '未知')
        user = get_user(user_id)
        keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='withdraw')]]
        text = f"🏦 提现申请\n\n"
        text += f"提现方式：{method}\n"
        text += f"可提现余额：{user['balance']} 积分\n\n"
        text += "请回复提现金额（整数）："
        context.user_data['withdraw_method'] = method
        context.user_data['withdraw_user_id'] = user_id
        query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # ---------- 处理提现确认 ----------
    if data == 'withdraw_confirm':
        user_id = context.user_data.get('withdraw_user_id')
        method = context.user_data.get('withdraw_method')
        amount = context.user_data.get('withdraw_amount')
        if not user_id or not method or not amount:
            keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='back')]]
            query.edit_message_text("❌ 提现会话已过期，请重新操作", reply_markup=InlineKeyboardMarkup(keyboard))
            return
        user = get_user(user_id)
        if amount > user['balance']:
            keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='withdraw')]]
            query.edit_message_text(f"❌ 余额不足！当前余额：{user['balance']} 积分", reply_markup=InlineKeyboardMarkup(keyboard))
            return
        conn = sqlite3.connect('data.db')
        c = conn.cursor()
        request_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        c.execute('''INSERT INTO withdraw_requests (user_id, amount, method, account_info, status, request_time, type)
                     VALUES (?, ?, ?, ?, ?, ?, ?)''',
                  (user_id, amount, method, '', 'pending', request_time, '提现'))
        conn.commit()
        conn.close()
        add_balance(user_id, -amount)
        keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='back')]]
        query.edit_message_text(
            f"✅ 提现申请已提交！\n\n"
            f"金额：{amount} 积分\n"
            f"方式：{method}\n"
            f"预计24小时内到账",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        context.user_data.clear()
        return

    # ---------- VIP等级 ----------
    if data == 'vip':
        user = get_user(user_id)
        vip_config = get_vip_config()

        text = "👑 VIP等级详情\n\n"
        text += f"当前等级：VIP{user['vip_level']}\n"
        text += f"累计流水：{user['total_water']}\n\n"
        text += "━━━ VIP 0-10 要求与福利 ━━━\n\n"

        for lv in range(0, 11):
            cfg = vip_config[lv]
            if lv == 0:
                text += f"VIP0：初始\n"
            else:
                text += f"VIP{lv}：升级需 {cfg['upgrade']:,} 流水\n"
            text += f"  ├ 保级：{cfg['keep']:,} 流水/月\n"
            text += f"  ├ 反水：{cfg['water']*100}%\n"
            text += f"  ├ 每月福利：{cfg['monthly']} 积分\n"
            text += f"  └ 升级奖励：{cfg['reward']} 积分（一次性）\n\n"

        keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='back')]]
        query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # ---------- VIP福利专区 ----------
    if data == 'vip_rewards':
        user = get_user(user_id)
        vip_config = get_vip_config()
        config = vip_config[user['vip_level']]
        claimed = user['vip_claimed']
        text = "🎁 VIP福利专区\n\n"
        text += f"👑 当前等级：VIP{user['vip_level']}\n"
        text += f"📊 累计流水：{user['total_water']}\n"
        text += f"💰 反水比例：{config['water']*100}%\n\n"
        text += "═══ 升级福利（一次性）═══\n"
        for lv in range(1, 11):
            cfg = vip_config[lv]
            if str(lv) in claimed:
                text += f"VIP{lv} ✅ 已领取（+{cfg['reward']}）\n"
            elif user['vip_level'] >= lv:
                text += f"VIP{lv} 🔓 可领取！（+{cfg['reward']}）\n"
            else:
                text += f"VIP{lv} 🔒 升到VIP{lv}可领取（+{cfg['reward']}）\n"
        text += "\n═══ 每月福利 ═══\n"
        text += f"VIP{user['vip_level']}：每月 {config['monthly']} 积分\n"
        text += "📆 每月1号可领取\n"
        keyboard = []
        has_reward = False
        for lv in range(1, user['vip_level'] + 1):
            if str(lv) not in claimed:
                has_reward = True
                break
        if has_reward:
            keyboard.append([InlineKeyboardButton("📥 领取升级福利", callback_data='claim_upgrade')])
        if user['month_water'] >= config['keep'] and user['vip_level'] > 0:
            keyboard.append([InlineKeyboardButton("🎁 领取每月福利", callback_data='claim_monthly')])
        keyboard.append([InlineKeyboardButton("🔙 返回", callback_data='back')])
        query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == 'claim_upgrade':
        user = get_user(user_id)
        claimed = user['vip_claimed']
        vip_config = get_vip_config()
        total_reward = 0
        new_claimed = claimed.copy()
        for lv in range(1, user['vip_level'] + 1):
            if str(lv) not in claimed:
                reward = vip_config[lv]['reward']
                total_reward += reward
                new_claimed.append(str(lv))
        if total_reward > 0:
            add_balance(user_id, total_reward)
            update_user(user_id, vip_claimed=new_claimed)
            keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='vip_rewards')]]
            query.edit_message_text(f"🎉 领取成功！+{total_reward} 积分\n💰 新余额：{get_user(user_id)['balance']}", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='vip_rewards')]]
            query.edit_message_text("❌ 没有可领取的升级福利", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == 'claim_monthly':
        user = get_user(user_id)
        vip_config = get_vip_config()
        config = vip_config[user['vip_level']]
        if user['month_water'] >= config['keep'] and user['vip_level'] > 0:
            add_balance(user_id, config['monthly'])
            update_user(user_id, month_water=0)
            keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='vip_rewards')]]
            query.edit_message_text(f"🎉 领取成功！+{config['monthly']} 积分\n💰 新余额：{get_user(user_id)['balance']}", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='vip_rewards')]]
            query.edit_message_text("❌ 本月流水未达标，无法领取", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # ---------- 限时福利 ----------
    if data == 'limited_offers':
        user = get_user(user_id)

        today = datetime.now().strftime('%Y-%m-%d')
        signin_day = user.get('signin_day', 0)
        signin_last = user.get('signin_last', '')

        if signin_last and signin_last != today:
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            if signin_last != yesterday:
                signin_day = 0

        signin_table = [
            {'day': 1, 'recharge': 50, 'reward': 2},
            {'day': 2, 'recharge': 150, 'reward': 8},
            {'day': 3, 'recharge': 300, 'reward': 15},
            {'day': 4, 'recharge': 600, 'reward': 36},
            {'day': 5, 'recharge': 1200, 'reward': 80},
            {'day': 6, 'recharge': 2500, 'reward': 200},
            {'day': 7, 'recharge': 5000, 'reward': 150},
        ]

        text = "🔥 限时福利\n\n"
        text += "━━━ 📅 签到中心 ━━━\n"
        if user['total_recharge'] == 0:
            text += "🔒 请先充值解锁签到\n"
        else:
            text += f"当前签到：Day {signin_day if signin_day < 7 else '7（满签）'}\n"
            if signin_day < 7:
                next_day = signin_day + 1
                text += f"今日任务：充值 {signin_table[next_day-1]['recharge']} → 领 {signin_table[next_day-1]['reward']}\n"
            text += "\n"
            for entry in signin_table:
                day = entry['day']
                if day <= signin_day:
                    text += f"Day {day} ✅ 已领 ({entry['reward']})\n"
                elif day == signin_day + 1 and user['total_recharge'] >= entry['recharge']:
                    text += f"Day {day} 🔓 可领取 ({entry['reward']})\n"
                elif day == signin_day + 1:
                    text += f"Day {day} 🔒 需充值 {entry['recharge']}\n"
                else:
                    text += f"Day {day} 🔒 ({entry['reward']})\n"

        text += "\n━━━ 💎 首充福利 ━━━\n"
        first_table = [
            {'amount': 50, 'reward': 5},
            {'amount': 100, 'reward': 12},
            {'amount': 200, 'reward': 30},
            {'amount': 500, 'reward': 100},
            {'amount': 1000, 'reward': 250},
            {'amount': 2000, 'reward': 600},
            {'amount': 5000, 'reward': 1800},
        ]
        claimed = user.get('first_recharge_claimed', [])
        for entry in first_table:
            key = str(entry['amount'])
            if key in claimed:
                text += f"首充 {entry['amount']} ✅ 已领 ({entry['reward']})\n"
            elif user['total_recharge'] >= entry['amount']:
                text += f"首充 {entry['amount']} 🔓 可领取 ({entry['reward']})\n"
            else:
                text += f"首充 {entry['amount']} 🔒 ({entry['reward']})\n"

        keyboard = []
        if user['total_recharge'] > 0 and signin_day < 7:
            next_day = signin_day + 1
            if next_day <= 7:
                entry = signin_table[next_day - 1]
                if user['total_recharge'] >= entry['recharge']:
                    keyboard.append([InlineKeyboardButton("📥 签到领取", callback_data='claim_signin')])

        for entry in first_table:
            key = str(entry['amount'])
            if key not in claimed and user['total_recharge'] >= entry['amount']:
                keyboard.append([InlineKeyboardButton(f"领取首充 {entry['amount']}", callback_data=f'claim_first_{entry["amount"]}')])
                break

        keyboard.append([InlineKeyboardButton("🔙 返回", callback_data='back')])
        query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # ---------- 签到领取 ----------
    if data == 'claim_signin':
        user = get_user(user_id)
        if user['total_recharge'] == 0:
            keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='limited_offers')]]
            query.edit_message_text("❌ 请先充值解锁签到", reply_markup=InlineKeyboardMarkup(keyboard))
            return

        today = datetime.now().strftime('%Y-%m-%d')
        signin_day = user.get('signin_day', 0)
        signin_last = user.get('signin_last', '')

        if signin_last == today:
            keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='limited_offers')]]
            query.edit_message_text("❌ 今日已签到，明天再来", reply_markup=InlineKeyboardMarkup(keyboard))
            return

        if signin_last:
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            if signin_last != yesterday:
                signin_day = 0

        signin_table = [
            {'day': 1, 'recharge': 50, 'reward': 2},
            {'day': 2, 'recharge': 150, 'reward': 8},
            {'day': 3, 'recharge': 300, 'reward': 15},
            {'day': 4, 'recharge': 600, 'reward': 36},
            {'day': 5, 'recharge': 1200, 'reward': 80},
            {'day': 6, 'recharge': 2500, 'reward': 200},
            {'day': 7, 'recharge': 5000, 'reward': 150},
        ]

        next_day = signin_day + 1
        if next_day > 7:
            keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='limited_offers')]]
            query.edit_message_text("🎉 已完成全部7天签到！", reply_markup=InlineKeyboardMarkup(keyboard))
            return

        entry = signin_table[next_day - 1]
        if user['total_recharge'] < entry['recharge']:
            keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='limited_offers')]]
            query.edit_message_text(
                f"❌ 充值未达标\n\n"
                f"Day {next_day} 需要累计充值 {entry['recharge']} 积分\n"
                f"当前累计充值：{user['total_recharge']} 积分",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        add_balance(user_id, entry['reward'])
        update_user(user_id, signin_day=next_day, signin_last=today)

        keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='limited_offers')]]
        query.edit_message_text(
            f"🎉 签到成功！\n"
            f"Day {next_day} 奖励：+{entry['reward']} 积分\n"
            f"💰 新余额：{get_user(user_id)['balance']} 积分",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # ---------- 首充领取 ----------
    if data.startswith('claim_first_'):
        amount = int(data.replace('claim_first_', ''))
        user = get_user(user_id)
        claimed = user.get('first_recharge_claimed', [])
        key = str(amount)

        if key in claimed:
            keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='limited_offers')]]
            query.edit_message_text("❌ 已领取过", reply_markup=InlineKeyboardMarkup(keyboard))
            return

        if user['total_recharge'] < amount:
            keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='limited_offers')]]
            query.edit_message_text(f"❌ 累计充值未达到 {amount} 积分", reply_markup=InlineKeyboardMarkup(keyboard))
            return

        first_recharge_table = {
            50: 5, 100: 12, 200: 30, 500: 100, 1000: 250, 2000: 600, 5000: 1800
        }
        reward = first_recharge_table.get(amount, 0)
        add_balance(user_id, reward)
        claimed.append(key)
        update_user(user_id, first_recharge_claimed=claimed)

        keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='limited_offers')]]
        query.edit_message_text(
            f"🎉 领取成功！\n"
            f"首充 {amount} 送 {reward}\n"
            f"💰 新余额：{get_user(user_id)['balance']} 积分",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # ---------- 限时福利 ----------
    if data == 'limit':
        if not limit_enabled:
            keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='back')]]
            query.edit_message_text("🔥 当前无限时福利活动", reply_markup=InlineKeyboardMarkup(keyboard))
            return

        keyboard = [[InlineKeyboardButton("💳 充值", callback_data='recharge'), InlineKeyboardButton("🔙 返回", callback_data='back')]]
        text = f"🔥 今日限时福利\n\n"
        text += f"充值额外 +{limit_percent}%！\n\n"
        text += f"━━━━━━━━━━━━━━━\n"
        text += f"适用：所有充值档位\n"
        text += f"充值100 → 额外得 {limit_percent} 积分\n"
        text += f"充值500 → 额外得 {limit_percent * 5} 积分\n"
        text += f"充值1000 → 额外得 {limit_percent * 10} 积分\n\n"
        text += f"联系客服 {客服} 充值即可享受"
        query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # ---------- 风控规则 ----------
    if data == 'rules':
        text = "⚠️ 平台风控规则\n\n"
        text += "为维护公平游戏环境，以下行为一经发现，\n"
        text += "账户将被永久冻结，所有资金（余额/充值/奖励）一律充公：\n\n"
        text += "━━━━━━━━━━━━━━━\n"
        text += "1. 对冲套利\n"
        text += "同一期同时押大和押小，或押3个以上单号\n\n"
        text += "2. 重复注册（多账号）\n"
        text += "使用多个账号（同IP/同设备/同手机号）注册参与活动\n\n"
        text += "3. 恶意刷水\n"
        text += "利用充值福利/签到奖励进行无风险套利\n\n"
        text += "4. 虚假充值\n"
        text += "使用虚假支付凭证/伪造充值记录骗取奖励\n\n"
        text += "5. 外挂/自动化\n"
        text += "使用脚本、机器人、自动化工具进行下注或签到\n\n"
        text += "6. 套取首充/福利\n"
        text += "利用多个账号重复领取首充福利、签到奖励\n\n"
        text += "7. 恶意投诉/攻击\n"
        text += "散布谣言、恶意攻击平台、威胁客服\n\n"
        text += "━━━━━━━━━━━━━━━\n"
        text += "平台保留最终解释权及补充条款的权利"
        keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='back')]]
        query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # ---------- 返回主菜单 ----------
    if data == 'back':
        query.delete_message()
        show_menu(chat_id, context)
        return

    # ---------- 管理面板 ----------
    if data == 'admin':
        if user_id != ADMIN_ID:
            keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='back')]]
            query.edit_message_text("❌ 仅管理员可操作", reply_markup=InlineKeyboardMarkup(keyboard))
            return
        keyboard = [
            [InlineKeyboardButton("💰 加积分", callback_data='admin_add')],
            [InlineKeyboardButton("📊 查余额", callback_data='admin_bal')],
            [InlineKeyboardButton("📋 查转账记录", callback_data='admin_betlog')],
            [InlineKeyboardButton("🚨 对冲检测", callback_data='admin_hedge')],
            [InlineKeyboardButton("🎮 开关游戏", callback_data='admin_toggle')],
            [InlineKeyboardButton("🔥 限时福利", callback_data='admin_limit')],
            [InlineKeyboardButton("📝 审核充值/提现", callback_data='admin_audit')],
            [InlineKeyboardButton("🔙 返回", callback_data='back')]
        ]
        query.edit_message_text("⚙️ 管理面板", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == 'admin_add':
        if user_id != ADMIN_ID:
            keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='admin')]]
            query.edit_message_text("❌ 仅管理员可操作", reply_markup=InlineKeyboardMarkup(keyboard))
            return
        keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='admin')]]
        query.edit_message_text("💳 请使用 /add 玩家ID 数量 命令加积分", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == 'admin_bal':
        if user_id != ADMIN_ID:
            keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='admin')]]
            query.edit_message_text("❌ 仅管理员可操作", reply_markup=InlineKeyboardMarkup(keyboard))
            return
        keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='admin')]]
        query.edit_message_text("📊 请使用 /bal 玩家ID 命令查余额", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == 'admin_betlog':
        if user_id != ADMIN_ID:
            keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='admin')]]
            query.edit_message_text("❌ 仅管理员可操作", reply_markup=InlineKeyboardMarkup(keyboard))
            return
        keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='admin')]]
        query.edit_message_text("📋 请使用 /betlog 用户名/ID/@用户名 命令查下注记录", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == 'admin_hedge':
        if user_id != ADMIN_ID:
            keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='admin')]]
            query.edit_message_text("❌ 仅管理员可操作", reply_markup=InlineKeyboardMarkup(keyboard))
            return
        hedge_players = []
        for uid, user_bets in bets.items():
            types = [b['type'] for b in user_bets]
            if '大' in types and '小' in types:
                hedge_players.append(uid)
            num_bets = [t for t in types if t.isdigit()]
            if len(set(num_bets)) >= 4:
                hedge_players.append(uid)
        keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='admin')]]
        if hedge_players:
            text = "🚨 对冲检测报告\n\n"
            for uid in set(hedge_players):
                username = get_username(uid) or str(uid)
                text += f"玩家：{username}\n下注：{bets.get(uid, [])}\n\n"
            query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            query.edit_message_text("✅ 未检测到对冲行为", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == 'admin_toggle':
        if user_id != ADMIN_ID:
            keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='admin')]]
            query.edit_message_text("❌ 仅管理员可操作", reply_markup=InlineKeyboardMarkup(keyboard))
            return
        global game_enabled
        game_enabled = not game_enabled
        status = "🟢 已开启" if game_enabled else "🔴 已关闭"
        keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='admin')]]
        query.edit_message_text(f"🎮 游戏{status}", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == 'admin_limit':
        if user_id != ADMIN_ID:
            keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='admin')]]
            query.edit_message_text("❌ 仅管理员可操作", reply_markup=InlineKeyboardMarkup(keyboard))
            return
        keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='admin')]]
        query.edit_message_text(
            "🔥 限时福利管理\n\n"
            "开启：/limit 8（8%为例）\n"
            "关闭：/limit off\n\n"
            "当前状态：" + ("🟢 已开启 +{}%".format(limit_percent) if limit_enabled else "🔴 已关闭"),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # ---------- 审核充值/提现 ----------
    if data == 'admin_audit':
        if user_id != ADMIN_ID:
            keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='admin')]]
            query.edit_message_text("❌ 仅管理员可操作", reply_markup=InlineKeyboardMarkup(keyboard))
            return

        conn = sqlite3.connect('data.db')
        c = conn.cursor()
        c.execute('''SELECT id, user_id, amount, method, status, request_time 
                     FROM withdraw_requests 
                     WHERE status='pending' 
                     ORDER BY request_time ASC''')
        rows = c.fetchall()
        conn.close()

        if not rows:
            keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='admin')]]
            query.edit_message_text("✅ 暂无待审核申请", reply_markup=InlineKeyboardMarkup(keyboard))
            return

        text = "📝 待审核申请\n\n"
        for req_id, uid, amount, method, status, request_time in rows:
            username = get_username(uid) or str(uid)
            time_str = request_time.split(' ')[1] if ' ' in request_time else request_time
            text += f"#{req_id} {username}\n"
            text += f"  {amount}积分 | {method}\n"
            text += f"  {time_str} ⏳ 待审核\n\n"

        keyboard = [
            [InlineKeyboardButton("✅ 全部通过", callback_data='audit_all_approve')],
            [InlineKeyboardButton("❌ 全部拒绝", callback_data='audit_all_reject')],
            [InlineKeyboardButton("🔙 返回", callback_data='admin')]
        ]
        query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # ---------- 审核通过/拒绝 ----------
    if data == 'audit_all_approve' or data == 'audit_all_reject':
        if user_id != ADMIN_ID:
            return
        status = 'approved' if data == 'audit_all_approve' else 'rejected'

        conn = sqlite3.connect('data.db')
        c = conn.cursor()
        c.execute('SELECT id, user_id, amount FROM withdraw_requests WHERE status="pending"')
        rows = c.fetchall()

        for req_id, uid, amount in rows:
            if status == 'approved':
                add_balance(uid, amount)
            c.execute('UPDATE withdraw_requests SET status=? WHERE id=?', (status, req_id))

        conn.commit()
        conn.close()

        keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='admin_audit')]]
        query.edit_message_text(f"✅ 已全部{'通过' if status == 'approved' else '拒绝'}", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # ---------- 兜底 ----------
    keyboard = [[InlineKeyboardButton("🔙 返回主菜单", callback_data='back')]]
    query.edit_message_text("❌ 功能开发中...", reply_markup=InlineKeyboardMarkup(keyboard))

# ========== 管理员命令 ==========
def add_balance_cmd(update, context):
    if update.effective_user.id != ADMIN_ID:
        return
    args = context.args
    if len(args) < 2:
        update.message.reply_text("用法：/add 玩家ID 数量")
        return
    try:
        try:
            uid = int(args[0])
        except:
            uid = get_user_by_username(args[0])
            if uid is None:
                update.message.reply_text(f"❌ 找不到用户：{args[0]}")
                return

        amount = int(args[1])
        if amount <= 0:
            update.message.reply_text("❌ 数量必须大于0")
            return

        add_balance(uid, amount)
        user = get_user(uid)
        update_user(uid, total_recharge=user['total_recharge'] + amount)

        username = get_username(uid) or str(uid)
        update.message.reply_text(
            f"✅ 已给 {username} 添加 {amount} 积分\n"
            f"💰 新余额：{user['balance'] + amount}\n"
            f"📊 累计充值：{user['total_recharge'] + amount}\n"
            f"📊 已刷流水：{user['withdrawable_water']}（需下注才能增加）"
        )
    except:
        update.message.reply_text("❌ 格式错误\n用法：/add 玩家ID 数量")

def bal_cmd(update, context):
    user_id = update.effective_user.id
    args = context.args
    if args and user_id == ADMIN_ID:
        try:
            uid = int(args[0])
            user = get_user(uid)
            update.message.reply_text(f"玩家 {uid} 余额：{user['balance']} 积分")
        except:
            update.message.reply_text("❌ 格式错误")
    else:
        user = get_user(user_id)
        update.message.reply_text(f"💰 你的余额：{user['balance']} 积分")

def betlog_cmd(update, context):
    if update.effective_user.id != ADMIN_ID:
        update.message.reply_text("❌ 仅管理员可操作")
        return

    args = context.args
    if len(args) < 1:
        update.message.reply_text("用法：/betlog 用户名/ID/@用户名")
        return

    query = ' '.join(args).strip()
    try:
        uid = int(query)
        user = get_user(uid)
    except:
        if query.startswith('@'):
            query = query[1:]
        uid = get_user_by_username(query)
        if uid is None:
            update.message.reply_text(f"❌ 找不到用户：{query}")
            return
        user = get_user(uid)

    username = user.get('username', str(uid))
    history = get_all_bet_history(uid)
    if not history:
        update.message.reply_text(f"📋 玩家 {username} 暂无下注记录")
        return

    text = f"📋 玩家 {username} (ID: {uid}) 下注记录\n\n"
    last_period = None
    count = 0
    for period, bet_type, amount, win_amount, result_number, bet_time in history:
        if count >= 20:
            break
        if period != last_period:
            last_period = period
            result_text = get_result_text(result_number)
            time_str = bet_time.split(' ')[1] if ' ' in bet_time else bet_time
            text += f"\n第{period}期 | 开奖 {result_number}（{result_text}）| {time_str}\n"
        if win_amount > 0:
            text += f"  • {bet_type} {amount} ✅ +{win_amount}\n"
        else:
            text += f"  • {bet_type} {amount} ❌ {win_amount}\n"
        count += 1

    if count > 0:
        text += f"\n共 {len(history)} 条记录（显示最近{count}条）"
    update.message.reply_text(text)

def toggle_command(update, context):
    if update.effective_user.id != ADMIN_ID:
        update.message.reply_text("❌ 仅管理员可操作")
        return
    global game_enabled
    game_enabled = not game_enabled
    status = "🟢 已开启" if game_enabled else "🔴 已关闭"
    update.message.reply_text(f"🎮 游戏{status}")

def limit_command(update, context):
    if update.effective_user.id != ADMIN_ID:
        update.message.reply_text("❌ 仅管理员可操作")
        return
    global limit_enabled, limit_percent
    args = context.args
    if len(args) < 1:
        update.message.reply_text("用法：/limit 8（开启8%）或 /limit off（关闭）")
        return

    if args[0].lower() == 'off':
        limit_enabled = False
        limit_percent = 0
        update.message.reply_text("🔥 限时福利已关闭")
        return

    try:
        percent = int(args[0])
        if percent <= 0 or percent > 50:
            update.message.reply_text("❌ 百分比需在1-50之间")
            return
        limit_enabled = True
        limit_percent = percent
        update.message.reply_text(f"🔥 限时福利已开启！充值额外+{percent}%")
    except:
        update.message.reply_text("❌ 格式错误，请使用 /limit 8 或 /limit off")

def stop_notifications(update, context):
    user_id = update.effective_user.id
    update_user(user_id, notifications_on=0)
    update.message.reply_text(
        "🔕 已关闭播报\n\n"
        "你不会再收到开奖通知和播报\n"
        "使用 /resume 重新开启"
    )

def resume_notifications(update, context):
    user_id = update.effective_user.id
    update_user(user_id, notifications_on=1)
    update.message.reply_text(
        "🔔 已开启播报\n\n"
        "你会正常收到开奖通知和播报"
    )

# ========== 开奖函数 ==========
def run_period(context):
    global current_period, betting_open, bets, game_enabled

    if not game_enabled:
        return

    betting_open = False
    result = get_controlled_result()  # ← 改用控盘函数
    result_text = get_result_text(result)

    save_period_result(current_period, result)

    for uid, user_bets in bets.items():
        user = get_user(uid)
        total_win = 0
        total_bet = 0
        period_win_details = []

        for bet in user_bets:
            bet_type = bet['type']
            amount = bet['amount']
            total_bet += amount
            win = 0

            if bet_type == '大' and result >= 4:
                win = int(amount * 0.95)
            elif bet_type == '小' and result <= 3:
                win = int(amount * 0.95)
            elif bet_type == str(result):
                win = int(amount * 6 * 0.95)
            else:
                win = -amount

            total_win += win
            save_bet_history(uid, current_period, bet_type, amount, win, result)
            period_win_details.append({'type': bet_type, 'amount': amount, 'win': win})

        if total_win > 0:
            add_balance(uid, total_win + total_bet)

        update_user(uid, 
                   total_water=user['total_water'] + total_bet,
                   month_water=user['month_water'] + total_bet,
                   withdrawable_water=user['withdrawable_water'] + total_bet)

        new_vip, rewards = check_vip_upgrade(uid)
        if rewards:
            try:
                context.bot.send_message(uid, f"🎉 恭喜升到VIP{new_vip}！请到VIP福利专区领取升级奖励")
            except:
                pass

        bet_summary = f"第{current_period}期 开奖：{result}（{result_text}）\n"
        for detail in period_win_details:
            if detail['win'] > 0:
                bet_summary += f"✅ {detail['type']} {detail['amount']} → +{detail['win']}\n"
            else:
                bet_summary += f"❌ {detail['type']} {detail['amount']} → {detail['win']}\n"
        bet_summary += f"净赚：{'+' if total_win > 0 else ''}{total_win} 积分"
        update_user(uid, last_period_result=bet_summary)

    all_users = get_all_users()
    for uid in all_users:
        try:
            user = get_user(uid)
            if user.get('notifications_on', 1) == 0:
                continue

            if uid in bets:
                result_text_full = get_bet_result_text(uid, current_period, result)
                if result_text_full:
                    keyboard = [
                        [InlineKeyboardButton("🎲 继续下注", callback_data='bet_guide')],
                        [InlineKeyboardButton("📊 开奖记录", callback_data='global_history')],
                        [InlineKeyboardButton("🏠 返回主菜单", callback_data='back')]
                    ]
                    context.bot.send_message(uid, result_text_full, reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                keyboard = [
                    [InlineKeyboardButton("🎲 去下注", callback_data='bet_guide')],
                    [InlineKeyboardButton("📊 开奖记录", callback_data='global_history')]
                ]
                context.bot.send_message(
                    uid,
                    f"🎲 第{current_period}期 开奖结果：{result}（{result_text}）\n\n📝 本期未下注",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
        except:
            pass

    bets = {}
    current_period += 1
    save_period(current_period)
    betting_open = True

def get_all_users():
    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    c.execute('SELECT user_id FROM users')
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

# ========== 主程序 ==========
def main():
    init_db()

    global current_period
    current_period = get_saved_period()

    updater = Updater(TOKEN)
    dp = updater.dispatcher

    updater.bot.set_my_commands([
        BotCommand("start", "打开主菜单"),
        BotCommand("bet", "下注 /bet 金额 类型"),
        BotCommand("bal", "查看余额"),
        BotCommand("stop", "关闭播报通知"),
        BotCommand("resume", "开启播报通知"),
        BotCommand("toggle", "开关游戏（管理员）"),
        BotCommand("limit", "限时福利 /limit 8 或 /limit off"),
        BotCommand("add", "加积分 /add 玩家ID 数量"),
        BotCommand("betlog", "查下注记录 /betlog 用户名"),
    ])

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("bet", bet_command))
    dp.add_handler(CommandHandler("bal", bal_cmd))
    dp.add_handler(CommandHandler("add", add_balance_cmd))
    dp.add_handler(CommandHandler("betlog", betlog_cmd))
    dp.add_handler(CommandHandler("toggle", toggle_command))
    dp.add_handler(CommandHandler("limit", limit_command))
    dp.add_handler(CommandHandler("stop", stop_notifications))
    dp.add_handler(CommandHandler("resume", resume_notifications))
    dp.add_handler(CallbackQueryHandler(button_handler))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_username_input))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_withdraw_amount))

    jq = updater.job_queue
    jq.run_repeating(run_period, interval=60, first=10)

    print(f"🎰 Bot 启动成功！当前期数：{current_period}")
    print("🟢 游戏状态：运行中")
    print("🎯 真实控盘逻辑已开启（大/小比例稳定在50/50）")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()