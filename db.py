import os
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, select, Column, BigInteger

DATABASE_URL = "sqlite+aiosqlite:///channels.db"
async_engine = create_async_engine(DATABASE_URL, echo=False)

AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

class Base(DeclarativeBase):
    pass

class LastSequenceNumber(Base):
    __tablename__ = "last_sequence_number"
    id = Column(Integer, primary_key=True, default=1)  # всегда одна запись с id=1
    last_number = Column(Integer, default=0)


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


class MessageMapping(Base):
    __tablename__ = "message_mapping"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    src_chat_id = Column(BigInteger, index=True)
    src_msg_id = Column(BigInteger, index=True)
    dst_chat_id = Column(BigInteger, index=True)
    dst_msg_id = Column(BigInteger, index=True)

async def init_db():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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








async def add_message_mapping(session: AsyncSession, src_chat_id: int, src_msg_id: int, dst_chat_id: int, dst_msg_id: int):
    mapping = MessageMapping(
        src_chat_id=src_chat_id,
        src_msg_id=src_msg_id,
        dst_chat_id=dst_chat_id,
        dst_msg_id=dst_msg_id
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