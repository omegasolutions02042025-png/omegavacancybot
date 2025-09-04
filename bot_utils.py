import asyncio
import time
from datetime import datetime
from aiogram import Bot
import os

# Глобальные переменные для отслеживания статуса
bot_start_time = time.time()
error_count = 0
last_activity = time.time()

# ID администратора для отправки ошибок
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "429765805"))

async def send_error_to_admin(bot: Bot, error_message: str, function_name: str = ""):
    """Отправляет сообщение об ошибке администратору"""
    global error_count
    error_count += 1
    
    try:
        message = f"""
⚠️ **Ошибка в боте**

🕒 **Время:** {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
📝 **Функция:** {function_name}
❌ **Ошибка:** {error_message}
📊 **Всего ошибок:** {error_count}
"""
        
        await bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=message,
            parse_mode='Markdown'
        )
    except Exception as e:
        print(f"Не удалось отправить ошибку в чат: {e}")

def update_activity():
    """Обновляет время последней активности"""
    global last_activity
    last_activity = time.time()

def get_bot_status():
    """Возвращает статус бота"""
    uptime = int(time.time() - bot_start_time)
    hours = uptime // 3600
    minutes = (uptime % 3600) // 60
    seconds = uptime % 60
    
    last_activity_ago = int(time.time() - last_activity)
    
    status_message = f"""
🤖 **Статус бота Omega Vacancy**

⏱️ **Время работы:** {hours}ч {minutes}м {seconds}с
🕐 **Последняя активность:** {last_activity_ago}с назад
📊 **Всего ошибок:** {error_count}

🟢 **Статус:** Работает
🕒 **Время проверки:** {datetime.now().strftime('%H:%M:%S')}
"""
    
    return status_message
