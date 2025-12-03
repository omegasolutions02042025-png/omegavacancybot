from telethon.tl.types import MessageEntityStrike
from telethon.tl.types import Channel, Chat, User
from aiogram import Bot
import asyncio
import re
import os
from dotenv import load_dotenv
from db import *
from funcs import get_vacancy_title, extract_vacancy_id
from datetime import datetime, timezone, timedelta
from telethon import TelegramClient
from telethon.tl.functions.channels import GetForumTopicsRequest
load_dotenv()

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
PHONE_NUMBER = os.getenv("PHONE_NUMBER")

VACANCY_ID_REGEX = re.compile(
    r"(?:🆔\s*)?(?:[\w\-\u0400-\u04FF]+[\s\-]*)?\d+", 
    re.IGNORECASE
)
GROUP_ID = os.getenv('GROUP_ID')
ADMIN_ID = os.getenv('ADMIN_ID')



def has_strikethrough_id(message, vacancy_id: str) -> bool:
    """
    Проверяет, есть ли зачёркнутый именно ID вакансии (а не любое слово)
    """
    if not message.entities:
        return False

    for entity in message.entities:
        if entity.__class__.__name__ == 'MessageEntityStrike':
            start = entity.offset
            end = start + entity.length
            text_fragment = message.text[start:end]

            if vacancy_id and vacancy_id in text_fragment:
                print(f"🔍 Найден зачёркнутый именно ID {vacancy_id} в сообщении {message.id}")
                return True

    return False


def has_strikethrough(message):
    if not message.entities:
        return False
    for entity in message.entities:
        if entity.__class__.__name__ == 'MessageEntityStrike':
            print(f"🔍 Найден зачёркнутый текст в сообщении {message.id}")
            return True
    return False


        
        
from datetime import datetime, timezone



async def monitor_and_cleanup(telethon_client: TelegramClient, AsyncSessionLocal, bot: Bot):
    while True:
        try:
            if not await ensure_connected(telethon_client):
                await asyncio.sleep(60)
                continue
                
            mappings = await get_all_message_mappings()

            for mapping in mappings:
                try:
                    msg = await telethon_client.get_messages(mapping.src_chat_id, ids=mapping.src_msg_id)
                    
                    vacancy_id = None
                    if not msg:
                        #print(f"❌ Сообщение {mapping.src_msg_id} не найдено — пропускаем функция monitor_and_cleanup")
                        continue
                    if msg.message:
                        vacancy_id = extract_vacancy_id(msg.message)
                    
                    # Если сообщение удалено или зачёркнуто
                    if has_strikethrough(msg):
                        await bot.send_message(ADMIN_ID, f"❌ Сообщение {mapping.src_msg_id} содержит зачёркнутый текст — удаляем функция monitor_and_cleanup")
                        asyncio.create_task(mark_inactive_and_schedule_delete(
                            telethon_client, mapping, vacancy_id, bot
                        ))
                        await remove_message_mapping(mapping.src_chat_id, mapping.src_msg_id)
                        continue
                    
                    stop_pattern = re.compile(
                        r'(🛑.*(?:СТОП|STOP).*🛑|\bстоп\b|\bstop\b)',
                        re.IGNORECASE
                    )
                    # Проверка на слово "стоп"
                    if msg.message and stop_pattern.search(msg.message):
                        await bot.send_message(ADMIN_ID, f"🛑 Сообщение {mapping.src_msg_id} содержит слово 'стоп' — удаляем функция monitor_and_cleanup")
                        asyncio.create_task(mark_inactive_and_schedule_delete(
                            telethon_client, mapping, vacancy_id,  bot
                        ))
                        await remove_message_mapping(mapping.src_chat_id, mapping.src_msg_id)
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
                                await bot.send_message(ADMIN_ID, f"⏰ Дедлайн для сообщения {vacancy_id} {mapping.src_msg_id} истёк — удаляем функция monitor_and_cleanup")
                                asyncio.create_task(mark_inactive_and_schedule_delete(
                                    telethon_client, mapping, vacancy_id,  bot
                                ))
                                await remove_message_mapping(mapping.src_chat_id, mapping.src_msg_id)
                                continue

                        except Exception as e:
                            await bot.send_message(ADMIN_ID, f"⚠ Ошибка парсинга дедлайна для {mapping.src_msg_id} "
                                  f"в {mapping.src_chat_id}: {e} функция monitor_and_cleanup")

                except Exception as e:
                    await bot.send_message(ADMIN_ID, f"Ошибка проверки {mapping.src_msg_id} в {mapping.src_chat_id}: {e} функция monitor_and_cleanup")

        except Exception as e:
            print(f"❌ Ошибка в monitor_and_cleanup: {e}")
        
        await asyncio.sleep(60)


async def mark_inactive_and_schedule_delete(client: TelegramClient, mapping, vacancy_id, bot: Bot):
    try:
        msg = await client.get_messages(mapping.dst_chat_id, ids=mapping.dst_msg_id)
        if not msg:
            return
        title = get_vacancy_title(msg.message)
        
        if vacancy_id and title:
            new_text = f"\n\n{vacancy_id} — вакансия неактивна\n{title}"
        elif vacancy_id:
            new_text = f"\n\n{vacancy_id} — вакансия неактивна"
        else:
            new_text = "Вакансия неактивна"
            vacancy_id = None
    
        await client.delete_messages(mapping.dst_chat_id, mapping.dst_msg_id)
        await remove_actual_vacancy(vacancy_id, bot, client)
        message = await client.send_message(mapping.dst_chat_id, new_text)
        

        # Закрепляем
        
        await bot.send_message(ADMIN_ID, f"📌 Закреплено сообщение {vacancy_id} {message.id} в {mapping.dst_chat_id}")

        # Ждём 24 часа
        await asyncio.sleep(86400)

        # Открепляем и удаляем
        await client.delete_messages(mapping.dst_chat_id, message.id)
        
        await bot.send_message(ADMIN_ID, f"🗑 Удалено сообщение {vacancy_id} {message.id} в {mapping.dst_chat_id}")

    except Exception as e:
        await bot.send_message(ADMIN_ID, f"Ошибка при изменении/удалении {vacancy_id} {mapping.dst_msg_id}: {e}")
  # проверяем каждую минуту
  # проверяем каждую минуту



async def generate_bd_id() -> str:
    sequence_num = await get_next_sequence_number()
    seq_str = str(sequence_num).zfill(4)
    return f"{seq_str}"

def remove_request_id(text: str):
    """
    Удаляет из текста идентификатор вакансии вида:
    🆔 XX-1234 или 🆔 1234
    Возвращает:
        - очищенный текст
        - 4-значный ID как строку (или None, если не найден)
    """
    match = re.search(r'🆔(?:[A-Z]{2}-)?(\d{4})', text)
    vacancy_id = match.group(1) if match else None
    cleaned_text = re.sub(r'🆔(?:[A-Z]{2}-)?\d{4}', '', text).strip()
    return cleaned_text, vacancy_id



async def check_and_delete_duplicates(teleton_client: TelegramClient, channel_id: int, bot: Bot, topic_map: dict):
    """Проверяет последние сообщения канала на дубликаты по ID в тексте"""
    seen_ids = set()
    
    target_topics = [v[1] for v in topic_map.values()]
    
    while True:
        try:
            for topic_id in target_topics:
                if topic_id == 1:
                    continue
                async for message in teleton_client.iter_messages(channel_id, reply_to=topic_id):
                    if not message.text:
                        continue
                    
                    vacancy_id = extract_vacancy_id(message.text)
                    if not vacancy_id:
                        vacancy_id = extract_vacancy_id(message.message)
                        if not vacancy_id:
                            continue
                    
            
                    stop_pattern = re.compile(
                        r'(🛑.*(?:СТОП|STOP).*🛑|\bстоп\b|\bstop\b)',
                        re.IGNORECASE
                    )
                    
                    if stop_pattern.search(message.text):
                        await bot.send_message(ADMIN_ID, f'❌ Стоп-слово найдено в сообщении {vacancy_id} {message.id} в канале {channel_id} функция check_and_delete_duplicates')
                        await message.delete()
                        continue
                    
                    
                    if vacancy_id in seen_ids:
                        
                        await bot.send_message(ADMIN_ID, f'❌ Дубликат найден: {vacancy_id}, удаляю сообщение {message.id} в канале {channel_id} функция check_and_delete_duplicates')
                        await message.delete()
                    else:
                        seen_ids.add(vacancy_id)
        except Exception as e:
            await bot.send_message(ADMIN_ID, 'Ошибка при проверке функции check_and_delete_duplicates', e)
        # очищаем сет в конце итерации
        seen_ids.clear()
        
        await asyncio.sleep(60)

async def check_and_delete_duplicates_partners(teleton_client: TelegramClient, channel_id: int, bot: Bot):
    """Проверяет последние сообщения канала на дубликаты по ID в тексте"""
    seen_ids = set()
    
    
    
    while True:
        try:
            async for message in teleton_client.iter_messages(channel_id):
                    if not message.text:
                        continue
                    
                    vacancy_id = extract_vacancy_id(message.text)
                    if not vacancy_id:
                        vacancy_id = extract_vacancy_id(message.message)
                        if not vacancy_id:
                            continue
                    
            
                    stop_pattern = re.compile(
                        r'(🛑.*(?:СТОП|STOP).*🛑|\bстоп\b|\bstop\b)',
                        re.IGNORECASE
                    )
                    
                    if stop_pattern.search(message.text):
                        await bot.send_message(ADMIN_ID, f'❌ Стоп-слово найдено в сообщении {vacancy_id} {message.id} в канале {channel_id} функция check_and_delete_duplicates')
                        await message.delete()
                        continue
                    
                    
                    if vacancy_id in seen_ids:
                        
                        await bot.send_message(ADMIN_ID, f'❌ Дубликат найден: {vacancy_id}, удаляю сообщение {message.id} в канале {channel_id} функция check_and_delete_duplicates')
                        await message.delete()
                    else:
                        seen_ids.add(vacancy_id)
        except Exception as e:
            await bot.send_message(ADMIN_ID, 'Ошибка при проверке функции check_and_delete_duplicates', e)
        # очищаем сет в конце итерации
        seen_ids.clear()
        
        await asyncio.sleep(60)

async def mark_as_deleted(client: TelegramClient,  chat_id: int, vacancy_id: str, name_vac: str, bot: Bot):
    try:
        async for message in client.iter_messages(chat_id):
            if vacancy_id in message.text:
                msg_id = message.id
                title = get_vacancy_title(message.text)
                break
            if not message.text:
                continue
        if vacancy_id and title:
        
            new_text = f"🆔{vacancy_id} — вакансия неактивна\n{title}"
        elif vacancy_id:
            new_text = f"🆔{vacancy_id} — вакансия неактивна"
        else:
            new_text = "Вакансия неактивна"
            vacancy_id = None
        await client.delete_messages(chat_id, msg_id)
        await remove_actual_vacancy(vacancy_id, bot, client)
        message = await client.send_message(chat_id, new_text)

        # Закрепляем
        
        await bot.send_message(ADMIN_ID, f"📌 Закреплено сообщение {vacancy_id} {message.id}")

        # Ждём 24 часа
        await asyncio.sleep(86400)

        # Открепляем и удаляем
        await client.delete_messages(chat_id, message.id)
        
        await bot.send_message(ADMIN_ID, f"🗑 Удалено сообщение {vacancy_id} {message.id}")

    except Exception as e:
        await bot.send_message(ADMIN_ID, f"Ошибка при изменении/удалении {vacancy_id} {msg_id}: {e}")
 
    
    
    
async def check_old_messages_and_mark(teleton_client: TelegramClient, channel_id: int, bot: Bot):
    """
    Проверяет все сообщения в канале без привязки к топикам.
    Если сообщение старше 21 дня — вызывает mark_inactive_and_schedule_delete(message).
    """
    while True:
        now = datetime.now(timezone.utc)
        max_age = timedelta(days=14)

        async for message in teleton_client.iter_messages(channel_id):
            if not message.text:  # игнорируем медиа/системные
                continue

            msg_date = message.date
            
            if msg_date.tzinfo is None:  # если naive
                msg_date = msg_date.replace(tzinfo=timezone.utc)
            else:  # если aware, приведём к UTC на всякий случай
                msg_date = msg_date.astimezone(timezone.utc)
            # дата отправки
            
            age = now - msg_date
            

            if age > max_age:
                #await bot.send_message(ADMIN_ID, f'⚠️Удалено сообщение {message.id} старше 21 дня ({age.days} дней). Помечаем...')
                message_text = message.text
                vacancy_id = extract_vacancy_id(message_text)
                await remove_actual_vacancy(vacancy_id, bot, teleton_client)
                await teleton_client.delete_messages(channel_id, message.id)
                
        await asyncio.sleep(3600)
        


from telethon import TelegramClient, events
async def on_edit(message, bot: Bot, telethon_client: TelegramClient, src_chat_id: int):
    chat_id = -1002658129391
    stop_pattern = re.compile(
                        r'(🛑.*(?:СТОП|STOP).*🛑|\bстоп\b|\bstop\b)',
                        re.IGNORECASE
                    )
    
    
    text = message.text
    print(text[0:10])
    vacancy_id = extract_vacancy_id(text)
    print(vacancy_id)
    if not vacancy_id:
        return
        
    if has_strikethrough_id(message, vacancy_id):
        await bot.send_message(ADMIN_ID, f"🗑 Найден зачеркнутый ID {vacancy_id} в {src_chat_id} → удаляем сообщение {message.id} из {src_chat_id}, функция cleanup_by_striked_id")
        title = get_vacancy_title(message.text)
        asyncio.create_task(mark_as_deleted(telethon_client, chat_id, vacancy_id, title, bot))
    elif stop_pattern.search(message.text):
        await bot.send_message(ADMIN_ID, f"🛑 Найдено слово 'стоп' в {vacancy_id} {src_chat_id} → удаляем сообщение {message.id} из {src_chat_id}, функция cleanup_by_striked_id")
        title = get_vacancy_title(message.text)
        
        asyncio.create_task(mark_as_deleted(telethon_client, chat_id, vacancy_id, title, bot))
    

async def register_simple_edit_listener(client: TelegramClient, channel, bot: Bot):
    @client.on(events.MessageEdited(chats=[channel]))
    async def _on_edit(event: events.MessageEdited.Event):
        m = event.message
        if not m:
            return
        await on_edit(m, bot, client, channel)


async def ensure_connected(client):
    if not client.is_connected():
        try:
            await client.connect()
        except Exception as e:
            print(f"[!] Ошибка подключения Telethon: {e}")
            return False
    return True


