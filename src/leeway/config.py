"""Configuração dos limites de carga (início/fim) e sua persistência."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_LOWER = 20
DEFAULT_UPPER = 80

MIN_LOWER = 5
MIN_UPPER = 10
MAX_UPPER = 100

CONFIG_PATH = Path(
    os.path.expanduser("~/.config/leeway/config.json")
)


@dataclass
class Settings:
    """Limites de carga (``lower``/``upper``, em %) e preferências."""

    lower: int = DEFAULT_LOWER
    upper: int = DEFAULT_UPPER
    keep_awake: bool = False


def validate(lower: int, upper: int) -> None:
    """Valida os limites; levanta ``ValueError`` com mensagem clara se inválidos."""
    if not isinstance(lower, int) or not isinstance(upper, int):
        raise ValueError("Os limites precisam ser números inteiros.")
    if not (MIN_UPPER <= upper <= MAX_UPPER):
        raise ValueError(
            f"O fim da carga precisa estar entre {MIN_UPPER}% e {MAX_UPPER}%."
        )
    if lower < MIN_LOWER:
        raise ValueError(f"O início da carga não pode ser menor que {MIN_LOWER}%.")
    if lower >= upper:
        raise ValueError("O início da carga precisa ser menor que o fim.")


def load(path: Path = CONFIG_PATH) -> Settings:
    """Carrega os limites; em qualquer erro (ausente/corrompido/inválido) usa defaults."""
    path = Path(path)
    try:
        data = json.loads(path.read_text())
        lower = int(data["lower"])
        upper = int(data["upper"])
        validate(lower, upper)
        keep_awake = bool(data.get("keep_awake", False))
        return Settings(lower=lower, upper=upper, keep_awake=keep_awake)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return Settings()


def save(settings: Settings, path: Path = CONFIG_PATH) -> None:
    """Persiste os limites em disco, criando o diretório se necessário."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "lower": settings.lower,
                "upper": settings.upper,
                "keep_awake": settings.keep_awake,
            }
        )
    )
