import asyncio
import sys
import subprocess
from datetime import datetime, timedelta, time

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
import signal
from db import init_db, AsyncSessionLocal, async_engine
from aiogram import Bot, Dispatcher
from telethon_bot import *
import os
from dotenv import load_dotenv
from telethon_monitor import check_and_delete_duplicates, monitor_and_cleanup, check_old_messages_and_mark, check_and_delete_duplicates_partners
from aiogram_bot import bot_router, TOPIC_MAP
from googlesheets import update_currency_sheet
from telethon_monitor import register_simple_edit_listener
from privyazka_messangers import pr_router
import redis.asyncio as redis
from aiogram.fsm.storage.redis import RedisStorage, DefaultKeyBuilder
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.strategy import FSMStrategy
from aiogram.enums import ParseMode
from aiogram.client.bot import DefaultBotProperties
from db_basa_resume import init_db_basa_resume

from error_monitor import (
    error_worker,
    setup_loop_exception_handler,
    create_monitored_task,
    push_error,
)
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


import asyncio
import logging
from telethon.errors import FloodWaitError 


# logging_config.py
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Папка для логов
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

LOG_FILE = LOG_DIR / "bot_errors.log"

# Главный логгер проекта
logger = logging.getLogger("omega_bot")
logger.setLevel(logging.INFO)

formatter = logging.Formatter(
    "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Вывод в консоль
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)

# Файл с ротацией
file_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=5 * 1024 * 1024,  # 5 МБ
    backupCount=3,
    encoding="utf-8",
)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)

# Чтобы не дублировать хендлеры при повторном импорте
if not logger.handlers:
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)


async def telethon_runner():
    while True:
        try:
            # если ещё не подключен — подключаем
            if not telethon_client.is_connected():
                await telethon_client.connect()

            # если сессия есть – авторизация уже должна быть
            # если сессия слетела — тут можно залогировать и выйти
            if not await telethon_client.is_user_authorized():
                logger.error("Telethon: сессия не авторизована, требуется ручной логин")
                # тут можно отправить алерт админу и сделать break
                break

            logger.info("Telethon: run_until_disconnected() старт")
            await telethon_client.run_until_disconnected()
            logger.warning("Telethon: run_until_disconnected() вернулась без исключения")
        except FloodWaitError as e:
            logger.warning("Telethon FloodWait %s сек, спим...", e.seconds)
            await asyncio.sleep(e.seconds + 5)
        except (ConnectionError, OSError) as e:
            logger.warning("Telethon ConnectionError %r, переподключение через 5 сек", e)
            await asyncio.sleep(5)
        except Exception as e:
            logger.exception("Telethon: непойманная ошибка %r, перезапуск через 10 сек", e)
            await asyncio.sleep(10)
    await asyncio.sleep(60)


async def restart_telethon_client():
    """Перезагружает telethon client: отключает и подключает заново"""
    try:
        logger.info("🔄 Начинаю перезагрузку Telethon client...")
        
        # Отключаем клиент, если подключен
        if telethon_client.is_connected():
            await telethon_client.disconnect()
            logger.info("✅ Telethon client отключен")
            await asyncio.sleep(2)
        
        # Подключаем заново
        await telethon_client.connect()
        
        # Проверяем авторизацию
        if not await telethon_client.is_user_authorized():
            logger.error("❌ Telethon: сессия не авторизована после перезагрузки")
            await bot.send_message(ADMIN_ID, "⚠️ Telethon: требуется повторная авторизация после перезагрузки")
        else:
            logger.info("✅ Telethon client успешно перезагружен и авторизован")
            
            # Перерегистрируем слушателей после перезагрузки
            await register_topic_listener(telethon_client, TOPIC_MAP, AsyncSessionLocal, bot)
            await register_simple_edit_listener(telethon_client, -1002189931727, bot)
            await register_chat_listener(telethon_client, [-1001259051878, -1001898906854, -1001527372844], bot)
            logger.info("✅ Слушатели Telethon перерегистрированы")
            
    except Exception as e:
        logger.exception(f"❌ Ошибка при перезагрузке Telethon client: {e}")
        await bot.send_message(ADMIN_ID, f"❌ Ошибка при перезагрузке Telethon: {e}")


async def daily_telethon_restart():
    """Планирует перезагрузку telethon client раз в день в 03:00"""
    while True:
        try:
            # Вычисляем время до следующей 03:00
            now = datetime.now()
            target_time = time(3, 0)  # 03:00
            
            # Если уже прошло 03:00 сегодня, планируем на завтра
            if now.time() >= target_time:
                next_restart = datetime.combine(now.date() + timedelta(days=1), target_time)
            else:
                next_restart = datetime.combine(now.date(), target_time)
            
            wait_seconds = (next_restart - now).total_seconds()
            logger.info(f"⏰ Следующая перезагрузка Telethon запланирована на {next_restart.strftime('%Y-%m-%d %H:%M:%S')} (через {wait_seconds/3600:.1f} часов)")
            
            await asyncio.sleep(wait_seconds)
            
            # Выполняем перезагрузку
            await restart_telethon_client()
            
        except Exception as e:
            logger.exception(f"❌ Ошибка в планировщике перезагрузки Telethon: {e}")
            await asyncio.sleep(3600)  # Ждем час перед повторной попыткой


# ————————————————
# Инициализация FSM-хранилища
# ————————————————
async def get_storage():
    """Пытается подключиться к Redis, при неудаче использует MemoryStorage"""
    redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    try:
        storage = RedisStorage.from_url(redis_url)
        # Проверяем подключение
        redis_client = await redis.from_url(redis_url)
        await redis_client.ping()
        await redis_client.aclose()
        logger.info("✅ Redis подключен успешно")
        return storage
    except Exception as e:
        logger.warning(f"⚠️ Не удалось подключиться к Redis ({e}), используется MemoryStorage")
        if sys.platform.startswith("win"):
            try:
                logger.info("🔄 Пытаюсь запустить Memurai через: net start memurai")
                result = subprocess.run(
                    ["net", "start", "memurai"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    logger.info("✅ Memurai успешно запущен, повторная попытка подключения...")
                    # Пробуем подключиться снова после запуска
                    await asyncio.sleep(2)
                    try:
                        storage = RedisStorage.from_url(redis_url)
                        redis_client = await redis.from_url(redis_url)
                        await redis_client.ping()
                        await redis_client.aclose()
                        logger.info("✅ Redis подключен успешно после запуска Memurai")
                        return storage
                    except Exception as e2:
                        logger.warning(f"⚠️ Не удалось подключиться к Redis после запуска: {e2}")
                else:
                    logger.warning(f"⚠️ Не удалось запустить Memurai: {result.stderr}")
            except subprocess.TimeoutExpired:
                logger.warning("⚠️ Таймаут при запуске Memurai")
            except Exception as cmd_error:
                logger.warning(f"⚠️ Ошибка при запуске Memurai: {cmd_error}")
        else:
            logger.warning("💡 Для запуска Redis выполните команду для вашей ОС")
        return MemoryStorage()

# Инициализируем storage и dp в main() асинхронно
storage = None  # Будет инициализировано в main()
dp = None  # Будет инициализировано в main()

async def main():
    tasks: list[asyncio.Task] = []
    
    # Инициализируем storage
    global storage, dp
    storage = await get_storage()
    dp = Dispatcher(fsm_strategy=FSMStrategy.USER_IN_TOPIC, storage=storage)
    dp.include_router(bot_router)
    dp.include_router(pr_router)

    try:
        # --- База ---
        await init_db()

        # --- Логин Telethon (один раз) ---
        await telethon_client.start(phone=PHONE_NUMBER)

        # --- Регистрируем слушателей Telethon ---
        await register_topic_listener(telethon_client, TOPIC_MAP, AsyncSessionLocal, bot)
        await register_simple_edit_listener(telethon_client, -1002189931727, bot)
        #await forward_messages_from_chats(telethon_client, CHAT_LIST, AsyncSessionLocal, bot)
        await register_chat_listener(telethon_client, [-1001259051878, -1001898906854, -1001527372844], bot)
        #await forward_messages_from_chats(telethon_client, [-1001259051878], AsyncSessionLocal, bot)
        # --- Aiogram: снимаем вебхук и включаем long polling ---
        await bot.delete_webhook(drop_pending_updates=True)

        # --- Глобальный обработчик ошибок event loop ---
        loop = asyncio.get_running_loop()
        setup_loop_exception_handler(loop, bot, ADMIN_ID)

        # --- Запускаем воркер ошибок + фоновые задачи под мониторингом ---
        tasks.extend([
            create_monitored_task(error_worker(bot, [ADMIN_ID, 429765805]), name="error_worker"),
            create_monitored_task(telethon_runner(), name="telethon_runner"),
            create_monitored_task(
                monitor_and_cleanup(telethon_client, AsyncSessionLocal, bot),
                name="monitor_and_cleanup",
            ),
            create_monitored_task(
                check_and_delete_duplicates(telethon_client, -1002658129391, bot, TOPIC_MAP),
                name="check_and_delete_duplicates",
            ),
            create_monitored_task(
                check_old_messages_and_mark(telethon_client, -1002658129391, bot),
                name="check_old_messages_and_mark",
            ),
            create_monitored_task(
                update_currency_sheet(bot, ADMIN_ID),
                name="update_currency_sheet",
            ),
            create_monitored_task(
                check_and_delete_duplicates_partners(telethon_client, -1003360331196, bot),
                name="check_and_delete_duplicates_partners",
            ),
            create_monitored_task(
                daily_telethon_restart(),
                name="daily_telethon_restart",
            ),
            # пример на будущее:
            # create_monitored_task(
            #     replace_mails_in_channel(telethon_client, bot),
            #     name="replace_mails_in_channel",
            # ),
        ])

        # --- Стартуем aiogram-поллинг (блокирующий) ---
        await dp.start_polling(bot)

    finally:
        logger.info("🔄 Завершаем фоновые задачи...")
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

        # Закрываем Telethon
        await telethon_client.disconnect()

        # Закрываем коннекты к БД
        await async_engine.dispose()
        logger.info("✅ Все соединения закрыты")


if __name__ == "__main__":
    asyncio.run(main())
