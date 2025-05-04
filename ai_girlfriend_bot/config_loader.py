# config_loader.py
import yaml
from pydantic import ValidationError
from loguru import logger
from models_config import AppConfig # Импортируем Pydantic модель
from typing import Optional # Используем Optional из typing

CONFIG_PATH = "config.yaml"
_config: Optional[AppConfig] = None # Переменная для хранения загруженного конфига

def load_config() -> Optional[AppConfig]:
    """Загружает, валидирует и кэширует конфигурацию."""
    global _config
    if _config:
        return _config # Возвращаем из кэша, если уже загружен

    try:
        # Создаем файл с дефолтными значениями, если он не существует
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
                if not config_data: # Если файл пуст
                     raise FileNotFoundError # Переходим к созданию дефолтного
        except FileNotFoundError:
            logger.warning(f"Файл конфигурации {CONFIG_PATH} не найден или пуст. Создаю дефолтный.")
            create_default_config()
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)

        # Валидация через Pydantic
        _config = AppConfig(**config_data)
        logger.info("Конфигурация успешно загружена и валидна.")
        return _config

    except yaml.YAMLError as e:
        logger.error(f"Ошибка чтения YAML файла ({CONFIG_PATH}): {e}")
        return None
    except ValidationError as e:
        logger.error(f"Ошибка валидации конфигурации ({CONFIG_PATH}):\n{e}")
        return None
    except Exception as e:
        logger.exception(f"Неизвестная ошибка при загрузке конфигурации ({CONFIG_PATH}):")
        return None

def get_config() -> AppConfig:
    """Возвращает загруженную конфигурацию. Вызывает ошибку, если не загружена."""
    if _config is None:
        logger.critical("Конфигурация не была загружена!")
        raise RuntimeError("Конфигурация не загружена. Запустите load_config() сначала.")
    return _config

def create_default_config():
     """Создает config.yaml с дефолтными значениями."""
     # Используем Pydantic модель для генерации дефолтных значений
     try:
         # Создаем экземпляр с дефолтными значениями (кроме обязательных)
         default_conf_model = AppConfig(
             llm=LLMConfig(
                 api_url="http://127.0.0.1:5005/api/v1/generate", # Обязательно указать
                 generation_params=LLMGenerationParams(), # Возьмет дефолты из модели
                 character=LLMCharacterConfig(
                     name="AI-Девушка", # Обязательно
                     persona="Описание персонажа по умолчанию." # Обязательно
                 )
             )
             # Добавить другие секции по мере необходимости
         )
         # Преобразуем Pydantic модель в словарь
         default_conf_dict = default_conf_model.model_dump()

         with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
             yaml.dump(default_conf_dict, f, allow_unicode=True, sort_keys=False, indent=2)
         logger.info(f"Создан файл конфигурации по умолчанию: {CONFIG_PATH}")
         logger.warning("!!! Пожалуйста, проверьте и отредактируйте config.yaml, особенно llm.api_url и llm.character.persona, затем перезапустите бота !!!")

     except Exception as e:
         logger.exception(f"Не удалось создать файл конфигурации по умолчанию:")


# Загружаем конфиг при импорте модуля (или можно вызвать вручную в main.py)
# load_config() # Закомментировано, лучше вызывать явно в main