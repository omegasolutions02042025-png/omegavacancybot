import gspread
from typing import Optional
from typing import List, Optional, Dict, Any
from google.oauth2.service_account import Credentials
import os
import re
import math
import gspread
# --- Настройка ---
# Замените 'path/to/your/credentials.json' на путь к вашему файлу
# Ключ создается в Google Cloud Console.
SERVICE_ACCOUNT_FILE = 'creds.json'

# Замените 'your_spreadsheet_id' на ID вашей таблицы.
# ID находится в URL: https://docs.google.com/spreadsheets/d/your_spreadsheet_id/edit#gid=...
SPREADSHEET_ID = '1ApDxmH0BL4rbuKTni6cj-D_d0vJ5KG45sEQjOyXM3PY'

# Имя листа, с которым вы работаете
SHEET_NAME = 'Для Бота'

SHEET_URL = 'https://docs.google.com/spreadsheets/d/1ApDxmH0BL4rbuKTni6cj-D_d0vJ5KG45sEQjOyXM3PY/edit#gid=0'
# --- Функция для получения данных ---
def find_rate_in_sheet_gspread(search_value_usd: int) -> Optional[str]:
    """
    Ищет значение в столбце J (Ставка из вакансии, USD) и возвращает
    соответствующее значение из столбца B (Верхнее значение зарплаты вилки, RUB).
    Если точное совпадение не найдено, ищет ближайшее число.

    Args:
        search_value_usd (int): Искомое число в столбце J.

    Returns:
        str | None: Значение из столбца B, если найдено совпадение, иначе None.
    """
    try:
        # Аутентификация с помощью gspread
        gc = gspread.service_account(filename=SERVICE_ACCOUNT_FILE)

        # Открытие таблицы по ID
        sh = gc.open_by_key(SPREADSHEET_ID)
        
        # Получение доступа к нужному листу по имени
        worksheet = sh.worksheet(SHEET_NAME)
        if search_value_usd == None:
            return None
        if search_value_usd <= 300:
            j_column_values = worksheet.col_values(11)
        else:
            j_column_values = worksheet.col_values(10)
        
        # Итерируемся по значениям, чтобы найти совпадение как по числу
        # Пропускаем первую строку (часто содержит заголовки)
        target_value = int(search_value_usd)
        closest_value = None
        min_difference = float('inf')
        
        for row_index, value in enumerate(j_column_values, start=1):
            if row_index == 1:
                continue
            # Пытаемся привести ячейку к int (удаляем пробелы и разделители тысяч)
            cell_text = str(value).strip().replace('\xa0', '').replace(' ', '').replace(',', '')
            try:
                cell_number = int(float(cell_text)) if ('.' in cell_text) else int(cell_text)
            except ValueError:
                continue
                
            # Если найдено точное совпадение - сразу возвращаем
            if cell_number == target_value:
                # Получаем всю строку, в которой найдено совпадение
                row_values = worksheet.row_values(row_index)
                # Столбец B - это второй элемент (индекс 1)
                if len(row_values) > 1 and row_values[1] != "":
                    return row_values[1]
            
            # Если точное совпадение не найдено, ищем ближайшее
            difference = abs(cell_number - target_value)
            if difference < min_difference:
                min_difference = difference
                closest_value = (row_index, cell_number)
        
        # Если точное совпадение не найдено, но есть ближайшее число
        if closest_value:
            row_index, cell_number = closest_value
            row_values = worksheet.row_values(row_index)
            if len(row_values) > 1 and row_values[1] != "":
                return row_values[1]

        # Если ничего не найдено
        return None

    except gspread.exceptions.APIError as e:
        print(f"Ошибка API Google Sheets: {e}")
        return None
    except Exception as e:
        print(f"Произошла непредвиденная ошибка: {e}")
        return None



def search_and_extract_values(
    search_column: str,
    search_value: float,
    extract_columns: List[str],
    worksheet_name: str = "Resume_Database"
) -> Optional[Dict[str, Any]]:
    """
    Поиск значения в указанной колонке и извлечение данных из других колонок
    
    Args:
        search_column: Буква колонки для поиска (например, 'B')
        search_value: Числовое значение для поиска
        extract_columns: Список букв колонок для извлечения данных (например, ['A', 'C', 'D'])
        worksheet_name: Название листа
    
    Returns:
        Словарь с найденными значениями или None если ничего не найдено
    """
    try:
        # URL таблицы
        

        # Авторизация
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_file("./creds.json", scopes=scopes)
        client = gspread.authorize(creds)

        # Подключаемся к таблице
        spreadsheet = client.open_by_url(SHEET_URL)

        # Выбираем лист
        try:
            worksheet = spreadsheet.worksheet(worksheet_name)
        except gspread.WorksheetNotFound:
            print(f"❌ Лист '{worksheet_name}' не найден")
            return None

        # Получаем все строки
        all_values = worksheet.get_all_values()
        if not all_values:
            print("❌ Лист пуст")
            return None

        # Индекс колонки
        search_col_index = ord(search_column.upper()) - ord('A')

        # Диапазон поиска ±20
        search_range = list(range(int(search_value) - 20, int(search_value) + 21))
        print(f"🔍 Поиск в диапазоне {search_range[0]} - {search_range[-1]} в колонке {search_column}")

        target_row_index = None
        exact_match_row = None
        valid_values = []

        for row_index, row in enumerate(all_values):
            if row_index == 0:  # пропускаем заголовки
                continue

            if len(row) <= search_col_index:
                continue

            cell_value = row[search_col_index]
            if not cell_value:
                continue

            try:
                cell_value = cell_value.strip().split(",")[0]
                numeric_value = int(re.sub(r"[^\d]", "", cell_value))
                valid_values.append(numeric_value)
                

                if numeric_value == search_value:
                    exact_match_row = row_index
                    target_row_index = row_index
                    print(f"✅ Найдено точное совпадение: {numeric_value} в строке {row_index + 1}")
                    break

                if numeric_value in search_range:
                    target_row_index = row_index
                    print(f"✅ Найдено совпадение в диапазоне: {numeric_value} в строке {row_index + 1}")
                    break

            except (ValueError, AttributeError):
                continue

        if target_row_index is None:
            print(f"❌ Не найдено значений рядом с {search_value} в колонке {search_column}")
            print(f"📋 Найденные значения: {sorted(set(valid_values))[:10]}...")
            return None

        target_row = all_values[target_row_index]

        result = {
            "found_row": target_row_index + 1,
            "search_value_found": target_row[search_col_index] if len(target_row) > search_col_index else "",
            "is_exact_match": exact_match_row is not None,
            "extracted_values": {}
        }

        for col_letter in extract_columns:
            col_index = ord(col_letter.upper()) - ord('A')
            if len(target_row) > col_index:
                clean_value = target_row[col_index].replace("\xa0", "").strip()
                rounded = (int(clean_value) // 1000) * 1000
                clean_value = f"{rounded:,}".replace(",", " ")
                result["extracted_values"][col_letter] = clean_value
            else:
                result["extracted_values"][col_letter] = ""

        print(result["extracted_values"])
        return result["extracted_values"]

    except Exception as e:
        print(f"❌ Ошибка при поиске и извлечении данных: {e}")
        return None


