import asyncio
import sqlite3
from aiogram import Bot

BOT_TOKEN = "8049745792:AAEmq5_8i-TLmM9YundzJxwJdOJ9SopDYGU"
bot = Bot(token=BOT_TOKEN)

# Получаем всех пользователей из базы
def get_all_users() -> list[int]:
    conn = sqlite3.connect("dating_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users

async def broadcast_message(text: str):
    users = get_all_users()
    for user_id in users:
        try:
            await bot.send_message(user_id, text)
            print(f"📢 Отправлено пользователю {user_id}")
        except Exception as e:
            print(f"🔥 Ошибка при отправке пользователю {user_id}: {e}")

if __name__ == "__main__":
    msg = input("Введите сообщение для рассылки: ")
    asyncio.run(broadcast_message(msg))

