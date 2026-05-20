import os
import logging
import requests
from src.delivery.base import BaseDeliveryProvider

logger = logging.getLogger("Delivery.YandexMsg")

class YandexMsgDeliveryProvider(BaseDeliveryProvider):
    def send(self, file_path: str, provider_config: dict, global_config: dict) -> bool:
        # Глобальные настройки бота
        yandex_cfg = global_config.get("delivery", {}).get("yandex_messenger", {})
        token = yandex_cfg.get("bot_token")
        
        # Настройки чата для конкретного отчета
        chat_id = provider_config.get("chat_id")
        caption = provider_config.get("caption", "Сформирован новый отчет")
        
        if not token:
            logger.error("YandexMessenger: Токен бота 'bot_token' не задан в main.toml.")
            return False
        if not chat_id:
            logger.error("YandexMessenger: Целевой 'chat_id' не задан в config.yaml отчета.")
            return False

        # URL Яндекс Мессенджер Bot API для отправки документов
        api_url = f"https://botapi.messenger.yandex.net/v1/messages/sendDocument"
        
        headers = {
            "Authorization": f"OAuth {token}"
        }
        
        payload = {
            "chat_id": chat_id,
            "caption": caption
        }
        
        filename = os.path.basename(file_path)
        logger.info(f"Отправка файла {filename} в чат Яндекс Мессенджера: {chat_id}")
        
        try:
            with open(file_path, "rb") as f:
                files = {
                    "document": (filename, f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                }
                
                response = requests.post(
                    api_url, 
                    headers=headers, 
                    data=payload, 
                    files=files,
                    timeout=30
                )
                
            if response.status_code == 200:
                logger.info("Отчет успешно доставлен в Яндекс Мессенджер.")
                return True
            else:
                logger.error(f"Яндекс Мессенджер вернул ошибку: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка при отправке в Яндекс Мессенджер: {e}", exc_info=True)
            return False