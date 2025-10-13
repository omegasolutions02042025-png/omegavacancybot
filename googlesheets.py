import asyncio
import os
import re
from typing import Optional, List, Dict, Any
import gspread
from google.oauth2.service_account import Credentials
from aiogram import Bot
from funcs import parse_cb_rf

# === Конфигурация ===
SERVICE_ACCOUNT_FILE = 'creds.json'
SPREADSHEET_ID = '1ApDxmH0BL4rbuKTni6cj-D_d0vJ5KG45sEQjOyXM3PY'
SHEET_NAME = 'Для Бота'
SHEET_URL = 'https://docs.google.com/spreadsheets/d/1ApDxmH0BL4rbuKTni6cj-D_d0vJ5KG45sEQjOyXM3PY/edit#gid=0'

# === Асинхронное подключение ===
def get_gspread_client():
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    return gspread.authorize(creds)

# ======================
# 🔹 1. Поиск ставки
# ======================
async def find_rate_in_sheet_gspread(search_value_usd: int) -> Optional[str]:
    """Асинхронно ищет ставку в Google Sheets и возвращает соответствующее значение."""
    if search_value_usd is None:
        return None

    def _sync_task():
        try:
            gc = get_gspread_client()
            sh = gc.open_by_key(SPREADSHEET_ID)
            ws = sh.worksheet(SHEET_NAME)

            # Выбор колонки в зависимости от диапазона
            j_column_values = ws.col_values(11 if search_value_usd <= 300 else 10)
            target_value = int(search_value_usd)
            closest_value = None
            min_diff = float("inf")

            for row_index, value in enumerate(j_column_values, start=1):
                if row_index == 1:
                    continue
                cell_text = str(value).strip().replace("\xa0", "").replace(" ", "").replace(",", "")
                try:
                    cell_number = int(float(cell_text)) if "." in cell_text else int(cell_text)
                except ValueError:
                    continue

                if cell_number == target_value:
                    row_values = ws.row_values(row_index)
                    if len(row_values) > 1 and row_values[1]:
                        return row_values[1]

                diff = abs(cell_number - target_value)
                if diff < min_diff:
                    min_diff = diff
                    closest_value = (row_index, cell_number)

            if closest_value:
                row_index, _ = closest_value
                row_values = ws.row_values(row_index)
                if len(row_values) > 1 and row_values[1]:
                    return row_values[1]

            return None
        except Exception as e:
            print(f"❌ Ошибка find_rate_in_sheet_gspread: {e}")
            return None

    return await asyncio.to_thread(_sync_task)

# ======================
# 🔹 2. Поиск и извлечение данных
# ======================
async def search_and_extract_values(
    search_column: str,
    search_value: float,
    extract_columns: List[str],
    worksheet_name: str = "Resume_Database"
) -> Optional[Dict[str, Any]]:
    """Асинхронно ищет значение и извлекает данные из указанных колонок."""
    
    def _sync_task():
        try:
            gc = get_gspread_client()
            spreadsheet = gc.open_by_url(SHEET_URL)
            ws = spreadsheet.worksheet(worksheet_name)
            all_values = ws.get_all_values()

            if not all_values:
                print("❌ Лист пуст")
                return None

            search_col_index = ord(search_column.upper()) - ord("A")
            search_range = list(range(int(search_value) - 20, int(search_value) + 21))

            target_row_index = None
            exact_match_row = None

            for row_index, row in enumerate(all_values):
                if row_index == 0:
                    continue
                if len(row) <= search_col_index:
                    continue

                cell_value = row[search_col_index]
                if not cell_value:
                    continue

                try:
                    cell_value = cell_value.strip().split(",")[0]
                    numeric_value = int(re.sub(r"[^\d]", "", cell_value))

                    if numeric_value == search_value:
                        exact_match_row = row_index
                        target_row_index = row_index
                        break

                    if numeric_value in search_range:
                        target_row_index = row_index
                        break
                except Exception:
                    continue

            if target_row_index is None:
                return None

            target_row = all_values[target_row_index]
            result = {"extracted_values": {}}

            for col_letter in extract_columns:
                col_index = ord(col_letter.upper()) - ord("A")
                if len(target_row) > col_index:
                    clean_value = target_row[col_index].replace("\xa0", "").strip()
                    rounded = (int(clean_value) // 1000) * 1000
                    clean_value = f"{rounded:,}".replace(",", " ")
                    result["extracted_values"][col_letter] = clean_value
                else:
                    result["extracted_values"][col_letter] = ""

            return result["extracted_values"]
        except Exception as e:
            print(f"❌ Ошибка search_and_extract_values: {e}")
            return None

    return await asyncio.to_thread(_sync_task)

# ======================
# 🔹 3. Заполнение колонки
# ======================
async def fill_column_with_sequential_numbers(
    column_letter: str,
    worksheet_name: str = "Свободные ресурсы на аутстафф",
    start_row: int = 2,
    value: int = 0,
    sheet_id: str = SPREADSHEET_ID,
) -> bool:
    """Асинхронно заполняет указанную колонку одним и тем же числом."""
    
    def _sync_task():
        try:
            gc = get_gspread_client()
            sh = gc.open_by_key(sheet_id)
            ws = sh.worksheet(worksheet_name)

            all_values = ws.get_all_values()
            last_row = len(all_values)
            if last_row < start_row:
                print(f"⚠️ В листе нет строк начиная с {start_row}")
                return False

            values = [[value] for _ in range(start_row, last_row + 1)]
            range_a1 = f"{column_letter}{start_row}:{column_letter}{last_row}"
            ws.update(range_a1, values)
            print(f"✅ Колонка {column_letter} заполнена ({worksheet_name})")
            return True
        except gspread.WorksheetNotFound:
            print(f"❌ Лист '{worksheet_name}' не найден в таблице {sheet_id}")
            return False
        except gspread.exceptions.APIError as e:
            # Развёрнутый текст API-ошибки
            print(f"❌ APIError fill_column_with_sequential_numbers: {e}")
            return False
        except Exception as e:
            print(f"❌ Ошибка fill_column_with_sequential_numbers: {e}")
            return False

    return await asyncio.to_thread(_sync_task)

# ======================
# 🔹 4. Обновление курсов валют
# ======================
async def update_currency_sheet(bot: Bot, ADMIN_ID: int):
    """Асинхронно обновляет курсы валют каждые 24 часа."""
    sheet_name_1 = 'Расчет ставки (штат) ЮЛ РФ'
    sheet_name_2 = 'Расчет ставки (ИП) ЮЛ РФ'
    sheet_id = '1vjHlEdWO-IkzU5urYrorb0FlwMS7TPfnBDSAhnSYp98'


    while True:
        curses = await asyncio.to_thread(parse_cb_rf)
        usd, eur, byn = curses["USD"], curses["EUR"], curses["BYN"]

        await fill_column_with_sequential_numbers("G", sheet_name_1, 2, usd, sheet_id)
        await asyncio.sleep(2)
        await fill_column_with_sequential_numbers("H", sheet_name_1, 2, eur, sheet_id)
        await asyncio.sleep(2)
        await fill_column_with_sequential_numbers("F", sheet_name_1, 2, byn, sheet_id)
        await asyncio.sleep(2)

        await fill_column_with_sequential_numbers("H", sheet_name_2, 2, usd, sheet_id)
        await asyncio.sleep(2)
        await fill_column_with_sequential_numbers("I", sheet_name_2, 2, eur, sheet_id)
        await asyncio.sleep(2)
        await fill_column_with_sequential_numbers("G", sheet_name_2, 2, byn, sheet_id)
    

        await bot.send_message(ADMIN_ID, f"✅ Курсы валют обновлены: BYN {byn}, USD {usd}, EUR {eur}")
        await asyncio.sleep(86400)
