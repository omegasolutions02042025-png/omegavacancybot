from aiogram import Router
from aiogram import Bot, Dispatcher, types, F

from aiogram.types import CallbackQuery, FSInputFile, Message
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart, Command
from kb import *
from telethon_bot import *
import os
from send_email import send_email_gmail
from dotenv import load_dotenv
from funcs import *
from gpt_gimini import  process_vacancy_with_gemini, format_vacancy_gemini, generate_mail_for_candidate_finalist, generate_mail_for_candidate_otkaz, generate_cover_letter_for_client
from googlesheets import search_and_extract_values
from telethon_bot import telethon_client
from db import *
from scan_documents import process_file_and_gpt, create_finalists_table, create_mails
import shutil
from dotenv import load_dotenv
import asyncio
from telethon_bot import create_vacancy_thread, create_recruiter_forum , telethon_client
from generate_wl_res import create_white_label_resume_once
load_dotenv()

CLIENT_CHANNEL = os.getenv('CLIENT_CHANNEL')
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

bot_router = Router()
SAVE_DIR = "downloads"

class AddChannel(StatesGroup):
    waiting_for_id = State()
    waiting_for_name = State()

class ScanHand(StatesGroup):
    waiting_for_hand = State()
    waiting_for_topic = State()
    

class ScanVacRekr(StatesGroup):
    waiting_for_vac = State()


class WaitForNewResume(StatesGroup):
    waiting_for_new_resume = State()

class AddUtochnenie(StatesGroup):
    waiting_for_utochnenie = State()

class AddContact(StatesGroup):
    waiting_for_contact = State()


TOPIC_MAP = {
    (-1002189931727, 3): (-1002658129391, 4),
    (-1002189931727, 1): (-1002658129391, 1),
    (-1002189931727, 14): (-1002658129391, 6),
    (-1002189931727, 5): (-1002658129391, 9),
    (-1002189931727, 8): (-1002658129391, 11),
    (-1002189931727, 20): (-1002658129391, 13),
    (-1002189931727, 25): (-1002658129391, 15),
    (-1002189931727, 16): (-1002658129391, 17),
    (-1002189931727, 12): (-1002658129391, 19),
    (-1002189931727, 27): (-1002658129391, 21),
    (-1002189931727, 1573): (-1002658129391, 23),
    (-1002189931727, 22): (-1002658129391, 25),
    (-1002189931727, 29): (-1002658129391, 27),
    (-1002189931727, 18): (-1002658129391, 29),
   
    

}


import re

def escape_md(text):
    return re.sub(r'([_*[\]()`])', r'\\\1', text)

@bot_router.message(Command('add_privyazka'))
async def add_privyazka_for_admin(message: types.Message, state: FSMContext):
    user_name = message.from_user.username
    await message.answer("Это бот для подбора кандидатов к вакансиям!\n\nДля использования бота необходимо нажать на кнопку под каждой вакансией в нашей группе", reply_markup = await service_kb(user_name))

@bot_router.message(CommandStart())
async def cmd_start(message: types.Message, command : CommandStart, state: FSMContext, bot: Bot):
    
        await state.clear()
        payload = command.args
        user_name = message.from_user.username
        if not user_name:
            await message.answer("Для работы с ботом необходимо создать имя пользователя")
            return
        if not payload:
            if message.from_user.id  not in [6264939461,429765805]:
                await message.answer("Это бот для подбора кандидатов к вакансиям!\n\nДля использования бота необходимо нажать на кнопку под каждой вакансией в нашей группе", reply_markup = await service_kb(user_name))
                return
            await message.answer(text="Основное меню", reply_markup = await main_kb())
            return
        vac_id = payload.split('_')[1]
        mess_id = payload.split('_')[0]
        try:
            # Проверяем, подключен ли клиент
            if not telethon_client.is_connected():
                await message.answer("❌ Telethon клиент не подключен. Попробуйте позже.")
                return
                
            mes = await telethon_client.get_messages(-1002658129391, ids = int(mess_id))
            if not mes:
                await message.answer("❌ Сообщение не найдено")
                return
                
            clean_text = remove_vacancy_id(mes.message)
            
            link = f"https://t.me/c/{str(-1002658129391)[4:]}/{mess_id}"
            messsage_text = f"<a href='{link}'>{vac_id}</a>\n{clean_text}"
            
            user_gr = await get_recruter_group(user_name)
            if user_gr:
                group_id = int(user_gr.group_id)
                topic_id, tread_create = await create_vacancy_thread(client = telethon_client, vac_id = vac_id, mes_text = messsage_text, group_id = group_id, bot = bot)
            else:
                bot_user_name = await bot.get_me()
                bot_user_name = bot_user_name.username
                print(bot_user_name)
                group_id, topic_id = await create_recruiter_forum(recruiter_id=message.from_user.id, client=telethon_client, recruiter_username=user_name, bot_username=bot_user_name, vac_id = vac_id, message_text = messsage_text, bot = bot)
                print(group_id)
                await add_recruter_group(recruter_user_name = user_name, group_id = str(group_id))
        except ConnectionError:
            await message.answer("❌ Ошибка соединения с Telegram. Попробуйте позже.")
            group_id = None
            topic_id = None
        except Exception as e:
            await message.answer(f"❌ Ошибка при получении вакансии: {str(e)}")
            group_id = None
            topic_id = None
        
        # Проверяем, что group_id и topic_id успешно получены
        if group_id and topic_id:
            
                
            try:
                thread_state = FSMContext(
                        storage=state.storage,
                        key=state.key.__class__(
                            bot_id=bot.id,
                            chat_id=int(group_id),
                            user_id=message.from_user.id,
                            thread_id=topic_id
                        )
                )
                await thread_state.update_data(vacancy = mes.message)
                await thread_state.set_state(ScanVacRekr.waiting_for_vac)
                
                link_to_thread = f"https://t.me/c/{str(group_id)[4:]}/{topic_id}"
                if not tread_create:
                    await message.answer(f"✅ Тред создан! Проверьте форум-группу для работы с вакансией {vac_id}", reply_markup = link_to_thread_kb(link_to_thread))
                    await bot.send_message(chat_id = group_id, message_thread_id = topic_id, text = 'Отправьте резюме')
                else:
                    await message.answer(f"✅ Тред уже был создан! Вот ссылка на тред", reply_markup = link_to_thread_kb(link_to_thread))
                    
            except Exception as e:
                print(f"Ошибка при отправке в тред: {e}")
                await message.answer("⚠️ Тред создан, но возникла ошибка при отправке сообщения. Попробуйте работать напрямую в форуме.")
        else:
            await message.answer("❌ Ошибка при создании треда. Попробуйте еще раз.")
            await message.answer('Отправьте резюме')
            await state.update_data(vacancy = mes.message)
            await state.set_state(ScanVacRekr.waiting_for_vac)
        return
    



@bot_router.callback_query(F.data == 'scan_redlab')
async def scan_redlab(calback : CallbackQuery, bot : Bot):
    try:
        if not telethon_client.is_connected():
            await calback.message.answer("❌ Telethon клиент не подключен. Попробуйте позже.")
            return
        await calback.message.answer('Начинаю сканирование...')
        await forward_messages_from_topics(telethon_client, TOPIC_MAP, AsyncSessionLocal, days=14, bot = bot)
    except ConnectionError:
        await calback.message.answer("❌ Ошибка соединения с Telegram. Попробуйте позже.")
    except Exception as e:
        await calback.message.answer(f"❌ Ошибка при сканировании: {str(e)}")

@bot_router.callback_query(F.data == 'scan_redlab_day')
async def scan_redlab_day(calback : CallbackQuery, bot : Bot):
    try:
        if not telethon_client.is_connected():
            await calback.message.answer("❌ Telethon клиент не подключен. Попробуйте позже.")
            return
        await calback.message.answer('Начинаю сканирование...')
        await forward_messages_from_topics(telethon_client, TOPIC_MAP, AsyncSessionLocal, days=1, bot = bot)
    except ConnectionError:
        await calback.message.answer("❌ Ошибка соединения с Telegram. Попробуйте позже.")
    except Exception as e:
        await calback.message.answer(f"❌ Ошибка при сканировании: {str(e)}")
    
@bot_router.callback_query(F.data == 'scan_redlab_21')
async def scan_redlab_21(calback : CallbackQuery, bot : Bot):
    try:
        if not telethon_client.is_connected():
            await calback.message.answer("❌ Telethon клиент не подключен. Попробуйте позже.")
            return
        await calback.message.answer('Начинаю сканирование...')
        await forward_messages_from_topics(telethon_client, TOPIC_MAP, AsyncSessionLocal, days=21, bot = bot)
    except ConnectionError:
        await calback.message.answer("❌ Ошибка соединения с Telegram. Попробуйте позже.")
    except Exception as e:
        await calback.message.answer(f"❌ Ошибка при сканировании: {str(e)}")





@bot_router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery):
    await callback.message.edit_text(text="Основное меню", reply_markup = await main_kb())



@bot_router.callback_query(F.data == 'scan_hand')
async def scan_hand(calback : CallbackQuery, state: FSMContext):
    await calback.message.answer('Отправьте вакансию для проверки')
    await state.set_state(ScanHand.waiting_for_hand)
    print(await state.get_state())
    


@bot_router.message(ScanHand.waiting_for_hand)
async def scan_hand_message(message: types.Message, state: FSMContext, bot: Bot):
    text = message.text
    print(await state.get_state())
    if not text:
        await message.answer('Нет текста')
        return
    if check_project_duration(text):
        await message.answer('Маленькая продолжительность проекта')
        
        return

    try:
        text_gpt = await process_vacancy_with_gemini(text)
        
    except Exception as e:
        await message.answer('Ошибка при обработке вакансии')
        return
    
    reason = text_gpt.get("reason")
    if reason:
        await message.answer(reason)
        return
    
    
    
    if text_gpt == None or text_gpt == 'None':
        await message.answer('Вакансия отсеяна')
        return
    
    try:
        text = text_gpt.get("text")
        if text is None:
            await message.answer('Вакансия отсеяна')
            return
        
        vac_id = text_gpt.get('vacancy_id')
        rate = text_gpt.get("rate")
        print(rate)
        vacancy = text_gpt.get('vacancy_title')
        deadline_date = text_gpt.get("deadline_date")
        deadline_time = text_gpt.get("deadline_time")
        utochnenie = text_gpt.get("utochnenie")
        short_project = text_gpt.get("short_project")
        delay_payment = text_gpt.get("delay_payment")
        acts = text_gpt.get("acts")
        only_fulltime = text_gpt.get("only_fulltime")
        short_project = text_gpt.get("short_project")
        long_payment = text_gpt.get("long_payment")
        location = text_gpt.get("location")
        rf_loc = False
        rb_loc = False
        for i in location:
            if i == 'РФ':
                rf_loc = True
            if i == 'РБ':
                rb_loc = True
        
        
        
        if vacancy is None or vacancy == 'None':
            await message.answer('Вакансия отсеяна')
            return
        

        # Вакансия отсекается, если нет ID
        if vac_id is None  or vac_id == 'None':
            await message.answer('Вакансия отсеяна, нет ID')
            return
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
            print(rate_rf, rate_rb)
            if rate_rb:
                rate_rb = int(rate_rb)
            if rate_rf:
                rate_rf = int(rate_rf)

            rate_rf_contract = None
            rate_rf_ip = None
            rate_rb_contract = None
            rate_rb_ip = None

            # --- варианты для РФ ---
            if rf_loc:
                rate_rf_contract = await search_and_extract_values(
                    'K', rate_rf, ['B'], 'Расчет ставки (штат) ЮЛ РФ','https://docs.google.com/spreadsheets/d/1vjHlEdWO-IkzU5urYrorb0FlwMS7TPfnBDSAhnSYp98'
                )
                rate_rf_ip = await search_and_extract_values(
                    'K', rate_rf, ['B', 'J'], 'Расчет ставки (ИП) ЮЛ РФ','https://docs.google.com/spreadsheets/d/1vjHlEdWO-IkzU5urYrorb0FlwMS7TPfnBDSAhnSYp98'
                )
                print(rate_rf_contract, rate_rf_ip)
            # --- варианты для РБ ---
            if rb_loc:
                rate_rb_contract = await search_and_extract_values(
                    'M', rate_rb, ['B'], 'Расчет ставки (штат/контракт) СНГ'
                )
                rate_rb_ip = await search_and_extract_values(
                    'N', rate_rb, ['B', 'L'], 'Расчет ставки (Самозанятый/ИП) СНГ'
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
                    state_contract_text = (
                        f"<s>Вариант 1. Ежемесячная выплата Штат/Контракт (на руки) до: {rate_contract} RUB "
                        f"(с выплатой зарплаты 11 числа месяца следующего за отчетным)</s>\n"
                    )
                else:
                    acts_text = "Актирование: ежемесячное\n"
                    state_contract_text = (
                        f"Вариант 1. Ежемесячная выплата Штат/Контракт (на руки) до: {rate_contract} RUB "
                        f"(с выплатой зарплаты 11 числа месяца следующего за отчетным)\n"
                    )

                # зачёркивания по условиям
                if short_project or long_payment:
                    state_contract_text = f"<s>{state_contract_text}</s>"

                if only_fulltime:
                    ip_text = f"<s>Вариант 2. Выплата ИП/Самозанятый\n{delay_payment_text}({acts_text}):\n{gross} RUB/час (Gross)\nСправочно в месяц (при 170 раб. часов): {rate_ip} RUB(Gross)</s>"
                else:
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

            # --- финальное объединение ---
            text_cleaned = f"🆔{vac_id}\n\n{vacancy}\n\n{salary_text}\n{text}"
            
        formatted_text = await format_vacancy_gemini(text_cleaned, vac_id)
        clean_text = remove_vacancy_id(formatted_text)


            
            
                
        try:
            await message.answer(formatted_text, parse_mode='HTML')
        except Exception as e:
            await message.answer(f'Ошибка при отправке вакансии {e}')
            return
        await state.update_data(vac_id=vac_id, vacancy_id=vac_id, clean_text=clean_text)
    except Exception as e:
        await message.answer(f'Ошибка при обработке вакансии {e}')
        return
    await message.answer('Выберите топик куда отправить вакансию', reply_markup=await send_kb())
    await state.set_state(ScanHand.waiting_for_topic)


@bot_router.callback_query(ScanHand.waiting_for_topic, F.data.startswith("topic:"))
async def scan_hand_topic(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.message.delete()
    topic_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    vac_id = data.get('vac_id')
    vacancy_id = data.get('vacancy_id')
    clean_text = data.get('clean_text')
    
    if not clean_text:
        await callback.message.answer('Нет текста')
        return
    message_id = await bot.send_message(chat_id=-1002658129391, text='.', message_thread_id=topic_id, parse_mode='HTML')
    url_bot = f"https://t.me/omega_vacancy_bot?start={message_id.message_id}_{vac_id}"
    text_cleaned = f'<a href="{url_bot}">{vacancy_id}</a>\n{clean_text}'
    await bot.edit_message_text(chat_id=-1002658129391, message_id=message_id.message_id, text=text_cleaned,parse_mode='HTML')
    await state.clear()
    await callback.message.answer('Вакансия отправлена')
    await send_mess_to_group(GROUP_ID, text_cleaned, vac_id, bot)
    
    



state_users = []
text_mes_id = {}



    

@bot_router.message(F.document, ScanVacRekr.waiting_for_vac)
async def scan_vac_rekr(message: Message, state: FSMContext, bot: Bot):
    await save_document(message, state, bot)
    


ACTIVE_MEDIA_GROUPS = {}
RESET_DELAY = 10.0
UPLOAD_DELAY = 2.0  # сколько ждать после последнего файла, прежде чем ответить

# глобальный буфер для пользователей (таймеры и задачи)
USER_UPLOAD_TASKS = {}

async def save_document(message: types.Message, state: FSMContext, bot):
    """
    Сохраняет документы пользователя.
    — Не спамит при массовой загрузке.
    — После паузы 2 сек отправляет одно сообщение с кнопками "Добавить ещё файлы?".
    — После 10 сек без новых загрузок — сбрасывает счётчик.
    """

    document = message.document
    if not document:
        await message.answer("Отправьте резюме в формате PDF/DOCX/RTF/TXT")
        return

    user_id = message.from_user.id
    message_thread_id = message.message_thread_id
    user_dir = os.path.join(SAVE_DIR, (str(user_id)+'_'+str(message_thread_id)))
    os.makedirs(user_dir, exist_ok=True)

    file_name = document.file_name
    local_file_path = os.path.join(user_dir, file_name)

    # Получаем текущее состояние
    data = await state.get_data()
    files_count = data.get("files_count", 0)
    summary_message_id = data.get("summary_message_id")

    # Сохраняем файл
    if not os.path.exists(local_file_path):
        file_info = await bot.get_file(document.file_id)
        await bot.download_file(file_info.file_path, destination=local_file_path)
        print(f"📁 [{user_id}] Файл сохранён: {file_name}")
    else:
        print(f"⚠️ [{user_id}] Файл уже существует: {file_name}")

    # Увеличиваем счётчик файлов
    files_count += 1
    now = asyncio.get_event_loop().time()
    await state.update_data(files_count=files_count, last_upload_time=now)

    # Отменяем предыдущий таймер, если есть
    if USER_UPLOAD_TASKS.get(user_id):
        USER_UPLOAD_TASKS[user_id].cancel()

    # ⏳ Таймер с задержкой для вывода итогового сообщения
    async def delayed_summary():
        try:
            await asyncio.sleep(UPLOAD_DELAY)
            current_data = await state.get_data()
            count = current_data.get("files_count", 0)
            last_time = current_data.get("last_upload_time", 0)

            # Проверяем, прошло ли достаточно времени без новых файлов
            if asyncio.get_event_loop().time() - last_time >= UPLOAD_DELAY - 0.1:
                if count >= 10:
                    text = f"📦 Загружено {count} файлов. Все сохранены ✅"
                elif count > 1:
                    text = f"📥 Загружено {count} файлов. Все сохранены ✅"
                else:
                    text = "📥 Файл сохранён ✅"

                # Если уже есть сообщение — редактируем, иначе создаём новое
                if summary_message_id:
                    try:
                        await bot.edit_message_text(
                            chat_id=message.chat.id,
                            message_id=summary_message_id,
                            text=text
                        )
                    except:
                        pass
                    # Добавляем кнопки
                    await message.answer(
                        text="Хотите добавить ещё файлы?",
                        reply_markup=scan_vac_rekr_yn_kb()
                    )
                else:
                    msg = await message.answer(text)
                    await message.answer(
                        text="Хотите добавить ещё файлы?",
                        reply_markup=scan_vac_rekr_yn_kb()
                    )
                    await state.update_data(summary_message_id=msg.message_id)

                # Сбрасываем счётчик через 10 секунд
                await asyncio.sleep(RESET_DELAY)
                await state.update_data(files_count=0, summary_message_id=None)
                print(f"♻️ [{user_id}] Сброс счётчика файлов ({count} шт).")

        except asyncio.CancelledError:
            pass

    # Запускаем новый таймер
    task = asyncio.create_task(delayed_summary())
    USER_UPLOAD_TASKS[user_id] = task





    
@bot_router.callback_query(F.data == "yes_vac_rekr")
async def scan_vac_rekr_y(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.message.delete()
    mes3 = await callback.message.answer("Жду файлы")
    data = await state.get_data()
    mes1 = data.get("mes1")
    mes2 = data.get("mes2")
    try:
        await bot.delete_messages(callback.message.chat.id, [mes1, mes2])
    except:
        pass
    await state.update_data(mes3=mes3.message_id)
    

@bot_router.callback_query(F.data == "no_vac_rekr")
async def scan_vac_rekr_n(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.message.delete()
    await callback.message.answer("Начинаю обработку...")
    user_id = callback.from_user.id
    message_thread_id = callback.message.message_thread_id
    user_dir = os.path.join(SAVE_DIR, (str(user_id)+'_'+str(message_thread_id)))
    data = await state.get_data()
    
    vac_text = await get_vacancy_thread(message_thread_id)
    vac_text = vac_text.vacancy_text
    
    mes3 = data.get("mes3")
    mes2 = data.get("mes2")
    mes1 = data.get("mes1")
    try:
        await bot.delete_messages(callback.message.chat.id, [mes1, mes2, mes3])
    except:
        pass
    asyncio.create_task(
        process_vac_tuks(user_dir, user_id, vac_text, bot, callback, state)
    )


async def process_vac_tuks(user_dir, user_id, vac_text, bot: Bot, callback: CallbackQuery, state : FSMContext):
    if not os.path.exists(user_dir):
        await callback.message.answer("❌ Нет загруженных файлов для обработки.")
        return

    files = [
        (file_name, os.path.join(user_dir, file_name))
        for file_name in os.listdir(user_dir)
        if os.path.isfile(os.path.join(user_dir, file_name))
    ]
    if not files:
        await callback.message.answer("❌ Не найдено ни одного файла.")
        return

    result = []
    BATCH_SIZE = 5
    total = len(files)

    for i in range(0, total, BATCH_SIZE):
        batch = files[i:i + BATCH_SIZE]
        tasks = [
            process_file_and_gpt(file_path, bot, user_id, vac_text, file_name)
            for (file_name, file_path) in batch
        ]
        batch_result = await asyncio.gather(*tasks, return_exceptions=False)
        result.extend(batch_result)
    
    finalist_list = []
    utochnit_list = []
    otkaz_list = []

    for finalist in result:
        verdict = finalist.get('verdict')
        
        if verdict == 'Полностью подходит':
            finalist_list.append(finalist)
        elif verdict == 'Частично подходит (нужны уточнения)':
            utochnit_list.append(finalist)
        elif verdict == 'Не подходит':
            otkaz_list.append(finalist)

    # === Отправка по группам ===
    await callback.message.answer("📊 СВОДКА ПО ВСЕМ КАНДИДАТАМ")

    # 1️⃣ Финалисты
    if finalist_list:
        await callback.message.answer("🏆 Финалисты:")
        for finalist in finalist_list:
            candidate = finalist.get('candidate')
            verdict = finalist.get('verdict')
            sverka_text = finalist.get('sverka_text')
            candidate_json = finalist.get('candidate_json')
            resume_text = finalist.get('resume_text')
            salary = candidate_json.get('summary', {}).get('salary_expectations', 'не указано')
            contacts = candidate_json.get('candidate', {}).get('contacts')
            telegram = contacts.get('telegram')
            if telegram in ['Нет (требуется уточнение)', 'Нет']:
                telegram = None
            email = contacts.get('email')
            if email in ['Нет (требуется уточнение)', 'Нет']:
                email = None
            phone = contacts.get('phone')
            if phone in ['Нет (требуется уточнение)', 'Нет']:
                phone = None

            location = candidate_json.get('candidate', {}).get('location')
            city = location.get('city',None)
            country = location.get('country',None)
            if city in ['Нет (требуется уточнение)', 'Нет']:
                city = None
            if country in ['Нет (требуется уточнение)', 'Нет']:
                country = None
            if city and country:
                location = f"{city}, {country}"
            elif city:
                location = city
            elif country:
                location = country
            else:
                location = "не указано"

            kandidate_verdict = f"ФИО: {candidate}\nЗарплатные ожидания: {salary}\nЛокация: {location}"
            await callback.message.answer('--------------------------')
            await asyncio.sleep(0.1)
            messs = await callback.message.answer(kandidate_verdict, reply_markup=get_all_info_kb())
            await callback.message.answer('--------------------------')
            await asyncio.sleep(0.1)
            await add_candidate_resume(messs.message_id, messs.text, candidate_json, resume_text, sverka_text, False, False)
            await add_contact(messs.message_id, candidate, telegram, email, phone)

    # 2️⃣ Требуют уточнения
    if utochnit_list:
        await callback.message.answer("🟡 Требуют уточнений:")
        for finalist in utochnit_list:
            candidate = finalist.get('candidate')
            verdict = finalist.get('verdict')
            sverka_text = finalist.get('sverka_text')
            candidate_json = finalist.get('candidate_json')
            resume_text = finalist.get('resume_text')
            salary = candidate_json.get('summary', {}).get('salary_expectations', 'не указано')
            contacts = candidate_json.get('candidate', {}).get('contacts')
            telegram = contacts.get('telegram')
            if telegram in ['Нет (требуется уточнение)', 'Нет']:
                telegram = None
            email = contacts.get('email')
            if email in ['Нет (требуется уточнение)', 'Нет']:
                email = None
            phone = contacts.get('phone')
            if phone in ['Нет (требуется уточнение)', 'Нет']:
                phone = None
            
            location = candidate_json.get('candidate', {}).get('location')
            city = location.get('city',None)
            country = location.get('country',None)
            if city in ['Нет (требуется уточнение)', 'Нет']:
                city = None
            if country in ['Нет (требуется уточнение)', 'Нет']:
                country = None
            if city and country:
                location = f"{city}, {country}"
            elif city:
                location = city
            elif country:
                location = country
            else:
                location = "не указано"

            kandidate_verdict = f"ФИО: {candidate}\nЗарплатные ожидания: {salary}\nЛокация: {location}"
            await callback.message.answer('--------------------------')
            await asyncio.sleep(0.1)
            messs = await callback.message.answer(kandidate_verdict, reply_markup=get_all_info_kb())
            await asyncio.sleep(0.1)
            await callback.message.answer('--------------------------')
            await asyncio.sleep(0.1)
            await add_candidate_resume(messs.message_id, messs.text, candidate_json, resume_text, sverka_text, False, False)
            await add_contact(messs.message_id, candidate, telegram, email, phone)


    # 3️⃣ Отказы
    if otkaz_list:
        await callback.message.answer("🔴 Не подходят:")
        for finalist in otkaz_list:
            candidate = finalist.get('candidate')
            verdict = finalist.get('verdict')
            sverka_text = finalist.get('sverka_text')
            candidate_json = finalist.get('candidate_json')
            resume_text = finalist.get('resume_text')
            salary = candidate_json.get('summary', {}).get('salary_expectations', 'не указано')
            contacts = candidate_json.get('candidate', {}).get('contacts')
            location = candidate_json.get('candidate', {}).get('location')
            telegram = contacts.get('telegram')
            if telegram in ['Нет (требуется уточнение)', 'Нет']:
                telegram = None
            email = contacts.get('email')
            if email in ['Нет (требуется уточнение)', 'Нет']:
                email = None
            phone = contacts.get('phone')
            if phone in ['Нет (требуется уточнение)', 'Нет']:
                phone = None
            
            city = location.get('city',None)
            if city in ['Нет (требуется уточнение)', 'Нет']:
                city = None
            country = location.get('country',None)
            if country in ['Нет (требуется уточнение)', 'Нет']:
                country = None
            if city and country:
                location = f"{city}, {country}"
            elif city:
                location = city
            elif country:
                location = country
            else:
                location = "не указано"

            kandidate_verdict = f"ФИО: {candidate}\nЗарплатные ожидания: {salary}\nЛокация: {location}"
            await callback.message.answer('--------------------------')
            await asyncio.sleep(0.1)
            messs = await callback.message.answer(kandidate_verdict, reply_markup=get_all_info_kb())
            await asyncio.sleep(0.1)
            await callback.message.answer('--------------------------')
            await asyncio.sleep(0.1)
            await add_candidate_resume(messs.message_id, messs.text, candidate_json, resume_text, sverka_text, False, False)
            await add_contact(messs.message_id, candidate, telegram, email, phone)
            
    await callback.message.answer('--------------------------')
    await asyncio.sleep(0.1)        
    await callback.message.answer("✅ Резюме сканированы!\n\nДобавить еще резюме?", reply_markup=add_another_resume_kb())      
    await asyncio.sleep(0.1)
    await callback.message.answer('--------------------------')
    shutil.rmtree(user_dir)
    
    

        
        
@bot_router.callback_query(F.data.startswith("generate_mail:"))
async def generate_mail_bot(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    
    message_id = callback.message.message_id
    verdict = callback.data.split(":")[1]
    data = await get_candidate_resume(message_id)
    
    if not data:
        await callback.message.answer("❌ Нет данных для генерации письма.", reply_markup=generate_mail_kb())
        return
    
    state_data = await state.get_data()
    tread_id = callback.message.message_thread_id
    print(tread_id)
    vac_info = await get_vacancy_thread(tread_id)
    if not vac_info:
        await callback.message.answer("❌ Нет данных для генерации письма.", reply_markup=generate_mail_kb())
        return
    vacancy_text = vac_info.vacancy_text
    
    candidate = data.json_text
    if isinstance(candidate, str):
        candidate_json = json.loads(candidate)
    
    candidate_name = candidate_json.get("candidate").get("full_name")
    await callback.message.edit_text(f'Подготовка письма для {candidate_name}')
    
    user_name = (
            f"@{callback.from_user.username}"
            if callback.from_user.username
            else (callback.from_user.first_name or "Не указано")
        )
    tread_id = callback.message.message_thread_id
    user_gr = await get_recruter_group(callback.from_user.username)
    gr_id = int(user_gr.group_id)
    mail = await create_mails(candidate_json, user_name,vacancy_text, gr_id, tread_id, verdict)
    if mail:
        mail_text = mail
    else:
        mail_text = "."
    if verdict == "PP":
        await bot.edit_message_text(text = f"📨 Создано письмо для кандидата {candidate_name} !", chat_id=callback.message.chat.id, message_id=message_id)
        await asyncio.sleep(3)
        await bot.edit_message_text(chat_id=callback.message.chat.id, message_id=message_id, text=mail_text, reply_markup=send_mail_or_generate_client_mail_kb(mail = mail_text), parse_mode='HTML')
        await update_candidate_is_finalist(message_id, True)
        
    elif verdict == 'CP':
        verdict = 'Частично подходит (нужны уточнения)'
        await bot.edit_message_text(text = f"📨 Создано письмо для кандидата {candidate_name} !", chat_id=callback.message.chat.id, message_id=message_id)
        await asyncio.sleep(3)
        await bot.edit_message_text(chat_id=callback.message.chat.id, message_id=message_id, text=mail_text, reply_markup=send_mail_to_candidate_kb(verdict, mail_text), parse_mode='HTML')
        await update_candidate_is_utochnenie(message_id, True)
        
        
    else:
        await bot.edit_message_text(text = f"📨 Создано письмо для кандидата {candidate_name} !", chat_id=callback.message.chat.id, message_id=message_id)
        await asyncio.sleep(3)
        await bot.edit_message_text(chat_id=callback.message.chat.id, message_id=message_id, text=mail_text, reply_markup=send_mail_to_candidate_kb(verdict, mail_text))
    
    await update_candidate_messsage_text(message_id, mail_text)

@bot_router.callback_query(F.data == "generate_klient_mail")
async def generate_klient_mail_bot(callback: CallbackQuery, state: FSMContext, bot: Bot):
    
    
    vac_info = await get_vacancy_thread(callback.message.message_thread_id)
    if not vac_info:
        await callback.message.edit_text("❌ Не удалось найти данные для генерации письма клиента.", reply_markup=generate_klient_mail_kb())
        return
    vacancy_text = vac_info.vacancy_text
    message_id = callback.message.message_id
    data = await get_candidate_resume(message_id)
    if not data:
        await callback.message.edit_text("❌ Не удалось найти данные для генерации письма клиента.", reply_markup=generate_klient_mail_kb())
        return
    
    candidate = data.json_text
    resume_text = data.resume_text
    text_mail = data.message_text
    api_key = GEMINI_API_KEY
    if isinstance(candidate, str):
        candidate_json = json.loads(candidate)
    
    candidate_name = candidate_json.get("candidate").get("full_name")
    await callback.message.edit_text(f"📨 Создаю письмо для клиента по кандидату {candidate_name}...")
    try:
        
        mail_text = await generate_cover_letter_for_client(candidate_json)
        print(mail_text)
        if not resume_text:
            await callback.message.edit_text("❌ Не удалось найти резюме для генерации письма клиента.", reply_markup=send_mail_or_generate_client_mail_kb(mail = text_mail))
            return
        wl_path = await asyncio.to_thread(create_white_label_resume_once, api_key, resume_text, vacancy_text, candidate_name)
    except Exception as e:
        await callback.message.edit_text(f"⚠️ Ошибка при генерации письма клиента: {e}")
        return

    await bot.edit_message_text(chat_id=callback.message.chat.id, message_id=message_id, text=f"✅ Письмо для клиента по кандидату {candidate_name} создано!", reply_markup=None)
    await asyncio.sleep(3)
    await update_candidate_wl_path(message_id, wl_path)
    await update_candidate_mail(message_id, mail_text)
    await bot.edit_message_text(chat_id=callback.message.chat.id, message_id=message_id, text=mail_text, reply_markup=send_to_group_kb(), parse_mode='HTML')







@bot_router.callback_query(F.data == "get_all_info")
async def get_all_info_bot(callback: CallbackQuery, state: FSMContext, bot: Bot):
    
    message_id = callback.message.message_id
    
    sverka = await get_candidate_resume(message_id)
    if sverka:
        await bot.edit_message_text(chat_id=callback.message.chat.id, message_id=message_id, text=sverka.sverka_text, reply_markup=generate_mail_kb())
    else:
        await bot.edit_message_text(chat_id=callback.message.chat.id, message_id=message_id, text="❌ Не удалось найти данные для генерации письма клиента.")
            

@bot_router.callback_query(F.data.startswith("send_mail_to_candidate"))
async def send_mail_to_candidate_bot(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await get_candidate_resume(callback.message.message_id)
    if not data:
        await callback.message.edit_text("❌ Нет данных для отправки письма кандидату.")
        return
    data_json = data.json_text
    if isinstance(data_json, str):
        data_json = json.loads(data_json)
    candidate_name = data_json.get("candidate").get("full_name")
    await callback.message.edit_text(f"Выберете куда отправить сообщение кандидату {candidate_name}", reply_markup=await create_contacts_kb(callback.message.message_id))
    

@bot_router.callback_query(F.data.startswith("con:"))
async def send_mail_to_candidate_bot(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    
    source = callback.data.split(":")[1]
    contact = callback.data.split(":")[2]
    
    data = await get_candidate_resume(callback.message.message_id)
    if not data:
        await callback.message.edit_text("❌ Нет данных для отправки письма кандидату.")
        return
    
    
    candidate = data.json_text
    mail_text = data.message_text
    if isinstance(candidate, str):
        candidate_json = json.loads(candidate)
    
    
    candidate_name = candidate_json.get("candidate", {}).get("full_name", {})
    if not candidate_name:
        await callback.message.edit_text("❌ Нет данных для отправки письма кандидату.")
        return
    
    
    if source == "t":
        if callback.from_user.id in [6264939461,429765805]:
            if not telethon_client.is_connected():
                await callback.message.edit_text("❌ Telethon клиент не подключен. Попробуйте позже.")
                return
            client = telethon_client
            
        else:
            user_name = callback.from_user.username
            if not user_name:
                await callback.message.edit_text("Для продолжения создайте имя пользователя в Telegram и отправте еще раз код подтверждения", reply_markup=await create_contacts_kb(callback.message.message_id))
                return

            print(user_name)
            client = f'sessions/{user_name}'
            user = await get_tg_user(user_name)
            if not user:
                await callback.message.edit_text("❌ У вас нет привязанного Telegram",reply_markup=await create_contacts_kb(callback.message.message_id))
                return
                
            api_id = user.api_id
            api_hash = user.api_hash
            client = TelegramClient(client, api_id, api_hash)


            await client.connect()
            if not await client.is_user_authorized():
                await callback.message.edit_text("❌ Не удалось авторизоваться в Telegram",reply_markup=await create_contacts_kb(callback.message.message_id))
                return
        success = await send_message_by_username(contact, mail_text, client)
        if success:
           await callback.message.edit_text(f"✅ Сообщение отправлено пользователю {candidate_name}")
           await asyncio.sleep(3)
           
           if client != telethon_client:
               await client.disconnect()
           await callback.message.edit_text(f"Выберете куда отправить сообщение {candidate_name}", reply_markup=await create_contacts_kb(callback.message.message_id))
        else:
           await callback.message.edit_text(f"❌ Не удалось отправить сообщение пользователю {candidate_name}",reply_markup=await create_contacts_kb(callback.message.message_id))
    
    elif source == "e":
        email_and_pass = await get_email_user(callback.from_user.username)
        if not email_and_pass:
            await callback.message.edit_text("❌ У вас нет привязанного email", reply_markup=await create_contacts_kb(callback.message.message_id))
            return
        success = await send_email_gmail(
            sender_email=email_and_pass.user_email,
            app_password=email_and_pass.email_password, 
            recipient_email=contact,
            subject=mail_text,
            body=mail_text,
            html=True,
            attachments=[]
        )
        if success:
           await callback.message.edit_text("✅ Сообщение отправлено пользователю")
           await asyncio.sleep(3)
           await callback.message.edit_text("Выберете куда отправить сообщение", reply_markup=await create_contacts_kb(callback.message.message_id))
        else:
           await callback.message.edit_text("❌ Не удалось отправить сообщение пользователю", reply_markup=await create_contacts_kb(callback.message.message_id))
    
    elif source == "p":
        try:
            await bot.send_contact(chat_id=callback.message.chat.id, phone_number=contact, first_name=candidate_name)
            await callback.message.edit_text("Выберете куда отправить сообщение", reply_markup=await create_contacts_kb(callback.message.message_id))
        except Exception as e:
            await callback.message.edit_text("❌ Не удалось отправить сообщение пользователю", reply_markup=await create_contacts_kb(callback.message.message_id))



@bot_router.callback_query(F.data == "add_another_resume")
async def add_another_resume_bot(callback: CallbackQuery, state: FSMContext, ):
    await callback.message.edit_text("Добавьте еще резюме")
    print(await state.get_state())
    await state.set_state(WaitForNewResume.waiting_for_new_resume)
    print(await state.get_state())


@bot_router.message(F.document, WaitForNewResume.waiting_for_new_resume)
async def new_resume_after_scan(message: Message, bot: Bot, state: FSMContext):
    await save_document(message, state, bot)
    await state.set_state(WaitForNewResume.waiting_for_new_resume)

@bot_router.message(F.document)
async def document_without_state(message: Message, bot: Bot, state: FSMContext):
    await message.answer("📄 Чтобы загрузить резюме, сначала выберите вакансию в боте.")

@bot_router.callback_query(F.data == "add_utochnenie")
async def add_utochnenie_bot(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    mes_id = callback.message.message_id
    a = await callback.message.answer("Напишите уточнения в чат")
    await state.set_state(AddUtochnenie.waiting_for_utochnenie)
    await state.update_data(mes_id_for_del=a.message_id, mes_id_for_db=mes_id)

@bot_router.message(AddUtochnenie.waiting_for_utochnenie)
async def add_utochnenie_after_scan(message: Message, state: FSMContext, bot: Bot):
    a = await message.answer("Уточнения скоро будут добавлены")
    data_state = await state.get_data()
    tread_id = message.message_thread_id
    vac_info = await get_vacancy_thread(tread_id)
    if not vac_info:
        await message.answer("❌ Нет данных для уточнения.")
        return
    vacancy = vac_info.vacancy_text
    message_id = message.message_id
    mes_id_for_del = data_state.get("mes_id_for_del")
    mes_id_for_db = data_state.get("mes_id_for_db")
    data = await get_candidate_resume(mes_id_for_db)
    
    
    candidate = data.json_text
    if isinstance(candidate, str):
        candidate_json = json.loads(candidate)
    resume_text = data.resume_text
    candidate_name = candidate_json.get("candidate").get("full_name")
    mail = await generate_cover_letter_for_client(candidate_json, additional_notes=message.text)
    api_key = GEMINI_API_KEY
    wl_path = await asyncio.to_thread(create_white_label_resume_once, api_key, resume_text, vacancy, candidate_name)
    
    await bot.delete_messages(chat_id=message.chat.id, message_ids=[mes_id_for_del, message_id])
    await bot.edit_message_text(chat_id=message.chat.id, message_id=a.message_id, text="Уточнения добавлены")
    await asyncio.sleep(3)
    await bot.edit_message_text(chat_id=message.chat.id, message_id=a.message_id, text=mail, reply_markup=send_to_group_kb(), parse_mode='HTML')
    await update_candidate_wl_path(mes_id_for_db, wl_path)
    await update_message_id(mes_id_for_db, a.message_id)
    

@bot_router.callback_query(F.data == "back_to_mail")
async def back_to_mail_bot(callback: CallbackQuery, state: FSMContext):
    data = await get_candidate_resume(callback.message.message_id)
    if not data:
        await callback.message.edit_text("❌ Нет данных для отправки письма кандидату.")
        return
    text = data.message_text
    data_json = data.json_text
    if isinstance(data_json, str):
        data_json = json.loads(data_json)
    await callback.message.edit_text(text, reply_markup=send_mail_to_candidate_kb('Полностью подходит', text),parse_mode='HTML')

@bot_router.callback_query(F.data == "del")
async def del_bot(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    
@bot_router.callback_query(F.data == "show_mail")
async def accept_delete_email_bot(callback: CallbackQuery, state: FSMContext):
    data = await get_candidate_resume(callback.message.message_id)
    if not data:
        await callback.message.edit_text("❌ Нет данных для отправки письма кандидату.")
        return
    text = data.message_text
    candidate = data.json_text
    if isinstance(candidate, str):
        candidate_json = json.loads(candidate)
    verdict = candidate_json.get("candidate", {}).get("verdict", {})
    finalist = data.is_finalist
    utochnenie = data.is_utochnenie
    candidate_mail = data.candidate_mail
    if finalist:
        await callback.message.edit_text(text, reply_markup=send_mail_or_generate_client_mail_kb(candidate_mail, mail = text), parse_mode='HTML')
    elif utochnenie:
        verdict = 'Частично подходит (нужны уточнения)'    
        await callback.message.edit_text(text, reply_markup=send_mail_to_candidate_kb(verdict, text), parse_mode='HTML')
    else:
        await callback.message.edit_text(text, reply_markup=send_mail_to_candidate_kb(verdict, text), parse_mode='HTML')

@bot_router.callback_query(F.data == "show_sverka")
async def accept_delete_email_bot(callback: CallbackQuery, state: FSMContext):
    data = await get_candidate_resume(callback.message.message_id)
    if not data:
        await callback.message.edit_text("❌ Нет данных для отправки письма кандидату.")
        return
    text = data.sverka_text
    
    
    await callback.message.edit_text(text, reply_markup=show_mail_kb(), parse_mode='HTML')


@bot_router.callback_query(F.data.startswith("send_to_group"))
async def send_to_group_bot(callback: CallbackQuery, state: FSMContext, bot: Bot):
    mail = callback.message.text
    data = await get_candidate_resume(callback.message.message_id)
    wl_path = data.wl_path
    if not data:
        await callback.message.edit_text("❌ Нет данных")
        return
    if callback.data == "send_to_group":
        await callback.message.edit_text("Письмо и WL резюме отправлены в группу")
        await bot.send_message(chat_id=GROUP_ID, text=mail, parse_mode='HTML')
        doc = FSInputFile(wl_path)
        try:
            await bot.send_document(chat_id=CLIENT_CHANNEL, document=doc)
        except:
            await callback.message.edit_text("Файл был удален")
        await asyncio.sleep(3)
        await callback.message.edit_text(data.message_text, reply_markup=send_to_group_kb(), parse_mode='HTML')
        try:
            os.remove(wl_path)
        except:
            pass

    elif callback.data == "send_to_group_mail":
        await callback.message.edit_text("Письмо отправлено в группу")
        await bot.send_message(chat_id=CLIENT_CHANNEL, text=mail, parse_mode='HTML')
        await asyncio.sleep(3)
        await callback.message.edit_text(data.message_text, reply_markup=send_to_group_kb(), parse_mode='HTML')

    
@bot_router.callback_query(F.data == "show_wl")
async def show_wl_bot(callback: CallbackQuery, state: FSMContext):
    
    data = await get_candidate_resume(callback.message.message_id)
    if not data:
        await callback.message.edit_text("❌ Нет данных")
        return
    wl_path = data.wl_path
    
    try:
        doc = FSInputFile(wl_path)
        await callback.message.answer_document(doc)
    except:
        await callback.message.answer("Файл был удален")
    





@bot_router.callback_query(F.data == "back_to_group")
async def back_to_group_bot(callback: CallbackQuery, state: FSMContext):
    data = await get_candidate_resume(callback.message.message_id)
    if not data:
        await callback.message.edit_text("❌ Нет данных")
        return
    mail = data.candidate_mail
    await callback.message.edit_text(mail, reply_markup=send_to_group_kb(), parse_mode='HTML')


@bot_router.callback_query(F.data == "add_contacts")
async def add_contact_bot(callback: CallbackQuery, state: FSMContext):
    mess_for_db = callback.message.message_id
    await callback.message.delete()
    print(mess_for_db)
    await callback.message.answer("Выберете какой контакт добавить", reply_markup=contacts_add_kb())
    await state.update_data(mess_for_db=mess_for_db)

@bot_router.callback_query(F.data.startswith("addcontacts_"))
async def add_contact_after_bot(callback: CallbackQuery, state: FSMContext):
    contact_to_add = callback.data.split("_")[1]
    print(contact_to_add)
    mes_for_delete = callback.message.message_id
    await callback.message.edit_text("Введите контакт")
    await state.set_state(AddContact.waiting_for_contact)
    await state.update_data(contact_to_add=contact_to_add, mes_for_delete=mes_for_delete)


@bot_router.message(AddContact.waiting_for_contact)
async def add_contact_after_message(message: Message, state: FSMContext, bot: Bot):
    message_id = message.message_id
    state_data = await state.get_data()
    contact_to_add = state_data.get("contact_to_add")
    mess_for_db = state_data.get("mess_for_db")
    mes_for_delete = state_data.get("mes_for_delete")
    data = await get_candidate_resume(mess_for_db)
    if not data:
        await message.answer("❌ Нет данных")
        return
    finalist = data.is_finalist
    utochnenie = data.is_utochnenie
    message_text = data.message_text
    candidate_mail = data.candidate_mail
    
    
    if contact_to_add == "tg":
        await update_contact(message_id=mess_for_db, contact_tg=message.text)
    elif contact_to_add == "email":
        await update_contact(message_id=mess_for_db, contact_email=message.text)
    elif contact_to_add == "phone":
        await update_contact(message_id=mess_for_db, contact_phone=message.text)
    await state.clear()

    a = await message.answer("Контакт добавлен")
    await asyncio.sleep(3)
    await bot.delete_messages(chat_id=message.chat.id, message_ids=[message_id, mes_for_delete, a.message_id])
    if finalist:
        a = await message.answer(message_text, reply_markup=send_mail_or_generate_client_mail_kb(candidate_mail, mail = message_text), parse_mode='HTML')
    elif utochnenie:
        verdict = 'Частично подходит (нужны уточнения)'    
        a = await message.answer(message_text, reply_markup=send_mail_to_candidate_kb(verdict, message_text), parse_mode='HTML')
    else:
        a = await message.answer(message_text, reply_markup=send_mail_to_candidate_kb('.', message_text), parse_mode='HTML')
    await update_contact_message_id(mess_for_db, a.message_id)
    await update_message_id(mess_for_db, a.message_id)


@bot_router.callback_query(F.data == "hide")
async def hide_message_bot(callback: CallbackQuery):
    data = await get_candidate_resume(callback.message.message_id)
    if not data:
        await callback.message.edit_text("❌ Нет данных", reply_markup=get_all_info_kb(), parse_mode='HTML')
        return
    
    data_json = data.json_text
    if isinstance(data_json, str):
        data_json = json.loads(data_json)
    
    candidate = data_json.get("candidate", {}).get("full_name", "не указано")
    salary = data_json.get("candidate", {}).get("salary_expectations", "не указано")
    location = data_json.get("candidate", {}).get("location", "не указано")
    city = location.get("city", None)
    country = location.get("country", None)
    if city == 'Нет (требуется уточнение)':
        city = None
    if country == 'Нет (требуется уточнение)':
        country = None
    if city and country:
        location = f"{city}, {country}"
    elif city:
        location = city
    elif country:
        location = country
    else:
        location = "не указано"
    text = f"ФИО: {candidate}\nЗарплатные ожидания: {salary}\nЛокация: {location}"

    await callback.message.edit_text(text, reply_markup=get_all_info_kb(), parse_mode='HTML')