"""Lógica pura: tradução de limites em comandos ``batt`` e leitura do status.

Sem efeitos colaterais — facilita testar sem tocar no hardware.
"""

from __future__ import annotations

import json
from typing import Any


def commands_to_activate(lower: int, upper: int) -> list[list[str]]:
    """Comandos ``batt`` para ligar o sailing mode entre ``lower`` e ``upper``.

    O ``batt`` expressa o piso como delta abaixo do topo, então
    ``lower-limit-delta = upper - lower``.
    """
    delta = upper - lower
    return [["limit", str(upper)], ["lower-limit-delta", str(delta)]]


def command_to_deactivate() -> list[str]:
    """Comando ``batt`` para voltar ao carregamento normal."""
    return ["disable"]


def parse_status(json_text: str) -> dict[str, Any]:
    """Normaliza o JSON de ``batt status --json``.

    O JSON do ``batt`` é aninhado (``battery.*``, ``charging.*``,
    ``configuration.*``); usamos ``or {}`` para tolerar seções ausentes/nulas.
    """
    data = json.loads(json_text)
    battery = data.get("battery") or {}
    charging = data.get("charging") or {}
    configuration = data.get("configuration") or {}
    return {
        "percent": battery.get("currentChargePercent"),
        "state": battery.get("state"),
        "plugged_in": charging.get("pluggedIn"),
        "enabled": configuration.get("enabled"),
        "upper": configuration.get("upperLimitPercent"),
        "lower": configuration.get("lowerLimitPercent"),
        "allow_charging": charging.get("allowCharging"),
    }


def format_title(status: dict[str, Any], badge: str | None = None) -> str:
    """Texto minimalista da barra de menus: ``"52%"`` (+ selo do modo, se ativo).

    Se ``badge`` for informado, usa-o; senão deriva do status (⛵ quando há
    limite ativo). Sem ícone de bateria, para ocupar menos espaço.
    """
    percent = status.get("percent")
    if badge is None:
        badge = "⛵" if status.get("enabled") else ""
    parts = []
    if percent is not None:
        parts.append(f"{percent}%")
    if badge:
        parts.append(badge)
    return " ".join(parts) if parts else "—"


# --- ciclo força-descarga (lógica pura) ------------------------------------
#
# Fases: "draining" (drenando via adapter disable) e "charging" (carregando).
# Ações: "drain" (cortar adaptador) e "charge" (religar adaptador).


def initial_force_phase(percent: int | None, lower: int, upper: int) -> str:
    """Fase inicial ao entrar no modo força-descarga."""
    if percent is None:
        return "charging"  # carga desconhecida: nunca começar drenando às cegas
    if percent <= lower:
        return "charging"
    return "draining"  # de qualquer ponto acima do piso, drena primeiro


def force_step(
    phase: str, percent: int | None, lower: int, upper: int
) -> tuple[str, str]:
    """Decide a próxima ``(fase, ação)`` do ciclo força-descarga.

    Segurança: com a carga desconhecida, nunca continua drenando — religa.
    """
    if percent is None:
        return (phase, "charge")
    if phase == "draining":
        if percent <= lower:
            return ("charging", "charge")
        return ("draining", "drain")
    # charging
    if percent >= upper:
        return ("draining", "drain")
    return ("charging", "charge")


def force_commands(
    action: str, adapter_disabled: bool | None
) -> list[tuple[str, tuple]]:
    """Comandos ``BattRunner`` para aplicar a ação do ciclo força-descarga.

    Retorna pares ``(método, args)``. Idempotente: nada a fazer se o adaptador
    já está no estado desejado.

    Importante: ``charge`` **levanta o limite** (``deactivate`` → carga livre).
    Só religar o adaptador não basta — o ``batt`` segura a carga via limite +
    maintain loop e ela trava no piso. Quem para no fim é o próprio app.
    """
    if action == "drain":
        if adapter_disabled is True:
            return []
        return [("adapter_disable", ())]
    # charge
    if adapter_disabled is False:
        return []
    return [("deactivate", ()), ("adapter_enable", ())]
