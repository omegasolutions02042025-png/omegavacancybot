import asyncio
import sys
import signal
from db import init_db, AsyncSessionLocal
from aiogram import Bot, Dispatcher
from telethon_bot import *
import os
from dotenv import load_dotenv
from telethon_monitor import check_and_delete_duplicates, monitor_and_cleanup, check_old_messages_and_mark
from aiogram_bot import bot_router, TOPIC_MAP
from googlesheets import update_currency_sheet
from telethon_monitor import register_simple_edit_listener
from privyazka_messangers import pr_router
import redis.asyncio as redis
from aiogram.fsm.storage.redis import RedisStorage, DefaultKeyBuilder
from aiogram.fsm.strategy import FSMStrategy
from aiogram.enums import ParseMode
from aiogram.client.bot import DefaultBotProperties
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
PHONE_NUMBER = os.getenv("PHONE_NUMBER")
GROUP_ID = os.getenv("GROUP_ID")
ADMIN_ID = os.getenv("ADMIN_ID")

bot = Bot(token=BOT_TOKEN)

def handle_sigint(signum, frame):
    print("\n🛑 Получен Ctrl+C, завершаем...")
    sys.exit(0)

signal.signal(signal.SIGINT, handle_sigint)

# ————————————————
# Инициализация FSM-хранилища
# ————————————————
storage = RedisStorage.from_url("redis://127.0.0.1:6379/0")
dp = Dispatcher(fsm_strategy=FSMStrategy.USER_IN_TOPIC, storage=storage)
dp.include_router(bot_router)
dp.include_router(pr_router)

async def main():
    tasks = []
    try:
        await init_db()
        await telethon_client.start(phone=PHONE_NUMBER)
        await register_topic_listener(telethon_client, TOPIC_MAP, AsyncSessionLocal, bot)
        await register_simple_edit_listener(telethon_client, -1002189931727, bot)
        
        # Создаем фоновые задачи
        tasks.extend([
            asyncio.create_task(monitor_and_cleanup(telethon_client, AsyncSessionLocal, bot)),
            asyncio.create_task(check_and_delete_duplicates(telethon_client, -1002658129391, bot, TOPIC_MAP)),
            asyncio.create_task(telethon_client.run_until_disconnected()),
            asyncio.create_task(check_old_messages_and_mark(telethon_client, -1002658129391, bot)),
            asyncio.create_task(update_currency_sheet(bot, ADMIN_ID))
        ])
        
        await dp.start_polling(bot)
    finally:
        # Graceful shutdown
        print("🔄 Завершаем фоновые задачи...")
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Закрываем соединения
        await telethon_client.disconnect()
        from db import async_engine
        await async_engine.dispose()
        print("✅ Все соединения закрыты")
    
    

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("👋 Остановлено пользователем (Ctrl+C)")
