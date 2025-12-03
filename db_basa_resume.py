import re
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy import Integer, String, Column, Boolean, ForeignKey, DateTime
from datetime import datetime
from sqlalchemy import select, insert, update, delete,union
from utils import to_csv

# === Ваши MAP'ы ===
from maps_for_gpt import (
    LANG_MAP, ROLES_MAP, GRADE_MAP, PROGRAM_LANG_MAP, FRAMEWORKS_MAP,
    TECH_MAP, PRODUCT_INDUSTRIES_MAP, PORTFOLIO_MAP, WORK_TIME_MAP,
    WORK_FORM_MAP, CONTACTS_MAP, AVAILABILITY_MAP
)

DATABASE_URL = "postgresql+asyncpg://postgres:123546@localhost:5432/basa_resume"

async_engine_basa = create_async_engine(
    DATABASE_URL,
    echo=False,
)

AsyncSessionLocal_basa = sessionmaker(
    bind=async_engine_basa,
    class_=AsyncSession,
    expire_on_commit=False,
)

class Base_basa(DeclarativeBase):
    pass

# ---------- нормализация имён колонок ----------


def add_column_safe(model_cls: type, raw_key: str, column: Column) -> None:
    """Добавляет колонку, избегая коллизий по имени."""
    
    name = raw_key
    i = 1
    while hasattr(model_cls, name):
        name = f"{raw_key}_{i}"
        i += 1
    setattr(model_cls, name, column)

# ---------- Основная таблица кандидатов ----------
from sqlalchemy.orm import sessionmaker, DeclarativeBase, relationship, selectinload   # ← добавили relationship
from sqlalchemy import Integer, String, Column, Boolean, ForeignKey, DateTime, UniqueConstraint

# ...

class Candidates(Base_basa):
    __tablename__ = 'candidates'
    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(String, unique=True, nullable=False, index=True)
    surname_ru = Column(String, nullable=True)
    surname_en = Column(String, nullable=True)
    name_ru = Column(String, nullable=True)
    name_en = Column(String, nullable=True)
    patronymic_ru = Column(String, nullable=True)
    patronymic_en = Column(String, nullable=True)
    location_ru = Column(String, nullable=True)
    location_en = Column(String, nullable=True)
    city_ru = Column(String, nullable=True)
    city_en = Column(String, nullable=True)
    total_experience = Column(String, nullable=True)
    special_experience = Column(String, nullable=True)
    date_of_exit = Column(String, nullable=True)
    url_for_origin_resume = Column(String, nullable=True)
    url_for_form_res_ru = Column(String, nullable=True)
    url_for_form_res_en = Column(String, nullable=True)
    recruter_username = Column(String, nullable=True)
    date_add_recruiter = Column(DateTime(timezone=True), nullable=True)
    date_add_admin = Column(DateTime(timezone=True), nullable=True)

    # --- one-to-one связи на все дочерние таблицы
    salary = relationship("CandidateSalary", back_populates="candidate",
                          uselist=False, cascade="all, delete-orphan", passive_deletes=True, lazy="selectin")
    roles = relationship("CandidateRoles", back_populates="candidate",
                         uselist=False, cascade="all, delete-orphan", passive_deletes=True, lazy="selectin")
    grades = relationship("CandidateGrades", back_populates="candidate",
                          uselist=False, cascade="all, delete-orphan", passive_deletes=True, lazy="selectin")
    programming_languages_rel = relationship("CandidateProgrammingLanguages", back_populates="candidate",
                         uselist=False, cascade="all, delete-orphan", passive_deletes=True, lazy="selectin")
    frameworks_rel = relationship("CandidateFrameworks", back_populates="candidate",
                         uselist=False, cascade="all, delete-orphan", passive_deletes=True, lazy="selectin")
    technologies_rel = relationship("CandidateTechnologies", back_populates="candidate",
                         uselist=False, cascade="all, delete-orphan", passive_deletes=True, lazy="selectin")
    industries_rel = relationship("CandidateIndustries", back_populates="candidate",
                         uselist=False, cascade="all, delete-orphan", passive_deletes=True, lazy="selectin")
    contacts_rel = relationship("CandidateContacts", back_populates="candidate",
                         uselist=False, cascade="all, delete-orphan", passive_deletes=True, lazy="selectin")
    languages_rel = relationship("CandidateLanguages", back_populates="candidate",
                         uselist=False, cascade="all, delete-orphan", passive_deletes=True, lazy="selectin")
    portfolio_rel = relationship("CandidatePortfolio", back_populates="candidate",
                         uselist=False, cascade="all, delete-orphan", passive_deletes=True, lazy="selectin")
    work_time = relationship("CandidateWorkTime", back_populates="candidate",
                         uselist=False, cascade="all, delete-orphan", passive_deletes=True, lazy="selectin")
    work_form = relationship("CandidateWorkForm", back_populates="candidate",
                         uselist=False, cascade="all, delete-orphan", passive_deletes=True, lazy="selectin")
    availability = relationship("CandidateAvailability", back_populates="candidate",
                         uselist=False, cascade="all, delete-orphan", passive_deletes=True, lazy="selectin")
    


class CandidateSalary(Base_basa):
    __tablename__ = 'candidate_salary'
    id = Column(Integer, primary_key=True)
    candidate_id = Column(String, ForeignKey('candidates.candidate_id', ondelete="CASCADE"),
                          nullable=False, unique=True, index=True)
    salary_expectations = Column(String, nullable=True)
    rate_for_client_ru_contract = Column(String, nullable=True)
    rate_for_client_ru_ip = Column(String, nullable=True)
    rate_for_client_ru_sam = Column(String, nullable=True)
    rate_for_client_en_contract = Column(String, nullable=True)
    rate_for_client_en_ip = Column(String, nullable=True)
    rate_for_client_en_sam = Column(String, nullable=True)

    candidate = relationship("Candidates", back_populates="salary", uselist=False)
    __table_args__ = (UniqueConstraint('candidate_id', name='uq_candidate_salary_candidate_id'),)


class CandidateRoles(Base_basa):
    __tablename__ = 'candidate_roles'
    id = Column(Integer, primary_key=True)
    candidate_id = Column(String, ForeignKey('candidates.candidate_id', ondelete="CASCADE"),
                          nullable=False, unique=True, index=True)
    candidate = relationship("Candidates", back_populates="roles", uselist=False)

for raw_key in ROLES_MAP.keys():
    add_column_safe(CandidateRoles, raw_key, Column(Boolean, nullable=False, default=False))


class CandidateGrades(Base_basa):
    __tablename__ = 'candidate_grades'
    id = Column(Integer, primary_key=True)
    candidate_id = Column(String, ForeignKey('candidates.candidate_id', ondelete="CASCADE"),
                          nullable=False, unique=True, index=True)
    candidate = relationship("Candidates", back_populates="grades", uselist=False)

for raw_key in GRADE_MAP.keys():
    add_column_safe(CandidateGrades, raw_key, Column(Boolean, nullable=False, default=False))


class CandidateProgrammingLanguages(Base_basa):
    __tablename__ = 'candidate_programming_languages'
    id = Column(Integer, primary_key=True)
    candidate_id = Column(String, ForeignKey('candidates.candidate_id', ondelete="CASCADE"),
                          nullable=False, unique=True, index=True)
    candidate = relationship("Candidates", back_populates="programming_languages_rel", uselist=False)

for raw_key in PROGRAM_LANG_MAP.keys():
    add_column_safe(CandidateProgrammingLanguages, raw_key, Column(Boolean, nullable=False, default=False))


class CandidateFrameworks(Base_basa):
    __tablename__ = 'candidate_frameworks'
    id = Column(Integer, primary_key=True)
    candidate_id = Column(String, ForeignKey('candidates.candidate_id', ondelete="CASCADE"),
                          nullable=False, unique=True, index=True)
    candidate = relationship("Candidates", back_populates="frameworks_rel", uselist=False)

for raw_key in FRAMEWORKS_MAP.keys():
    add_column_safe(CandidateFrameworks, raw_key, Column(Boolean, nullable=False, default=False))


class CandidateTechnologies(Base_basa):
    __tablename__ = 'candidate_technologies'
    id = Column(Integer, primary_key=True)
    candidate_id = Column(String, ForeignKey('candidates.candidate_id', ondelete="CASCADE"),
                          nullable=False, unique=True, index=True)
    candidate = relationship("Candidates", back_populates="technologies_rel", uselist=False)

for raw_key in TECH_MAP.keys():
    add_column_safe(CandidateTechnologies, raw_key, Column(Boolean, nullable=False, default=False))


class CandidateIndustries(Base_basa):
    __tablename__ = 'candidate_industries'
    id = Column(Integer, primary_key=True)
    candidate_id = Column(String, ForeignKey('candidates.candidate_id', ondelete="CASCADE"),
                          nullable=False, unique=True, index=True)
    candidate = relationship("Candidates", back_populates="industries_rel", uselist=False)

for raw_key in PRODUCT_INDUSTRIES_MAP.keys():
    add_column_safe(CandidateIndustries, raw_key, Column(Boolean, nullable=False, default=False))


class CandidateContacts(Base_basa):
    __tablename__ = 'candidate_contacts'
    id = Column(Integer, primary_key=True)
    candidate_id = Column(String, ForeignKey('candidates.candidate_id', ondelete="CASCADE"),
                          nullable=False, unique=True, index=True)
    candidate = relationship("Candidates", back_populates="contacts_rel", uselist=False)

for raw_key in CONTACTS_MAP.keys():
    add_column_safe(CandidateContacts, raw_key, Column(String, nullable=True))


class CandidateLanguages(Base_basa):
    __tablename__ = 'candidate_languages'
    id = Column(Integer, primary_key=True)
    candidate_id = Column(String, ForeignKey('candidates.candidate_id', ondelete="CASCADE"),
                          nullable=False, unique=True, index=True)
    candidate = relationship("Candidates", back_populates="languages_rel", uselist=False)

for raw_key in LANG_MAP.keys():
    add_column_safe(CandidateLanguages, raw_key, Column(String, nullable=True))


class CandidatePortfolio(Base_basa):
    __tablename__ = 'candidate_portfolio'
    id = Column(Integer, primary_key=True)
    candidate_id = Column(String, ForeignKey('candidates.candidate_id', ondelete="CASCADE"),
                          nullable=False, unique=True, index=True)
    candidate = relationship("Candidates", back_populates="portfolio_rel", uselist=False)

for raw_key in PORTFOLIO_MAP.keys():
    add_column_safe(CandidatePortfolio, raw_key, Column(String, nullable=True))


class CandidateWorkTime(Base_basa):
    __tablename__ = 'candidate_work_time'
    id = Column(Integer, primary_key=True)
    candidate_id = Column(String, ForeignKey('candidates.candidate_id', ondelete="CASCADE"),
                          nullable=False, unique=True, index=True)
    candidate = relationship("Candidates", back_populates="work_time", uselist=False)

for raw_key in WORK_TIME_MAP.keys():
    add_column_safe(CandidateWorkTime, raw_key, Column(Boolean, nullable=False, default=False))


class CandidateWorkForm(Base_basa):
    __tablename__ = 'candidate_work_form'
    id = Column(Integer, primary_key=True)
    candidate_id = Column(String, ForeignKey('candidates.candidate_id', ondelete="CASCADE"),
                          nullable=False, unique=True, index=True)
    candidate = relationship("Candidates", back_populates="work_form", uselist=False)

for raw_key in WORK_FORM_MAP.keys():
    add_column_safe(CandidateWorkForm, raw_key, Column(Boolean, nullable=False, default=False))

class CandidateAvailability(Base_basa):
    __tablename__ = 'candidate_availability'
    id = Column(Integer, primary_key=True)
    candidate_id = Column(String, ForeignKey('candidates.candidate_id', ondelete="CASCADE"),
                          nullable=False, unique=True, index=True)
    candidate = relationship("Candidates", back_populates="availability", uselist=False)
for raw_key in AVAILABILITY_MAP.keys():
        low = raw_key.lower()
        if "date" in low:
            add_column_safe(CandidateAvailability, "available_from_date", Column(String, nullable=True))
        else:
            add_column_safe(CandidateAvailability, raw_key, Column(Boolean, nullable=False, default=False))


# ---------- инициализация БД ----------
async def init_db_basa_resume():
    async with async_engine_basa.begin() as conn:
        #await conn.run_sync(Base_basa.metadata.drop_all)
        await conn.run_sync(Base_basa.metadata.create_all)
    print("✅ База данных инициализирована")

# Не вызываем init_db_basa_resume() при импорте модуля!
# Это создаёт конфликты event loop.
# Вызывайте явно: await init_db_basa_resume() когда нужно.



# ---------- запись в БД ----------
import re
from typing import Dict, Any
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError

# === утилиты ===

def to_snake(name: str) -> str:
    """'Python Developer' -> 'python_developer', 'X (Y)' -> 'x_y'"""
    name = name.strip()
    name = re.sub(r'[\(\)\[\]\./&,+\-]+', ' ', name)   # убрать скобки/точки/знаки
    name = re.sub(r'\s+', '_', name)                   # пробелы -> _
    return name.lower()

def normalize_value(v: Any) -> Any:
    """'' -> None, остальное без изменений"""
    if isinstance(v, str) and v.strip() == "":
        return None
    return v

# === запись пачки строк по именам таблиц ===

async def write_to_db_basa_resume(named_rows: Dict[str, Dict[str, Any]]):
    """
    named_rows: {"candidate_roles": {...}, "candidate_frameworks": {...}, ...}
    """
    async with AsyncSessionLocal_basa() as conn:  # транзакция
        async with conn.begin():
            for table_name, row in named_rows.items():
                table = Base_basa.metadata.tables.get(table_name)
                print(table)
                if table is None:
                    raise ValueError(f"Таблица '{table_name}' не найдена в metadata")

                valid_cols = {c.name for c in table.columns}
                payload = {k: normalize_value(v) for k, v in row.items() if k in valid_cols}

                try:
                    await conn.execute(insert(table).values(**payload))
                except IntegrityError as e:
                    raise
    print("✅ Записали секции кандидата в БД")

# === построение строк для таблиц из вашего JSON ===

SECTION_TO_TABLE = {
    "roles": "candidate_roles",
    "grades": "candidate_grades",
    "programming_langs": "candidate_programming_languages",
    "frameworks": "candidate_frameworks",
    "technologies": "candidate_technologies",
    "project_industries": "candidate_industries",
    "portfolio": "candidate_portfolio",
    "work_time": "candidate_work_time",
    "work_form": "candidate_work_form",
    "availability": "candidate_availability",
    "contacts": "candidate_contacts",
    "languages": "candidate_languages",
}

def build_rows_from_extracted(extracted: Dict[str, Any], candidate_id: int) -> Dict[str, Dict[str, Any]]:
    """
    На вход — ваш огромный словарь (как в сообщении).
    На выход — словарь {table_name: row_dict} готовый к вставке.
    """
    named_rows: Dict[str, Dict[str, Any]] = {}

    for section_key, table_name in SECTION_TO_TABLE.items():
        section = extracted.get(section_key)
        if not isinstance(section, dict):
            continue

        row: Dict[str, Any] = {"candidate_id": candidate_id}

        for k, v in section.items():
            col = to_snake(k)  # имя столбца
            row[col] = normalize_value(v)

        named_rows[table_name] = row

    return named_rows

import random
import string



# Новый helper: создаём кандидата и записываем секции с корректным candidate_id
async def create_candidate_and_write(section_rows: Dict[str, Dict[str, Any]], candidate_record):
    """
    section_rows: {"roles": {...}, ...} уже в формате булевых/строчных значений
    candidate_record: запись Candidates с заполненным candidate_id
    Использует candidate_record.candidate_id как candidate_id для всех дочерних таблиц согласно SECTION_TO_TABLE.
    """
    async with AsyncSessionLocal_basa() as conn:
        async with conn.begin():
            candidate_id = candidate_record.candidate_id

            rows = build_rows_from_extracted(section_rows, candidate_id)

            for table_name, row in rows.items():
                table = Base_basa.metadata.tables.get(table_name)
                if table is None:
                    raise ValueError(f"Таблица '{table_name}' не найдена в metadata")

                valid_cols = {c.name for c in table.columns}
                payload = {k: normalize_value(v) for k, v in row.items() if k in valid_cols}
                await conn.execute(insert(table).values(**payload))



async def add_to_candidate_table(candidate_id :str , name_ru :str , name_en :str , surname_ru :str , surname_en :str , patronymic_ru :str , patronymic_en :str , location_ru :str , location_en :str , city_ru :str , city_en :str , total_experience :str , special_experience :str , date_of_exit :str , url_for_origin_resume :str , url_for_form_res_ru :str , url_for_form_res_en :str , recruter_username :str , date_of_add , date_add_admin):
    async with AsyncSessionLocal_basa() as session:
        res = await session.execute(
            select(Candidates.name_ru, Candidates.surname_ru).where((Candidates.name_ru == name_ru) & (Candidates.surname_ru == surname_ru) & (Candidates.recruter_username == recruter_username))
        )
        if res.scalar_one_or_none() is not None:
            print('Такой кандидат уже есть')
            return None
        res2 = await session.execute(
            select(Candidates.name_en, Candidates.surname_en).where((Candidates.name_en == name_en) & (Candidates.surname_en == surname_en) & (Candidates.recruter_username == recruter_username))
        )
        if res2.scalar_one_or_none() is not None:
            print('Такой кандидат уже есть')
            return None
        if not name_ru or not surname_ru:
            print('Нет имени')
            return None
            
        new_record = Candidates(
            candidate_id = candidate_id,
            name_ru = name_ru,
            name_en = name_en,
            surname_ru = surname_ru,
            surname_en = surname_en,
            patronymic_ru = patronymic_ru,
            patronymic_en = patronymic_en,
            location_ru = location_ru,
            location_en = location_en,
            city_ru = city_ru,
            city_en = city_en,
            total_experience = total_experience,
            special_experience = special_experience,
            date_of_exit = date_of_exit,
            url_for_origin_resume = url_for_origin_resume,
            url_for_form_res_ru = url_for_form_res_ru,
            url_for_form_res_en = url_for_form_res_en,
            recruter_username = recruter_username,
            date_add_recruiter = date_of_add,
            date_add_admin = date_add_admin
        )
        session.add(new_record)
        await session.commit()
        await session.refresh(new_record)  # Получаем id после commit
        return new_record


async def delete_candidate_by_id(candidate_id: str) -> bool:
    """
    Удаляет кандидата и все связанные записи по candidate_id
    
    Args:
        candidate_id: ID кандидата (например, "a_12345")
    
    Returns:
        True если запись удалена, False если кандидат не найден
    """
    async with AsyncSessionLocal_basa() as session:
        # Ищем кандидата по candidate_id
        result = await session.execute(
            select(Candidates).where(Candidates.candidate_id == candidate_id)
        )
        candidate = result.scalar_one_or_none()
        
        if candidate is None:
            return False
        
        # Удаляем кандидата (каскадно удалятся все связанные записи благодаря ondelete="CASCADE")
        await session.delete(candidate)
        await session.commit()
        return True


async def delete_all_candidates() -> int:
    """
    Удаляет всех кандидатов и все связанные записи
    
    Returns:
        Количество удаленных записей
    """
    async with AsyncSessionLocal_basa() as session:
        result = await session.execute(select(Candidates))
        candidates = result.scalars().all()
        count = len(candidates)
        
        for candidate in candidates:
            await session.delete(candidate)
        
        await session.commit()
        return count


# Функция для фильтрации полей (только True или непустые строки)
def filter_fields(obj):
            if obj is None:
                return {}
            
            filtered = {}
            for column in obj.__table__.columns:
                if column.name in ['id', 'candidate_id']:  # Пропускаем служебные поля
                    continue
                
                value = getattr(obj, column.name, None)
                
                # Для булевых полей - только True
                if isinstance(value, bool):
                    if value:
                        filtered[column.name] = value
                # Для строк - только непустые
                elif isinstance(value, str):
                    if value and value.strip():
                        filtered[column.name] = value
                # Для остальных типов - если не None
                elif value is not None:
                    filtered[column.name] = value
            
            return filtered



async def get_candidate_by_username( recruter_username: str) -> dict | None:
    """
    Получает кандидата по ID со всеми связанными данными.
    Возвращает словарь с основной информацией и отфильтрованными данными (только True/непустые значения).
    
    Args:
        recruter_username: имя рекрутера
    
    Returns:
        Словарь с данными кандидата или None если не найден
    """
    async with AsyncSessionLocal_basa() as session:
        # Загружаем кандидата со всеми связанными таблицами
        result = await session.execute(
            select(Candidates)
            .where(Candidates.recruter_username == recruter_username)
            .options(
                selectinload(Candidates.salary),
                selectinload(Candidates.roles),
                selectinload(Candidates.grades),
                selectinload(Candidates.programming_languages_rel),
                selectinload(Candidates.frameworks_rel),
                selectinload(Candidates.technologies_rel),
                selectinload(Candidates.industries_rel),
                selectinload(Candidates.contacts_rel),
                selectinload(Candidates.languages_rel),
                selectinload(Candidates.portfolio_rel),
                selectinload(Candidates.work_time),
                selectinload(Candidates.work_form),
                selectinload(Candidates.availability)
            )
        )
        candidate = result.scalars().all()
        
        # if candidate is None:
        #     return None
        def csv_from_dict(d) -> str:
            d = d or {}
            return ", ".join(
                str(k).strip().capitalize()
                for k, v in d.items()
                if v and str(k).strip()
            )

        result_str = ""
        for can in candidate:
            

            prog_lang = csv_from_dict(filter_fields(can.programming_languages_rel))
            frameworks = csv_from_dict(filter_fields(can.frameworks_rel))
            tech = csv_from_dict(filter_fields(can.technologies_rel))
            #grade = csv_from_dict(filter_fields(can.grades))
            tech_skills = ", ".join(s for s in [prog_lang, frameworks, tech] if s)
            candidate_id = can.candidate_id
            #total_experience = can.total_experience
            
            #if total_experience:
                
                #total_experience = float(total_experience)
                #if total_experience == 1:
                    # kolvo_let = 'год'
            #     elif total_experience < 5:
            #         kolvo_let = 'года'
            #     else:
            #         kolvo_let = 'лет'
            # else:
            #     total_experience = 'Не указан'
            #     kolvo_let = ""

            tech_skills = f'Технические навыки: {tech_skills}\n'

            #result_str += "-"*20 + "\n"
            result_str += f'ФИО: {can.name_ru} {can.surname_ru} {can.patronymic_ru if can.patronymic_ru else ""}\n'
            #result_str += f'Локация: {can.location_ru if can.location_ru else ""} {can.city_ru if can.city_ru else ""}\n'
            #result_str += f'Опыт работы: {total_experience} {kolvo_let}\n'
            result_str += tech_skills
            result_str += f'ID: {candidate_id}\n\n'
            #result_str += f'Грейд: {grade}\n'
            #result_str += "-"*20 + "\n"
            
        return result_str

# import asyncio
# can = asyncio.run(get_candidate_by_username("kupitmancik"))
# print(can)



async def get_orig_urls_for_candidate_ids(candidate_ids: list) -> dict | None:
    async with AsyncSessionLocal_basa() as session:
        result = await session.execute(
            select(Candidates.url_for_origin_resume)
            .where(Candidates.candidate_id.in_(candidate_ids))
        )
        candidate = result.scalars().all()
        
        return candidate
                                            