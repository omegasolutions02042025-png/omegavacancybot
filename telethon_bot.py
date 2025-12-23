
from datetime import datetime, timedelta, timezone
import re
import asyncio
from telethon import TelegramClient, events, types
from db import add_message_mapping, add_vacancy_thread, add_actual_vacancy, update_actual_vacancy
from googlesheets import  search_and_extract_values
from funcs import check_project_duration, send_mess_to_group, get_message_datetime, remove_vacancy_id
from aiogram import Bot
from utils import extract_telegram_usernames
import os
from gpt_gimini import process_vacancy_with_gemini, format_vacancy_gemini, scrap_vacancy, format_vacancy_gemini_for_partners, scrap_vacancy_for_new_gr
from telethon_monitor import has_strikethrough
from utils import extract_telegram_usernames
import traceback
import uuid
import tempfile
from PyPDF2 import PdfReader

VACANCY_ID_REGEX = re.compile(
    r"(?:🆔\s*)?(?:[\w\-\u0400-\u04FF]+[\s\-]*)?\d+", 
    re.IGNORECASE
)
GROUP_ID = os.getenv('GROUP_ID')
ADMIN_ID = os.getenv('ADMIN_ID')
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")



telethon_client = TelegramClient('dmitryi', API_ID, API_HASH)

async def forward_messages_from_topics(telethon_client, TOPIC_MAP, AsyncSessionLocal, bot : Bot, days=14):
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    await bot.send_message(ADMIN_ID, f"[i] Берем сообщения с {cutoff_date}")

    for (src_chat, src_topic_id), (dst_chat, dst_topic_id) in TOPIC_MAP.items():
        await bot.send_message(ADMIN_ID, f"[i] Проверяем топик {src_topic_id} в чате {src_chat}")
        try:
            msgs = []
            async for msg in telethon_client.iter_messages(
                src_chat,
                reply_to=src_topic_id,
                reverse=True,

            ):
                if msg.date >= cutoff_date:
                    msgs.append(msg)
            msgs.sort(key=lambda m: m.date)
            
            for msg in msgs:
                text = msg.text
                if not text:
                    continue
                
                if check_project_duration(text):
                    await bot.send_message(ADMIN_ID, f'❌ Маленькая продолжительность проекта в сообщении {msg.id}')
                    continue

                if has_strikethrough(msg):
                    await bot.send_message(ADMIN_ID, f"❌ Сообщение {msg.id} содержит зачёркнутый текст — пропускаем")
                    continue
                
                try:
                    text_gpt = await process_vacancy_with_gemini(text)
                except Exception as e:
                    await bot.send_message(ADMIN_ID, f'❌ Ошибка в GPT в сообщении {msg.id}: {e}')
                    continue
                
                reason = text_gpt.get("reason")
                if reason:
                    await bot.send_message(ADMIN_ID, f'❌ Вакансия отсеяна в GPT в сообщении {msg.id}: {reason}')
                    continue
                
                if text_gpt == None or text_gpt == 'None':
                    await bot.send_message(ADMIN_ID, f'❌ Вакансия отсеяна в GPT в сообщении {msg.id}')
                    continue
            
                try:
                    text = text_gpt.get("text")
                    if text is None:
                        await bot.send_message(ADMIN_ID, f'❌ Вакансия отсеяна в GPT в сообщении {msg.id}')
                        continue
                
                    
                    vac_id = text_gpt.get('vacancy_id')
                    if vac_id is None or vac_id == 'None':
                        await bot.send_message(ADMIN_ID, f'❌ Нет айди в GPT в сообщении {msg.id}')
                        continue
                    vac_id = vac_id.replace("_", "").replace(" ", "")
                    rate = text_gpt.get("rate")
                    vacancy = text_gpt.get('vacancy_title')
                    deadline_date = text_gpt.get("deadline_date")
                    deadline_time = text_gpt.get("deadline_time")
                    utochnenie = text_gpt.get("utochnenie")
                    delay_payment = text_gpt.get("delay_payment")
                    acts = text_gpt.get("acts")
                    only_fulltime = text_gpt.get("only_fulltime")
                    short_project = text_gpt.get("short_project")
                    long_payment = text_gpt.get("long_payment")
                    message_date = f'Дата публикации: {get_message_datetime(msg)}'
                    location = text_gpt.get("location")
                    rf_loc = False
                    rb_loc = False
                    for loc in location:
                        if loc == 'РФ':
                            rf_loc = True
                        elif loc == 'РБ':
                            rb_loc = True
                    
                    print(f'rate: {rate} в {vac_id}')
                    print(f'rf_loc: {rf_loc} в {vac_id}')
                    print(f'rb_loc: {rb_loc} в {vac_id}')
                    
                    if vacancy is None or vacancy == 'None':
                        await bot.send_message(ADMIN_ID, f'❌ Нет вакансии в GPT в сообщении {msg.id}')
                        continue
                     

                    # Вакансия отсекается, если нет ID
                    if vac_id is None  or vac_id == 'None':
                        await bot.send_message(ADMIN_ID, f'❌ Вакансия отсеяна, нет ID в сообщении {msg.id}')
                        continue

                    # Блок для обработки ставки
                    if delay_payment:
                        delay_payment_text = f"С отсрочкой платежа {delay_payment}после подписания акта:\n"
                        no_rate_delay = f'Условия оплаты: {delay_payment}'
                    else:
                        delay_payment_text = 'С отсрочкой платежа "35 рабочих дней" после подписания акта:\n'
                        no_rate_delay = 'Условия оплаты: Срок уточняется'
        
        
        
        
        # Блок для обработки ставки
                    if rate is None or rate =='0' or type(rate) != dict:
        # если ставки нет — общий текст
                        text_cleaned = (
                            f"🆔{vac_id}\n\n"
                            f"{vacancy}\n\n"
                            f"Месячная ставка (на руки) до: смотрим ваши предложения (приоритет на минимальную)\n\n"
                            f"{no_rate_delay}\n\n"
                            f"{text}"
                                            )
                    else:
                        rate_rb = rate.get("РБ")
                        rate_rf = rate.get("РФ")
                        rate_rf_contract = None
                        rate_rf_ip = None
                        rate_partners_rf = None
                        rate_rb_contract = None
                        rate_rb_ip = None
                        rate_partners_rb = None
                        print(rate_rf, rate_rb)

                        if rate_rb:
                            rate_rb = int(rate_rb)
                        if rate_rf:
                            rate_rf = int(rate_rf)

                        # --- варианты для РФ ---
                        if rf_loc:
                            rate_rf_contract = await search_and_extract_values(
                                'K', rate_rf, ['B'], 'Расчет ставки (штат) ЮЛ РФ','https://docs.google.com/spreadsheets/d/1vjHlEdWO-IkzU5urYrorb0FlwMS7TPfnBDSAhnSYp98'
                            )
                            rate_rf_ip = await search_and_extract_values(
                                'K', rate_rf, ['B', 'J'], 'Расчет ставки (ИП) ЮЛ РФ','https://docs.google.com/spreadsheets/d/1vjHlEdWO-IkzU5urYrorb0FlwMS7TPfnBDSAhnSYp98'
                            )

                            rate_partners_rf = await search_and_extract_values(
                                'H', rate_rf, ['L'], 'СНГ (РФ)','https://docs.google.com/spreadsheets/d/1M5YnAuCVghdjCBvCtoflTtRPm7lLHI98abuNyZpO3vc', partner=True
                            )

                        # --- варианты для РБ ---
                        if rb_loc:
                            rate_rb_contract = await search_and_extract_values(
                                'M', rate_rb, ['B'], 'Расчет ставки (штат/контракт) СНГ'
                            )
                            rate_rb_ip = await search_and_extract_values(
                                'N', rate_rb, ['B', 'L'], 'Расчет ставки (Самозанятый/ИП) СНГ'
                            )
                            rate_partners_rb = await search_and_extract_values(
                                'H', rate_rb, ['L'], 'СНГ (РБ)','https://docs.google.com/spreadsheets/d/1M5YnAuCVghdjCBvCtoflTtRPm7lLHI98abuNyZpO3vc', partner=True
                            )
                            print(rate_partners_rb)
                            print(rate_partners_rf)
                            

                        # --- объединённая логика оформления ---
                        def build_salary_block(flag_rf=False, flag_rb=False):
                            """Внутренняя функция для форматирования текста ставок"""
                            flag_text = "🇷🇺" if flag_rf else "🇧🇾"
                            region = "РФ" if flag_rf else "РБ"

                            # выбираем нужные пары
                            contract_data = rate_rf_contract if flag_rf else rate_rb_contract
                            ip_data = rate_rf_ip if flag_rf else rate_rb_ip

                            if not contract_data or not ip_data:
                                return (
                                    f"{flag_text}💰 Месячная ставка для юр лица {region}: "
                                    f"смотрим ваши предложения (приоритет на минимальную)\n\n{no_rate_delay}\n"
                                )

                            rate_contract = contract_data.get('B')
                            rate_ip = ip_data.get('B')
                            gross = None
                            if ip_data.get('L'):
                                gross = ip_data.get('L')
                            else:
                                gross = ip_data.get('J')

                            # округляем IP/самозанятый до 1000
                            try:
                                rounded = (int(rate_ip) // 1000) * 1000
                                rate_ip = f"{rounded:,}".replace(",", " ")
                            except Exception:
                                pass

                            # форматы актирования и зачёркиваний
                            if acts:
                                acts_text = "Актирование: поквартальное\n"
                            else:
                                acts_text = "Актирование: ежемесячное\n"
                            state_contract_text = (
                                    f"Вариант 1. Ежемесячная выплата Штат/Контракт (на руки) до: {rate_contract} RUB "
                                    f"(с выплатой зарплаты 11 числа месяца следующего за отчетным)\n"
                                )


                            
                            ip_text = f'Вариант 2. Выплата ИП/Самозанятый\n{delay_payment_text}({acts_text}):\n{gross} RUB/час (Gross)\nСправочно в месяц (при 170 раб. часов): {rate_ip} RUB(Gross)'

                            return (
                                f"{flag_text}"
                                f"💰 Месячная ставка для юр лица {region}:\n"
                                f"{state_contract_text}\n\n"
                                f"{ip_text}\n"
                            )

                        # --- итоговое формирование ---
                        salary_text = ""
                        rate_partners_rf = rate_partners_rf.get('L', 'Ставка из исходного текста') if rate_partners_rf else None
                        rate_partners_rb = rate_partners_rb.get('L', 'Ставка из исходного текста') if rate_partners_rb else None
                        if rate_partners_rf and rate_partners_rb:
                            salary_p_text = f'Ставка для подрядчиков РФ: {rate_partners_rf}\nСтавка для подрядчиков РБ: {rate_partners_rb}'
                        elif rate_partners_rf:
                            salary_p_text = f'Ставка для подрядчиков РФ: {rate_partners_rf}'
                        elif rate_partners_rb:
                            salary_p_text = f'Ставка для подрядчиков РБ: {rate_partners_rb}'
                        else:
                            salary_p_text = ''
                        print(salary_p_text)
                        text_cleaned_part = f"🆔{vac_id}\n\n{vacancy}\n\n{salary_p_text}\n{text}"

                        if rf_loc and rb_loc:
                            # обе страны
                            salary_text = build_salary_block(flag_rb=True) + "\n" + build_salary_block(flag_rf=True)
                        elif rf_loc:
                            # только РФ
                            salary_text = build_salary_block(flag_rf=True)
                        elif rb_loc:
                            # только РБ
                            salary_text = build_salary_block(flag_rb=True)
                        else:
                            # ни одна не указана
                            salary_text = (
                                "💰 Месячная ставка: смотрим ваши предложения "
                                "(приоритет на минимальную)\n\n"
                                f"{no_rate_delay}\n"
                            )
                        text_cleaned = f"🆔{vac_id}\n\n{vacancy}\n\n{salary_text}\n{text}"
                    formatted_text = await format_vacancy_gemini(text_cleaned, vac_id, message_date)
                    formatted_text_part = await format_vacancy_gemini_for_partners(text_cleaned_part, vac_id, message_date)
                        
                    if utochnenie == 'True' or utochnenie is True:
                        await bot.send_message(ADMIN_ID, "Отправлено для уточнения")
                        await bot.send_message(ADMIN_ID, formatted_text)
                        continue
                    try:                 
                        mess = await bot.send_message(chat_id=dst_chat, text='.', message_thread_id=dst_topic_id)
                        message_id_part = await bot.send_message(chat_id=-1003360331196, text='.', parse_mode='HTML')
                        cleaned_text = remove_vacancy_id(formatted_text)
                        cleaned_text_part = remove_vacancy_id(formatted_text_part)
                        url = f"https://t.me/omega_vacancy_bot?start={mess.message_id}_{vac_id}"
                        ms_text = f"<a href='{url}'>{vac_id}</a>\n{cleaned_text}"
                        ms_text_part = f"<a href='{url}'>{vac_id}</a>\n{cleaned_text_part}"
                        forwarded_msg = await bot.edit_message_text(
                            chat_id=dst_chat,
                            message_id=mess.message_id,
                            text=ms_text,
                            parse_mode='HTML',
                        )
                        await bot.edit_message_text(chat_id=-1003360331196, message_id=message_id_part.message_id, text=ms_text_part,parse_mode='HTML')
                        user_name_tg = extract_telegram_usernames(ms_text)
                        await send_mess_to_group(GROUP_ID, formatted_text, vac_id, bot)
                        await add_actual_vacancy(vac_id, vacancy, mess.message_id, user_name_tg)
                        await update_actual_vacancy(bot, telethon_client)
            
                    except Exception as e:
                        await bot.send_message(ADMIN_ID, f'❌ Ошибка при отправке в сообщении {msg.id}: {e}')
                        continue
                    
                    
                    
                
                    await add_message_mapping(
                        src_chat_id=src_chat,
                        src_msg_id=msg.id,
                        dst_chat_id=dst_chat,
                        dst_msg_id=forwarded_msg.message_id,
                        deadline_date=deadline_date,
                        deadline_time=deadline_time
                    )
                
                except Exception as e:
                    traceback.print_exc()
                    await bot.send_message(ADMIN_ID, f'❌ Ошибка при обработке и отправке в сообщении {msg.id}: {e}')
                    continue
            
        except Exception as e:
            await bot.send_message(ADMIN_ID, f"[!] Ошибка при чтении топика {src_topic_id} в чате {src_chat}: {e}")
    


async def extract_text_from_pdf(pdf_path: str) -> str:
    """Извлекает текст из PDF файла"""
    try:
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        print(f"❌ Ошибка при извлечении текста из PDF: {e}")
        return ""

async def forward_messages_from_chats(telethon_client, CHAT_LIST, AsyncSessionLocal, bot : Bot, days=14):
    """
    Обрабатывает сообщения из списка чатов за последние N дней.
    Вызывает scrap_vacancy и отправляет данные на сервер.
    
    Args:
        telethon_client: Клиент Telethon
        CHAT_LIST: Список chat_id исходных чатов (например, [-1001259051878])
        AsyncSessionLocal: Сессия БД
        bot: Бот Aiogram
        days: Количество дней назад для выборки сообщений (по умолчанию 14)
    """
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    await bot.send_message(ADMIN_ID, f"[i] Берем сообщения с {cutoff_date}")

    for src_chat in CHAT_LIST:
        await bot.send_message(ADMIN_ID, f"[i] Проверяем чат {src_chat}")
        try:
            msgs = []
            # Итерируемся по сообщениям из обычного чата (без reply_to)
            async for msg in telethon_client.iter_messages(
                src_chat,
                reverse=True,
            ):
                if msg.date >= cutoff_date:
                    msgs.append(msg)
            msgs.sort(key=lambda m: m.date)
            
            for msg in msgs:
                text = msg.text or ""
                data = []
                
                # Определяем offer по chat_id
                if src_chat == -1001898906854:
                    offer = 'Ekleft'
                elif src_chat == -1001527372844:
                    offer = 'VOLNA'
                elif src_chat == -1001259051878:
                    offer = 'SkillStaff'
                elif src_chat == -1001870091031:
                    offer = 'Novelect'
                else:
                    offer = None
                
                # Для канала Novelect обрабатываем PDF файл
                if src_chat == -1001870091031 and msg.media:
                    try:
                        # Проверяем, что это документ (PDF)
                        if isinstance(msg.media, types.MessageMediaDocument):
                            document = msg.media.document
                            if document.mime_type == 'application/pdf':
                                # Создаем временный файл для PDF
                                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                                    pdf_path = tmp_file.name
                                
                                try:
                                    # Скачиваем PDF файл
                                    await telethon_client.download_media(msg.media, pdf_path)
                                    
                                    # Извлекаем текст из PDF
                                    pdf_text = await extract_text_from_pdf(pdf_path)
                                    
                                    if pdf_text:
                                        # Генерируем случайный ID
                                        random_id = str(uuid.uuid4())[:8].upper()
                                        
                                        # Добавляем ID в начало текста
                                        text = f"🆔 {random_id}\n\n{pdf_text}"
                                        
                                        await bot.send_message(ADMIN_ID, f'✅ PDF файл обработан для канала Novelect (сообщение {msg.id}), ID: {random_id}')
                                    else:
                                        await bot.send_message(ADMIN_ID, f'⚠️ Не удалось извлечь текст из PDF для сообщения {msg.id}')
                                        continue
                                except Exception as e:
                                    await bot.send_message(ADMIN_ID, f'❌ Ошибка при обработке PDF для сообщения {msg.id}: {e}')
                                    continue
                                finally:
                                    # Удаляем временный файл
                                    if os.path.exists(pdf_path):
                                        os.remove(pdf_path)
                            else:
                                await bot.send_message(ADMIN_ID, f'⚠️ В сообщении {msg.id} канала Novelect не PDF файл, пропускаем')
                                continue
                        else:
                            # Если нет медиа или это не документ, проверяем есть ли текст
                            if not text:
                                continue
                    except Exception as e:
                        await bot.send_message(ADMIN_ID, f'❌ Ошибка при проверке медиа для сообщения {msg.id}: {e}')
                        continue
                
                if not text:
                    continue
                
                if 'вакансия неактивна' in text.lower():
                    print('Вакансия неактивна')
                    continue
                
                    
                message_text = remove_vacancy_id(text)
                
                
                try:
                    text_gpt = await process_vacancy_with_gemini(text)
                    reason = text_gpt.get("reason")
                    if reason:
                        await bot.send_message(ADMIN_ID, f'❌ Вакансия отсеяна в GPT в сообщении {msg.id}: {reason}')
                        continue
                    
                    # Используем scrap_vacancy или scrap_vacancy_for_new_gr в зависимости от наличия offer
                    if offer:
                        vacancy_scraping = await scrap_vacancy_for_new_gr(text, offer)
                    else:
                        vacancy_scraping = await scrap_vacancy(text)
                   
                    
                    print(vacancy_scraping)
                    vacancy_scraping = json.loads(vacancy_scraping)
                except Exception as e:
                    print(f"❌ Ошибка при обработке вакансии: {e}")
                    await bot.send_message(ADMIN_ID, f'❌ Ошибка при обработке вакансии в сообщении {msg.id}: {e}')
                    continue

                vac_id = vacancy_scraping['vacancy_id']
                title = vacancy_scraping['title']
                work_format = vacancy_scraping['work_format']
                employment_type = vacancy_scraping['employment_type']
                english_level = vacancy_scraping['english_level']
                language = vacancy_scraping.get('language', 'unspecified')
                grade = vacancy_scraping['grade']
                company_type = vacancy_scraping['company_type']
                specialization = vacancy_scraping['specializations']
                skills = vacancy_scraping['skills']
                domains = vacancy_scraping['domains']
                location = vacancy_scraping['location']
                manager_username = vacancy_scraping['manager_username']
                customer = vacancy_scraping['customer']
                categories = vacancy_scraping['categories']
                subcategories = vacancy_scraping['subcategories']
                salary = vacancy_scraping.get('salary', '')
                created_at = msg.date.isoformat() if msg.date else None
                specialization = ', '.join(specialization) if specialization else None
                skills = ', '.join(skills) if skills else None
                domains = ', '.join(domains) if domains else None
                location = ', '.join(location) if location else None
                categories = ', '.join(categories) if categories else None
                subcategories = ', '.join(subcategories) if subcategories else None

                if not vacancy_scraping:
                    continue

                data.append({
                    'vacancy_id': vac_id,
                    'title': title,
                    'vacancy_text': strip_md_link(message_text),
                    'vacancy_scrap': vacancy_scraping,
                    'work_format': work_format,
                    'employment_type': employment_type,
                    'english_level': english_level,
                    'language': language,
                    'grade': grade,
                    'company_type': company_type,
                    'specializations': specialization,
                    'skills': skills,
                    'domains': domains,
                    'location': location,
                    'manager_username': manager_username,
                    'customer': customer,
                    'categories': categories,
                    'subcategories': subcategories,
                    'created_at': created_at,
                    'salary': salary
                })
                
                try:
                    status = requests.post('https://omegahire.tech/vacancy_create', json=data)
                    print(f"Статус отправки: {status.status_code}")
                    if status.status_code == 200:
                        await bot.send_message(ADMIN_ID, f'✅ Вакансия {vac_id} отправлена на сервер из чата {src_chat} (сообщение {msg.id})')
                    else:
                        await bot.send_message(ADMIN_ID, f'⚠️ Ошибка отправки вакансии {vac_id} на сервер: статус {status.status_code}')
                except Exception as e:
                    print(f"❌ Ошибка при отправке на сервер: {e}")
                    await bot.send_message(ADMIN_ID, f'❌ Ошибка при отправке вакансии {vac_id} на сервер: {e}')
            
        except Exception as e:
            await bot.send_message(ADMIN_ID, f"[!] Ошибка при чтении чата {src_chat}: {e}")
    




async def register_topic_listener(telethon_client, TOPIC_MAP, AsyncSessionLocal, bot : Bot):
    print('Сканирование топиков включено')

    # Берём все уникальные чаты из TOPIC_MAP для подписки
    chats_to_watch = list({chat_id for chat_id, _ in TOPIC_MAP.keys()})

    @telethon_client.on(events.NewMessage(chats=chats_to_watch))
    async def new_topic_message(event):
        # Проверяем, что сообщение из топика
        if not hasattr(event.message, 'reply_to') or not event.message.reply_to:
            return  # Не топик-сообщение
        
        src_topic_id = event.message.reply_to.reply_to_msg_id
        
        # Ищем точное соответствие чата и топика
        key = (event.chat_id, src_topic_id)
        if key not in TOPIC_MAP:
            return  # Этот топик не отслеживаем

        dst_chat_id, dst_topic_id = TOPIC_MAP[key]

        text = getattr(event.message, 'message', '') or ""
        if not text:
            return

        # Добавляем все необходимые фильтры

        if has_strikethrough(event.message):
            await bot.send_message(ADMIN_ID, f"❌ Сообщение {event.message.id} содержит зачёркнутый текст — пропускаем")
            return

        if check_project_duration(text):
            await bot.send_message(ADMIN_ID, f'❌ Маленькая продолжительность проекта в топике {src_topic_id} в чате {event.chat_id}')
            return

        try:
            text_gpt = await process_vacancy_with_gemini(text)
        except Exception as e:
            await bot.send_message(ADMIN_ID, f'❌ Ошибка при обработке вакансии в топике {src_topic_id} в чате {event.chat_id}: {e}')
            return
        
        reason = text_gpt.get("reason")
        if reason:
            await bot.send_message(ADMIN_ID, f'❌ Вакансия отсеяна в топике {src_topic_id} в чате {event.chat_id}: {reason}')
            return
        
        if text_gpt is None or text_gpt == 'None':
            return

        try:
            text = text_gpt.get("text")
            if text == None or text == 'None':
                await bot.send_message(ADMIN_ID, f'❌ Вакансия отсеяна в топике {src_topic_id} в чате {event.chat_id}')
                return
            vac_id = text_gpt.get('vacancy_id')
            if vac_id is None or vac_id == 'None':
                await bot.send_message(ADMIN_ID, f'❌ Нет айди в топике {src_topic_id} в чате {event.chat_id}')
                return
            vac_id = vac_id.replace("_", "").replace(" ", "")
            rate = text_gpt.get("rate")
            print(f'rate: {rate} в {vac_id}')
            vacancy = text_gpt.get('vacancy_title')
            if vacancy is None or vacancy == 'None':
                await bot.send_message(ADMIN_ID, f'❌ Нет вакансии в топике {src_topic_id} в чате {event.chat_id}')
                return
            if vac_id is None or vac_id == 'None':
                await bot.send_message(ADMIN_ID, f'❌ Нет айди в топике {src_topic_id} в чате {event.chat_id}')
                return

            deadline_date = text_gpt.get("deadline_date")
            deadline_time = text_gpt.get("deadline_time")
            utochnenie = text_gpt.get("utochnenie")
            delay_payment = text_gpt.get("delay_payment")
            acts = text_gpt.get("acts")
            only_fulltime = text_gpt.get("only_fulltime")
            short_project = text_gpt.get("short_project")
            long_payment = text_gpt.get("long_payment")
            message_date = f"Дата публикации: {get_message_datetime(event.message)}"
            location = text_gpt.get("location")
            rf_loc = False
            rb_loc = False
            for loc in location:
                if loc == 'РФ':
                    rf_loc = True
                elif loc == 'РБ':
                    rb_loc = True
            print(f'location: {location} в {vac_id}')
            
            if delay_payment:
                delay_payment_text = f"С отсрочкой платежа {delay_payment}после подписания акта:\n"
                no_rate_delay = f'Условия оплаты: {delay_payment}'
            else:
                delay_payment_text = 'С отсрочкой платежа "35 рабочих дней" после подписания акта:\n'
                no_rate_delay = 'Условия оплаты: Срок уточняется'
            
            if rate is None or rate =='0' or type(rate) != dict:
                text_cleaned = (
                    f"🆔{vac_id}\n\n"
                    f"{vacancy}\n\n"
                    f"Месячная ставка (на руки) до: смотрим ваши предложения (приоритет на минимальную)\n\n"
                    f"{no_rate_delay}\n\n"
                    f"{text}"
                                    )
                text_cleaned_part = (f"🆔{vac_id}\n\n"
                                    f"{vacancy}\n\n"
                                    f"Ставка для партнеров: смотрим ваши предложения\n\n"
                                    f"{no_rate_delay}\n\n"
                                    f"{text}")
            else:
                rate_rb = rate.get("РБ")
                rate_rf = rate.get("РФ")
                rate_partners_rf = None
                rate_partners_rb = None
                print(rate_rf, rate_rb)
                if rate_rb:
                    rate_rb = int(rate_rb)
                if rate_rf:
                    rate_rf = int(rate_rf)

                # --- варианты для РФ ---
                if rf_loc:
                    rate_rf_contract = await search_and_extract_values(
                        'K', rate_rf, ['B'], 'Расчет ставки (штат) ЮЛ РФ','https://docs.google.com/spreadsheets/d/1vjHlEdWO-IkzU5urYrorb0FlwMS7TPfnBDSAhnSYp98'
                    )
                    rate_rf_ip = await search_and_extract_values(
                        'K', rate_rf, ['B', 'J'], 'Расчет ставки (ИП) ЮЛ РФ','https://docs.google.com/spreadsheets/d/1vjHlEdWO-IkzU5urYrorb0FlwMS7TPfnBDSAhnSYp98'
                    )
                    rate_partners_rf = await search_and_extract_values(
                    'H', rate_rf, ['L'], 'СНГ (РФ)','https://docs.google.com/spreadsheets/d/1M5YnAuCVghdjCBvCtoflTtRPm7lLHI98abuNyZpO3vc', partner=True
                    )

                # --- варианты для РБ ---
                if rb_loc:
                    rate_rb_contract = await search_and_extract_values(
                        'M', rate_rb, ['B'], 'Расчет ставки (штат/контракт) СНГ'
                    )
                    rate_rb_ip = await search_and_extract_values(
                        'N', rate_rb, ['B', 'L'], 'Расчет ставки (Самозанятый/ИП) СНГ'
                    )

                    rate_partners_rb = await search_and_extract_values(
                    'H', rate_rf, ['L'], 'СНГ (РБ)','https://docs.google.com/spreadsheets/d/1M5YnAuCVghdjCBvCtoflTtRPm7lLHI98abuNyZpO3vc', partner=True
                    )       

                # --- объединённая логика оформления ---
                def build_salary_block(flag_rf=False, flag_rb=False):
                    """Внутренняя функция для форматирования текста ставок"""
                    flag_text = "🇷🇺" if flag_rf else "🇧🇾"
                    region = "РФ" if flag_rf else "РБ"

                    # выбираем нужные пары
                    contract_data = rate_rf_contract if flag_rf else rate_rb_contract
                    ip_data = rate_rf_ip if flag_rf else rate_rb_ip

                    if not contract_data or not ip_data:
                        return (
                            f"{flag_text}💰 Месячная ставка для юр лица {region}: "
                            f"смотрим ваши предложения (приоритет на минимальную)\n\n{no_rate_delay}\n"
                        )

                    rate_contract = contract_data.get('B')
                    rate_ip = ip_data.get('B')
                    gross = None
                    if ip_data.get('L'):
                        gross = ip_data.get('L')
                    else:
                        gross = ip_data.get('J')

                    # округляем IP/самозанятый до 1000
                    try:
                        rounded = (int(rate_ip) // 1000) * 1000
                        rate_ip = f"{rounded:,}".replace(",", " ")
                    except Exception:
                        pass

                    # форматы актирования и зачёркиваний
                    if acts:
                        acts_text = "Актирование: поквартальное\n"
                      
                    else:
                        acts_text = "Актирование: ежемесячное\n"
                    state_contract_text = (
                            f"Вариант 1. Ежемесячная выплата Штат/Контракт (на руки) до: {rate_contract} RUB "
                            f"(с выплатой зарплаты 11 числа месяца следующего за отчетным)\n"
                        )

                    

                 
                    ip_text = f'Вариант 2. Выплата ИП/Самозанятый\n{delay_payment_text}({acts_text}):\n{gross} RUB/час (Gross)\nСправочно в месяц (при 170 раб. часов): {rate_ip} RUB(Gross)'

                    return (
                        f"{flag_text}"
                        f"💰 Месячная ставка для юр лица {region}:\n"
                        f"{state_contract_text}\n\n"
                        f"{ip_text}\n"
                    )

                # --- итоговое формирование ---
                salary_text = ""

                if rf_loc and rb_loc:
                    # обе страны
                    salary_text = build_salary_block(flag_rb=True) + "\n" + build_salary_block(flag_rf=True)
                elif rf_loc:
                    # только РФ
                    salary_text = build_salary_block(flag_rf=True)
                elif rb_loc:
                    # только РБ
                    salary_text = build_salary_block(flag_rb=True)
                else:
                    # ни одна не указана
                    salary_text = (
                        "💰 Месячная ставка: смотрим ваши предложения "
                        "(приоритет на минимальную)\n\n"
                        f"{no_rate_delay}\n"
                    )
                text_cleaned = f"🆔{vac_id}\n\n{vacancy}\n\n{salary_text}\n{text}"
                salary_p_text = ''
                rate_partners_rf = rate_partners_rf.get('L', 'Ставка из исходного текста') if rate_partners_rf else None
                rate_partners_rb = rate_partners_rb.get('L', 'Ставка из исходного текста') if rate_partners_rb else None
                if rate_partners_rf and rate_partners_rb:
                    salary_p_text = f'Ставка для подрядчиков РФ: {rate_partners_rf}\nСтавка для подрядчиков РБ: {rate_partners_rb}'
                elif rate_partners_rf:
                    salary_p_text = f'Ставка для подрядчиков РФ: {rate_partners_rf}'
                elif rate_partners_rb:
                    salary_p_text = f'Ставка для подрядчиков РБ: {rate_partners_rb}'
                else:
                    salary_p_text = ''
                print(salary_p_text)
                text_cleaned_part = f"🆔{vac_id}\n\n{vacancy}\n\n{salary_p_text}\n{text}"
                
            formatted_text = await format_vacancy_gemini(text_cleaned, vac_id, message_date)
            formatted_text_part = await format_vacancy_gemini_for_partners(text_cleaned_part, vac_id, message_date)   
        except Exception as e:
            await bot.send_message(ADMIN_ID, f'❌ Ошибка обработки данных вакансии в топике {src_topic_id} в чате {event.chat_id}: {e}')
            return

        try:
            if utochnenie == 'True' or utochnenie is True:
                await bot.send_message(ADMIN_ID, "Отправлено для уточнения")
                await bot.send_message(ADMIN_ID, formatted_text)
                return  # Если отправили в группу уточнений, не отправляем в канал
        except Exception as e:
            await bot.send_message(ADMIN_ID, f'❌ Ошибка отправки в группу уточнений в топике {src_topic_id} в чате {event.chat_id}: {e}')
            return

        try:
            mess = await bot.send_message(chat_id=dst_chat_id, text='.', message_thread_id=dst_topic_id)
            message_id_part = await bot.send_message(chat_id=-1003360331196, text='.', parse_mode='HTML')
            cleaned_text = remove_vacancy_id(formatted_text)
            clean_text_part = remove_vacancy_id(formatted_text_part)
            url = f"https://t.me/omega_vacancy_bot?start={mess.message_id}_{vac_id}"
            ms_text = f"<a href='{url}'>{vac_id}</a>\n{cleaned_text}"
            text_cleaned_part = f'<a href="{url}">{vac_id}</a>\n{clean_text_part}'
            forwarded_msg = await bot.edit_message_text(
                chat_id=dst_chat_id,
                message_id=mess.message_id,
                text=ms_text,
                parse_mode='HTML',
            )
            await bot.edit_message_text(chat_id=-1003360331196, message_id=message_id_part.message_id, text=text_cleaned_part,parse_mode='HTML')
            user_name_tg = extract_telegram_usernames(ms_text)
            await send_mess_to_group(GROUP_ID, formatted_text, vac_id, bot)
            await add_actual_vacancy(vac_id, vacancy, mess.message_id, user_name_tg)
            await update_actual_vacancy(bot, telethon_client)
            
        except Exception as e:
            await bot.send_message(ADMIN_ID, f'❌ Не удалось отправить в канал в топике {src_topic_id} в чате {event.chat_id}: {e}')
            traceback.print_exc()
            return

        # Сохраняем сопоставление сообщений
        await add_message_mapping(
            src_chat_id=event.chat_id,
            src_msg_id=event.message.id,
            dst_chat_id=dst_chat_id,
            dst_msg_id=forwarded_msg.message_id,
            deadline_date=deadline_date,
            deadline_time=deadline_time
        )
        await bot.send_message(ADMIN_ID, f'✅ Вакансия добавлена в канал в топике {src_topic_id} в чате {event.chat_id}')


async def register_chat_listener(telethon_client, src_chat_list, bot: Bot):
    """
    Регистрирует обработчик новых сообщений из списка чатов.
    Вызывает scrap_vacancy и отправляет данные на сервер.
    """
   
    # Преобразуем в список, если передан один элемент
    if not isinstance(src_chat_list, list):
        src_chat_list = [src_chat_list]
    
    print(f'Сканирование чатов {src_chat_list} включено')

    @telethon_client.on(events.NewMessage(chats=src_chat_list))
    async def new_chat_message(event):
        message = event.message
        text = message.text
        data = []
        
        if not text:
            return
        
        if 'вакансия неактивна' in text.lower():
            print('Вакансия неактивна')
            return
        
        message_text = remove_vacancy_id(text)

        if event.chat.id == -1001898906854:
            offer = 'Ekleft Job'
        elif event.chat.id == -1001527372844:
            offer = 'VOLNA'
        elif event.chat.id == -1001259051878:
            offer = 'SkillStaff'
        else:
            offer = None
        
        try:
            text_gpt = await process_vacancy_with_gemini(text)
            reason = text_gpt.get("reason")
            if reason:
                await bot.send_message(ADMIN_ID, f'❌ Вакансия отсеяна в GPT в чате {event.chat_id}: {reason}')
                return
            
            # Используем scrap_vacancy или scrap_vacancy_for_new_gr в зависимости от наличия offer
            if offer:
                vacancy_scraping = await scrap_vacancy_for_new_gr(text, offer)
            else:
                vacancy_scraping = await scrap_vacancy(message_text)
            
            print(vacancy_scraping)
            vacancy_scraping = json.loads(vacancy_scraping)
        except Exception as e:
            print(f"❌ Ошибка при обработке вакансии: {e}")
            await bot.send_message(ADMIN_ID, f'❌ Ошибка при обработке вакансии в чате {event.chat_id}: {e}')
            return
        
        vac_id = vacancy_scraping['vacancy_id']
        title = vacancy_scraping['title']
        work_format = vacancy_scraping['work_format']
        employment_type = vacancy_scraping['employment_type']
        english_level = vacancy_scraping['english_level']
        language = vacancy_scraping.get('language', 'unspecified')
        grade = vacancy_scraping['grade']
        company_type = vacancy_scraping['company_type']
        specialization = vacancy_scraping['specializations']
        skills = vacancy_scraping['skills']
        domains = vacancy_scraping['domains']
        location = vacancy_scraping['location']
        manager_username = vacancy_scraping['manager_username']
        customer = vacancy_scraping['customer']
        categories = vacancy_scraping['categories']
        subcategories = vacancy_scraping['subcategories']
        salary = vacancy_scraping.get('salary', '')
        created_at = message.date.isoformat() if message.date else None
        specialization = ', '.join(specialization) if specialization else None
        skills = ', '.join(skills) if skills else None
        domains = ', '.join(domains) if domains else None
        location = ', '.join(location) if location else None
        categories = ', '.join(categories) if categories else None
        subcategories = ', '.join(subcategories) if subcategories else None

        if not vacancy_scraping:
            return

        data.append({
            'vacancy_id': vac_id,
            'title': title,
            'vacancy_text': strip_md_link(message_text),
            'vacancy_scrap': vacancy_scraping,
            'work_format': work_format,
            'employment_type': employment_type,
            'english_level': english_level,
            'language': language,
            'grade': grade,
            'company_type': company_type,
            'specializations': specialization,
            'skills': skills,
            'domains': domains,
            'location': location,
            'manager_username': manager_username,
            'customer': customer,
            'categories': categories,
            'subcategories': subcategories,
            'created_at': created_at,
            'salary': salary
        })
        
        try:
            status = requests.post('https://omegahire.tech/vacancy_create', json=data)
            print(f"Статус отправки: {status.status_code}")
            if status.status_code == 200:
                await bot.send_message(ADMIN_ID, f'✅ Вакансия {vac_id} отправлена на сервер из чата {event.chat_id}')
            else:
                await bot.send_message(ADMIN_ID, f'⚠️ Ошибка отправки вакансии {vac_id} на сервер: статус {status.status_code}')
        except Exception as e:
            print(f"❌ Ошибка при отправке на сервер: {e}")
            await bot.send_message(ADMIN_ID, f'❌ Ошибка при отправке вакансии {vac_id} на сервер: {e}')


async def send_message_by_username(username: str, text: str, client: TelegramClient):
        try:
            # username можно писать без "@"
            if username.startswith("@"):
                username = username[1:]
            
            entity = await client.get_entity(username)
            await client.send_message(entity, text, parse_mode='html')
            print(f"✅ Сообщение отправлено пользователю @{username}")
            return True
        except Exception as e:
            print(f"❌ Ошибка при отправке @{username}: {e}")
            return False
        


from telethon import functions, types

async def create_recruiter_forum(recruiter_id: int, recruiter_username: str, bot_username: str, client: TelegramClient, vac_id: str, message_text: str, bot: Bot, vac_title: str):
    recruiter_input = None
    if recruiter_username:
        try:
            resolved = await client(functions.contacts.ResolveUsernameRequest(recruiter_username))
            user = resolved.users[0]
            recruiter_input = types.InputUser(user.id, user.access_hash)
        except errors.UsernameNotOccupiedError:
            pass
        except IndexError:
            pass
    title = f"Omega Recruiter — {recruiter_username}"
    about = f"Приватная форум-группа для рекрутера {recruiter_username}"
    group_id = -1002658129391  # ID твоей группы
    if not recruiter_input:
        
        group = await client.get_entity(group_id)
        dialogs = await client.get_dialogs()
        entity = None
        for dialog in dialogs:
            if dialog.entity.id == recruiter_id:
                entity = await client.get_input_entity(dialog.entity)
                break

        if not entity:
            participants = await client.get_participants(group)
            for p in participants:
                if p.id == recruiter_id:
                    entity = await client.get_input_entity(p)
                    break
        if not entity:
            print("❌ Не удалось найти пользователя в группе")
            return
    else:
        entity = recruiter_input
    # 1️⃣ Создаём мегагруппу
    result = await client(functions.channels.CreateChannelRequest(
        title=title,
        about=about,
        megagroup=True  # обязательно, чтобы включить форум
    ))

    group = result.chats[0]
    group_id = group.id
    print(f"[+] Создана группа: {title} ({group_id})")

    # 2️⃣ Включаем режим форума (topics)
    await client(functions.channels.ToggleForumRequest(
        channel=group,
        enabled=True,
        tabs = False
    ))
    print("[+] Форум включён")
    

    # 3️⃣ Добавляем туда рекрутера и бота
    try:
        await client(functions.channels.InviteToChannelRequest(
            channel=group,
            users=[entity, f"@{bot_username}", f'@kupitmancik']
        ))
    except Exception as e:
        await bot.send_message(ADMIN_ID, f"❌ Ошибка при добавлении @{bot_username} и рекрутера {recruiter_username}: {e}")
    print(f"[+] Добавлены @{bot_username} и рекрутер {recruiter_username}")
    
    # 3.5️⃣ Даем боту права администратора
    try:
        await client(functions.channels.EditAdminRequest(
            channel=group,
            user_id=f"@{bot_username}",
            admin_rights=types.ChatAdminRights(
                change_info=False,
                post_messages=True,
                edit_messages=True,
                delete_messages=True,
                ban_users=False,
                invite_users=False,
                pin_messages=True,
                add_admins=False,
                anonymous=False,
                manage_call=False,
                other=False,
                manage_topics=True
            ),
            rank="Bot Assistant"
        ))
        print(f"[+] Боту @{bot_username} предоставлены права администратора")
    except Exception as e:
        await bot.send_message(ADMIN_ID, f"❌ Ошибка при предоставлении прав боту: {e}")
    
    # 3.6️⃣ Даем рекрутеру права администратора
    try:
        await client(functions.channels.EditAdminRequest(
            channel=group,
            user_id=recruiter_id,
            admin_rights=types.ChatAdminRights(
                change_info=True,
                post_messages=True,
                edit_messages=True,
                delete_messages=True,
                ban_users=True,
                invite_users=True,
                pin_messages=True,
                add_admins=False,
                anonymous=False,
                manage_call=True,
                other=True,
                manage_topics=True
            ),
            rank="Recruiter"
        ))
        print(f"[+] Рекрутеру {recruiter_username} предоставлены права администратора")
    except Exception as e:
        await bot.send_message(ADMIN_ID, f"❌ Ошибка при предоставлении прав рекрутеру: {e}")

    # 4️⃣ Создаём тестовую тему (пример вакансии)
    topic_result = await client(functions.channels.CreateForumTopicRequest(
        channel=group,
        title=f"{vac_id}  {vac_title}",
        icon_color=7322096 
    ))

    # Получаем topic_id из updates
    topic_id = None
    
    for update in topic_result.updates:
        # Ищем UpdateNewChannelMessage с MessageActionTopicCreate
        if hasattr(update, 'message') and hasattr(update.message, 'action'):
            if 'TopicCreate' in str(type(update.message.action)):
                topic_id = update.message.id
                break
    
    if not topic_id:
        await bot.send_message(ADMIN_ID, "❌ Не удалось получить topic_id")
        return group_id
        
    print(f"[+] Создана тема: {topic_id}")
    group_id = f'-100{group_id}'

    await bot.send_message(chat_id = group_id, message_thread_id = topic_id, text = message_text, parse_mode='HTML')
    await add_vacancy_thread(thread_id = topic_id, chat_id = group_id, vacancy_text = message_text, vacancy_id = vac_id)

    return group_id, topic_id
        
    


async def create_vacancy_thread(group_id: int, mes_text: str, client: TelegramClient, vac_id: str, bot: Bot, title: str):
    """
    Создаёт новый тред (forum topic) в указанной форум-группе.
    Возвращает словарь с данными темы.
    """
    tread_create = False
    resp = await client(functions.channels.GetForumTopicsRequest(channel=group_id,offset_date=None, offset_id=0, offset_topic=0, limit=100, q=vac_id))
    
    
    if resp.topics != []:
        tread_id = resp.topics[0].id
        tread_create = True
        print(f"[+] Тема {vac_id} уже существует")
        return tread_id, tread_create

    # 1️⃣ Создаём тему в форуме
    result = await client(functions.channels.CreateForumTopicRequest(
        channel=group_id,
        title=f"{vac_id}  {title}",
        icon_color=7322096  # красивый синий (HEX #6FB1FC)
    ))

    # Получаем topic_id из updates
    topic_id = None
    
    for update in result.updates:
        # Ищем UpdateNewChannelMessage с MessageActionTopicCreate
        if hasattr(update, 'message') and hasattr(update.message, 'action'):
            if 'TopicCreate' in str(type(update.message.action)):
                topic_id = update.message.id
                break
    
    if not topic_id:
        await bot.send_message(ADMIN_ID, f"❌ Не удалось получить topic_id для группы {group_id}")
        return

    print(f"[+] Создан новый тред в группе {group_id}: {vac_id} (topic_id={topic_id})")

    try:
        await bot.send_message(chat_id = group_id, message_thread_id = topic_id, text = mes_text, parse_mode='HTML')
        await add_vacancy_thread(thread_id = topic_id, chat_id = group_id, vacancy_text = mes_text, vacancy_id = vac_id)
        print(f"[+] Отправлено описание вакансии в тред {topic_id}")
    except Exception as e:
        await bot.send_message(ADMIN_ID, f"❌ Ошибка при отправке в тред {topic_id}: {e}")
        
    return topic_id, tread_create

from utils import replace_channel_mail

import os
from telethon import TelegramClient, errors

from aiogram.exceptions import TelegramRetryAfter
from telethon.errors import FloodWaitError

async def replace_mails_in_channel(client: TelegramClient, bot: Bot):
    GROUP_ID_STR = os.getenv("GROUP_ID")
    try:
        GROUP_ID = int(GROUP_ID_STR)
    except (ValueError, TypeError):
        print(f"❌ Ошибка: GROUP_ID должен быть числом, получено: {GROUP_ID_STR}")
        return
    
    print(f"GROUP_ID: {GROUP_ID} (type: {type(GROUP_ID)})")
    print("[+] Запущен процесс замены ссылок в группе")
    
    try:
        # Получаем entity для группы
        entity = await client.get_entity(GROUP_ID)
        print(f"[+] Получена entity для группы: {entity.title if hasattr(entity, 'title') else entity}")
        
        message_count = 0
        async for message in client.iter_messages(entity, limit=None, reverse=False):
            message_count += 1
            if message_count % 100 == 0:
                print(f"[+] Обработано {message_count} сообщений...")
            
            # service messages пропускаем
            if not message.message:
                continue

            new_text = replace_channel_mail(message.message)
            
            if not new_text:
                try:
                    #await client.delete_messages(entity=GROUP_ID, message_ids=message.id)
                    print(f"[✓] Удалено сообщение {message.id} в группе {GROUP_ID}")
                    continue
                except Exception as e:
                    print(f"[!] Ошибка при удалении {message.id}: {e}")
                    
                   
                    continue

            # Если new_text не None, значит была замена - редактируем
            if new_text:
                try:
                    await client.edit_message(entity=GROUP_ID, message=message.id, text=new_text)
                    print(f"[✓] Заменено сообщение {message.id} в группе {GROUP_ID}")
                    await asyncio.sleep(5)
                
                except TelegramRetryAfter as e:
                    print(f"[!] Ошибка при редактировании {message.id}: {e}")
                    print(f"[!] Задержка на {e.retry_after} секунд")
                    await asyncio.sleep(e.retry_after)
                    continue
                except FloodWaitError as e:
                    print(f"[!] Ошибка при редактировании {message.id}: {e}")
                    print(f"[!] Задержка на {e.seconds} секунд")
                    await asyncio.sleep(e.seconds)
                    continue
                except Exception as e:
                    print(f"[!] Ошибка при редактировании {message.id}: {e}")
                    await client.delete_messages(entity=GROUP_ID, message_ids=message.id)
                    print(f"[✓] Удалено сообщение {message.id} в группе {GROUP_ID}")
                    await asyncio.sleep(5)
                    continue
        
        print(f"[+] Завершено. Всего обработано сообщений: {message_count}")
        
    except Exception as e:
        print(f"❌ Ошибка при итерации по сообщениям: {e}")
        import traceback
        traceback.print_exc()

from funcs import remove_vacancy_id, extract_vacancy_id, get_vacancy_title
from telethon.tl import functions
import asyncio
import requests
import json
import re

def strip_md_link(text: str) -> str:
    # находим конструкции вида [текст](ссылка) и оставляем только текст
    return re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)


async def send_vac_to_site(client: TelegramClient):
    import json
    
    channel = -1002658129391
    
    # Получаем информацию о канале/группе
   
    
    async for message in client.iter_messages(channel, limit=None, reverse=False):
        data = []
        if not message.message:
            continue
        if not message.text:
            continue
        if 'вакансия неактивна' in message.text.lower():
            print('Вакансия неактивна')
            continue
        
        vac_id = extract_vacancy_id(message.text)
        if not vac_id:
            continue
            
        message_text = remove_vacancy_id(message.text)
        title = get_vacancy_title(message_text)
        if not title:
            continue
       
        vacancy_scraping = await scrap_vacancy(message_text)
        try:
            vacancy_scraping = json.loads(vacancy_scraping)
        except Exception as e:
            print(f"❌ Ошибка при загрузке вакансии: {e}")
            continue
        work_format = vacancy_scraping['work_format']
        employment_type = vacancy_scraping['employment_type']
        english_level = vacancy_scraping['english_level']
        language = vacancy_scraping.get('language', 'unspecified')
        grade = vacancy_scraping['grade']
        company_type = vacancy_scraping['company_type']
        specialization = vacancy_scraping['specializations']
        skills = vacancy_scraping['skills']
        domains = vacancy_scraping['domains']
        location = vacancy_scraping['location']
        manager_username = vacancy_scraping['manager_username']
        customer = vacancy_scraping['customer']
        categories = vacancy_scraping['categories']
        subcategories = vacancy_scraping['subcategories']
        salary = vacancy_scraping.get('salary', '')
        created_at = message.date.isoformat() if message.date else None
        specialization = ', '.join(specialization) if specialization else None
        skills = ', '.join(skills) if skills else None
        domains = ', '.join(domains) if domains else None
        location = ', '.join(location) if location else None
        categories =', '.join(categories) if categories else None
        subcategories =', '.join(subcategories) if subcategories else None

        
        
        
        if not vacancy_scraping:
            continue    
            
        data.append({
            'vacancy_id': vac_id,
            'title': title,
            'vacancy_text': strip_md_link(message_text),
            'vacancy_scrap': vacancy_scraping,
            'work_format': work_format,
            'employment_type': employment_type,
            'english_level': english_level,
            'language': language,
            'grade': grade,
            'company_type': company_type,
            'specializations': specialization,
            'skills': skills,
            'domains': domains,
            'location': location,
            'manager_username': manager_username,
            'customer': customer,
            'categories' : categories,
            'subcategories' : subcategories,
            'created_at': created_at,
            'salary': salary
        
        })
        
        print(data)
    
       
        status = requests.post('https://omegahire.tech/vacancy_create', json=data)
        print(f"Статус отправки: {status.status_code}")
        
@telethon_client.on(events.NewMessage(chats=-1002658129391))
async def channel_post_bot(event):
    print('Новое сообщение')

    message = event.message
    text = message.text
    data = []
    
    if not text:
        return
    if 'вакансия неактивна' in text.lower():
        print('Вакансия неактивна')
        return
        
    vac_id = extract_vacancy_id(text)
    if not vac_id:
        return
            
    message_text = remove_vacancy_id(text)
    title = get_vacancy_title(message_text)
    if not title:
        return
       
    vacancy_scraping = await scrap_vacancy(message_text)
    print(vacancy_scraping)
    try:
        vacancy_scraping = json.loads(vacancy_scraping)
    except Exception as e:
        print(f"❌ Ошибка при загрузке вакансии: {e}")
        return
    work_format = vacancy_scraping['work_format']
    employment_type = vacancy_scraping['employment_type']
    english_level = vacancy_scraping['english_level']
    language = vacancy_scraping.get('language', 'unspecified')
    grade = vacancy_scraping['grade']
    company_type = vacancy_scraping['company_type']
    specialization = vacancy_scraping['specializations']
    skills = vacancy_scraping['skills']
    domains = vacancy_scraping['domains']
    location = vacancy_scraping['location']
    manager_username = vacancy_scraping['manager_username']
    customer = vacancy_scraping['customer']
    categories = vacancy_scraping['categories']
    subcategories = vacancy_scraping['subcategories']
    salary = vacancy_scraping.get('salary', '')
    created_at = message.date.isoformat() if message.date else None
    specialization = ', '.join(specialization) if specialization else None
    skills = ', '.join(skills) if skills else None
    domains = ', '.join(domains) if domains else None
    location = ', '.join(location) if location else None
    categories = ', '.join(categories) if categories else None
    subcategories = ', '.join(subcategories) if subcategories else None

    if not vacancy_scraping:
            return

    data.append({
            'vacancy_id': vac_id,
            'title': title,
            'vacancy_text': strip_md_link(message_text),
            'vacancy_scrap': vacancy_scraping,
            'work_format': work_format,
            'employment_type': employment_type,
            'english_level': english_level,
            'language': language,
            'grade': grade,
            'company_type': company_type,
            'specializations': specialization,
            'skills': skills,
            'domains': domains,
            'location': location,
            'manager_username': manager_username,
            'customer': customer,
            'categories': categories,
            'subcategories': subcategories,
            'created_at': created_at,
            'salary': salary
        })
        
        
    
       
    status = requests.post('https://omegahire.tech/vacancy_create', json=data)
    print(f"Статус отправки: {status.status_code}")

         
     