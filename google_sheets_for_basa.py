import os
import io
import pickle
import mimetypes
from typing import Optional, Dict, Any
import logging
import aiofiles
from aiogoogle import Aiogoogle
from aiogoogle.auth.creds import UserCreds
import json
from datetime import datetime

# Настройка логирования
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

class GoogleDriveManager:
    """Асинхронный класс для работы с Google Drive API через OAuth аутентификацию"""
    
    def __init__(self, credentials_path: str = "oauth.json", token_file: str = "token.json"):
        """
        Инициализация менеджера Google Drive
        
        Args:
            credentials_path: Путь к файлу с OAuth учетными данными
            token_file: Путь к файлу с сохраненным OAuth токеном
        """
        self.credentials_path = credentials_path
        self.token_file = token_file
        self.user_creds = None
        self.client_creds = None
    
    async def _load_credentials(self) -> dict:
        """Загрузка учетных данных из файла"""
        try:
            if os.path.exists(self.token_file):
                async with aiofiles.open(self.token_file, 'r') as f:
                    creds_dict = json.loads(await f.read())
                    return creds_dict
            return None
        except Exception as e:
            logger.error(f"Ошибка загрузки credentials: {e}")
            return None
    
    async def _save_credentials(self, creds: dict):
        """Сохранение учетных данных в файл"""
        try:
            async with aiofiles.open(self.token_file, 'w') as f:
                await f.write(json.dumps(creds, indent=2))
            logger.info("Credentials сохранены")
        except Exception as e:
            logger.error(f"Ошибка сохранения credentials: {e}")
    
    async def _get_creds(self) -> tuple:
        """Получение client и user credentials"""
        if self.user_creds and self.client_creds:
            return self.client_creds, self.user_creds
        
        # Загружаем token.json
        token_data = await self._load_credentials()
        if not token_data:
            logger.warning("Нет сохраненных credentials. Требуется OAuth авторизация.")
            raise Exception("Требуется OAuth авторизация. Запустите convert_token.py или setup_oauth.py")
        
        # Разделяем на client_creds и user_creds
        self.client_creds = {
            'client_id': token_data.get('client_id'),
            'client_secret': token_data.get('client_secret'),
            'scopes': token_data.get('scopes', ['https://www.googleapis.com/auth/drive']),
            'redirect_uri': 'http://localhost:8080'
        }
        
        # Конвертируем expires_at из timestamp в ISO формат если нужно
        expires_at = token_data.get('expires_at')
        if expires_at and isinstance(expires_at, (int, float)):
            expires_at = datetime.fromtimestamp(expires_at).isoformat()
        
        self.user_creds = UserCreds(
            access_token=token_data.get('access_token'),
            refresh_token=token_data.get('refresh_token'),
            expires_at=expires_at,
            token_uri=token_data.get('token_uri', 'https://oauth2.googleapis.com/token')
        )
        
        return self.client_creds, self.user_creds
    
    async def upload_file(self, file_path: str, folder_id: Optional[str] = None, 
                         file_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Асинхронная загрузка файла в Google Drive
        
        Args:
            file_path: Путь к загружаемому файлу
            folder_id: ID папки в Google Drive (если None, загружается в корень)
            file_name: Имя файла в Google Drive (если None, используется оригинальное имя)
        
        Returns:
            Словарь с информацией о загруженном файле
        """
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Файл не найден: {file_path}")
            
            # Определение имени файла
            if file_name is None:
                file_name = os.path.basename(file_path)
            
            # Определение MIME типа
            mime_type, _ = mimetypes.guess_type(file_path)
            if mime_type is None:
                mime_type = 'application/octet-stream'
            
            # Читаем файл асинхронно
            async with aiofiles.open(file_path, 'rb') as f:
                file_data = await f.read()
            
            # Метаданные файла
            file_metadata = {
                'name': file_name
            }
            
            # Если указана папка, добавляем её в родители
            if folder_id:
                file_metadata['parents'] = [folder_id]
            
            # Получаем credentials
            client_creds, user_creds = await self._get_creds()
            
            # Загружаем файл через aiogoogle
            async with Aiogoogle(client_creds=client_creds, user_creds=user_creds) as aiogoogle:
                drive_v3 = await aiogoogle.discover('drive', 'v3')
                
                # Создаем upload request
                upload_req = drive_v3.files.create(
                    upload_file=file_data,
                    fields='id,name,webViewLink,size,createdTime',
                    json=file_metadata
                )
                
                file = await aiogoogle.as_user(upload_req)
            
            logger.info(f"Файл '{file_name}' успешно загружен в Google Drive")
            logger.info(f"ID файла: {file.get('id')}")
            logger.info(f"Ссылка: {file.get('webViewLink')}")
            
            return {
                'success': True,
                'file_id': file.get('id'),
                'file_name': file.get('name'),
                'web_link': file.get('webViewLink'),
                'size': file.get('size'),
                'created_time': file.get('createdTime')
            }
            
        except Exception as e:
            logger.error(f"Ошибка загрузки файла: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def upload_file_from_bytes(self, file_data: bytes, file_name: str, 
                                    mime_type: str = 'application/octet-stream',
                                    folder_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Асинхронная загрузка файла из байтов в Google Drive
        
        Args:
            file_data: Данные файла в виде байтов
            file_name: Имя файла в Google Drive
            mime_type: MIME тип файла
            folder_id: ID папки в Google Drive
        
        Returns:
            Словарь с информацией о загруженном файле
        """
        try:
            # Метаданные файла
            file_metadata = {
                'name': file_name
            }
            
            # Если указана папка, добавляем её в родители
            if folder_id:
                file_metadata['parents'] = [folder_id]
            
            # Получаем credentials
            client_creds, user_creds = await self._get_creds()
            
            # Загружаем файл через aiogoogle
            async with Aiogoogle(client_creds=client_creds, user_creds=user_creds) as aiogoogle:
                drive_v3 = await aiogoogle.discover('drive', 'v3')
                
                # Создаем upload request
                upload_req = drive_v3.files.create(
                    upload_file=file_data,
                    fields='id,name,webViewLink,size,createdTime',
                    json=file_metadata
                )
                
                file = await aiogoogle.as_user(upload_req)
            
            logger.info(f"Файл '{file_name}' успешно загружен из байтов в Google Drive")
            
            return {
                'success': True,
                'file_id': file.get('id'),
                'file_name': file.get('name'),
                'web_link': file.get('webViewLink'),
                'size': file.get('size'),
                'created_time': file.get('createdTime')
            }
            
        except Exception as e:
            logger.error(f"Ошибка загрузки файла из байтов: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def create_folder(self, folder_name: str, parent_folder_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Асинхронное создание папки в Google Drive
        
        Args:
            folder_name: Имя создаваемой папки
            parent_folder_id: ID родительской папки (если None, создается в корне)
        
        Returns:
            Словарь с информацией о созданной папке
        """
        try:
            # Метаданные папки
            folder_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            # Если указана родительская папка
            if parent_folder_id:
                folder_metadata['parents'] = [parent_folder_id]
            
            # Получаем credentials
            client_creds, user_creds = await self._get_creds()
            
            # Создаем папку через aiogoogle
            async with Aiogoogle(client_creds=client_creds, user_creds=user_creds) as aiogoogle:
                drive_v3 = await aiogoogle.discover('drive', 'v3')
                
                folder = await aiogoogle.as_user(
                    drive_v3.files.create(
                        json=folder_metadata,
                        fields='id,name,webViewLink'
                    )
                )
            
            logger.info(f"Папка '{folder_name}' успешно создана в Google Drive")
            logger.info(f"ID папки: {folder.get('id')}")
            
            return {
                'success': True,
                'folder_id': folder.get('id'),
                'folder_name': folder.get('name'),
                'web_link': folder.get('webViewLink')
            }
            
        except Exception as e:
            logger.error(f"Ошибка создания папки: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def find_folder_by_name(self, folder_name: str, parent_folder_id: Optional[str] = None) -> Optional[str]:
        """
        Асинхронный поиск папки по имени
        
        Args:
            folder_name: Имя искомой папки
            parent_folder_id: ID родительской папки для поиска
        
        Returns:
            ID найденной папки или None
        """
        try:
            # Формирование запроса поиска
            query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            if parent_folder_id:
                query += f" and '{parent_folder_id}' in parents"
            
            # Получаем credentials
            client_creds, user_creds = await self._get_creds()
            
            # Поиск папки через aiogoogle
            async with Aiogoogle(client_creds=client_creds, user_creds=user_creds) as aiogoogle:
                drive_v3 = await aiogoogle.discover('drive', 'v3')
                
                results = await aiogoogle.as_user(
                    drive_v3.files.list(
                        q=query,
                        fields='files(id, name)'
                    )
                )
            
            files = results.get('files', [])
            if files:
                folder_id = files[0]['id']
                logger.info(f"Папка '{folder_name}' найдена с ID: {folder_id}")
                return folder_id
            else:
                logger.info(f"Папка '{folder_name}' не найдена")
                return None
                
        except Exception as e:
            logger.error(f"Ошибка поиска папки: {e}")
            return None
    
    async def get_or_create_folder(self, folder_name: str, parent_folder_id: Optional[str] = None) -> Optional[str]:
        """
        Асинхронное получение ID существующей папки или создание новой
        
        Args:
            folder_name: Имя папки
            parent_folder_id: ID родительской папки
        
        Returns:
            ID папки или None в случае ошибки
        """
        # Сначала пытаемся найти существующую папку
        folder_id = await self.find_folder_by_name(folder_name, parent_folder_id)
        
        if folder_id:
            return folder_id
        
        # Если папка не найдена, создаем новую
        result = await self.create_folder(folder_name, parent_folder_id)
        if result['success']:
            return result['folder_id']
        
        return None
    
    async def set_file_permissions(self, file_id: str, permission_type: str = 'reader', 
                                   role: str = 'anyone') -> bool:
        """
        Асинхронная установка разрешений для файла
        
        Args:
            file_id: ID файла
            permission_type: Тип разрешения ('reader', 'writer', 'commenter')
            role: Роль ('anyone', 'user', 'group', 'domain')
        
        Returns:
            True если разрешения установлены успешно
        """
        try:
            permission = {
                'type': role,
                'role': permission_type
            }
            
            # Получаем credentials
            client_creds, user_creds = await self._get_creds()
            
            # Устанавливаем разрешения через aiogoogle
            async with Aiogoogle(client_creds=client_creds, user_creds=user_creds) as aiogoogle:
                drive_v3 = await aiogoogle.discover('drive', 'v3')
                
                await aiogoogle.as_user(
                    drive_v3.permissions.create(
                        fileId=file_id,
                        json=permission
                    )
                )
            
            logger.info(f"Разрешения для файла {file_id} установлены успешно")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка установки разрешений: {e}")
            return False


# Асинхронные функции-обертки для удобного использования
async def upload_file_to_drive(file_path: str, folder_name: Optional[str] = None, 
                               file_name: Optional[str] = None,
                               credentials_path: str = "oauth.json") -> Dict[str, Any]:
    """
    Асинхронная функция для загрузки файла в Google Drive через OAuth
    
    Args:
        file_path: Путь к файлу
        folder_name: Имя папки в Google Drive (создается если не существует)
        file_name: Имя файла в Google Drive
        credentials_path: Путь к файлу OAuth credentials
    
    Returns:
        Результат загрузки
    """
    try:
        drive_manager = GoogleDriveManager(credentials_path=credentials_path)
        
        folder_id = None
        if folder_name:
            folder_id = await drive_manager.get_or_create_folder(folder_name)
        
        return await drive_manager.upload_file(file_path, folder_id, file_name)
        
    except Exception as e:
        logger.error(f"Ошибка в upload_file_to_drive: {e}")
        return {
            'success': False,
            'error': str(e)
        }


async def upload_bytes_to_drive(file_data: bytes, file_name: str, folder_name: Optional[str] = None,
                                mime_type: str = 'application/octet-stream',
                                credentials_path: str = "oauth.json") -> Dict[str, Any]:
    """
    Асинхронная функция для загрузки данных из байтов в Google Drive через OAuth
    
    Args:
        file_data: Данные файла в байтах
        file_name: Имя файла
        folder_name: Имя папки в Google Drive
        mime_type: MIME тип файла
        credentials_path: Путь к файлу OAuth credentials
    
    Returns:
        Результат загрузки
    """
    try:
        drive_manager = GoogleDriveManager(credentials_path=credentials_path)
        
        folder_id = None
        if folder_name:
            folder_id = await drive_manager.get_or_create_folder(folder_name)
        
        return await drive_manager.upload_file_from_bytes(file_data, file_name, mime_type, folder_id)
        
    except Exception as e:
        logger.error(f"Ошибка в upload_bytes_to_drive: {e}")
        return {
            'success': False,
            'error': str(e)
        }
