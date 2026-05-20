import os
import logging
from datetime import datetime
import pandas as pd

logger = logging.getLogger("ExcelWriter")

def generate_filename(template: str) -> str:
    """Заменяет макросы даты в шаблоне имени файла на реальные значения."""
    now = datetime.now()
    filename = template.format(
        YYYY=now.strftime("%Y"),
        MM=now.strftime("%m"),
        DD=now.strftime("%d")
    )
    return filename

def build_excel_workbook(sheets_data: dict, job_config: dict, output_dir: str = "output") -> str:
    """
    Собирает Excel-книгу.
    :param sheets_data: Словарь вида {"Имя вкладки": DataFrame}
    :param job_config: Конфиг отчета (dict из yaml)
    :param output_dir: Папка для сохранения временного файла
    :return: Абсолютный путь к созданному файлу
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Считаем шаблон имени файла из конфига
    wb_config = job_config.get("workbook", {})
    filename_template = wb_config.get("filename_template", "report_{YYYY}_{MM}_{DD}.xlsx")
    filename = generate_filename(filename_template)
    file_path = os.path.join(output_dir, filename)
    
    logger.info(f"Начало сборки Excel-файла: {file_path}")
    
    # Будем использовать xlsxwriter внутри pandas для тонкой настройки стилей
    with pd.ExcelWriter(file_path, engine="xlsxwriter") as writer:
        workbook = writer.book
        
        # Настройки стилей шапки таблицы
        header_format = workbook.add_format({
            'bold': True,
            'text_wrap': True,
            'valign': 'vcenter',
            'fg_color': '#D9E1F2',  # Симпатичный светло-синий цвет
            'border': 1
        })
        
        # Пробегаемся по описанию страниц в конфиге, чтобы сохранить правильный порядок
        for sheet_cfg in wb_config.get("sheets", []):
            raw_sheet_name = sheet_cfg.get("name")
            
            if raw_sheet_name not in sheets_data:
                logger.warning(f"Данные для вкладки '{raw_sheet_name}' не найдены в кэше. Пропуск.")
                continue
                
            df = sheets_data[raw_sheet_name].copy()
            
            # Применяем расширенные имена колонок, если они заданы
            column_mapping = sheet_cfg.get("columns", {})
            if column_mapping:
                df.rename(columns=column_mapping, inplace=True)
                logger.debug(f"Переименованы колонки для вкладки '{raw_sheet_name}'")
            
            # Записываем данные на соответствующий лист
            df.to_excel(writer, sheet_name=raw_sheet_name, index=False, startrow=1)
            
            # Получаем объект листа xlsxwriter для кастомизации сетки и ширины колонок
            worksheet = writer.sheets[raw_sheet_name]
            worksheet.hide_gridlines(0) # Включаем отображение сетки (0 - показывать везде)
            
            # Перезаписываем шапку с нашими стилями
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
            
            # Автоматическая подгонка ширины колонок по длине контента
            for i, col in enumerate(df.columns):
                # Вычисляем максимальную длину значения в этой колонке
                max_len = max(
                    df[col].astype(str).map(len).max(),
                    len(str(col))
                ) + 3 # Добавляем небольшой отступ
                worksheet.set_column(i, i, max_len)
                
    logger.info(f"Excel-файл успешно сохранен: {file_path}")
    return os.path.abspath(file_path)