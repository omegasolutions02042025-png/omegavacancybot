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
from gpt import process_vacancy, format_vacancy
from gpt_gimini import generate_mail_for_candidate_utochnenie, process_vacancy_with_gemini, format_vacancy_gemini, generate_mail_for_candidate_finalist, generate_mail_for_candidate_otkaz, generate_cover_letter_for_client
from googlesheets import find_rate_in_sheet_gspread, search_and_extract_values
from telethon_bot import telethon_client
from db import AsyncSessionLocal, add_otkonechenie_resume, get_otkolenie_resume 
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

async def save_document(message: types.Message, state: FSMContext, bot):
    document = message.document
    if not document:
        await message.answer("Отправьте резюме в формате PDF/DOCX/RTF/TXT")
        return

    user_id = message.from_user.id
    user_dir = os.path.join(SAVE_DIR, str(user_id))
    os.makedirs(user_dir, exist_ok=True)

    file_name = document.file_name
    local_file_path = os.path.join(user_dir, file_name)

    # --- Проверяем, существует ли уже файл ---
    if os.path.exists(local_file_path):
        print(f"⚠️ Файл {file_name} уже существует — пропускаем сохранение.")
        await message.answer(f"⚠️ Файл **{file_name}** уже есть, пропускаю сохранение.")
        return

    # --- Загружаем файл ---
    file_info = await bot.get_file(document.file_id)
    await bot.download_file(file_info.file_path, destination=local_file_path)
    print(f"📁 Файл сохранён: {local_file_path}")

    data = await state.get_data()

    # --- Удаляем старое сообщение "Жду файлы" ---
    if data.get("mes3"):
        try:
            await bot.delete_message(message.chat.id, data["mes3"])
        except:
            pass

    # === Если сообщение часть группы ===
    media_group_id = message.media_group_id
    if media_group_id:
        # Проверяем, обрабатывается ли уже эта группа
        if ACTIVE_MEDIA_GROUPS.get(media_group_id):
            # уже есть обработка этой группы — просто сохраняем файл
            return

        # Помечаем группу как активную
        ACTIVE_MEDIA_GROUPS[media_group_id] = True
        print(f"📦 Начало обработки группы файлов {media_group_id}")

        # ждём, пока Telegram догрузит остальные файлы группы
        await asyncio.sleep(2.0)

        mes1 = await message.answer("📥 Файлы сохранены.")
        mes2 = await message.answer("Хотите добавить ещё файлы?", reply_markup=scan_vac_rekr_yn_kb())
        await state.update_data(mes1=mes1.message_id, mes2=mes2.message_id)

        # снимаем блокировку через 10 секунд
        await asyncio.sleep(10)
        ACTIVE_MEDIA_GROUPS.pop(media_group_id, None)
        print(f"✅ Группа {media_group_id} обработана и разблокирована.")

    else:
        # --- Одиночный файл ---
        mes1 = await message.answer("📥 Файл сохранён.")
        mes2 = await message.answer("Хотите добавить ещё файлы?", reply_markup=scan_vac_rekr_yn_kb())
        await state.update_data(mes1=mes1.message_id, mes2=mes2.message_id)




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
            tasks.append(process_file_and_gpt(file_path, bot, user_id, vac_text))

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
        message_id = finalist.get('message_id')
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
            message_id = finalist.get('message_id')
            candidate_json = finalist.get('candidate_json')
            salary = finalist.get('summary', 'не указано').get('salary_expectations', 'не указано')

            kandidate_verdict = f"ФИО: {candidate}\nЗарплатные ожидания: {salary}\nСгенерировать ли сопроводительное письмо?"

            messs = await callback.message.answer(kandidate_verdict, reply_markup=generate_mail_kb(verdict))
            candidate_data = {
                messs.message_id: {
                    'candidate_json': candidate_json,
                    'sverka_text': sverka_text,
                    'message_id': message_id,
                    'verdict': verdict,
                    'candidate_name': candidate
                }
            }
            canditates_data.update(candidate_data)

    # 2️⃣ Требуют уточнения
    if utochnit_list:
        await callback.message.answer("🟡 Требуют уточнений:")
        for finalist in utochnit_list:
            candidate = finalist.get('candidate')
            verdict = finalist.get('verdict')
            sverka_text = finalist.get('sverka_text')
            message_id = finalist.get('message_id')
            candidate_json = finalist.get('candidate_json')
            salary = finalist.get('summary', 'не указано').get('salary_expectations', 'не указано')

            kandidate_verdict = f"ФИО: {candidate}\nЗарплатные ожидания: {salary}\nСгенерировать ли уточняющее письмо?"

            messs = await callback.message.answer(kandidate_verdict, reply_markup=generate_mail_kb(verdict))
            candidate_data = {
                messs.message_id: {
                    'candidate_json': candidate_json,
                    'sverka_text': sverka_text,
                    'message_id': message_id,
                    'verdict': verdict,
                    'candidate_name': candidate
                }
            }
            canditates_data.update(candidate_data)

    # 3️⃣ Отказы
    if otkaz_list:
        await callback.message.answer("🔴 Не подходят:")
        for finalist in otkaz_list:
            candidate = finalist.get('candidate')
            verdict = finalist.get('verdict')
            sverka_text = finalist.get('sverka_text')
            message_id = finalist.get('message_id')
            candidate_json = finalist.get('candidate_json')
            salary = finalist.get('summary', {}).get('salary_expectations', 'не указано')

            kandidate_verdict = f"ФИО: {candidate}\nЗарплатные ожидания: {salary}\nПодготовить отказ?"

            messs = await callback.message.answer(kandidate_verdict, reply_markup=generate_mail_kb(verdict))
            candidate_data = {
                messs.message_id: {
                    'candidate_json': candidate_json,
                    'sverka_text': sverka_text,
                    'message_id': message_id,
                    'verdict': verdict,
                    'candidate_name': candidate
                }
            }
            canditates_data.update(candidate_data)

    await state.update_data(candidate_data=canditates_data)
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
        
        
        
        
@bot_router.callback_query(F.data == "generate_mail")
async def generate_mail_bot(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    await callback.message.edit_text('Подготовка письма...')
    message_id = callback.message.message_id
    data = await state.get_data()
    candidate_data_dict = data.get("candidate_data", {})
    candidate_data = candidate_data_dict.get(message_id)
    if not candidate_data:
        await callback.message.answer("❌ Нет данных для генерации письма.")
        return
    candidate = candidate_data.get("candidate_json")
    sverka_text = candidate_data.get("sverka_text")
    old_message_id = candidate_data.get("message_id")
    candidate_name = candidate_data.get("candidate_name")
    verdict = candidate_data.get("verdict")
    user_name = (
            f"@{callback.message.chat.username}"
            if callback.message.chat.username
            else (callback.message.chat.first_name or "Не указано")
        )
    mail = await create_mails(candidate, user_name)
    if mail:
        mail_text = mail
    else:
        mail_text = "."
    if verdict == "Полностью подходит":
        await bot.edit_message_text(chat_id=callback.message.chat.id, message_id=message_id, text=mail_text, reply_markup=generate_klient_mail_kb())
        client_data = {message_id:{'candidate_json': candidate, 'candidate_name': candidate_name}}
        await state.update_data(client_data=client_data)
    else:
        await bot.edit_message_text(text = f"📨 Создано письмо для кандидата {candidate_name} !", chat_id=callback.message.chat.id, message_id=message_id)
        await asyncio.sleep(3)
        await bot.edit_message_text(chat_id=callback.message.chat.id, message_id=message_id, text=mail_text)
    
    
    if verdict != "Полностью подходит":
        if not candidate_data_dict:
            await state.clear()
        else:
            await state.update_data(candidate_data=candidate_data_dict)
    else:
        await state.update_data(candidate_data=candidate_data_dict)
    
@bot_router.callback_query(F.data == "generate_klient_mail")
async def generate_klient_mail_bot(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    await callback.message.edit_text("📨 Создаю письмо для клиента...")

    message_id = callback.message.message_id
    data = await state.get_data()
    client_data_dict = data.get("client_data", {})
    client_data = client_data_dict.get(message_id)
    if not client_data:
        await callback.message.answer("❌ Не удалось найти данные для генерации письма клиента.")
        return

    candidate = client_data.get("candidate_json")
    candidate_name = client_data.get("candidate_name", "кандидата")

    try:
        
        mail_text = await generate_cover_letter_for_client(candidate)
    except Exception as e:
        await callback.message.answer(f"⚠️ Ошибка при генерации письма клиента: {e}")
        return

    try:
        await callback.message.delete()
    except Exception:
        pass
    await bot.edit_message_text(chat_id=callback.message.chat.id, message_id=message_id, text=f"✅ Письмо для клиента по кандидату {candidate_name} создано и отправлено в группу!", reply_markup=None)
    await asyncio.sleep(3)
    await bot.edit_message_text(chat_id=callback.message.chat.id, message_id=message_id, text=f"Вот текст письма:\n{mail_text}", reply_markup=None)
    await bot.send_message(CLIENT_CHANNEL, mail_text)

    client_data_dict.pop(message_id, None)
    if not client_data_dict:
        await state.clear()
    else:
        await state.update_data(client_data=client_data_dict)
