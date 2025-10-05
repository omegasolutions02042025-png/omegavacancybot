from telethon.tl.types import MessageEntityStrike
from telethon.tl.types import Channel, Chat, User
from aiogram import Bot
import asyncio
import re
import os
from dotenv import load_dotenv
from db import *
from funcs import get_vacancy_title
from datetime import datetime, timezone, timedelta
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



def has_strikethrough(message):
    if not message.entities:
        return False
    for entity in message.entities:
        if entity.__class__.__name__ == 'MessageEntityStrike':
            print(f"🔍 Найден зачёркнутый текст в сообщении {message.id}")
            return True
    return False

async def list_all_dialogs(telethon_client, PHONE_NUMBER):
    await telethon_client.start(phone=PHONE_NUMBER)

    async for dialog in telethon_client.iter_dialogs():
        entity = dialog.entity

        if isinstance(entity, Channel):
            kind = 'Канал'
        elif isinstance(entity, Chat):
            kind = 'Группа'
        elif isinstance(entity, User):
            kind = 'Пользователь'
        else:
            kind = 'Другое'

        print(f"{kind}: {dialog.name} — ID: {entity.id}")
        
        
        
from datetime import datetime, timezone



async def monitor_and_cleanup(telethon_client, AsyncSessionLocal):
    while True:
        async with AsyncSessionLocal() as session:
            mappings = await get_all_message_mappings(session)

            for mapping in mappings:
                try:
                    msg = await telethon_client.get_messages(mapping.src_chat_id, ids=mapping.src_msg_id)
                    
                    
                   
                    vacancy_id = None
                    if not msg:
                        #print(f"❌ Сообщение {mapping.src_msg_id} не найдено — пропускаем функция monitor_and_cleanup")
                        continue
                    if msg.message:
                        match = VACANCY_ID_REGEX.search(msg.message)
                        if match:
                            vacancy_id = match.group(0)
                    title = get_vacancy_title(msg.message)
                    # Если сообщение удалено или зачёркнуто
                    if has_strikethrough(msg):
                        print(f"❌ Сообщение {mapping.src_msg_id} содержит зачёркнутый текст — удаляем функция monitor_and_cleanup")
                        await mark_inactive_and_schedule_delete(
                            telethon_client, mapping, vacancy_id, title
                        )
                        await remove_message_mapping(session, mapping.src_chat_id, mapping.src_msg_id)
                        continue
                    stop_pattern = re.compile(
                        r'(🛑.*(?:СТОП|STOP).*🛑|\bстоп\b|\bstop\b)',
                        re.IGNORECASE
                    )
                    # Проверка на слово "стоп"
                    if msg.message and stop_pattern.search(msg.message):
                        print(f"🛑 Сообщение {mapping.src_msg_id} содержит слово 'стоп' — удаляем функция monitor_and_cleanup")
                        await mark_inactive_and_schedule_delete(
                            telethon_client, mapping, vacancy_id, title
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
                                print(f"⏰ Дедлайн для сообщения {mapping.src_msg_id} истёк — удаляем функция monitor_and_cleanup")
                                await mark_inactive_and_schedule_delete(
                                    telethon_client, mapping, vacancy_id, get_vacancy_title(msg.message)
                                )
                                await remove_message_mapping(session, mapping.src_chat_id, mapping.src_msg_id)
                                continue

                        except Exception as e:
                            print(f"⚠ Ошибка парсинга дедлайна для {mapping.src_msg_id} "
                                  f"в {mapping.src_chat_id}: {e} функция monitor_and_cleanup")

                except Exception as e:
                    print(f"Ошибка проверки {mapping.src_msg_id} в {mapping.src_chat_id}: {e} функция monitor_and_cleanup")

        await asyncio.sleep(60)


async def mark_inactive_and_schedule_delete(client, mapping, vacancy_id, title):
    try:
        msg = await client.get_messages(mapping.dst_chat_id, ids=mapping.dst_msg_id)
        if not msg:
            return

        
        if vacancy_id:
            new_text = f"\n\n{vacancy_id} — вакансия неактивна\n{title}"
        else:
            new_text = "Вакансия неактивна"
    
        await client.delete_messages(mapping.dst_chat_id, mapping.dst_msg_id)

        message = await client.send_message(mapping.dst_chat_id, new_text)
        

        # Закрепляем
        
        print(f"📌 Закреплено сообщение {message.id} в {mapping.dst_chat_id}")

        # Ждём 24 часа
        await asyncio.sleep(86400)

        # Открепляем и удаляем
        await client.delete_messages(mapping.dst_chat_id, message.id)
        
        print(f"🗑 Удалено сообщение {message.id} в {mapping.dst_chat_id}")

    except Exception as e:
        print(f"Ошибка при изменении/удалении {mapping.dst_msg_id}: {e}")
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



async def check_and_delete_duplicates(teleton_client, channel_id: int, bot: Bot, topic_map: dict):
    """Проверяет последние сообщения канала на дубликаты по ID в тексте"""
    seen_ids = set()
    
    target_topics = [v[1] for v in topic_map.values()]
    
    while True:
        try:
            for topic_id in target_topics:
                
                async for message in teleton_client.iter_messages(channel_id, reply_to=topic_id):
                    if not message.text:
                        continue
                    
                    match = VACANCY_ID_REGEX.search(message.text)
                    if match:
                        vacancy_id = match.group(0).strip()         # например: "🆔00668801" или "🆔 00668801"
                        vac_id_without_symbol = vacancy_id.replace("🆔", "").strip()
                           # оставляем только цифры/буквы
                       
                        
                    else:
                        continue
                    
                    
                    stop_pattern = re.compile(
                        r'(🛑.*(?:СТОП|STOP).*🛑|\bстоп\b|\bstop\b)',
                        re.IGNORECASE
                    )
                    
                    if stop_pattern.search(message.text):
                        await bot.send_message(ADMIN_ID, f'❌ Стоп-слово найдено в сообщении {message.id} в канале {channel_id} функция check_and_delete_duplicates')
                        await message.delete()
                        continue
                    
                    
                    if vac_id_without_symbol in seen_ids:
                        
                        await bot.send_message(ADMIN_ID, f'❌ Дубликат найден: {vac_id_without_symbol}, удаляю сообщение {message.id} в канале {channel_id} функция check_and_delete_duplicates')
                        await message.delete()
                    else:
                        seen_ids.add(vac_id_without_symbol)
        except Exception as e:
            print('Ошибка при проверке функции check_and_delete_duplicates', e)
        # очищаем сет в конце итерации
        seen_ids.clear()
        
        await asyncio.sleep(60)


async def cleanup_by_striked_id(telethon_client, src_chat_id, dst_chat_id):
    """
    src_chat_id — канал-источник, откуда берём айди
    dst_chat_id — канал, где ищем зачёркнутый айди
    """
    while True:
        async for msg in telethon_client.iter_messages(src_chat_id, limit=None):
            try:
                if not msg.text:
                    continue
                
                text = msg.text
                # Ищем vacancy_id по regex
                match = VACANCY_ID_REGEX.search(text)
                
                if not match:
                    continue

                vacancy_id = match.group(0)
                vacancy_id = vacancy_id.replace("🆔", "").strip()
                
                
                
                title = get_vacancy_title(text)
                stop_pattern = re.compile(
                    r'(🛑.*(?:СТОП|STOP).*🛑|\bстоп\b|\bstop\b)',
                    re.IGNORECASE
                )
                try:
                    
                    # Ищем в другом канале это зачёркнутое айди
                    async for dst_msg in telethon_client.iter_messages(dst_chat_id, limit=None):
                        
                        if dst_msg.text and vacancy_id in dst_msg.text:
                            
                            
                            msg_date = dst_msg.date
                            if msg_date.tzinfo is None:  # если naive
                                msg_date = msg_date.replace(tzinfo=timezone.utc)
                            else:  # если aware, приведём к UTC на всякий случай
                                msg_date = msg_date.astimezone(timezone.utc)
                            
                            
                            
                            if has_strikethrough(dst_msg):
                                print(f"🗑 Найден зачеркнутый ID {vacancy_id} в {dst_chat_id} → удаляем сообщение {msg.id} из {src_chat_id}, функция cleanup_by_striked_id")
                                await mark_as_deleted(telethon_client, msg.id, src_chat_id, vacancy_id, title)
                                break  # нашли и удалили → идём к следующему
                            elif stop_pattern.search(dst_msg.text):
                                print(f"🛑 Найдено слово 'стоп' в {dst_chat_id} → удаляем сообщение {msg.id} из {src_chat_id}, функция cleanup_by_striked_id")
                                await mark_as_deleted(telethon_client, msg.id, src_chat_id, vacancy_id, title)
                                break  # нашли и удалили → идём к следующему
                            elif msg_date < datetime.now(timezone.utc) - timedelta(days=21):
                                print(f"🗑 Найдено сообщение старше 21 дня в {dst_chat_id} → удаляем сообщение {msg.id} из {src_chat_id}, функция cleanup_by_striked_id")
                                await mark_as_deleted(telethon_client, msg.id, src_chat_id, vacancy_id, title)
                                break  # нашли и удалили → идём к следующему
                except Exception as e:
                        print(f"Ошибка обработки сообщения {msg.id}: {e}")
                        continue
            except Exception as e:
                print(f"Ошибка обработки сообщения {msg.id}: {e}")
                continue
            
        await asyncio.sleep(500)


async def mark_as_deleted(client, msg_id, chat_id, vacancy_id, name_vac):
    try:
        
        if vacancy_id:
            new_text = f"🆔{vacancy_id} — вакансия неактивна\n{name_vac}"
        else:
            new_text = "Вакансия неактивна"
        await client.delete_messages(chat_id, msg_id)
        message = await client.send_message(chat_id, new_text)

        # Закрепляем
        
        print(f"📌 Закреплено сообщение {message.id}")

        # Ждём 24 часа
        await asyncio.sleep(86400)

        # Открепляем и удаляем
        await client.delete_messages(chat_id, message.id)
        print(f"🗑 Удалено сообщение {message.id}")

    except Exception as e:
        print(f"Ошибка при изменении/удалении {msg_id}: {e}")
  # проверяем каждую минуту
    await asyncio.sleep(20)
    
    
    
async def check_old_messages_and_mark(teleton_client, channel_id: int, bot: Bot):
    """
    Проверяет все сообщения в канале без привязки к топикам.
    Если сообщение старше 21 дня — вызывает mark_inactive_and_schedule_delete(message).
    """
    while True:
        now = datetime.now(timezone.utc)
        max_age = timedelta(days=21)

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
                print(f"⚠️ Сообщение {message.id} старше 21 дня ({age.days} дней). Помечаем...")
                await bot.send_message(ADMIN_ID, f'⚠️Удалено сообщение {message.id} старше 21 дня ({age.days} дней). Помечаем...')
                await message.delete()
                
        await asyncio.sleep(86400)