import logging
from src.delivery.local import LocalDeliveryProvider
from src.delivery.mail import MailDeliveryProvider

logger = logging.getLogger("Delivery.Factory")
import logging
from src.delivery.local import LocalDeliveryProvider
from src.delivery.mail import MailDeliveryProvider
from src.delivery.nextcloud import NextcloudDeliveryProvider
from src.delivery.yandex_msg import YandexMsgDeliveryProvider

logger = logging.getLogger("Delivery.Factory")

# Регистрируем абсолютно всех доступных провайдеров
PROVIDERS = {
    "local": LocalDeliveryProvider(),
    "mail": MailDeliveryProvider(),
    "nextcloud": NextcloudDeliveryProvider(),
    "yandex_messenger": YandexMsgDeliveryProvider()
}

def dispatch_delivery(file_path: str, job_delivery_config: dict, global_config: dict):
    for provider_name, provider_cfg in job_delivery_config.items():
        if not provider_cfg.get("enabled", False):
            logger.debug(f"Провайдер '{provider_name}' отключен в настройках отчета.")
            continue
            
        if provider_name not in PROVIDERS:
            logger.warning(f"Запрошен неизвестный провайдер доставки: '{provider_name}'")
            continue
            
        logger.info(f"Запуск отправки через канал: '{provider_name}'")
        provider = PROVIDERS[provider_name]
        
        try:
            success = provider.send(file_path, provider_cfg, global_config)
            if success:
                logger.info(f"Провайдер '{provider_name}' успешно отработал.")
            else:
                logger.error(f"Провайдер '{provider_name}' завершил работу с ошибкой.")
        except Exception as e:
            logger.error(f"Критический сбой внутри провайдера '{provider_name}': {e}", exc_info=True)