import os
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, select, Column, BigInteger, update 
from datetime import datetime, timedelta
import asyncio
from sqlalchemy import JSON
import json


DATABASE_URL = "sqlite+aiosqlite:///channels.db"
async_engine = create_async_engine(DATABASE_URL, echo=False)

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



class OtkonechenieResume(Base):
    __tablename__ = 'otkonechenie_resume'
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    message_text = Column(String, nullable=False)
    json_text = Column(String, nullable=False)
    message_time = Column(String, nullable=False)
    
class FinalResume(Base):
    __tablename__ = 'final_resume'
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    message_text = Column(String, nullable=False)
    json_text = Column(String, nullable=False)
    message_time = Column(String, nullable=False)


class UtochnenieResume(Base):
    __tablename__ = 'utochnenie_resume'
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    message_text = Column(String, nullable=False)
    json_text = Column(String, nullable=False)
    message_time = Column(String, nullable=False)
 
    
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
    


class SaveResumes(Base):
    __tablename__ = "save_resumes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    canditdate_name = Column(String, nullable=False)
    resume_text = Column(String, nullable=False)
    

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
                await session.refresh(channel)
                
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
            await session.refresh(filter)

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
            await session.refresh(filter)


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
    session: AsyncSession,
    src_chat_id: int,
    src_msg_id: int,
    dst_chat_id: int,
    dst_msg_id: int,
    deadline_date: str | None = None,
    deadline_time: str | None = None
):
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


async def get_all_message_mappings(session: AsyncSession):
    result = await session.execute(select(MessageMapping))
    return result.scalars().all()

async def remove_message_mapping(session: AsyncSession, src_chat_id: int, src_msg_id: int):
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
    
    
    
    
async def add_otkonechenie_resume(message_id: int, message_text: str, json_text: dict):
    """
    Добавляет или обновляет запись OtkonechenieResume.
    Если message_id уже существует — обновляет текст и JSON.
    """
    if isinstance(json_text, dict):
        json_text = json.dumps(json_text)

    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(OtkonechenieResume).where(OtkonechenieResume.message_id == message_id)
            )
            existing_record = result.scalar_one_or_none()

            if existing_record:
                existing_record.message_text = message_text
                existing_record.json_text = json_text
                existing_record.message_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
                print(f"♻️ Обновлена запись OtkonechenieResume с message_id={message_id}")
            else:
                new_record = OtkonechenieResume(
                    message_id=message_id,
                    message_text=message_text,
                    json_text=json_text,
                    message_time=datetime.now().strftime("%d.%m.%Y %H:%M:%S")
                )
                session.add(new_record)
                print(f"✅ Добавлена новая запись OtkonechenieResume с message_id={message_id}")

            await session.commit()

        except Exception as e:
            await session.rollback()
            print(f"❌ Ошибка при добавлении/обновлении OtkonechenieResume: {e}")


async def remove_old_otkonechenie_resumes(hours: int = 12):
    """
    Удаляет записи из таблицы otkonechenie_resume,
    у которых message_time старше N часов (по умолчанию 12).
    """
    async with AsyncSessionLocal() as session:  # type: AsyncSession
        try:
            # Определяем пороговую дату
            threshold_time = datetime.now() - timedelta(hours=hours)

            # Загружаем все записи
            result = await session.execute(select(OtkonechenieResume))
            records = result.scalars().all()

            deleted_count = 0

            for record in records:
                # message_time хранится в строке "ДД.ММ.ГГГГ ЧЧ:ММ:СС"
                try:
                    record_time = datetime.strptime(record.message_time, "%d.%m.%Y %H:%M:%S")
                    if record_time < threshold_time:
                        await session.delete(record)
                        deleted_count += 1
                except ValueError:
                    # если формат даты битый — пропускаем
                    continue

            await session.commit()

            print(f"🧹 Удалено {deleted_count} записей старше {hours} часов.")

        except Exception as e:
            await session.rollback()
            print(f"❌ Ошибка при удалении старых записей: {e}")

    
async def periodic_cleanup_task():
    while True:
        try:
            await remove_old_otkonechenie_resumes(hours=12)
            await remove_old_utochnenie_resumes(hours=12)
            await remove_old_final_resumes(hours=12)
        except Exception as e:
            print(f"❌ Ошибка при автоочистке: {e}")
        await asyncio.sleep(60 * 60) 
        
        
async def get_otkolenie_resume(message_id: int):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(OtkonechenieResume).where(OtkonechenieResume.message_id == message_id))
        return result.scalar_one_or_none()
    
# ===============================================================
#  FINAL RESUME (ФИНАЛИСТЫ)
# ===============================================================

async def add_final_resume(message_id: int, message_text: str, json_text: dict):
    """
    Добавляет или обновляет запись FinalResume.
    Если message_id уже существует — обновляет текст и JSON.
    """
    if isinstance(json_text, dict):
        json_text = json.dumps(json_text)
        
        
    async with AsyncSessionLocal() as session:
        try:
            # Проверяем, есть ли уже запись с таким message_id
            result = await session.execute(
                select(FinalResume).where(FinalResume.message_id == message_id)
            )
            existing_record = result.scalar_one_or_none()

            if existing_record:
                # Обновляем поля
                existing_record.message_text = message_text
                existing_record.json_text = json_text
                existing_record.message_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
                print(f"♻️ Обновлена запись FinalResume с message_id={message_id}")
            else:
                # Создаём новую запись
                new_record = FinalResume(
                    message_id=message_id,
                    message_text=message_text,
                    json_text=json_text,
                    message_time=datetime.now().strftime("%d.%m.%Y %H:%M:%S")
                )
                session.add(new_record)
                print(f"✅ Добавлена новая запись FinalResume с message_id={message_id}")

            await session.commit()

        except Exception as e:
            await session.rollback()
            print(f"❌ Ошибка при добавлении/обновлении FinalResume: {e}")



async def remove_old_final_resumes(hours: int = 12):
    """Удаляет финальные резюме старше N часов (по умолчанию 12)."""
    async with AsyncSessionLocal() as session:
        try:
            threshold_time = datetime.now() - timedelta(hours=hours)
            result = await session.execute(select(FinalResume))
            records = result.scalars().all()
            deleted_count = 0

            for record in records:
                try:
                    record_time = datetime.strptime(record.message_time, "%d.%m.%Y %H:%M:%S")
                    if record_time < threshold_time:
                        await session.delete(record)
                        deleted_count += 1
                except ValueError:
                    continue

            await session.commit()
            print(f"🧹 Удалено {deleted_count} финальных резюме старше {hours} часов.")

        except Exception as e:
            await session.rollback()
            print(f"❌ Ошибка при удалении финальных резюме: {e}")


async def get_final_resume(message_id: int):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(FinalResume).where(FinalResume.message_id == message_id)
        )
        return result.scalar_one_or_none()



# ===============================================================
#  UTOCHNENIE RESUME (ТРЕБУЮТ УТОЧНЕНИЙ)
# ===============================================================

async def add_utochnenie_resume(message_id: int, message_text: str, json_text: dict):
    """
    Добавляет или обновляет запись UtochnenieResume.
    Если message_id уже существует — обновляет текст и JSON.
    """
    if isinstance(json_text, dict):
        json_text = json.dumps(json_text)

    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(UtochnenieResume).where(UtochnenieResume.message_id == message_id)
            )
            existing_record = result.scalar_one_or_none()

            if existing_record:
                existing_record.message_text = message_text
                existing_record.json_text = json_text
                existing_record.message_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
                print(f"♻️ Обновлена запись UtochnenieResume с message_id={message_id}")
            else:
                new_record = UtochnenieResume(
                    message_id=message_id,
                    message_text=message_text,
                    json_text=json_text,
                    message_time=datetime.now().strftime("%d.%m.%Y %H:%M:%S")
                )
                session.add(new_record)
                print(f"✅ Добавлена новая запись UtochnenieResume с message_id={message_id}")

            await session.commit()

        except Exception as e:
            await session.rollback()
            print(f"❌ Ошибка при добавлении/обновлении UtochnenieResume: {e}")


async def remove_old_utochnenie_resumes(hours: int = 12):
    """Удаляет записи из таблицы utochnenie_resume, старше N часов."""
    async with AsyncSessionLocal() as session:
        try:
            threshold_time = datetime.now() - timedelta(hours=hours)
            result = await session.execute(select(UtochnenieResume))
            records = result.scalars().all()
            deleted_count = 0

            for record in records:
                try:
                    record_time = datetime.strptime(record.message_time, "%d.%m.%Y %H:%M:%S")
                    if record_time < threshold_time:
                        await session.delete(record)
                        deleted_count += 1
                except ValueError:
                    continue

            await session.commit()
            print(f"🧹 Удалено {deleted_count} уточняющих резюме старше {hours} часов.")

        except Exception as e:
            await session.rollback()
            print(f"❌ Ошибка при удалении уточняющих резюме: {e}")


async def get_utochnenie_resume(message_id: int):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UtochnenieResume).where(UtochnenieResume.message_id == message_id)
        )
        return result.scalar_one_or_none()    




# ===============================================================
#  SAVE RESUMES (СОХРАНЯЮТСЯ)
# ===============================================================


async def add_save_resume(canditdate_name: str, resume_text: str):
    async with AsyncSessionLocal() as session:
        try:
            resume = SaveResumes(
                canditdate_name=canditdate_name,
                resume_text=resume_text,
            )
            session.add(resume)
            await session.commit()
            await session.refresh(resume)
            
        except Exception as e:
            await session.rollback()
            print(f"❌ Ошибка при добавлении SaveResumes: {e}")


async def get_save_resume(canditdate_name: str):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(SaveResumes).where(SaveResumes.canditdate_name == canditdate_name)
        )
        return result.scalar_one_or_none()


async def remove_save_resume(canditdate_name: str):
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(SaveResumes).where(SaveResumes.canditdate_name == canditdate_name)
            )
            record = result.scalar_one_or_none()
            if record:
                await session.delete(record)
                await session.commit()
                print(f"🧹 Удалено резюме {canditdate_name} из таблицы save_resumes.")
            else:
                print(f"❌ Резюме {canditdate_name} не найдено в таблице save_resumes.")
        except Exception as e:
            await session.rollback()
            print(f"❌ Ошибка при удалении SaveResumes: {e}")

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