# Тесты проекта Universal Reporter

## Структура тестов

```
tests/
├── __init__.py
├── conftest.py              # Общие fixtures для pytest
├── test_config_loader.py    # Тесты для загрузки конфигураций
├── test_db_logger.py       # Тесты для логирования в БД
├── test_main.py             # Тесты для основного модуля (main.py)
├── test_db_client.py        # Тесты для клиента БД
└── README.md               # Этот файл
```

## Запуск тестов

### Установка зависимостей

```bash
pip install -r requirements.txt
```

### Запуск всех тестов

```bash
pytest tests/
```

### Запуск с покрытием кода

```bash
pytest tests/ --cov=src --cov-report=html
```

Отчет покрытия будет в папке `htmlcov/index.html`

### Запуск конкретного файла тестов

```bash
pytest tests/test_config_loader.py
```

### Запуск конкретного теста

```bash
pytest tests/test_config_loader.py::TestLoadMainConfig::test_load_main_config_success
```

### Запуск с детальным выводом

```bash
pytest tests/ -v
```

## Описание тестов

### test_config_loader.py

Тестирует модуль `src/utils/config_loader.py`:
- `setup_logging()` - инициализация логирования
- `load_main_config()` - загрузка главного конфига
- `load_job_config()` - загрузка конфига отчета
- `get_job_title()` - получение заголовка отчета

### test_db_logger.py

Тестирует модуль `src/utils/db_logger.py`:
- `init_history_db()` - создание таблиц в БД
- `log_job_state()` - логирование состояния задачи
- `log_user_run()` - логирование запусков пользователей

### test_main.py

Тестирует модуль `src/main.py`:
- `get_all_jobs()` - получение списка отчетов
- `get_connection_for_job()` - фабрика подключений к БД
- `handle_delivery()` - доставка отчетов

### test_db_client.py

Тестирует модуль `src/database/db_client.py`:
- Инициализация DBClient для разных СУБД
- `execute_sql_file()` - выполнение SQL файлов
- Создание engine для разных диалектов

## Fixtures

В `conftest.py` определены следующие fixtures:
- `temp_dir` - временная директория для тестов
- `sample_job_config` - пример конфигурации отчета
- `sample_main_config` - пример главного конфига
- `sample_sql_file` - тестовый SQL файл

## Добавление новых тестов

1. Создайте новый файл в папке `tests/` с именем `test_<module_name>.py`
2. Импортируйте pytest и тестируемый модуль
3. Создайте классы тестов с префиксом `Test`
4. Имена методов тестов должны начинаться с `test_`
5. Используйте fixtures из `conftest.py` при необходимости

Пример:

```python
import pytest
from src.utils.my_module import my_function

class TestMyFunction:
    def test_success(self, temp_dir):
        result = my_function(temp_dir)
        assert result is not None
```
