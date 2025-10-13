import asyncio
import sys
import signal
from db import init_db, AsyncSessionLocal, periodic_cleanup_task
from aiogram import Bot, Dispatcher
from telethon_bot import *
import os
from dotenv import load_dotenv
from telethon_monitor import cleanup_by_striked_id, check_and_delete_duplicates, monitor_and_cleanup, check_old_messages_and_mark
from aiogram_bot import bot_router, TOPIC_MAP
from googlesheets import update_currency_sheet


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
PHONE_NUMBER = os.getenv("PHONE_NUMBER")
GROUP_ID = os.getenv("GROUP_ID")
ADMIN_ID = os.getenv("ADMIN_ID")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
dp.include_router(bot_router)

def handle_sigint(signum, frame):
    print("\n🛑 Получен Ctrl+C, завершаем...")
    sys.exit(0)

signal.signal(signal.SIGINT, handle_sigint)



async def main():
    
    await telethon_client.start(phone=PHONE_NUMBER)
    await register_topic_listener(telethon_client, TOPIC_MAP, AsyncSessionLocal, bot)
   
    asyncio.create_task(monitor_and_cleanup(telethon_client, AsyncSessionLocal, bot))
    asyncio.create_task(check_and_delete_duplicates(telethon_client, -1002658129391, bot, TOPIC_MAP))
    asyncio.create_task(telethon_client.run_until_disconnected())
    asyncio.create_task(cleanup_by_striked_id(telethon_client, src_chat_id=-1002658129391, dst_chat_id=-1002189931727, bot=bot))
    asyncio.create_task(check_old_messages_and_mark(telethon_client, -1002658129391, bot))
    asyncio.create_task(periodic_cleanup_task())
    asyncio.create_task(update_currency_sheet(bot, ADMIN_ID))    
    await dp.start_polling(bot)
    
    

if __name__ == "__main__":
    try:
        asyncio.run(init_db())
        asyncio.run(main())
    except KeyboardInterrupt:
        print("👋 Остановлено пользователем (Ctrl+C)")
