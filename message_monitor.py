import asyncio
from datetime import datetime, timezone
import re
from telethon.errors import FloodWaitError
from db import get_all_message_mappings, remove_message_mapping
from message_handlers import has_strikethrough
from bot_utils import send_error_to_admin, update_activity
import os

VACANCY_ID_REGEX = re.compile(r"🆔\s*([A-Z]{2}-\d+|\d+)", re.UNICODE)

async def monitor_and_cleanup(telethon_client, AsyncSessionLocal):
    """Мониторит и очищает неактивные сообщения"""
    while True:
        update_activity()
        
        async with AsyncSessionLocal() as session:
            mappings = await get_all_message_mappings(session)

            for mapping in mappings:
                try:
                    msg = await telethon_client.get_messages(mapping.src_chat_id, ids=mapping.src_msg_id)
                    
                    vacancy_id = None
                    if msg.message:
                        match = VACANCY_ID_REGEX.search(msg.message)
                        if match:
                            vacancy_id = match.group(0)

                    # Если сообщение удалено или зачёркнуто
                    if has_strikethrough(msg):
                        await mark_inactive_and_schedule_delete(
                            telethon_client, mapping, vacancy_id
                        )
                        await remove_message_mapping(session, mapping.src_chat_id, mapping.src_msg_id)
                        continue
                        
                    stop_pattern = re.compile(r'(🛑.*СТОП.*🛑|(?:\bстоп\b))', re.IGNORECASE)
                    # Проверка на слово "стоп"
                    if msg.message and stop_pattern.search(msg.message):
                        await mark_inactive_and_schedule_delete(
                            telethon_client, mapping, vacancy_id
                        )
                        await remove_message_mapping(session, mapping.src_chat_id, mapping.src_msg_id)
                        continue

                    # Проверка дедлайна
                    if mapping.deadline_date:
                        try:
                            date_str = mapping.deadline_date.strip() if mapping.deadline_date else None
                            time_str = mapping.deadline_time.strip() if mapping.deadline_time else "23:59"

                            if not date_str or date_str.lower() == "none":
                                continue  # дата отсутствует, пропускаем

                            parts = date_str.split(".")
                            if len(parts) != 3:
                                raise ValueError(f"Некорректный формат даты: {date_str}")

                            day, month, year = parts
                            day = day.zfill(2)
                            month = month.zfill(2)

                            deadline_dt = datetime.strptime(f"{day}.{month}.{year} {time_str}", "%d.%m.%Y %H:%M")

                            now_utc = datetime.now(timezone.utc)
                            if deadline_dt.replace(tzinfo=timezone.utc) <= now_utc:
                                await mark_inactive_and_schedule_delete(
                                    telethon_client, mapping, vacancy_id
                                )
                                await remove_message_mapping(session, mapping.src_chat_id, mapping.src_msg_id)
                                continue

                        except Exception as e:
                            from main import bot
                            await send_error_to_admin(bot, str(e), f"deadline_parsing for message {mapping.src_msg_id}")

                except FloodWaitError as e:
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    from main import bot
                    await send_error_to_admin(bot, str(e), f"monitor_and_cleanup - message {mapping.src_msg_id}")

        await asyncio.sleep(60)

async def check_and_delete_duplicates(telethon_client, channel_id: int):
    """Проверяет последние сообщения канала на дубликаты по ID в тексте"""
    seen_ids = set()
    while True:
        update_activity()
        
        try:
            async for message in telethon_client.iter_messages(channel_id):
                if not message.text:
                    continue
                
                match = VACANCY_ID_REGEX.search(message.text)
                if match:
                    vacancy_id = match.group(0).strip()
                else:
                    continue

                if vacancy_id in seen_ids:
                    await message.delete()
                else:
                    seen_ids.add(vacancy_id)
        except Exception as e:
            from main import bot
            await send_error_to_admin(bot, str(e), "check_and_delete_duplicates")
            
        # очищаем сет в конце итерации
        seen_ids.clear()
        await asyncio.sleep(60)

async def cleanup_by_striked_id(telethon_client, src_chat_id, dst_chat_id):
    """
    src_chat_id — канал-источник, откуда берём айди
    dst_chat_id — канал, где ищем зачёркнутый айди
    """
    while True:
        update_activity()
        
        async for msg in telethon_client.iter_messages(src_chat_id):
            try:
                if not msg.message:
                    continue

                # Ищем vacancy_id по regex
                match = VACANCY_ID_REGEX.search(msg.message)
                if not match:
                    continue

                vacancy_id = match.group(0)

                # Ищем в другом канале это зачёркнутое айди
                async for dst_msg in telethon_client.iter_messages(dst_chat_id, search=vacancy_id):
                    
                    if dst_msg.message and vacancy_id in dst_msg.message:
                        if has_strikethrough(dst_msg):
                            await mark_as_deleted(telethon_client, msg.id, src_chat_id, vacancy_id)
                            break  # нашли и удалили → идём к следующему

            except FloodWaitError as e:
                await asyncio.sleep(e.seconds)
            except Exception as e:
                print(f"Error in cleanup_by_striked_id: {e}")
        
        await asyncio.sleep(500)

async def mark_inactive_and_schedule_delete(client, mapping, vacancy_id):
    """Помечает сообщение как неактивное и планирует его удаление"""
    try:
        msg = await client.get_messages(mapping.dst_chat_id, ids=mapping.dst_msg_id)
        if not msg:
            return

        if vacancy_id:
            new_text = f"\n\n{vacancy_id} — вакансия неактивна"
        else:
            new_text = "Вакансия неактивна"

        await client.edit_message(mapping.dst_chat_id, mapping.dst_msg_id, new_text)

        # Закрепляем
        await client.pin_message(mapping.dst_chat_id, mapping.dst_msg_id, notify=False)

        # Ждём 24 часа
        await asyncio.sleep(24 * 60 * 60)

        # Открепляем и удаляем
        await client.unpin_message(mapping.dst_chat_id, mapping.dst_msg_id)
        await client.delete_messages(mapping.dst_chat_id, mapping.dst_msg_id)

    except FloodWaitError as e:
        await asyncio.sleep(e.seconds)
        await mark_inactive_and_schedule_delete(client, mapping, vacancy_id)
    except Exception as e:
        from main import bot
        await send_error_to_admin(bot, str(e), f"mark_inactive_and_schedule_delete - message {mapping.dst_msg_id}")

async def mark_as_deleted(client, msg_id, chat_id, vacancy_id):
    """Помечает сообщение как удаленное"""
    try:
        if vacancy_id:
            new_text = f"\n\n{vacancy_id} — вакансия неактивна"
        else:
            new_text = "Вакансия неактивна"

        await client.edit_message(chat_id, msg_id, new_text)

        # Закрепляем
        await client.pin_message(chat_id, msg_id, notify=False)

        # Ждём 24 часа
        await asyncio.sleep(24 * 60 * 60)

        # Открепляем и удаляем
        await client.unpin_message(chat_id, msg_id)
        await client.delete_messages(chat_id, msg_id)

    except Exception as e:
        print(f"Error in mark_as_deleted: {e}")
        
    await asyncio.sleep(20)
