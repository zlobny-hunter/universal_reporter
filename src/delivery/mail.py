import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from src.delivery.base import BaseDeliveryProvider

logger = logging.getLogger("Delivery.Mail")

class MailDeliveryProvider(BaseDeliveryProvider):
    def send(self, file_path: str, provider_config: dict, global_config: dict) -> bool:
        # Извлекаем глобальные настройки SMTP сервера
        smtp_cfg = global_config.get("delivery", {}).get("mail", {})
        
        # Извлекаем настройки получателей для конкретного отчета
        recipients = provider_config.get("to", [])
        subject = provider_config.get("subject", "Сгенерирован новый отчет")
        body_text = provider_config.get("body", "Здравствуйте.\nВо вложении к письму находится сформированный отчет.")
        
        if not recipients:
            logger.warning("Email-доставка: Список получателей 'to' пуст. Отправка отменена.")
            return False
        
        try:
            # Создаем контейнер для MIME-сообщения
            msg = MIMEMultipart()
            msg['From'] = smtp_cfg.get("sender")
            msg['To'] = ", ".join(recipients)
            msg['Subject'] = subject
            
            # Добавляем текстовое тело письма
            msg.attach(MIMEText(body_text, 'plain', 'utf-8'))
            
            # Подготавливаем вложение (Excel файл)
            filename = os.path.basename(file_path)
            with open(file_path, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
                
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename={filename}",
            )
            msg.attach(part)
            
            # Подключение к SMTP серверу
            server_host = smtp_cfg.get("smtp_server")
            server_port = int(smtp_cfg.get("smtp_port", 587))
            
            logger.info(f"Подключение к SMTP-серверу {server_host}:{server_port}")
            server = smtplib.SMTP(server_host, server_port)
            
            if smtp_cfg.get("use_tls", True):
                server.starttls()
                
            server.login(smtp_cfg.get("sender"), smtp_cfg.get("password"))
            
            # Отправка
            server.sendmail(smtp_cfg.get("sender"), recipients, msg.as_string())
            server.quit()
            
            logger.info(f"Письмо успешно отправлено получателям: {recipients}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при отправке почты: {e}", exc_info=True)
            return False