# models_config.py
from pydantic import BaseModel, HttpUrl, Field, field_validator
from typing import List, Optional

class LLMGenerationParams(BaseModel):
    # Используем Field для дефолтных значений и документации
    max_new_tokens: int = Field(default=250, description="Max tokens in response")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0) # ge/le - границы значений
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    top_k: int = Field(default=0, ge=0)
    repetition_penalty: float = Field(default=1.1, ge=1.0)
    do_sample: bool = Field(default=True)
    stopping_strings: Optional[List[str]] = Field(default=None)

    # Могут быть и другие параметры, Pydantic по умолчанию игнорирует лишние,
    # но если нужно их принимать, можно добавить:
    # class Config:
    #     extra = 'allow'

class LLMCharacterConfig(BaseModel):
    name: str
    persona: str # Описание персонажа, может быть многострочным

class LLMConfig(BaseModel):
    api_url: str # Пока строка, т.к. может быть не http (напр. Ollama)
    generation_params: LLMGenerationParams
    character: LLMCharacterConfig

    @field_validator('api_url')
    @classmethod
    def check_api_url(cls, v: str):
        # Простая проверка, что URL не пустой
        if not v:
            raise ValueError('LLM API URL не может быть пустым')
        # Можно добавить более сложную валидацию URL, если нужно
        # Например, через `HttpUrl` из Pydantic, если уверены, что всегда http/https
        # from pydantic import HttpUrl
        # try:
        #     HttpUrl(v)
        # except Exception:
        #      raise ValueError(f"Невалидный URL: {v}")
        return v


class AppConfig(BaseModel):
    llm: LLMConfig
    # Сюда добавим конфиг для SD, DB и т.д. в будущем