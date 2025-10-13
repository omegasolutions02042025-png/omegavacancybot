from aiogram import Router
from aiogram import Bot, Dispatcher, types, F

from aiogram.types import CallbackQuery, FSInputFile, Message
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart, Command
from kb import *
from telethon_bot import *
from funcs import update_channels_and_restart_handler
import os
from dotenv import load_dotenv
from funcs import *
from gpt_gimini import generate_mail_for_candidate_utochnenie, process_vacancy_with_gemini, format_vacancy_gemini, generate_mail_for_candidate_finalist, generate_mail_for_candidate_otkaz, generate_cover_letter_for_client
from googlesheets import find_rate_in_sheet_gspread, search_and_extract_values
from telethon_bot import telethon_client
from db import AsyncSessionLocal, add_otkonechenie_resume, add_utochnenie_resume, add_final_resume, get_otkolenie_resume, get_final_resume, get_utochnenie_resume 
from scan_documents import process_file_and_gpt, create_finalists_table, create_mails
import shutil
import markdown
from dotenv import load_dotenv
load_dotenv()

CLIENT_CHANNEL = os.getenv('CLIENT_CHANNEL')

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


class GenerateMail(StatesGroup):
    waiting_for_mail = State()


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


@bot_router.message(CommandStart())
async def cmd_start(message: types.Message, command : CommandStart, state: FSMContext):
    
        
        payload = command.args
        
        if not payload:
            if message.from_user.id not in [6264939461,429765805]:
                await message.answer("Это бот для подбора кандидатов к вакансиям!\n\nДля использования бота необходимо нажать на кнопку под каждой вакансией в нашей группе")
                return
            await message.answer(text="Основное меню", reply_markup = await main_kb())
            return
        vac_id = payload.split('_')[1]
        mess_id = payload.split('_')[0]
        mes = await telethon_client.get_messages(-1002658129391, ids = int(mess_id))
        clean_text = remove_vacancy_id(mes.message)
        
        link = f"https://t.me/c/{str(-1002658129391)[4:]}/{mess_id}"
        messsage_text = f"<a href='{link}'>{vac_id}</a>\n{clean_text}"
        await message.answer(messsage_text, parse_mode='HTML')
        await message.answer('Отправьте резюме')
        await state.update_data(vacancy = mes.message)
        await state.set_state(ScanVacRekr.waiting_for_vac)
        return
    



@bot_router.callback_query(F.data == 'scan_redlab')
async def scan_redlab(calback : CallbackQuery, bot : Bot):
    await calback.message.answer('Начинаю сканирование...')
    await forward_messages_from_topics(telethon_client, TOPIC_MAP, AsyncSessionLocal, days=14, bot = bot)

@bot_router.callback_query(F.data == 'scan_redlab_day')
async def scan_redlab(calback : CallbackQuery, bot : Bot):
    await calback.message.answer('Начинаю сканирование...')
    await forward_messages_from_topics(telethon_client, TOPIC_MAP, AsyncSessionLocal, days=1, bot = bot)
    
@bot_router.callback_query(F.data == 'scan_redlab_21')
async def scan_redlab(calback : CallbackQuery, bot : Bot):
    await calback.message.answer('Начинаю сканирование...')
    await forward_messages_from_topics(telethon_client, TOPIC_MAP, AsyncSessionLocal, days=21, bot = bot)





@bot_router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery):
    await callback.message.edit_text(text="Основное меню", reply_markup = await main_kb())



@bot_router.callback_query(F.data == 'scan_hand')
async def scan_hand(calback : CallbackQuery, state: FSMContext):
    await calback.message.answer('Отправьте вакансию для проверки')
    await state.set_state(ScanHand.waiting_for_hand)
    


@bot_router.message(ScanHand.waiting_for_hand)
async def scan_hand_message(message: types.Message, state: FSMContext, bot: Bot):
    text = message.text
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
            delay_payment_text = 'С отсрочкой платежа "Срок уточняется" после подписания акта:\n'
            no_rate_delay = 'Условия оплаты: Срок уточняется'
        
        
        
        # Блок для обработки ставки
        if rate is None or int(rate) == 0:
            text_cleaned = f"🆔{vac_id}\n\n{vacancy}\n\nМесячная ставка(на руки) до: смотрим ваши предложения (приоритет на минимальную)\n\n{no_rate_delay}\n\n{text}"
        else:
            rate = float(rate)
            rate_sng_contract = search_and_extract_values('M', rate, ['B'], 'Расчет ставки (штат/контракт) СНГ')
            rate_sng_ip = search_and_extract_values('M', rate, ['B'], 'Расчет ставки (ИП) СНГ')
            rate_sng_samozanyatii = search_and_extract_values('M', rate, ['B'], 'Расчет ставки (Самозанятый) СНГ')
            if rate_sng_contract and rate_sng_ip and rate_sng_samozanyatii:
                rate_sng_contract = rate_sng_contract.get('B')
                rate_sng_ip = rate_sng_ip.get('B')
                rate_sng_samozanyatii = rate_sng_samozanyatii.get('B')
                if acts:
                    acts_text = f"Актирование: поквартальное\n"
                    state_contract_text = f"<s>Ежемесячная выплата Штат/Контракт : {rate_sng_contract} RUB</s>"
                else:
                    acts_text = 'Актирование: ежемесячное\n'
                    state_contract_text = f"Ежемесячная выплата Штат/Контракт : {rate_sng_contract} RUB"
                if short_project or long_payment:
                    state_contract_text = f"<s>{state_contract_text}</s>"
                if only_fulltime:
                    ip_samoz_text = f"<s>ИП : {rate_sng_ip} RUB,\n Самозанятый : {rate_sng_samozanyatii} RUB</s>"
                else:
                    ip_samoz_text = f"ИП : {rate_sng_ip} RUB,\n Самозанятый : {rate_sng_samozanyatii} RUB"
                        
                text_cleaned = f"🆔{vac_id}\n\n{vacancy}\n\nМесячная ставка(на руки) до:\n{state_contract_text}\n{delay_payment_text}{acts_text}\n{ip_samoz_text}\n\n{text}"
            else:
                text_cleaned = f"🆔{vac_id}\n\n{vacancy}\n\nМесячная ставка(на руки) до: смотрим ваши предложения (приоритет на минимальную)\n\n{no_rate_delay}\n\n{text}"
        clean_text = remove_vacancy_id(text_cleaned)
        
        
                
        try:
            await message.answer(text_cleaned, parse_mode='HTML')
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
    user_dir = os.path.join(SAVE_DIR, str(user_id))
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
                    await bot.send_message(
                        chat_id=message.chat.id,
                        text="Хотите добавить ещё файлы?",
                        reply_markup=scan_vac_rekr_yn_kb()
                    )
                else:
                    msg = await message.answer(text)
                    await bot.send_message(
                        chat_id=message.chat.id,
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



@bot_router.message(F.document)
async def doc_without_state(message: Message):
    await message.answer("📄 Чтобы загрузить резюме, сначала выберите вакансию в боте.")


    
@bot_router.callback_query(F.data == "yes_vac_rekr")
async def scan_vac_rekr_y(callback: CallbackQuery, state: FSMContext, bot: Bot):
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
    await callback.answer()
    await callback.message.answer("Начинаю обработку...")
    user_id = callback.from_user.id
    user_dir = os.path.join(SAVE_DIR, str(user_id))
    data = await state.get_data()
    vac_text = data.get("vacancy")
    mes3 = data.get("mes3")
    mes2 = data.get("mes2")
    mes1 = data.get("mes1")
    try:
        await bot.delete_messages(callback.message.chat.id, [mes1, mes2, mes3])
    except:
        pass


    if not os.path.exists(user_dir):
        await callback.message.answer("❌ Нет загруженных файлов для обработки.")
        return

    tasks = []
    for file_name in os.listdir(user_dir):
        file_path = os.path.join(user_dir, file_name)
        if os.path.isfile(file_path):
            tasks.append(process_file_and_gpt(file_path, bot, user_id, vac_text, file_name))

    if not tasks:
        await callback.message.answer("❌ Не найдено ни одного файла.")
        return
    result = await asyncio.gather(*tasks)
    if not result:
        await callback.message.answer("❌ Нет результатов для финального списка")
        return
    await state.clear()
    finalist_list = []
    utochnit_list = []
    otkaz_list = []
    canditates_data = {}

    for finalist in result:
        candidate = finalist.get('candidate')
        verdict = finalist.get('verdict')
        sverka_text = finalist.get('sverka_text')
        candidate_json = finalist.get('candidate_json')

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
            salary = candidate_json.get('summary', {}).get('salary_expectations', 'не указано')

            kandidate_verdict = f"ФИО: {candidate}\nЗарплатные ожидания: {salary}"

            messs = await callback.message.answer(kandidate_verdict, reply_markup=get_all_info_kb(verdict))
            await add_final_resume(messs.message_id, sverka_text, candidate_json)
            

    # 2️⃣ Требуют уточнения
    if utochnit_list:
        await callback.message.answer("🟡 Требуют уточнений:")
        for finalist in utochnit_list:
            candidate = finalist.get('candidate')
            verdict = finalist.get('verdict')
            sverka_text = finalist.get('sverka_text')
            candidate_json = finalist.get('candidate_json')
            salary = candidate_json.get('summary', {}).get('salary_expectations', 'не указано')

            kandidate_verdict = f"ФИО: {candidate}\nЗарплатные ожидания: {salary}"
            
            messs = await callback.message.answer(kandidate_verdict, reply_markup=get_all_info_kb(verdict))
            await add_utochnenie_resume(messs.message_id, sverka_text, candidate_json)
            

    # 3️⃣ Отказы
    if otkaz_list:
        await callback.message.answer("🔴 Не подходят:")
        for finalist in otkaz_list:
            candidate = finalist.get('candidate')
            verdict = finalist.get('verdict')
            sverka_text = finalist.get('sverka_text')
            candidate_json = finalist.get('candidate_json')
            salary = candidate_json.get('summary', {}).get('salary_expectations', 'не указано')

            kandidate_verdict = f"ФИО: {candidate}\nЗарплатные ожидания: {salary}"

            messs = await callback.message.answer(kandidate_verdict, reply_markup=get_all_info_kb(verdict))
            await add_otkonechenie_resume(messs.message_id, sverka_text, candidate_json)
            
            

    await state.set_state(GenerateMail.waiting_for_mail)
    
    shutil.rmtree(user_dir)
    
    
            
@bot_router.callback_query(F.data == "utochnit_prichinu")
async def utochnit_prichinu_bot(callback: CallbackQuery, bot: Bot):
    try:
        res = await get_otkolenie_resume(callback.message.message_id)
        if res:
            text = res.message_text
            message_id = res.message_id
            await bot.edit_message_text(chat_id=callback.message.chat.id, message_id=message_id, text=text, reply_markup=None)
        else:
            await bot.edit_message_text(chat_id=callback.message.chat.id, message_id=callback.message.message_id, text="❌ Данные об отклонении резюме удалены", reply_markup=None)
    except Exception as e:
        print("Ошибка в функции utochnit_prichinu: ", e)
        
        
        
        
@bot_router.callback_query(F.data.startswith("generate_mail:"))
async def generate_mail_bot(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    await callback.message.edit_text('Подготовка письма...')
    message_id = callback.message.message_id
    verdict = callback.data.split(":")[1]
    if verdict == "PP":
        data = await get_final_resume(message_id)
    elif verdict == "CP":
        data = await get_utochnenie_resume(message_id)
    elif verdict == "NP":
        data = await get_otkolenie_resume(message_id)
    
    if not data:
        await callback.message.answer("❌ Нет данных для генерации письма.")
        return
    
    
    candidate = data.json_text
    if isinstance(candidate, str):
        candidate_json = json.loads(candidate)
    
    candidate_name = candidate_json.get("candidate").get("full_name")
    verdict = candidate_json.get("summary").get("verdict")
    user_name = (
            f"@{callback.message.chat.username}"
            if callback.message.chat.username
            else (callback.message.chat.first_name or "Не указано")
        )
    mail = await create_mails(candidate_json, user_name)
    if mail:
        mail_text = mail
    else:
        mail_text = "."
    if verdict == "Полностью подходит":
        await bot.edit_message_text(text = f"📨 Создано письмо для кандидата {candidate_name} !", chat_id=callback.message.chat.id, message_id=message_id)
        await asyncio.sleep(3)
        await bot.edit_message_text(chat_id=callback.message.chat.id, message_id=message_id, text=mail_text, reply_markup=send_mail_or_generate_client_mail_kb(verdict))
        await add_final_resume(message_id, mail_text, candidate)
        
        
    else:
        await bot.edit_message_text(text = f"📨 Создано письмо для кандидата {candidate_name} !", chat_id=callback.message.chat.id, message_id=message_id)
        await asyncio.sleep(3)
        await bot.edit_message_text(chat_id=callback.message.chat.id, message_id=message_id, text=mail_text, reply_markup=send_mail_to_candidate_kb(verdict))
    
    
@bot_router.callback_query(F.data == "generate_klient_mail")
async def generate_klient_mail_bot(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    await callback.message.edit_text("📨 Создаю письмо для клиента...")

    message_id = callback.message.message_id
    data = await get_final_resume(message_id)
    if not data:
        await callback.message.answer("❌ Не удалось найти данные для генерации письма клиента.")
        return

    candidate = data.json_text
    if isinstance(candidate, str):
        candidate_json = json.loads(candidate)
    
    candidate_name = candidate_json.get("candidate").get("full_name")

    try:
        
        mail_text = await generate_cover_letter_for_client(candidate_json)
    except Exception as e:
        await callback.message.answer(f"⚠️ Ошибка при генерации письма клиента: {e}")
        return

    await bot.edit_message_text(chat_id=callback.message.chat.id, message_id=message_id, text=f"✅ Письмо для клиента по кандидату {candidate_name} создано и отправлено в группу!", reply_markup=None)
    await asyncio.sleep(3)
    await bot.edit_message_text(chat_id=callback.message.chat.id, message_id=message_id, text=f"Вот текст письма:\n{mail_text}", reply_markup=None)
    await bot.send_message(CLIENT_CHANNEL, mail_text)




@bot_router.callback_query(F.data.startswith("get_all_info:"))
async def get_all_info_bot(callback: CallbackQuery, state: FSMContext, bot: Bot):
    verdict = callback.data.split(":")[1]
    message_id = callback.message.message_id
    if verdict == "PP":
        verdict = "Полностью подходит"
        sverka = await get_final_resume(message_id)
        if sverka:
            await bot.edit_message_text(chat_id=callback.message.chat.id, message_id=message_id, text=sverka.message_text, reply_markup=generate_mail_kb(verdict))
        else:
            await bot.edit_message_text(chat_id=callback.message.chat.id, message_id=message_id, text="❌ Не удалось найти данные для генерации письма клиента.")
    elif verdict == "CP":
        verdict = "Частично подходит (нужны уточнения)"
        sverka = await get_utochnenie_resume(message_id)
        if sverka:
            await bot.edit_message_text(chat_id=callback.message.chat.id, message_id=message_id, text=sverka.message_text, reply_markup=generate_mail_kb(verdict))
        else:
            await bot.edit_message_text(chat_id=callback.message.chat.id, message_id=message_id, text="❌ Не удалось найти данные для генерации письма клиента.")
    elif verdict == "NP":
        verdict = "Не подходит"
        sverka = await get_otkolenie_resume(message_id)
        if sverka:
            await bot.edit_message_text(chat_id=callback.message.chat.id, message_id=message_id, text=sverka.message_text, reply_markup=generate_mail_kb(verdict))
        else:
            await bot.edit_message_text(chat_id=callback.message.chat.id, message_id=message_id, text="❌ Не удалось найти данные для генерации письма клиента.")
            
@bot_router.callback_query(F.data.startswith("send_mail_to_candidate"))
async def send_mail_to_candidate_bot(callback: CallbackQuery, state: FSMContext, bot: Bot):
    verdict = callback.data.split(":")[1]
    message_id = callback.message.message_id
    if verdict == "PP":
        data = await get_final_resume(message_id)
    elif verdict == "CP":
        data = await get_utochnenie_resume(message_id)
    elif verdict == "NP":
        data = await get_otkolenie_resume(message_id)
    if not data:
        await callback.message.answer("❌ Нет данных для отправки письма кандидату.")
        return
    candidate = data.json_text
    if isinstance(candidate, str):
        candidate_json = json.loads(candidate)
    
    contacts = candidate_json.get("candidate", {}).get("contacts", {})
    if not contacts:
        await callback.message.edit_text("❌ Нет данных для отправки письма кандидату.")
        return
    else:
        await callback.message.edit_text("Выберете куда отправить сообщение", reply_markup=create_contacts_kb(contacts))
    
@bot_router.callback_query(F.data.startswith("con:"))
async def send_mail_to_candidate_bot(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    source = callback.data.split(":")[1]
    await callback.message.edit_text(f"source: {source}")
    
