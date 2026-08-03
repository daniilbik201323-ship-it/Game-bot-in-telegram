import sqlite3
import random
from dotenv import load_dotenv
from os import getenv
import logging
from logging.handlers import RotatingFileHandler
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    handlers=[
        RotatingFileHandler('read.log', maxBytes=5*1024*1024, backupCount=5, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

load_dotenv()

def init_db():
    try:
        conn = sqlite3.connect("data.db")
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS top(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        winst INTEGER)""")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT)""")
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Ошибка в бд {e}")

def select():
    try:
        conn = sqlite3.connect("data.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM top")
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        logger.error(f"Ошибка при просмотре таблицы top, {e}")
        return []

def get_user_wins(user_id):
    try:
        conn = sqlite3.connect("data.db")
        cursor = conn.cursor()
        cursor.execute("SELECT winst FROM top WHERE user_id=?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else 0
    except Exception as e:
        logger.error(f"Ошибка при получении побед: {e}")
        return 0

def get_top_players():
    try:
        conn = sqlite3.connect("data.db")
        cursor = conn.cursor()
        cursor.execute("SELECT username, winst FROM top WHERE winst > 20 ORDER BY winst DESC")
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        logger.error(f"Ошибка при получении топа: {e}")
        return []

TOKEN = getenv("TOKEN")
bot = telebot.TeleBot(TOKEN)

win_number = {}
attempts = {}
blocked_users = set()

def main():
    keyboard = InlineKeyboardMarkup()
    btn1 = InlineKeyboardButton("1", callback_data="1")
    btn2 = InlineKeyboardButton("2", callback_data="2")
    btn3 = InlineKeyboardButton("3", callback_data="3")
    btn4 = InlineKeyboardButton("4", callback_data="4")
    btn5 = InlineKeyboardButton("5", callback_data="5")
    btn6 = InlineKeyboardButton("6", callback_data="6")
    keyboard.add(btn1, btn2, btn3)
    keyboard.add(btn4, btn5, btn6)
    return keyboard

def prize():
    keyboard = InlineKeyboardMarkup()
    btn1 = InlineKeyboardButton("Мои победы", callback_data="wins")
    btn2 = InlineKeyboardButton("Чемпионы", callback_data="top")
    keyboard.add(btn1)
    keyboard.add(btn2)
    return keyboard

def come_back():
    keyboard = InlineKeyboardMarkup()
    btn1 = InlineKeyboardButton("Попытаться еще (3 попытки)", callback_data="back")
    keyboard.add(btn1)
    return keyboard

@bot.message_handler(commands=["start"])
def start(message):
    user_id = message.chat.id
    username = message.from_user.username or message.from_user.full_name
    
    if user_id in blocked_users:
        bot.send_message(user_id, "Вы заблокированы в игре.")
        return
    
    win_number[user_id] = random.randint(1, 6)
    attempts[user_id] = 0
    
    try:
        conn = sqlite3.connect("data.db")
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users(user_id, username) VALUES(?, ?)", (user_id, username))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Ошибка при добавлении пользователя: {e}")
    
    bot.send_message(
        user_id,
        "Данная игра не только про подарки...\nСоревнуйтесь с другими игроками по всему миру в количествах побед\nПопытки всего 3, если вы их потратите за одну игру (в конце игры обнуление) то вы уже никогда не сыграете...*Удачи игрок*\np.s, Порекомендуйте нас друзьям",
        reply_markup=main(),
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: True)
def call_handler(call):
    logger.info(f"Пользователь {user_id} Зашел в бота")
    user_id = call.message.chat.id
    
    if user_id in blocked_users:
        bot.answer_callback_query(call.id, "Вы заблокированы в игре.", show_alert=True)
        return
    
    if call.data in ["1", "2", "3", "4", "5", "6"]:
        if win_number.get(user_id) is None:
            win_number[user_id] = random.randint(1, 6)
            attempts[user_id] = 0
        
        if call.data == str(win_number[user_id]):
            bot.edit_message_text(
                "Поздравляю, ты выиграл! +1 победа",
                user_id,
                call.message.message_id,
                reply_markup=come_back()
            )
            
            wins_count = get_user_wins(user_id) + 1
            
            try:
                conn = sqlite3.connect("data.db")
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO top(user_id, username, winst) VALUES(?, ?, ?)",
                    (user_id, call.from_user.username or call.from_user.full_name, wins_count)
                )
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"Ошибка записи победы: {e}")
            
            attempts.pop(user_id, None)
            win_number.pop(user_id, None)
        else:
            attempts[user_id] = attempts.get(user_id, 0) + 1
            remaining = 3 - attempts[user_id]
            
            if attempts[user_id] >= 3:
                blocked_users.add(user_id)
                bot.edit_message_text(
                    "Ты выбыл из игры навсегда.",
                    user_id,
                    call.message.message_id
                )
            else:
                bot.edit_message_text(
                    f"Неправильно, осталось {remaining} попыток",
                    user_id,
                    call.message.message_id,
                    reply_markup=main()
                )
    
    elif call.data == "back":
        if user_id in blocked_users:
            bot.answer_callback_query(call.id, "Вы заблокированы в игре.", show_alert=True)
            return
        
        win_number[user_id] = random.randint(1, 6)
        attempts[user_id] = 0
        
        bot.edit_message_text(
            "Данная игра не только про подарки...\nСоревнуйтесь с другими игроками по всему миру в количествах побед\nПопытки всего 3, если вы их потратите за одну игру (в конце игры обнуление) то вы уже никогда не сыграете...*Удачи игрок*\np.s, Порекомендуйте нас друзьям, ведь через месяц итоги и самым активным участникам придет приз",
            user_id,
            call.message.message_id,
            reply_markup=main(),
            parse_mode="Markdown"
        )
    
    elif call.data == "top":
        rows = get_top_players()
        if rows:
            text = "Пользователи с 20+ побед\n\n"
            for row in rows:
                text += f"@{row[0]} : {row[1]}\n"
            bot.send_message(user_id, text, reply_markup=come_back())
        else:
            bot.send_message(user_id, "Таких смельчаков пока не нашлось, СТАНЬ ИМ, ЖИВИ ЭТОЙ ИГРОЙ", reply_markup=come_back())
    
    elif call.data == "wins":
        wins_count = get_user_wins(user_id)
        bot.send_message(user_id, f"Твои победы: {wins_count}")

if __name__ == "__main__":
    init_db()
    bot.infinity_polling()