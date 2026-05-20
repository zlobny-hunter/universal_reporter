import logging
import pandas as pd

logger = logging.getLogger("Validator")

def validate_dataframe(df: pd.DataFrame, job_config: dict) -> str:
    """
    Проверяет DataFrame на пустоту согласно правилам в конфигурации отчета.
    Возвращает: 'PROCEED' (продолжать), 'SKIP' (пропустить) или вызывает ValueError.
    """
    validation_cfg = job_config.get("validation", {})
    allow_empty = validation_cfg.get("allow_empty", True)
    on_empty_action = validation_cfg.get("on_empty_action", "skip")

    if df.empty:
        if allow_empty:
            logger.warning("DataFrame пуст, но конфигурация разрешает дальнейшую обработку.")
            return "PROCEED"
        
        # Если пустые данные запрещены, обрабатываем согласно on_empty_action
        if on_empty_action == "skip":
            logger.info("Данные отсутствуют. Выполнение отчета тихо пропущено.")
            return "SKIP"
        elif on_empty_action == "alert":
            error_msg = "Критическая ошибка валидации: Датасет пуст, генерация отчета прервана!"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
    logger.info("Валидация данных пройдена успешно.")
    return "PROCEED"