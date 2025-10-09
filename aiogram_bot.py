from aiogram import Router
from aiogram import Bot, Dispatcher, types, F

from aiogram.types import CallbackQuery, FSInputFile, Message
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart, Command
from kb import main_kb, send_kb, scan_vac_rekr_yn_kb
from telethon_bot import *
from funcs import update_channels_and_restart_handler
import os
from dotenv import load_dotenv
from funcs import *
from gpt import process_vacancy, format_vacancy
from gpt_gimini import process_vacancy_with_gemini, format_vacancy_gemini, generate_mail_for_candidate_finalist
from googlesheets import find_rate_in_sheet_gspread, search_and_extract_values
from telethon_bot import telethon_client
from db import AsyncSessionLocal
from scan_documents import process_file_and_gpt, create_finalists_table, create_candidates_csv
import shutil
import markdown

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
        print(text_gpt) 
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
                print(text_cleaned)
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
    


async def save_document(message: types.Message, state: FSMContext, bot : Bot):
    document = message.document
    if not document:
        await message.answer("Отправьте резюме в формате PDF/DOCX/RTF/TXT")
        return

    file_info = await bot.get_file(document.file_id)
    file_path = file_info.file_path
    file_name = document.file_name

    # --- создаём папку для пользователя ---
    user_id = message.from_user.id
    user_dir = os.path.join(SAVE_DIR, str(user_id))
    os.makedirs(user_dir, exist_ok=True)

    # --- путь для сохранения файла ---
    local_file_path = os.path.join(user_dir, file_name)
    await bot.download_file(file_path, destination=local_file_path)
    # --- Обработка media_group_id ---
    data = await state.get_data()
    if message.media_group_id:
        if data.get("last_media_group_id") != message.media_group_id:
            # Сохраняем media_group_id и спрашиваем только один раз
            await state.update_data(last_media_group_id=message.media_group_id)
            await message.answer(f"📥 Файлы сохранены.")
            await message.answer("Хотите добавить ещё файлы?", reply_markup=scan_vac_rekr_yn_kb())
            
    else:
        # Для одиночного файла
        await message.answer(f"📥 Файл сохранён.")
        await message.answer("Хотите добавить ещё файлы?", reply_markup=scan_vac_rekr_yn_kb())




    
@bot_router.callback_query(F.data == "yes_vac_rekr")
async def scan_vac_rekr_y(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.message.answer("Жду файлы")
    

@bot_router.callback_query(F.data == "no_vac_rekr")
async def scan_vac_rekr_n(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    await callback.message.answer("Начинаю обработку...")
    user_id = callback.from_user.id
    user_dir = os.path.join(SAVE_DIR, str(user_id))
    data = await state.get_data()
    vac_text = data.get("vacancy")
    print(vac_text)

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
    #table = create_finalists_table(result)
    #await callback.message.answer(table)
    #create_candidates_csv(result)
    #document = FSInputFile("candidates_report.csv")
    #await callback.message.answer_document(document)
   
    for finalist in result:
      if isinstance(finalist, str):
        continue
      candidate = finalist.get("candidate", {})
      summary = finalist.get("summary", {})
      verdict = summary.get("verdict", "")
    #   if verdict == "Полностью подходит":
      res = await generate_mail_for_candidate_finalist(finalist)
      await callback.message.answer(f"Создано письмо для {candidate['full_name'] or '❌'}")
      await callback.message.answer(res)
    
    shutil.rmtree(user_dir)
    #os.remove("candidates_report.csv")

    await callback.message.answer("✅ Обработка завершена.")
    
            
        
@bot_router.message(Command("bot"))
async def bot_hr(message: Message):
    
    mess = await message.answer('.')
    await mess.edit_text(f"<a href='https://t.me/omega_vacancy_bot?start={mess.message_id}'>Нажмите для запуска бота</a>", parse_mode="HTML")
