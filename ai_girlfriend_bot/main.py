# main.py
import asyncio
import os
from dotenv import load_dotenv
from loguru import logger

from aiogram import Bot, Dispatcher, types, F, enums
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties

# Импортируем наши модули
from config_loader import load_config, get_config, AppConfig
from llm_interface import get_llm_response

# --- Загрузка конфигурации ---
load_dotenv() # Загружаем переменные из .env файла
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Загружаем основной конфиг ИЗ ФАЙЛА YAML
# Вызываем load_config() здесь, чтобы убедиться, что конфиг загружен до инициализации бота
config: AppConfig = load_config() # Загружаем конфиг при старте

if not BOT_TOKEN:
    logger.critical("!!! Ошибка: BOT_TOKEN не найден в .env файле! Бот не может стартовать.")
    exit()
if not config:
    logger.critical("!!! Ошибка: Не удалось загрузить конфигурацию из config.yaml! Бот не может стартовать.")
    # Возможно, config_loader уже вывел сообщение о создании дефолтного
    exit()

# --- Настройка логирования (можно вынести в отдельный модуль) ---
# Убедимся, что папка logs существует
os.makedirs("logs", exist_ok=True)
logger.add(
    "logs/bot_log_{time}.log", # Имя файла с датой/временем
    rotation="10 MB",          # Ротация по размеру
    retention="10 days",       # Хранить логи 10 дней
    compression="zip",         # Сжимать старые логи
    level="DEBUG",             # Уровень логирования для файла
    encoding='utf-8'           # Кодировка
)
# Добавляем вывод логов в консоль с уровнем INFO
logger.add(lambda msg: print(msg, end=''), level="INFO", format="{message}")
logger.info("Логирование настроено.")


# --- Инициализация бота и диспетчера ---
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=enums.ParseMode.HTML))
dp = Dispatcher()

# --- Формирование промпта ---
def create_llm_prompt(user_input: str, user_name: str) -> str:
    """
    Формирует промпт для LLM, подставляя данные из конфига и ввода пользователя.
    (Пока без истории)
    """
    cfg = get_config() # Получаем актуальный конфиг
    # Подставляем имя пользователя в персону, если есть плейсхолдер {user_name}
    try:
        persona = cfg.llm.character.persona.format(user_name=user_name)
    except KeyError:
        logger.warning("Плейсхолдер {user_name} не найден в persona конфига. Использую как есть.")
        persona = cfg.llm.character.persona

    char_name = cfg.llm.character.name

    # !!! ВАЖНО: Структура промпта ОЧЕНЬ СИЛЬНО зависит от модели !!!
    # Этот формат (System/User/Assistant) - пример для ChatML-подобных моделей.
    # Для других моделей (Alpaca, Vicuna, Llama-Chat) формат будет другим.
    # Возможно, Oobabooga сам преобразует формат, если указать правильный
    # 'instruction_template' или 'mode' через API (это продвинутая настройка).
    # Пока сделаем простой текстовый формат:
    # prompt = f"{persona}\n\nUser: {user_input}\n{char_name}:"

    # Пример формата ChatML (если ваша модель его понимает):
    # Убедитесь, что токены <|im_start|> и <|im_end|> соответствуют вашей модели
    prompt = f"""<|im_start|>system
{persona}<|im_end|>
<|im_start|>user
{user_input}<|im_end|>
<|im_start|>assistant
{char_name}: """ # Модель должна продолжить после "Имя:"

    # Альтернатива: простой формат (раскомментируйте, если ChatML не подходит)
    # prompt = f"""{persona}
    #
    # ### Пользователь:
    # {user_input}
    #
    # ### {char_name}:
    # """

    # Проверьте документацию вашей модели или настройки Oobabooga!
    logger.trace(f"Сформирован промпт (начало): {prompt[:300]}...")
    return prompt

# --- Обработчики (хэндлеры) ---

@dp.message(CommandStart())
async def handle_start(message: types.Message):
    """Обработчик команды /start"""
    user_name = message.from_user.full_name
    user_id = message.from_user.id
    logger.info(f"Пользователь {user_name} (ID: {user_id}) запустил бота командой /start.")
    # Приветствие с использованием имени из конфига
    char_name = get_config().llm.character.name
    await message.answer(f"Привет, <b>{user_name}</b>! Я <b>{char_name}</b>. Готова пообщаться.")

@dp.message(F.text)
async def handle_text_message(message: types.Message):
    """Обработчик текстовых сообщений для общения с LLM"""
    user_name = message.from_user.full_name
    user_id = message.from_user.id
    text = message.text
    logger.info(f"Получено сообщение от {user_name} (ID: {user_id}): '{text}'")

    # Показываем индикатор "печатает..."
    try:
        await bot.send_chat_action(chat_id=message.chat.id, action=enums.ChatAction.TYPING)
    except Exception as e:
        # Ошибки отправки статуса не критичны, просто логируем
        logger.warning(f"Не удалось отправить chat_action TYPING: {e}")


    # Получаем текущий конфиг
    try:
        cfg = get_config()
        llm_config = cfg.llm
    except Exception as e:
        logger.exception("Критическая ошибка при получении конфига во время обработки сообщения:")
        await message.reply("Произошла внутренняя ошибка конфигурации. Сообщите администратору.")
        return

    # Формируем промпт
    try:
        prompt = create_llm_prompt(user_input=text, user_name=user_name)
    except Exception as e:
        logger.exception("Ошибка при формировании промпта:")
        await message.reply("Произошла внутренняя ошибка при подготовке запроса.")
        return

    # Получаем ответ от LLM
    # Передаем параметры генерации как словарь
    generation_params_dict = llm_config.generation_params.model_dump(exclude_none=True) # Исключаем None

    llm_reply = await get_llm_response(
        prompt=prompt,
        api_url=str(llm_config.api_url), # Преобразуем URL в строку на всякий случай
        generation_params=generation_params_dict
    )

    if llm_reply:
        logger.info(f"Ответ LLM для {user_name} (ID: {user_id}): '{llm_reply[:100]}...'")
        # Очистка ответа (если необходимо)
        char_name = llm_config.character.name
        # Убираем имя персонажа, если модель его дублирует в начале (с двоеточием или без)
        prefixes_to_remove = [f"{char_name}:", f"{char_name} :", char_name]
        for prefix in prefixes_to_remove:
             if llm_reply.startswith(prefix):
                  llm_reply = llm_reply[len(prefix):].strip()
                  break # Удалили один раз, выходим

        # Убираем возможные стоп-фразы в конце, если API их не убрал
        stopping_strings = generation_params_dict.get("stopping_strings", [])
        if stopping_strings: # Убедимся, что список не None
            for stop_word in stopping_strings:
                 if stop_word and llm_reply.endswith(stop_word): # Проверяем, что stop_word не пустой
                      llm_reply = llm_reply[:-len(stop_word)].rstrip()
                      logger.debug(f"Удалено стоп-слово '{stop_word}' из конца ответа.")

        # Проверяем, не пустой ли ответ после очистки
        if not llm_reply:
             logger.warning("Ответ LLM стал пустым после очистки.")
             await message.reply("Модель сгенерировала пустой ответ. Попробуйте переформулировать.")
        else:
            # Отправляем очищенный ответ
             try:
                  await message.reply(llm_reply)
             except Exception as e:
                  logger.error(f"Ошибка отправки ответа LLM в Telegram: {e}")
                  await message.reply("Не удалось отправить ответ. Возможно, он слишком длинный или содержит некорректные символы.")

    else:
        logger.warning(f"Не удалось получить ответ от LLM для пользователя {user_name} (ID: {user_id}).")
        await message.reply("Произошла ошибка при генерации ответа на стороне LLM. Попробуйте повторить запрос позже или свяжитесь с администратором, если проблема повторяется.")

# --- Основная функция запуска ---
async def main():
    logger.info("Запуск бота...")
    # Пропускаем старые апдейты
    await bot.delete_webhook(drop_pending_updates=True)
    # Запускаем polling
    logger.info("Polling запущен. Бот готов к работе.")
    await dp.start_polling(bot)
    # Этот код выполнится после остановки polling (например, по Ctrl+C)
    logger.info("Polling остановлен.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен вручную (KeyboardInterrupt/SystemExit).")
    except Exception as e:
        # Логируем любую необработанную ошибку перед выходом
        logger.exception("Произошла критическая неперехваченная ошибка на верхнем уровне:")
    finally:
        logger.info("Завершение работы бота.")