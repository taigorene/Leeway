"""Wrapper fino sobre a CLI ``batt`` — a única camada com efeitos colaterais.

A execução real é injetável (``runner``) para os testes não tocarem no hardware.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Any, Callable

from .engine import (
    command_to_deactivate,
    commands_to_activate,
    parse_status,
)

Runner = Callable[[list[str]], str]


class BattError(Exception):
    """Falha ao executar um comando ``batt`` (rc != 0 ou daemon indisponível)."""


class BattNotInstalled(BattError):
    """O binário ``batt`` não está instalado."""


class BattRunner:
    def __init__(self, binary: str = "batt", runner: Runner | None = None):
        self.binary = binary
        self._runner = runner or self._default_runner

    # -- execução -----------------------------------------------------------
    def _default_runner(self, args: list[str]) -> str:
        try:
            proc = subprocess.run(
                [self.binary, *args],
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            raise BattNotInstalled(f"`{self.binary}` não está instalado.") from exc
        if proc.returncode != 0:
            msg = proc.stderr.strip() or f"`batt {' '.join(args)}` falhou."
            raise BattError(msg)
        return proc.stdout

    def run(self, args: list[str]) -> str:
        return self._runner(args)

    # -- disponibilidade ----------------------------------------------------
    def available(self) -> bool:
        """True se o binário ``batt`` está no PATH."""
        return shutil.which(self.binary) is not None

    def daemon_ready(self) -> bool:
        """True se o daemon responde (consegue ler o status)."""
        try:
            self.run(["status", "--json"])
            return True
        except BattError:
            return False

    # -- estado e ações -----------------------------------------------------
    def status_json(self) -> str:
        return self.run(["status", "--json"])

    def status(self) -> dict[str, Any]:
        return parse_status(self.status_json())

    def activate(self, lower: int, upper: int) -> None:
        for args in commands_to_activate(lower, upper):
            self.run(args)

    def deactivate(self) -> None:
        self.run(command_to_deactivate())

    def set_limit(self, upper: int) -> None:
        """Define apenas o limite superior (backstop do modo força-descarga)."""
        self.run(["limit", str(upper)])

    def adapter_disable(self) -> None:
        """Corta a energia da tomada (força descarga, mesmo plugado)."""
        self.run(["adapter", "disable"])

    def adapter_enable(self) -> None:
        """Restaura a energia da tomada."""
        self.run(["adapter", "enable"])
