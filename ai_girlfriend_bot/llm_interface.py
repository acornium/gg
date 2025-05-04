# llm_interface.py
import httpx
from loguru import logger
from typing import Optional, Dict, Any

# Таймауты: 10 сек на подключение, 5 минут (300 сек) на чтение ответа
_DEFAULT_TIMEOUT = httpx.Timeout(10.0, read=300.0)

async def get_llm_response(
    prompt: str,
    api_url: str,
    generation_params: Dict[str, Any]
) -> Optional[str]:
    """
    Асинхронно отправляет промпт к API LLM (Oobabooga-совместимому)
    и возвращает сгенерированный текст.

    Args:
        prompt: Полный текст промпта для модели.
        api_url: URL API LLM.
        generation_params: Словарь с параметрами генерации (max_new_tokens и т.д.).

    Returns:
        Сгенерированный текст или None в случае ошибки.
    """
    # Формируем payload для Oobabooga API v1 /generate
    # ВНИМАНИЕ: Формат может отличаться для других бэкендов!
    payload = {
        "prompt": prompt,
        **generation_params # Распаковываем параметры из конфига
        # Некоторые API могут требовать параметры внутри 'params' или иначе
        # "max_new_tokens": generation_params.get("max_new_tokens"),
        # "temperature": generation_params.get("temperature"),
        # ... и т.д.
    }
    # Удаляем None значения из параметров, если они там случайно оказались
    payload = {k: v for k, v in payload.items() if v is not None}

    try:
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            logger.debug(f"Отправка запроса на LLM API: {api_url}")
            # Логируем только часть промпта для безопасности и краткости
            log_prompt = prompt[:300] + "..." if len(prompt) > 300 else prompt
            logger.trace(f"Промпт (начало): {log_prompt}")
            logger.trace(f"Параметры генерации: {generation_params}")

            response = await client.post(api_url, json=payload)

            # Логируем статус и начало ответа для отладки
            logger.debug(f"Статус ответа от LLM API: {response.status_code}")
            response_text_preview = response.text[:300] + "..." if len(response.text) > 300 else response.text
            logger.trace(f"Тело ответа (начало): {response_text_preview}")

            response.raise_for_status() # Выбросит исключение для кодов 4xx/5xx

            result = response.json()

            # Парсинг ответа - СПЕЦИФИЧНО ДЛЯ OOBABOOGA API v1 /generate
            # Проверяем наличие ключей перед доступом
            if "results" in result and isinstance(result["results"], list) and len(result["results"]) > 0:
                first_result = result["results"][0]
                if "text" in first_result:
                    generated_text = first_result["text"].strip()
                    # Очистка от возможных артефактов в начале/конце
                    # generated_text = generated_text.replace("</s>", "").strip()
                    logger.debug(f"Успешно получен и обработан ответ от LLM.")
                    logger.trace(f"Сгенерированный текст: {generated_text}")
                    return generated_text
                else:
                     logger.warning("Ключ 'text' не найден в первом результате ответа LLM API.")
                     logger.trace(f"Полный результат: {result}")
                     return None
            else:
                logger.warning(f"Ключ 'results' не найден или пуст в ответе LLM API.")
                logger.trace(f"Полный ответ: {result}")
                return None

    except httpx.TimeoutException:
        logger.error(f"Таймаут при запросе к LLM API: {api_url}")
        return None
    except httpx.RequestError as e:
        # Ошибки сети, DNS и т.д.
        logger.error(f"Ошибка сети при запросе к LLM API ({api_url}): {e}")
        return None
    except httpx.HTTPStatusError as e:
        # Ошибки 4xx (например, 404 Not Found, 422 Unprocessable Entity) или 5xx (ошибка сервера)
        logger.error(f"Ошибка HTTP {e.response.status_code} при запросе к LLM API ({api_url}). Ответ: {e.response.text[:500]}")
        return None
    except Exception as e:
        # Любые другие ошибки (например, ошибка парсинга JSON, если ответ невалиден)
        logger.exception(f"Неизвестная ошибка при обращении к LLM API:")
        return None