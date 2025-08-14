import gspread
from typing import Optional

# --- Настройка ---
# Замените 'path/to/your/credentials.json' на путь к вашему файлу
# Ключ создается в Google Cloud Console.
SERVICE_ACCOUNT_FILE = 'creds.json'

# Замените 'your_spreadsheet_id' на ID вашей таблицы.
# ID находится в URL: https://docs.google.com/spreadsheets/d/your_spreadsheet_id/edit#gid=...
SPREADSHEET_ID = '1pIrNhJ9Fr7Ickp9X0ao73rRwlqDp1QbTzMn5ULzVjuw'

# Имя листа, с которым вы работаете
SHEET_NAME = 'Для Бота'

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

# --- Пример использования ---
if __name__ == "__main__":
    search_number = 27 # Искомое число
    result_rate = find_rate_in_sheet_gspread(search_number)

    if result_rate:
        print(f"Для ставки в {search_number} USD, верхняя граница зарплаты в RUB: {result_rate}")
    else:
        print(f"Ставка в {search_number} USD не найдена в листе '{SHEET_NAME}'.")