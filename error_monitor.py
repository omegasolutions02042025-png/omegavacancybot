# errors_monitor.py
import asyncio
import traceback
from dataclasses import dataclass
from typing import Optional, Dict, Any, Coroutine, Any as AnyType

from aiogram import Bot


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


@dataclass
class ErrorEvent:
    exc: Exception
    where: str
    extra: Optional[Dict[str, Any]] = None


# Глобальная очередь ошибок
error_queue: "asyncio.Queue[ErrorEvent]" = asyncio.Queue()


async def report_error(
    exc: Exception,
    where: str,
    bot: Optional[Bot] = None,
    admin_ids: Optional[list[int]] = None,
    extra: Optional[Dict[str, Any]] = None,
):
    """
    Репорт одной ошибки:
    — лог в файл + консоль
    — опционально сообщение админу в Telegram
    """
    tb_text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

    logger.error("Ошибка в %s: %r", where, exc)
    logger.error("Traceback (%s):\n%s", where, tb_text)

    if extra:
        logger.error("Контекст (%s): %s", where, extra)

    if bot and admin_ids:
        short_tb = tb_text[-1500:]
        text = (
            f"⚠️ Ошибка в *{where}*\n\n"
            f"`{repr(exc)}`\n\n"
            f"```{short_tb}```"
        )
        try:
            for admin_id in admin_ids:
                await bot.send_message(
                    chat_id=admin_id,
                    text=text,
                    parse_mode="Markdown",
                )
        except Exception as send_exc:
            logger.error("Не удалось отправить ошибку админу: %r", send_exc)


async def error_worker(bot: Bot, admin_ids: list[int]):
    """
    Вечный воркер, который ждёт ошибки из очереди и обрабатывает их.
    """
    logger.info("🚨 error_worker запущен")
    while True:
        try:
            event: ErrorEvent = await error_queue.get()
            try:
                await report_error(
                    exc=event.exc,
                    where=event.where,
                    bot=bot,
                    admin_ids=admin_ids,
                    extra=event.extra,
                )
            finally:
                error_queue.task_done()
        except asyncio.CancelledError:
            logger.info("⏹ error_worker остановлен (CancelledError)")
            break
        except Exception as e:
            logger.exception("Ошибка в error_worker: %r", e)
            await asyncio.sleep(5)


async def push_error(exc: Exception, where: str, extra: Optional[Dict[str, Any]] = None):
    """
    Положить ошибку в очередь для последующей обработки воркером.
    """
    try:
        await error_queue.put(ErrorEvent(exc=exc, where=where, extra=extra))
    except Exception as e:
        logger.exception("Не удалось положить ошибку в очередь: %r (исходная: %r)", e, exc)


def setup_loop_exception_handler(loop: asyncio.AbstractEventLoop, bot: Bot, admin_id: int):
    """
    Глобальный обработчик для ВСЕХ необработанных ошибок event loop.
    Сюда прилетают падения тасок, коллбеков и т.д., если их никто не поймал.
    """
    def handle_loop_exception(loop: asyncio.AbstractEventLoop, context: dict):
        exc = context.get("exception")
        where = "event_loop"

        if exc is None:
            exc = RuntimeError(context.get("message", "Unknown loop error"))

        extra = {
            k: str(v)
            for k, v in context.items()
            if k not in ("exception",)
        }

        logger.error("Глобальная ошибка event loop: %r, контекст: %s", exc, extra)

        # Создаём таску, чтобы асинхронно положить ошибку в очередь
        loop.create_task(
            push_error(exc, where=where, extra=extra)
        )

    loop.set_exception_handler(handle_loop_exception)


def create_monitored_task(
    coro: Coroutine[AnyType, AnyType, AnyType],
    name: str,
):
    """
    Обёртка над asyncio.create_task:
    — ловит любые необработанные ошибки из корутины,
    — шлёт их в очередь через push_error.
    """
    async def wrapper():
        try:
            await coro
        except asyncio.CancelledError:
            # штатная отмена — не считаем ошибкой
            raise
        except Exception as exc:
            loop = asyncio.get_running_loop()
            # Отправляем ошибку в очередь
            loop.create_task(
                push_error(exc, where=name)
            )
            # Пробрасываем дальше, чтобы global loop handler тоже увидел (по желанию)
            raise

    return asyncio.create_task(wrapper(), name=name)
