"""
Скрипт для первичной OAuth авторизации Google Drive
Создает token.json из creds.json
"""
import json
import asyncio
from aiogoogle import Aiogoogle
from aiogoogle.auth.creds import UserCreds

async def setup_oauth():
    """Настройка OAuth авторизации"""
    
    # Загружаем client credentials из creds.json
    with open('creds.json', 'r') as f:
        client_creds = json.load(f)
    
    # Извлекаем нужные данные
    if 'installed' in client_creds:
        creds_data = client_creds['installed']
    elif 'web' in client_creds:
        creds_data = client_creds['web']
    else:
        raise ValueError("Неверный формат creds.json")
    
    client_id = creds_data['client_id']
    client_secret = creds_data['client_secret']
    
    # Scopes для Google Drive
    scopes = ['https://www.googleapis.com/auth/drive']
    
    async with Aiogoogle(client_creds={
        'client_id': client_id,
        'client_secret': client_secret,
        'scopes': scopes,
        'redirect_uri': 'http://localhost:8080'
    }) as aiogoogle:
        
        # Получаем URL для авторизации
        if aiogoogle.oauth2.is_ready(client_creds):
            uri = aiogoogle.oauth2.authorization_url(
                client_creds=client_creds,
                scopes=scopes,
                access_type='offline',
                include_granted_scopes=True,
                prompt='consent'
            )
            
            print("=" * 80)
            print("ОТКРОЙТЕ ЭТУ ССЫЛКУ В БРАУЗЕРЕ:")
            print("=" * 80)
            print(uri)
            print("=" * 80)
            print("\nПосле авторизации вы будете перенаправлены на localhost.")
            print("Скопируйте ПОЛНЫЙ URL из адресной строки браузера и вставьте сюда:")
            print()
            
            # Получаем код авторизации от пользователя
            full_url = input("Вставьте полный URL: ").strip()
            
            # Извлекаем код из URL
            if 'code=' in full_url:
                code = full_url.split('code=')[1].split('&')[0]
            else:
                raise ValueError("Не найден код авторизации в URL")
            
            print(f"\n✅ Код получен: {code[:20]}...")
            
            # Обмениваем код на токены
            user_creds = await aiogoogle.oauth2.build_user_creds(
                grant=code,
                client_creds=client_creds
            )
            
            # Сохраняем токены в token.json
            token_data = {
                'access_token': user_creds.get('access_token'),
                'refresh_token': user_creds.get('refresh_token'),
                'expires_at': user_creds.get('expires_at'),
                'scopes': scopes,
                'token_type': user_creds.get('token_type', 'Bearer'),
                'token_uri': 'https://oauth2.googleapis.com/token',
                'client_id': client_id,
                'client_secret': client_secret
            }
            
            with open('token.json', 'w') as f:
                json.dump(token_data, f, indent=2)
            
            print("\n" + "=" * 80)
            print("✅ УСПЕШНО! Файл token.json создан.")
            print("=" * 80)
            print("\nТеперь вы можете использовать GoogleDriveManager в своих скриптах.")
            print("Токен будет автоматически обновляться при необходимости.")
            
        else:
            print("❌ Ошибка: client credentials не готовы")

if __name__ == "__main__":
    try:
        asyncio.run(setup_oauth())
    except FileNotFoundError:
        print("❌ Ошибка: Файл creds.json не найден!")
        print("Убедитесь, что файл creds.json находится в текущей директории.")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
