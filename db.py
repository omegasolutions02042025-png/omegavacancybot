import os
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, select, Column, BigInteger, update, Boolean 
from datetime import datetime, timedelta
import asyncio
from sqlalchemy import JSON
import json

DATABASE_URL = "postgresql+asyncpg://postgres:123546@localhost:5432/omega_db"

async_engine = create_async_engine(
    DATABASE_URL, 
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600
)

AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

class Base(DeclarativeBase):
    pass
    

class Channel(Base):
    __tablename__ = 'channels'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    channel_id: Mapped[int] = mapped_column(Integer, nullable=False)
    channel_name: Mapped[str] = mapped_column(String, nullable=True)
    

class Filter(Base):
    __tablename__ = 'filters'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    filter_text: Mapped[str] = mapped_column(String, nullable=False)


class Slova(Base):
    __tablename__ = 'slova'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    filter_text: Mapped[str] = mapped_column(String, nullable=False)




class CandidateResume(Base):
    __tablename__ = 'candidate_resume'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id= Column(Integer, nullable=False)
    message_text = Column(String, nullable=False)
    json_text = Column(String, nullable=False)
    resume_text = Column(String, nullable=False)
    sverka_text = Column(String, nullable=True)
    is_finalist = Column(Boolean, nullable=False)
    is_utochnenie = Column(Boolean, nullable=False)
    wl_path = Column(String, nullable=True)
    candidate_mail = Column(String, nullable=True)

class Contact(Base):
    __tablename__ = 'contact'
    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(Integer, nullable=False)
    candidate_fullname = Column(String, nullable=True)
    contact_tg = Column(String, nullable=True)
    contact_email = Column(String, nullable=True)
    contact_phone = Column(String, nullable=True)
    
    

 
    
class MessageMapping(Base):
    __tablename__ = "message_mapping"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    src_chat_id = Column(BigInteger, index=True)
    src_msg_id = Column(BigInteger, index=True)
    dst_chat_id = Column(BigInteger, index=True)
    dst_msg_id = Column(BigInteger, index=True)
    deadline_date = Column(String, nullable=True)  
    deadline_time = Column(String, nullable=True) 


class LastSequenceNumber(Base):
    __tablename__ = "last_sequence_number"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    last_number = Column(Integer, nullable=False)


class PrivyazanieEmail(Base):
    __tablename__ = "privyazanie_email"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_name_tg = Column(String, nullable=False)
    user_email = Column(String, nullable=True)
    email_password = Column(String, nullable=True)
    
class PrivyazanieTelegram(Base):
    __tablename__ = "privyazanie_telegram"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_name_tg = Column(String, nullable=False)
    api_id = Column(String, nullable=False)
    api_hash = Column(String, nullable=False)
    

class VacancyThread(Base):
    __tablename__ = "vacancy_thread"

    id = Column(Integer, primary_key=True, autoincrement=True)
    thread_chat_id = Column(String, nullable=False)
    vacancy_text = Column(String, nullable=False)
    vacancy_id = Column(String, nullable=False)
    
    

class RecruterGroup(Base):
    __tablename__ = "recruter_group"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    recruter_user_name = Column(String, nullable=False)
    group_id = Column(String, nullable=False)
    
class ActualVacancy(Base):
    __tablename__ = "actual_vacancy"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    vacancy_id = Column(String, nullable=False)
    title = Column(String, nullable=False)
    message_id = Column(Integer, nullable=False)
    user_name_tg = Column(String, nullable=False)
    

async def init_db():
    print("🧱 Инициализация базы данных...")
    print("📋 Таблицы в metadata:", list(Base.metadata.tables.keys()))
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Таблицы созданы (если их не было).")


async def add_channel(channel_name: str, channel_id: int):
    async with AsyncSessionLocal() as session:
        query = select(Channel).where(Channel.channel_id == channel_id)
        result = await session.execute(query)
        if result.scalars().first():
            return 'Такой канал уже есть'
        else:
            try:
                channel = Channel(channel_name=channel_name, channel_id=channel_id)
                session.add(channel)
                await session.commit()
                
            except:
                return "Канал не получилось добавить"
        

async def remove_channel(channel_id: str):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Channel).where(Channel.channel_id == channel_id)
        )
        channel = result.scalar_one_or_none()
        if channel:
            await session.delete(channel)
            await session.commit()
            print(f"Канал {channel_id} удалён из базы.")
        else:
            print(f"Канал {channel_id} не найден в базе.")


async def get_all_channels():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Channel))
        channels = result.scalars().all()
        return channels
    

async def add_filter(filter_text):
    async with AsyncSessionLocal() as session:
        query = select(Filter).where(Filter.filter_text == filter_text)
        result = await session.execute(query)
        if result.scalars().first():
            return True
        else:
            filter = Filter(filter_text=filter_text)
            session.add(filter)
            await session.commit()

async def get_all_filters():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Filter))
        filters = result.scalars().all()
        return filters
    
async def remove_filter(id):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Filter).where(Filter.id == id)
        )
        filter = result.scalar_one_or_none()
        if filter:
            await session.delete(filter)
            await session.commit()






async def add_slovo(filter_text):
    async with AsyncSessionLocal() as session:
        query = select(Filter).where(Filter.filter_text == filter_text)
        result = await session.execute(query)
        if result.scalars().first():
            return True
        else:
            filter = Slova(filter_text=filter_text)
            session.add(filter)
            await session.commit()


async def get_all_slova():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Slova))
        filters = result.scalars().all()
        return filters


async def remove_slovo(id):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Slova).where(Slova.id == id)
        )
        filter = result.scalar_one_or_none()
        if filter:
            await session.delete(filter)
            await session.commit()








async def add_message_mapping(
    src_chat_id: int,
    src_msg_id: int,
    dst_chat_id: int,
    dst_msg_id: int,
    deadline_date: str | None = None,
    deadline_time: str | None = None
):
    async with AsyncSessionLocal() as session:
        mapping = MessageMapping(
            src_chat_id=src_chat_id,
            src_msg_id=src_msg_id,
            dst_chat_id=dst_chat_id,
            dst_msg_id=dst_msg_id,
            deadline_date=deadline_date,
            deadline_time=deadline_time
        )
        session.add(mapping)
        await session.commit()


async def get_all_message_mappings():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(MessageMapping))
        return result.scalars().all()

async def remove_message_mapping(src_chat_id: int, src_msg_id: int):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(MessageMapping).where(
                (MessageMapping.src_chat_id == src_chat_id) & (MessageMapping.src_msg_id == src_msg_id)
            )
        )
        mapping = result.scalars().first()
        if mapping:
            await session.delete(mapping)
            await session.commit()


async def get_next_sequence_number() -> int:
    # Получаем запись с id=1 или создаём, если нет
    async with AsyncSessionLocal() as session:
        record = await session.get(LastSequenceNumber, 1)
        if not record:
            record = LastSequenceNumber(id=1, last_number=0)
            session.add(record)
            await session.commit()

        record.last_number += 1
        await session.commit()
        return record.last_number
    


# ===============================================================
#  CANDIDATE RESUME (Кандидаты)
# ===============================================================

async def add_candidate_resume(message_id: int, message_text: str, json_text: dict, resume_text: str, sverka_text: str,is_finalist: bool, is_utochnenie: bool):
    """
    Добавляет или обновляет запись CandidateResume.
    Если message_id уже существует — обновляет текст и JSON.
    """
    if isinstance(json_text, dict):
        json_text = json.dumps(json_text, ensure_ascii=False, indent=2)

    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(CandidateResume).where(CandidateResume.message_id == message_id)
            )
            existing_record = result.scalar_one_or_none()

            if existing_record:
                existing_record.message_text = message_text
                existing_record.json_text = json_text
                existing_record.resume_text = resume_text
                existing_record.sverka_text = sverka_text
                existing_record.is_finalist = is_finalist
                existing_record.is_utochnenie = is_utochnenie
                print(f"♻️ Обновлена запись CandidateResume с message_id={message_id}")
            else:
                new_record = CandidateResume(
                    message_id=message_id,
                    message_text=message_text,
                    json_text=json_text,
                    resume_text=resume_text,
                    sverka_text=sverka_text,
                    is_finalist=is_finalist,
                    is_utochnenie=is_utochnenie
                )
                session.add(new_record)
                print(f"✅ Добавлена новая запись CandidateResume с message_id={message_id}")
            await session.commit()
            

        except Exception as e:
            await session.rollback()
            print(f"❌ Ошибка при добавлении/обновлении CandidateResume: {e}")


async def get_candidate_resume(message_id: int):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(CandidateResume).where(CandidateResume.message_id == message_id)
        )
        return result.scalar_one_or_none()    


async def update_candidate_messsage_text(message_id: int, message_text: str):
    async with AsyncSessionLocal() as session:
        await session.execute(update(CandidateResume).where(CandidateResume.message_id == message_id).values(message_text=message_text))
        await session.commit()

async def update_candidate_is_finalist(message_id: int, is_finalist: bool):
    async with AsyncSessionLocal() as session:
        await session.execute(update(CandidateResume).where(CandidateResume.message_id == message_id).values(is_finalist=is_finalist))
        await session.commit()
        
async def update_candidate_wl_path(message_id: int, wl_path: str):
    async with AsyncSessionLocal() as session:
        await session.execute(update(CandidateResume).where(CandidateResume.message_id == message_id).values(wl_path=wl_path))
        await session.commit()

async def update_candidate_is_utochnenie(message_id: int, is_utochnenie: bool):
    async with AsyncSessionLocal() as session:
        await session.execute(update(CandidateResume).where(CandidateResume.message_id == message_id).values(is_utochnenie=is_utochnenie))
        await session.commit()

async def update_candidate_mail(message_id: int, candidate_mail: str):
    async with AsyncSessionLocal() as session:
        await session.execute(update(CandidateResume).where(CandidateResume.message_id == message_id).values(candidate_mail=candidate_mail))
        await session.commit()

async def update_message_id(message_id: int, new_message_id: int):
    async with AsyncSessionLocal() as session:
        await session.execute(update(CandidateResume).where(CandidateResume.message_id == message_id).values(message_id=new_message_id))
        await session.commit()

#
#Контакты
#

async def add_contact(message_id: int, candidate_fullname: str, contact_tg: str = None, contact_email: str = None, contact_phone: str = None):
    async with AsyncSessionLocal() as session:
       
        contact = Contact(message_id=message_id, candidate_fullname=candidate_fullname, contact_tg=contact_tg, contact_email=contact_email, contact_phone=contact_phone)
        session.add(contact)
        await session.commit()

async def get_contact(message_id: int):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Contact).where(Contact.message_id == message_id)
        )
        return result.scalar_one_or_none()

async def update_contact(message_id: int, contact_tg: str = None, contact_email: str = None, contact_phone: str = None):
    async with AsyncSessionLocal() as session:
        # Обновляем только те поля, которые переданы (не None)
        update_values = {}
        if contact_tg is not None:
            update_values['contact_tg'] = contact_tg
        if contact_email is not None:
            update_values['contact_email'] = contact_email
        if contact_phone is not None:
            update_values['contact_phone'] = contact_phone
        
        if update_values:  # Обновляем только если есть что обновлять
            await session.execute(update(Contact).where(Contact.message_id == message_id).values(**update_values))
            await session.commit()

async def update_contact_message_id(message_id: int, new_message_id: int):
    async with AsyncSessionLocal() as session:
        await session.execute(update(Contact).where(Contact.message_id == message_id).values(message_id=new_message_id))
        await session.commit()

#=====================================  
#Вакансии
#=====================================  

async def add_vacancy_thread(thread_id: int, chat_id: int, vacancy_text: str, vacancy_id: int):
    tread_chat_id = str(chat_id).replace('-100', '')
    tread_chat_id = f"{tread_chat_id}_{thread_id}"
    async with AsyncSessionLocal() as session:
        vacancy_thread = VacancyThread(thread_chat_id=tread_chat_id, vacancy_text=vacancy_text, vacancy_id=vacancy_id)
        session.add(vacancy_thread)
        await session.commit()

async def get_vacancy_thread(thread_id: int, chat_id: int):
    tread_chat_id = str(chat_id).replace('-100', '')
    tread_chat_id = f"{tread_chat_id}_{thread_id}"
    print(tread_chat_id)
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(VacancyThread).where(VacancyThread.thread_chat_id == tread_chat_id)
        )
        return result.scalar_one_or_none()

#=====================================  
#Привязка к мессенджерам
#=====================================

async def get_user_with_privyazka(user_name_tg: str):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(PrivyazanieEmail).where(PrivyazanieEmail.user_name_tg == user_name_tg)
        )
        res = result.scalar_one_or_none()
        if res:
            return res
        result = await session.execute(
            select(PrivyazanieTelegram).where(PrivyazanieTelegram.user_name_tg == user_name_tg)
        )
        res = result.scalar_one_or_none()
        return res


async def add_email(user_name_tg: str, user_email: str, password: str):
    async with AsyncSessionLocal() as session:
        try:
            # Проверяем, есть ли уже запись
            res = await session.execute(
                select(PrivyazanieEmail).where(
                    PrivyazanieEmail.user_name_tg == user_name_tg
                )
            )
            record = res.scalar_one_or_none()

            if record:
                # Обновляем существующую запись
                await session.execute(
                    update(PrivyazanieEmail)
                    .where(PrivyazanieEmail.user_name_tg == user_name_tg)
                    .values(user_email=user_email, email_password=password)
                )
                print(f"♻️ Обновлена запись PrivyazanieEmail для {user_name_tg}")
            else:
                # Создаём новую запись
                new_email = PrivyazanieEmail(
                    user_name_tg=user_name_tg,
                    user_email=user_email,
                    email_password=password,
                )
                session.add(new_email)
                print(f"✅ Добавлена новая запись PrivyazanieEmail для {user_name_tg}")

            await session.commit()

        except Exception as e:
            await session.rollback()
            print(f"❌ Ошибка при добавлении Email: {e}")


async def add_session_tg(user_name_tg: str, api_id: str, api_hash: str):
    async with AsyncSessionLocal() as session:
        try:
            # 1️⃣ Проверяем, есть ли запись
            res = await session.execute(
                select(PrivyazanieTelegram).where(PrivyazanieTelegram.user_name_tg == user_name_tg)
            )
            record = res.scalar_one_or_none()

            if record:
                # 2️⃣ Обновляем существующую запись
                await session.execute(
                    update(PrivyazanieTelegram)
                    .where(PrivyazanieTelegram.user_name_tg == user_name_tg)
                    .values(api_id=api_id, api_hash=api_hash)
                )
                print(f"♻️ Обновлена запись PrivyazanieTelegram для {user_name_tg}")

            else:
                # 3️⃣ Создаём новую запись
                new_record = PrivyazanieTelegram(
                    user_name_tg=user_name_tg,
                    api_id=api_id,
                    api_hash=api_hash,
                )
                session.add(new_record)
                print(f"✅ Добавлена новая запись PrivyazanieTelegram для {user_name_tg}")

            # 4️⃣ Коммитим изменения
            await session.commit()

        except Exception as e:
            await session.rollback()
            print(f"❌ Ошибка при добавлении Telegram: {e}")

async def get_tg_user(user_name_tg: str):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(PrivyazanieTelegram).where(PrivyazanieTelegram.user_name_tg == user_name_tg)
        )
        return result.scalar_one_or_none()

async def get_email_user(user_name_tg: str):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(PrivyazanieEmail).where(PrivyazanieEmail.user_name_tg == user_name_tg)
        )
        return result.scalar_one_or_none()



async def remove_session_tg(user_name_tg: str):
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(PrivyazanieTelegram).where(PrivyazanieTelegram.user_name_tg == user_name_tg)
            )
            record = result.scalar_one_or_none()
            if record:
                await session.delete(record)
                await session.commit()
                print(f"🧹 Удалена запись PrivyazanieTelegram для {user_name_tg}")
            else:
                print(f"❌ Запись PrivyazanieTelegram для {user_name_tg} не найдена")
        except Exception as e:
            await session.rollback()
            print(f"❌ Ошибка при удалении Telegram: {e}")

async def remove_session_email(user_name_tg: str):
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(PrivyazanieEmail).where(PrivyazanieEmail.user_name_tg == user_name_tg)
            )
            record = result.scalar_one_or_none()
            if record:
                await session.delete(record)
                
                await session.commit()
                
                print(f"🧹 Удалена запись PrivyazanieEmail для {user_name_tg}")
            else:
                print(f"❌ Запись PrivyazanieEmail для {user_name_tg} не найдена")
        except Exception as e:
            await session.rollback()
            print(f"❌ Ошибка при удалении Email: {e}")


#===========================================
#Работа с таблицей recruter_group
#===========================================

async def add_recruter_group(recruter_user_name: str, group_id: int):
    async with AsyncSessionLocal() as session:
        try:
            new_record = RecruterGroup(recruter_user_name=recruter_user_name, group_id=group_id)
            session.add(new_record)
            await session.commit()
            print(f"✅ Добавлена новая запись RecruterGroup для {recruter_user_name}")
        except Exception as e:
            await session.rollback()
            print(f"❌ Ошибка при добавлении RecruterGroup: {e}")

async def get_recruter_group(recruter_user_name: str):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(RecruterGroup).where(RecruterGroup.recruter_user_name == recruter_user_name)
        )
        return result.scalar_one_or_none()


#===========================================
#Работа с таблицей actual_vacancy
#===========================================

async def add_actual_vacancy(vacancy_id: int, title: str, message_id: int, user_name_tg: str):
    async with AsyncSessionLocal() as session:
        try:
            res = await session.execute(
                select(ActualVacancy).where(ActualVacancy.vacancy_id == vacancy_id)
            )
            record = res.scalar_one_or_none()
            if record:
                await session.delete(record)
                await session.commit()
                print(f"🧹 Удалена запись ActualVacancy для {vacancy_id}")
                
            new_record = ActualVacancy(vacancy_id=vacancy_id, title=title, message_id=message_id, user_name_tg=user_name_tg)
            session.add(new_record)
            await session.commit()
            print(f"✅ Добавлена новая запись ActualVacancy для {vacancy_id}")
        except Exception as e:
            await session.rollback()
            print(f"❌ Ошибка при добавлении ActualVacancy: {e}")

from telethon import TelegramClient
from aiogram import Bot


async def update_actual_vacancy(bot: Bot, client: TelegramClient):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ActualVacancy.user_name_tg)
        )
        res_one = result.all()
        if res_one:
            for (user_name_tg,) in res_one:
                print(user_name_tg)
                print(type(user_name_tg))
                res = await session.execute(
                    select(ActualVacancy.vacancy_id, ActualVacancy.title, ActualVacancy.message_id)
                    .where(ActualVacancy.user_name_tg == user_name_tg)
                )
                res = res.all()
                if res:
                    # Удаляем старые сообщения этого пользователя
                    async for msg in client.iter_messages(-1002658129391, reply_to=3388):
                        
                        if msg.id == 3388:
                            break
                        if user_name_tg in msg.text:    
                            try:
                                await bot.delete_message(
                                    chat_id=-1002658129391,
                                    message_id=msg.id
                                )
                            except Exception as e:
                                print(f"Ошибка при удалении сообщения {msg.id}: {e}")

                    text = f'Вакансии рекрутера {user_name_tg}:\n'
                    for row in res:
                        vac_id = row[0]
                        title = row[1]
                        message_id = row[2]
                        url = f"https://t.me/omega_vacancy_bot?start={message_id}_{vac_id}"
                        id_url = f"<a href='{url}'>{vac_id}</a>"
                        mess_url = f"https://t.me/c/2658129391/{message_id}"
                        title_url = f"<a href='{mess_url}'>{title}</a>"
                        
                        text += f"🆔{id_url} 🥇{title_url}\n"
                        
                    await bot.send_message(
                            chat_id=-1002658129391,
                            text=text,
                            message_thread_id=3388,
                            parse_mode="HTML",
                            disable_web_page_preview=True,
                            disable_notification=True
                        )
        

async def remove_actual_vacancy(vacancy_id: int, bot: Bot, client: TelegramClient):
    async with AsyncSessionLocal() as session:
        try:
            record = await session.execute(
                select(ActualVacancy).where(ActualVacancy.vacancy_id == vacancy_id)
            )
            record = record.scalar_one_or_none()
            if record:
                await session.delete(record)
                await session.commit()
                
                await update_actual_vacancy(bot, client)

                
        except Exception as e:
            await session.rollback()
            print(f"❌ Ошибка при удалении ActualVacancy: {e}")
    