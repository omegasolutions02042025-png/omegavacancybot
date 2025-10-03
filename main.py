import asyncio
from db import init_db, AsyncSessionLocal
from aiogram import Bot, Dispatcher
from telethon_bot import *
import os
from dotenv import load_dotenv
from telethon_monitor import cleanup_by_striked_id, check_and_delete_duplicates, monitor_and_cleanup, check_old_messages_and_mark
from aiogram_bot import bot_router, TOPIC_MAP


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
PHONE_NUMBER = os.getenv("PHONE_NUMBER")
GROUP_ID = os.getenv("GROUP_ID")
ADMIN_ID = os.getenv("ADMIN_ID")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
dp.include_router(bot_router)



async def main():
    await init_db()
    await telethon_client.start(phone=PHONE_NUMBER)

   
    tasks = []
    tasks.append(asyncio.create_task(monitor_and_cleanup(telethon_client, AsyncSessionLocal)))
    tasks.append(asyncio.create_task(check_and_delete_duplicates(telethon_client, -1002658129391, bot, TOPIC_MAP)))
    tasks.append(asyncio.create_task(telethon_client.run_until_disconnected()))
    tasks.append(asyncio.create_task(cleanup_by_striked_id(telethon_client, src_chat_id=-1002658129391, dst_chat_id=-1002189931727)))
    tasks.append(asyncio.create_task(check_old_messages_and_mark(telethon_client, -1002658129391, bot)))
    tasks.append(asyncio.create_task(dp.start_polling(bot)))
    tasks.append(asyncio.create_task(register_topic_listener(telethon_client, TOPIC_MAP, AsyncSessionLocal, bot)))
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        print("⏹ Задачи были отменены")
    finally:
        # Корректное завершение
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await bot.session.close()
        print("✅ Бот и все фоновые задачи остановлены")

if __name__ == "__main__":
    asyncio.run(main())
