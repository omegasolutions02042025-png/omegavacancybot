from aiogram import Router, F   
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram import Bot
from kb import service_kb, next_email_kb, next_telegram_kb, accept_delete_tg_kb, accept_delete_email_kb
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from send_email import send_email_gmail
from db import add_email, add_session_tg, remove_session_tg, remove_session_email, get_tg_user
import os
from telethon import TelegramClient
from read_jpg import extract_code_from_image
import io
from telethon.errors import SessionPasswordNeededError
from telethon.errors.rpcerrorlist import (
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    FloodWaitError,
    PhoneNumberUnoccupiedError,
    PhoneNumberInvalidError,
    ApiIdInvalidError,
)
from aiogram.types import FSInputFile

pr_router = Router()
os.makedirs("sessions", exist_ok=True)

class PrivyazkaEmail(StatesGroup):
    waiting_for_email = State()
    waiting_for_password = State()


class PrivyazkaTelegram(StatesGroup):
    waiting_for_number = State()
    waiting_for_api_id = State()
    waiting_for_api_hash = State()
    waiting_for_code = State()
    waiting_for_password = State()



@pr_router.message(Command("add_account"))
async def add_account(message: Message, bot: Bot):
    user_name = message.from_user.username
    await message.answer("Выберете сервис для привзяки к боту для отправки сообщений", reply_markup=service_kb(user_name))


@pr_router.callback_query(F.data == "gmail")
async def add_gmail_account(callback: CallbackQuery, bot: Bot):
    await callback.message.answer("""
        ✉️ Настройка подключения e-mail


1) Перейти по ссылке: https://myaccount.google.com/

2) Открыть раздел «Безопасность» → «Вход в аккаунт Google».

3) Включить двухэтапную аутентификацию.

4) После включения — внизу страницы выбрать «Пароли приложений».

5) Создать новый пароль:

6) Приложение — «Почта»

7) Устройство — «Компьютер Windows» или «Mac»

8) Нажать «Создать», скопировать сгенерированный пароль.

9) После того как получили пароль нажать кнопку "Далее".

        """, reply_markup=next_email_kb())


    



@pr_router.callback_query(F.data == "next_email")
async def next_email(callback: CallbackQuery, bot: Bot, state: FSMContext):
    await callback.message.answer("Введите почту для привязки")
    await state.set_state(PrivyazkaEmail.waiting_for_email)


@pr_router.message(PrivyazkaEmail.waiting_for_email)
async def add_email_account(message: Message, bot: Bot, state: FSMContext):
    email = message.text
    await state.update_data(email=email)
    await message.answer('Введите Пароль Приложений')
    await state.set_state(PrivyazkaEmail.waiting_for_password)


@pr_router.message(PrivyazkaEmail.waiting_for_password)
async def add_email_password(message: Message, bot: Bot, state: FSMContext):
    password = message.text
    user_name = message.from_user.username
    if not user_name:
        message.answer("Для продолжения создайте имя пользователя в Telegram и отправте еще раз пароль приложений")
        return
    data = await state.get_data()
    email = data.get("email")
    await message.answer("Отправляю тестовое сообщение...")
    success = await send_email_gmail(
        sender_email=email,
        app_password=password,
        recipient_email="artursimoncik@gmail.com",
        subject="Тестовое сообщение",
        body="Это тестовое сообщение"
    )
    if success:
        await message.answer(f"Подключение к почте {email} успешно!")
        await add_email(user_name_tg=user_name, user_email=email, password=password)
    else:
        await message.answer("Не удалось подключиться к почте")
    await state.set_state(PrivyazkaEmail.waiting_for_password)




@pr_router.callback_query(F.data == "telegram")
async def add_telegram(callback: CallbackQuery, bot: Bot):
    await callback.message.answer("""
    Для привязки Telegram нужно получить API ID и API Hash.Вот инструкция:
    🚀 Как получить API ID и API Hash
🔹 Шаг 1. Перейди на сайт Telegram Developers

👉 https://my.telegram.org

🔹 Шаг 2. Войди через свой Telegram

— Введи номер телефона,
— Подтверди вход кодом из Telegram (приходит в приложение).

🔹 Шаг 3. Зайди в раздел “API Development Tools”

После входа кликни:
"API Development Tools" → откроется форма для создания нового приложения.

🔹 Шаг 4. Создай новое приложение

Заполни поля:

App title — любое имя (например, OmegaTelethonBot)

Short name — короткое (например, omega)

URL — можно оставить пустым

Platform — выбери “Other”

Нажми Create application.

🔹 Шаг 5. Получи данные

На открывшейся странице ты увидишь:

App api_id: 1234567

App api_hash: abcdef1234567890abcdef1234567890""", reply_markup=next_telegram_kb())


@pr_router.callback_query(F.data == "next_telegram")
async def next_telegram(callback: CallbackQuery, bot: Bot, state: FSMContext):
    await callback.message.answer("Введите номер телефона в формате +7XXXXXXXXXX:")
    await state.set_state(PrivyazkaTelegram.waiting_for_number)


@pr_router.message(PrivyazkaTelegram.waiting_for_number)
async def add_number(message: Message, bot: Bot, state: FSMContext):
    number = message.text.strip()
    
    # Базовая валидация номера телефона
    if not number.startswith('+') and not number.startswith('7') and not number.startswith('8'):
        await message.answer("❌ Введите номер телефона в формате +7XXXXXXXXXX или 8XXXXXXXXXX")
        return
    
    await state.update_data(number=number)
    await message.answer("Введите API ID")
    await state.set_state(PrivyazkaTelegram.waiting_for_api_id)


@pr_router.message(PrivyazkaTelegram.waiting_for_api_id)
async def add_api_id(message: Message, bot: Bot, state: FSMContext):
    api_id = message.text.strip()
    
    # Проверяем, что API ID - это число
    if not api_id.isdigit():
        await message.answer("❌ API ID должен быть числом. Введите корректный API ID:")
        return
    
    await state.update_data(api_id=int(api_id))
    await message.answer("Введите API Hash")
    await state.set_state(PrivyazkaTelegram.waiting_for_api_hash)


@pr_router.message(PrivyazkaTelegram.waiting_for_api_hash)
async def add_api_hash(message: Message, bot: Bot, state: FSMContext):
    api_hash = message.text.strip()
    
    # Базовая валидация API Hash - должен быть строкой из 32 символов
    if len(api_hash) != 32:
        await message.answer("❌ API Hash должен содержать 32 символа. Введите корректный API Hash:")
        return
    data = await state.get_data()
    api_id = data.get("api_id")
    number = data.get("number")
    user_name = message.from_user.username
    if not user_name:
        await message.answer("Для продолжения создайте имя пользователя в Telegram и отправте еще раз API Hash")
        return
    try:
        client = TelegramClient(f"sessions/{user_name}", api_id, api_hash)
        await client.connect()
        if await client.is_user_authorized():
            me = await client.get_me()
            await message.answer(f"✅ Уже авторизован как @{me.username or me.id}")
            await client.disconnect()
            await state.clear()
            return
        
        sent = await client.send_code_request(number)
        phone_code_hash = sent.phone_code_hash
        await message.answer("Отправьте скриншот кода подтверждения")
        photo = FSInputFile("image.png")
        await message.answer_photo(photo=photo, caption='Вот пример фото')
        await state.update_data(api_hash = api_hash, phone_code_hash = phone_code_hash)
        await state.set_state(PrivyazkaTelegram.waiting_for_code)
    except ApiIdInvalidError:
        await message.answer("❌ Неверный API ID или API Hash. Проверьте данные и попробуйте еще раз.\n\nВведите API ID:")
        await state.set_state(PrivyazkaTelegram.waiting_for_api_id)
    except Exception as e:
        await message.answer(f"❌ Ошибка подключения: {str(e)}\n\nВведите API ID:")
        await state.set_state(PrivyazkaTelegram.waiting_for_api_id)


@pr_router.message(PrivyazkaTelegram.waiting_for_code)
async def add_code(message: Message, bot: Bot, state: FSMContext):
    if not message.photo:
        await message.answer("Отправьте скриншот кода подтверждения")
        return
    photo = message.photo[-1]
    os.makedirs("temp", exist_ok=True)
    save_path = os.path.join("temp", f"{photo.file_id}.jpg")
    file_info = await bot.get_file(photo.file_id)
    await bot.download_file(file_info.file_path, destination=save_path)
    code = extract_code_from_image(save_path)
    os.remove(save_path)
    user_name = message.from_user.username
    data = await state.get_data()
    api_id = data.get("api_id")
    api_hash = data.get("api_hash")
    number = data.get("number")
    phone_code_hash = data.get("phone_code_hash")
    user_name = message.from_user.username
    if not user_name:
        await message.answer("Для продолжения создайте имя пользователя в Telegram и отправте еще раз код подтверждения")
        return
    
    try:
        client = TelegramClient(f"sessions/{user_name}", api_id, api_hash)
        await client.connect()
        await client.sign_in(phone=number, code=code, phone_code_hash=phone_code_hash)
        me = await client.get_me()
        await message.answer(f"✅ Успешный вход как {me.first_name} (@{me.username})")
        await client.disconnect()
        await add_session_tg(user_name_tg=user_name, api_id=str(api_id), api_hash=str(api_hash))
        await state.clear()
    except SessionPasswordNeededError:
        await message.answer("🔐 Включена 2FA. Введите пароль от аккаунта:")
        await state.set_state(PrivyazkaTelegram.waiting_for_password)
        await state.update_data(code = code)

    except PhoneCodeInvalidError:
        await message.answer("❌ Неверный код. Отправьте новый корректный код.")
    except PhoneCodeExpiredError:
        await message.answer("⌛ Срок действия кода истёк. Запрошу новый, пришлите свежий код.")
        # при необходимости вызови повторно send_code_request(phone)

    except FloodWaitError as e:
        await message.answer(f"⏱ Слишком много попыток. Подождите {e.seconds} сек и попробуйте снова.")
    except (PhoneNumberUnoccupiedError, PhoneNumberInvalidError):
        await message.answer("❌ Номер не привязан к аккаунту Telegram или некорректен.")
    except Exception as e:
        await message.answer(f"❌ Ошибка входа: {type(e).__name__}: {e}")
        

  
@pr_router.message(PrivyazkaTelegram.waiting_for_password)
async def add_password(message: Message, bot: Bot, state: FSMContext):
    password = message.text
    data = await state.get_data()
    api_id = data.get("api_id")
    api_hash = data.get("api_hash")
    number = data.get("number")
    code = data.get("code")
    user_name = message.from_user.username
    phone_code_hash = data.get("phone_code_hash")
    if not user_name:
        await message.answer("Для продолжения создайте имя пользователя в Telegram и отправте еще раз пароль")
        return
    
    try:
        client = TelegramClient(f"sessions/{user_name}", api_id, api_hash)
        await client.connect()
        await client.sign_in(password=password)
        me = await client.get_me()
        await message.answer(f"✅ Успешный вход как {me.first_name} (@{me.username})")
        await client.disconnect()
        await add_session_tg(user_name_tg=user_name, api_id=str(api_id), api_hash=str(api_hash))
        await state.clear()
        
    except Exception as e:
        await message.answer(f"❌ Ошибка входа: {str(e)}")

    
@pr_router.callback_query(F.data == "remove_tg")
async def remove_tg(callback: CallbackQuery, bot: Bot, state: FSMContext):
    await callback.message.edit_text("Вы уверены что хотите удалить привязку Telegram?", reply_markup=accept_delete_tg_kb())
    

@pr_router.callback_query(F.data == "accept_delete_tg")
async def accept_delete_tg(callback: CallbackQuery, bot: Bot, state: FSMContext):
    user_name = callback.from_user.username
    session = await get_tg_user(user_name_tg=user_name)
    api_id = session.api_id
    api_hash = session.api_hash
    client = TelegramClient(f"sessions/{user_name}", api_id, api_hash)
    await client.connect()
    await client.log_out()
    await client.disconnect()
    os.remove(f'sessions/{user_name}.session')
    await remove_session_tg(user_name_tg=user_name)
    await callback.message.edit_text("Успешно удалено")
    


@pr_router.callback_query(F.data == "remove_email")
async def remove_email(callback: CallbackQuery, bot: Bot, state: FSMContext):
    await callback.message.edit_text("Вы уверены что хотите удалить привязку Email?", reply_markup=accept_delete_email_kb())
    
@pr_router.callback_query(F.data == "accept_delete_email")
async def accept_delete_email(callback: CallbackQuery, bot: Bot, state: FSMContext):
    user_name = callback.from_user.username
    await remove_session_email(user_name_tg=user_name)
    await callback.message.edit_text("Успешно удалено")