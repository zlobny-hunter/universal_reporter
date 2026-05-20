import logging
import requests

logger = logging.getLogger("Monitoring.Alerts")

def send_admin_alert(message: str, global_config: dict):
    """
    Отправляет экстренное сообщение администратору системы.
    """
    monitor_cfg = global_config.get("monitoring", {})
    token = monitor_cfg.get("yandex_bot_token")
    chat_id = monitor_cfg.get("yandex_chat_id")
    
    alert_text = f"🚨 [REPORTER ALERT]\n{message}"
    
    # Всегда пишем в локальный лог сервера с уровнем CRITICAL
    logger.critical(alert_text)
    
    if not token or not chat_id or "here" in token:
        logger.warning("Алертинг: Сетевой алерт не отправлен (не настроены yandex_bot_token или chat_id в main.toml)")
        return

    # Отправка в чат админа
    url = "https://botapi.messenger.yandex.net/v1/messages/sendText"
    headers = {"Authorization": f"OAuth {token}"}
    payload = {"chat_id": chat_id, "text": alert_text}
    
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        if res.status_code != 200:
            logger.error(f"Не удалось отправить алерт в Яндекс: {res.status_code} - {res.text}")
    except Exception as e:
        logger.error(f"Ошибка сети при отправке алерта: {e}")