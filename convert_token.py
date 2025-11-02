"""
Конвертация token.pickle в token.json для aiogoogle
"""
import pickle
import json
import os

def convert_pickle_to_json():
    """Конвертирует token.pickle в token.json"""
    
    # Проверяем наличие файлов
    if not os.path.exists('token.pickle'):
        print("❌ Файл token.pickle не найден!")
        return
    
    if not os.path.exists('oauth.json'):
        print("❌ Файл oauth.json не найден!")
        return
    
    # Загружаем credentials из pickle
    print("📂 Загружаем token.pickle...")
    with open('token.pickle', 'rb') as token:
        creds = pickle.load(token)
    
    # Загружаем client credentials из oauth.json
    print("📂 Загружаем oauth.json...")
    with open('oauth.json', 'r') as f:
        oauth_data = json.load(f)
    
    # Извлекаем client_id и client_secret
    if 'installed' in oauth_data:
        client_creds = oauth_data['installed']
    elif 'web' in oauth_data:
        client_creds = oauth_data['web']
    else:
        print("❌ Неверный формат oauth.json")
        return
    
    client_id = client_creds.get('client_id')
    client_secret = client_creds.get('client_secret')
    
    # Создаем структуру для aiogoogle
    token_data = {
        'access_token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri or 'https://oauth2.googleapis.com/token',
        'client_id': client_id,
        'client_secret': client_secret,
        'scopes': creds.scopes if hasattr(creds, 'scopes') else ['https://www.googleapis.com/auth/drive']
    }
    
    # Добавляем expires_at если есть
    if hasattr(creds, 'expiry') and creds.expiry:
        # Конвертируем datetime в timestamp
        import datetime
        if isinstance(creds.expiry, datetime.datetime):
            token_data['expires_at'] = creds.expiry.timestamp()
    
    # Сохраняем в token.json
    print("💾 Сохраняем token.json...")
    with open('token.json', 'w') as f:
        json.dump(token_data, f, indent=2)
    
    print("\n" + "=" * 80)
    print("✅ УСПЕШНО! Файл token.json создан из token.pickle")
    print("=" * 80)
    print("\nСодержимое token.json:")
    print(json.dumps({k: v if k != 'access_token' else f"{v[:20]}..." for k, v in token_data.items()}, indent=2))
    print("\nТеперь GoogleDriveManager может использовать token.json для авторизации.")

if __name__ == "__main__":
    try:
        convert_pickle_to_json()
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
