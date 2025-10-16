import asyncio
import logging
import random
import sqlite3
import json
import sys
from typing import List, Optional
from datetime import datetime

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# === ДЕМОНСКОЕ ЛОГИРОВАНИЕ 😈 ===
class DemonFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[92m",
        "WARNING": "\033[93m",
        "ERROR": "\033[91m",
        "CRITICAL": "\033[95m"
    }

    EMOJIS = {
        "DEBUG": "🧠",
        "INFO": "⚙️",
        "WARNING": "⚠️",
        "ERROR": "🔥",
        "CRITICAL": "💀"
    }

    def format(self, record: logging.LogRecord) -> str:
        msg = record.getMessage()
        time = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        color = self.COLORS.get(record.levelname, "")
        emoji = self.EMOJIS.get(record.levelname, "💬")
        reset = "\033[0m"
        return f"{color}{emoji} {time} [{record.levelname}] [{record.name}] {msg}{reset}"

logger = logging.getLogger("DATING_BOT")
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(DemonFormatter())
logger.addHandler(console_handler)

file_handler = logging.FileHandler("demon_logs.log", encoding="utf-8")
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# === БОТ ===
BOT_TOKEN = "--"

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

# === FSM ===
class ProfileStates(StatesGroup):
    waiting_for_profile = State()

# === ИНИЦИАЛИЗАЦИЯ БД ===
def init_db():
    conn = sqlite3.connect("dating_bot.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT UNIQUE,
            name TEXT,
            bio TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            file_id TEXT,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS last_viewed (
            user_id INTEGER PRIMARY KEY,
            last_profile_id INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS queues (
            user_id INTEGER PRIMARY KEY,
            queue TEXT,
            idx INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            user_id INTEGER PRIMARY KEY
        )
    """)
    # For likes table, drop if exists to ensure correct schema
    cursor.execute("DROP TABLE IF EXISTS likes")
    cursor.execute("""
        CREATE TABLE likes (
            viewer_id INTEGER,
            profile_id INTEGER,
            like_type TEXT CHECK (like_type IN ('like', 'dislike')),
            PRIMARY KEY (viewer_id, profile_id)
        )
    """)
    conn.commit()
    conn.close()
    logger.info("💾 База данных инициализирована!")

init_db()

# === УТИЛИТЫ ЛОГИРОВАНИЯ ===
def _user_str_from_user_like(user_like) -> str:
    try:
        uid = getattr(user_like, "id", None) or getattr(user_like, "user_id", None)
        username = getattr(user_like, "username", None)
        first = getattr(user_like, "first_name", None) or ""
        last = getattr(user_like, "last_name", None) or ""
    except Exception:
        return f"id:{getattr(user_like, 'id', 'unknown')}"
    if username:
        return f"{first} @{username} (id:{uid})"
    else:
        return f"{first} {last} (id:{uid})"

def log_user_action(user_like, action: str, extra: str = ""):
    try:
        user_str = _user_str_from_user_like(user_like)
        msg = f"👤 {user_str} — {action}"
        if extra:
            msg += f" | {extra}"
        logger.info(msg)
    except Exception as e:
        logger.error(f"🔥 Ошибка в log_user_action: {e}")

def log_message(message: Message):
    try:
        user_str = _user_str_from_user_like(message.from_user)
        text = message.text if getattr(message, "text", None) else "(медиа или нет текста)"
        logger.info(f"💬 {user_str}: {text}")
    except Exception as e:
        logger.error(f"🔥 Ошибка в log_message: {e}")

def log_callback(callback: CallbackQuery):
    try:
        user_str = _user_str_from_user_like(callback.from_user)
        data = getattr(callback, "data", "(no-data)")
        logger.info(f"👇 {user_str} нажал кнопку: [{data}]")
    except Exception as e:
        logger.error(f"🔥 Ошибка в log_callback: {e}")

# === ФУНКЦИИ БД ===
def get_all_user_ids(exclude: Optional[int] = None) -> List[int]:
    conn = sqlite3.connect("dating_bot.db")
    cursor = conn.cursor()
    if exclude is None:
        cursor.execute("SELECT user_id FROM users")
    else:
        cursor.execute("SELECT user_id FROM users WHERE user_id != ?", (exclude,))
    ids = [row[0] for row in cursor.fetchall()]
    conn.close()
    return ids

def get_all_users() -> List[int]:
    conn = sqlite3.connect("dating_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users

def init_user_queue_if_missing(user_id: int):
    conn = sqlite3.connect("dating_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM queues WHERE user_id = ?", (user_id,))
    exists = cursor.fetchone()
    if not exists:
        others = get_all_user_ids(exclude=user_id)
        random.shuffle(others)
        cursor.execute("INSERT OR REPLACE INTO queues (user_id, queue, idx) VALUES (?, ?, ?)",
                       (user_id, json.dumps(others), 0))
        conn.commit()
    conn.close()

def get_user_queue(user_id: int):
    conn = sqlite3.connect("dating_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT queue, idx FROM queues WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        queue = json.loads(row[0]) if row[0] else []
        idx = int(row[1])
        return queue, idx
    return None, 0

def save_user_queue(user_id: int, queue: List[int], idx: int):
    conn = sqlite3.connect("dating_bot.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO queues (user_id, queue, idx) VALUES (?, ?, ?)",
                   (user_id, json.dumps(queue), idx))
    conn.commit()
    conn.close()

def remove_user_from_all_queues(removed_user_id: int):
    conn = sqlite3.connect("dating_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, queue, idx FROM queues")
    rows = cursor.fetchall()
    for owner_id, q_json, idx in rows:
        if not q_json:
            continue
        queue = json.loads(q_json)
        if removed_user_id in queue:
            queue = [u for u in queue if u != removed_user_id]
            new_idx = min(idx, len(queue))
            save_user_queue(owner_id, queue, new_idx)
    conn.close()

def add_new_profile_to_all_queues(new_user_id: int):
    conn = sqlite3.connect("dating_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, queue, idx FROM queues")
    rows = cursor.fetchall()
    for owner_id, q_json, idx in rows:
        if owner_id == new_user_id:
            continue
        queue = json.loads(q_json) if q_json else []
        queue = [u for u in queue if u != new_user_id]
        viewed = queue[:idx]
        remaining = queue[idx:]
        remaining.append(new_user_id)
        random.shuffle(remaining)
        save_user_queue(owner_id, viewed + remaining, idx)
    conn.close()

def get_notification_subscribers() -> List[int]:
    conn = sqlite3.connect("dating_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM notifications")
    subscribers = [row[0] for row in cursor.fetchall()]
    conn.close()
    return subscribers

def enable_notifications(user_id: int):
    conn = sqlite3.connect("dating_bot.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO notifications (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def disable_notifications(user_id: int):
    conn = sqlite3.connect("dating_bot.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM notifications WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_user_profile(user_id: int) -> Optional[dict]:
    conn = sqlite3.connect("dating_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT username, name, bio FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    if result:
        username, name, bio = result
        conn = sqlite3.connect("dating_bot.db")
        cursor = conn.cursor()
        cursor.execute("SELECT file_id FROM photos WHERE user_id = ? ORDER BY id", (user_id,))
        photos = [row[0] for row in cursor.fetchall()]
        conn.close()
        return {"username": username, "name": name, "bio": bio, "photos": photos[:1]}
    return None

async def save_user_profile(user_id: int, username: str, name: str, bio: str, photos: List[str]):
    conn = sqlite3.connect("dating_bot.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO users (user_id, username, name, bio)
        VALUES (?, ?, ?, ?)
    """, (user_id, username, name, bio))
    cursor.execute("DELETE FROM photos WHERE user_id = ?", (user_id,))
    for file_id in photos[:1]:
        cursor.execute("INSERT INTO photos (user_id, file_id) VALUES (?, ?)", (user_id, file_id))
    conn.commit()
    conn.close()

    add_new_profile_to_all_queues(user_id)
    init_user_queue_if_missing(user_id)

    profile = get_user_profile(user_id)
    if profile:
        subscribers = get_notification_subscribers()
        for subscriber_id in subscribers:
            if subscriber_id != user_id:
                try:
                    await bot.send_message(subscriber_id, "Новая анкета!😈")
                    await send_profile(subscriber_id, profile, include_button=True)
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления пользователю {subscriber_id}: {e}")

def delete_user_profile(user_id: int):
    conn = sqlite3.connect("dating_bot.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM photos WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM last_viewed WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM queues WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM notifications WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM likes WHERE profile_id = ? OR viewer_id = ?", (user_id, user_id))
    conn.commit()
    conn.close()
    remove_user_from_all_queues(user_id)

def get_random_user(user_id: int) -> Optional[int]:
    init_user_queue_if_missing(user_id)
    queue, idx = get_user_queue(user_id)
    if not queue:
        others = get_all_user_ids(exclude=user_id)
        if not others:
            return None
        random.shuffle(others)
        save_user_queue(user_id, others, 0)
        queue, idx = get_user_queue(user_id)
    if idx >= len(queue):
        others = get_all_user_ids(exclude=user_id)
        if not others:
            save_user_queue(user_id, [], 0)
            return None
        random.shuffle(others)
        save_user_queue(user_id, others, 0)
        queue, idx = get_user_queue(user_id)
    while idx < len(queue):
        candidate = queue[idx]
        if get_user_profile(candidate):
            save_user_queue(user_id, queue, idx + 1)
            return candidate
        else:
            queue.pop(idx)
            save_user_queue(user_id, queue, idx)
    return None

def get_likes_count(profile_id: int, like_type: str) -> int:
    conn = sqlite3.connect("dating_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM likes WHERE profile_id = ? AND like_type = ?", (profile_id, like_type))
    count = cursor.fetchone()[0]
    conn.close()
    return count

def has_user_voted(viewer_id: int, profile_id: int) -> bool:
    conn = sqlite3.connect("dating_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM likes WHERE viewer_id = ? AND profile_id = ?", (viewer_id, profile_id))
    exists = cursor.fetchone()
    conn.close()
    return bool(exists)

def set_user_vote(viewer_id: int, profile_id: int, like_type: str):
    conn = sqlite3.connect("dating_bot.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO likes (viewer_id, profile_id, like_type)
        VALUES (?, ?, ?)
    """, (viewer_id, profile_id, like_type))
    conn.commit()
    conn.close()

def get_mutual_likes(user_id: int) -> List[str]:
    conn = sqlite3.connect("dating_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT viewer_id FROM likes WHERE profile_id = ? AND like_type = 'like'", (user_id,))
    likers = [row[0] for row in cursor.fetchall()]
    matches = []
    for liker in likers:
        cursor.execute("SELECT 1 FROM likes WHERE viewer_id = ? AND profile_id = ? AND like_type = 'like'", (user_id, liker))
        if cursor.fetchone():
            cursor.execute("SELECT username FROM users WHERE user_id = ?", (liker,))
            row = cursor.fetchone()
            if row:
                matches.append(f"@{row[0]}")
    conn.close()
    return matches

async def send_profile(message_or_chat: Message | int, profile: dict, include_button: bool = False, profile_id: Optional[int] = None, viewer_id: Optional[int] = None):
    chat_id = message_or_chat.chat.id if isinstance(message_or_chat, Message) else message_or_chat
    inline_keyboard = []
    
    # Кнопка перехода, если нужно
    if include_button:
        inline_keyboard.append([
            InlineKeyboardButton(text=f"Перейти к @{profile['username']}", url=f"https://t.me/{profile['username']}")
        ])
    
    # Кнопки лайк/дизлайк, если это случайная анкета и указано profile_id и viewer_id
    if profile_id and viewer_id:
        likes_count = get_likes_count(profile_id, 'like')
        dislikes_count = get_likes_count(profile_id, 'dislike')
        
        like_text = f"👍[{likes_count}]"
        dislike_text = f"👎[{dislikes_count}]"
        
        like_callback = f"like_{profile_id}"
        dislike_callback = f"dislike_{profile_id}"
        
        inline_keyboard.append([
            InlineKeyboardButton(text=like_text, callback_data=like_callback),
            InlineKeyboardButton(text=dislike_text, callback_data=dislike_callback)
        ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
    
    if profile["photos"]:
        caption = f"{profile['name']}\n\n{profile['bio']}"
        await bot.send_photo(chat_id, profile["photos"][0], caption=caption, reply_markup=keyboard)
    else:
        await bot.send_message(chat_id, f"{profile['name']}\n\n{profile['bio']}", reply_markup=keyboard)

# === НОВАЯ ФУНКЦИЯ: ГЛОБАЛЬНАЯ РАССЫЛКА ОБНОВЛЕНИЙ ===
async def broadcast_update_menu():
    users = get_all_users()
    updated_menu = get_main_menu()  # Получаем актуальное меню (с возможными изменениями)
    for user_id in users:
        try:
            await bot.send_message(
                user_id,
                "Обновление бота! Меню и кнопки обновлены. 😈",
                reply_markup=updated_menu
            )
            logger.info(f"📢 Рассылка обновления меню пользователю {user_id}")
        except Exception as e:
            logger.error(f"🔥 Ошибка рассылки пользователю {user_id}: {e}")

# === МЕНЮ ===
def get_main_menu() -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Изменить или создать анкету"), KeyboardButton(text="🎲 Случайная анкета")],
            [KeyboardButton(text="👤 Моя анкета"), KeyboardButton(text="❤️ Метчи")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

# === ОБРАБОТЧИКИ ===
@router.message(Command("start"))
async def cmd_start(message: Message):
    log_message(message)
    await message.answer("Добро пожаловать! Используйте кнопки ниже:", reply_markup=get_main_menu())
    log_user_action(message.from_user, "начал диалог")

@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message):
    YOUR_ADMIN_ID = YOUR_ADMIN_ID_HERE  # Замените на ваш Telegram ID
    if message.from_user.id == YOUR_ADMIN_ID:
        await broadcast_update_menu()
        await message.answer("Рассылка обновлений меню запущена!", reply_markup=get_main_menu())
    else:
        await message.answer("Доступ запрещён.", reply_markup=get_main_menu())

@router.message(Command("profile"))
@router.message(F.text == "📝 Изменить или создать анкету")
async def cmd_profile(message: Message, state: FSMContext):
    log_message(message)
    user_id = message.from_user.id
    username = message.from_user.username
    if not username:
        await message.answer("У вас нет username в Telegram. Установите его для работы бота.", reply_markup=get_main_menu())
        return

    profile = get_user_profile(user_id)
    if profile:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="Обновить анкету", callback_data="update_profile"),
                InlineKeyboardButton(text="Удалить анкету", callback_data="delete_profile")
            ],
            [InlineKeyboardButton(text="Отменить", callback_data="cancel_update")]
        ])
        await message.answer("Выберите действие:", reply_markup=keyboard)
        await bot.send_message(message.chat.id, "\u180e", reply_markup=get_main_menu())
        log_user_action(message.from_user, "выбрал действие для анкеты")
    else:
        await message.answer("Отправьте вашу анкету одним сообщением (текст + фото).", reply_markup=None)
        await state.set_state(ProfileStates.waiting_for_profile)
        await state.update_data(username=username)
        log_user_action(message.from_user, "создаёт новую анкету")

@router.message(F.text == "👤 Моя анкета")
async def cmd_my_profile(message: Message):
    log_message(message)
    user_id = message.from_user.id
    profile = get_user_profile(user_id)
    if not profile:
        await message.answer("У вас нет анкеты. Создайте её через меню.", reply_markup=get_main_menu())
        return
    await send_profile(message, profile, include_button=False, profile_id=user_id, viewer_id=user_id)
    await bot.send_message(message.chat.id, "\u180e", reply_markup=get_main_menu())
    log_user_action(message.from_user, "просмотрел свою анкету")

@router.message(F.text == "❤️ Метчи")
async def cmd_matches(message: Message):
    log_message(message)
    user_id = message.from_user.id
    matches = get_mutual_likes(user_id)
    text = "Взаимные лайки:\n" + "\n".join(matches) if matches else "Взаимные лайки:\nПока нет взаимных лайков."
    await message.answer(text, reply_markup=get_main_menu())
    log_user_action(message.from_user, "просмотрел метчи")

@router.callback_query(F.data == "delete_profile")
async def cb_delete_profile(callback: CallbackQuery):
    log_callback(callback)
    user_id = callback.from_user.id
    profile = get_user_profile(user_id)
    if not profile:
        await callback.answer("У вас нет анкеты для удаления.", show_alert=True)
        return
    delete_user_profile(user_id)
    await callback.message.edit_text("Анкета удалена.")
    await bot.send_message(user_id, "Вы можете создать новую анкету через меню.", reply_markup=get_main_menu())
    log_user_action(callback.from_user, "удалил анкету (через inline)")

@router.callback_query(F.data == "update_profile")
async def cb_update_profile(callback: CallbackQuery, state: FSMContext):
    log_callback(callback)
    await callback.message.edit_text("Отправьте новую анкету (текст + фото).")
    await state.set_state(ProfileStates.waiting_for_profile)
    await state.update_data(username=callback.from_user.username)
    await bot.send_message(callback.from_user.id, "\u180e", reply_markup=get_main_menu())
    await callback.answer()

@router.callback_query(F.data == "cancel_update")
async def cb_cancel_update(callback: CallbackQuery):
    log_callback(callback)
    await callback.message.edit_text("Отменено.")
    await bot.send_message(callback.from_user.id, "Вернулись в главное меню.", reply_markup=get_main_menu())
    log_user_action(callback.from_user, "отменил обновление анкеты")

@router.message(ProfileStates.waiting_for_profile, F.photo)
async def process_profile_with_photo(message: Message, state: FSMContext):
    log_message(message)
    user_id = message.from_user.id
    data = await state.get_data()
    username = data["username"]
    caption = message.caption or ""
    lines = caption.strip().split("\n", 1)
    name = lines[0].strip() if lines else "Без имени"
    bio = lines[1].strip() if len(lines) > 1 else ""
    photos = [message.photo[-1].file_id]
    await save_user_profile(user_id, username, name, bio, photos)
    await message.answer("Анкета сохранена!", reply_markup=get_main_menu())
    await state.clear()
    log_user_action(message.from_user, "сохранил анкету")

@router.message(Command("random"))
@router.message(F.text == "🎲 Случайная анкета")
async def cmd_random(message: Message):
    log_message(message)
    user_id = message.from_user.id
    random_user_id = get_random_user(user_id)
    if not random_user_id:
        await message.answer("Пока нет других анкет.", reply_markup=get_main_menu())
        return
    profile = get_user_profile(random_user_id)
    if profile:
        await send_profile(message, profile, include_button=True, profile_id=random_user_id, viewer_id=user_id)
        await bot.send_message(message.chat.id, "\u180e", reply_markup=get_main_menu())
        log_user_action(message.from_user, f"просмотрел случайную анкету id:{random_user_id}")

@router.callback_query(F.data.startswith("like_"))
async def cb_like(callback: CallbackQuery):
    log_callback(callback)
    viewer_id = callback.from_user.id
    try:
        profile_id = int(callback.data.split("_")[1])
    except (IndexError, ValueError):
        await callback.answer("Ошибка обработки лайка.", show_alert=True)
        return
    
    if viewer_id == profile_id:
        await callback.answer("Нельзя голосовать за себя!", show_alert=True)
        return
    
    set_user_vote(viewer_id, profile_id, 'like')
    
    # Обновляем сообщение с новыми счетами
    profile = get_user_profile(profile_id)
    if profile:
        await send_profile(callback.message.chat.id, profile, include_button=True, profile_id=profile_id, viewer_id=viewer_id)
        await callback.message.delete()  # Удаляем старое сообщение
        await bot.send_message(callback.from_user.id, "\u180e", reply_markup=get_main_menu())
    else:
        await callback.message.edit_text("Анкета удалена.")
        await bot.send_message(callback.from_user.id, "\u180e", reply_markup=get_main_menu())
    
    await callback.answer("Лайк поставлен! 👍")
    log_user_action(callback.from_user, f"поставил лайк анкете id:{profile_id}")

@router.callback_query(F.data.startswith("dislike_"))
async def cb_dislike(callback: CallbackQuery):
    log_callback(callback)
    viewer_id = callback.from_user.id
    try:
        profile_id = int(callback.data.split("_")[1])
    except (IndexError, ValueError):
        await callback.answer("Ошибка обработки дизлайка.", show_alert=True)
        return
    
    if viewer_id == profile_id:
        await callback.answer("Нельзя голосовать за себя!", show_alert=True)
        return
    
    set_user_vote(viewer_id, profile_id, 'dislike')
    
    # Обновляем сообщение с новыми счетами
    profile = get_user_profile(profile_id)
    if profile:
        await send_profile(callback.message.chat.id, profile, include_button=True, profile_id=profile_id, viewer_id=viewer_id)
        await callback.message.delete()  # Удаляем старое сообщение
        await bot.send_message(callback.from_user.id, "\u180e", reply_markup=get_main_menu())
    else:
        await callback.message.edit_text("Анкета удалена.")
        await bot.send_message(callback.from_user.id, "\u180e", reply_markup=get_main_menu())
    
    await callback.answer("Дизлайк поставлен! 👎")
    log_user_action(callback.from_user, f"поставил дизлайк анкете id:{profile_id}")

# === ЗАПУСК ===
async def main():
    logger.info("🚀 Запуск демонического датинг-бота...")
    # Опционально: Автоматическая рассылка обновлений при запуске бота
    # await broadcast_update_menu()  # Раскомментируйте, если нужно
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
