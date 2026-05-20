import os
import shutil
import logging
from src.delivery.base import BaseDeliveryProvider

logger = logging.getLogger("Delivery.Local")

class LocalDeliveryProvider(BaseDeliveryProvider):
    def send(self, file_path: str, provider_config: dict, global_config: dict) -> bool:
        target_dir = provider_config.get("target_path")
        if not target_dir:
            logger.error("Локальная доставка: Не указан параметр 'target_path' в конфигурации отчета.")
            return False
        
        try:
            os.makedirs(target_dir, exist_ok=True)
            filename = os.path.basename(file_path)
            destination = os.path.join(target_dir, filename)
            
            # Копируем файл
            shutil.copy2(file_path, destination)
            logger.info(f"Файл успешно скопирован в локальную папку: {destination}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при копировании файла в {target_dir}: {e}", exc_info=True)
            return False