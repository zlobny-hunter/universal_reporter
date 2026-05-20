import os
import logging
import requests
from src.delivery.base import BaseDeliveryProvider

logger = logging.getLogger("Delivery.Nextcloud")

class NextcloudDeliveryProvider(BaseDeliveryProvider):
    def send(self, file_path: str, provider_config: dict, global_config: dict) -> bool:
        # Получаем глобальные доступы к облаку
        nc_cfg = global_config.get("delivery", {}).get("nextcloud", {})
        base_url = nc_cfg.get("url", "").rstrip("/")
        username = nc_cfg.get("username")
        password = nc_cfg.get("password")
        
        # Получаем целевой путь в облаке для конкретного отчета
        remote_path = provider_config.get("remote_path", "/").strip("/")
        filename = os.path.basename(file_path)
        
        if not base_url or not username or not password:
            logger.error("Nextcloud: Глобальные настройки авторизации не найдены в main.toml.")
            return False

        # Формируем стандартный WebDAV URL для Nextcloud
        # Формат: https://yourcloud.com/remote.php/dav/files/USERNAME/path/to/file.xlsx
        webdav_url = f"{base_url}/remote.php/dav/files/{username}/{remote_path}/{filename}"
        
        logger.info(f"Загрузка файла на Nextcloud по пути: /{remote_path}/{filename}")
        
        try:
            with open(file_path, "rb") as f:
                # Отправляем файл бинарным потоком
                response = requests.put(
                    webdav_url, 
                    data=f, 
                    auth=(username, password),
                    timeout=60
                )
            
            # WebDAV возвращает 201 Created при успешной загрузке или 204 No Content при перезаписи
            if response.status_code in [201, 204]:
                logger.info("Файл успешно загружен в Nextcloud.")
                return True
            else:
                logger.error(f"Nextcloud вернул ошибку: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка при работе с Nextcloud WebDAV: {e}", exc_info=True)
            return False