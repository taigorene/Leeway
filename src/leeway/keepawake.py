"""Mantém o Mac acordado via ``caffeinate -i`` enquanto estiver ativo.

Usado (opcionalmente) durante o modo força-descarga, para o ciclo não pausar
quando o Mac fica ocioso. O lançador é injetável para os testes.
"""

from __future__ import annotations

import subprocess
from typing import Callable


class KeepAwake:
    def __init__(self, launcher: Callable[[], object] | None = None):
        self._launcher = launcher or self._spawn
        self._proc = None

    @staticmethod
    def _spawn():
        # -i previne idle sleep (funciona também na bateria).
        return subprocess.Popen(["caffeinate", "-i"])

    @property
    def active(self) -> bool:
        return self._proc is not None

    def start(self) -> None:
        if self._proc is None:
            self._proc = self._launcher()

    def stop(self) -> None:
        proc = self._proc
        self._proc = None
        if proc is not None:
            try:
                proc.terminate()
            except Exception:
                pass
