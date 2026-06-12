import json

from leeway.engine import (
    commands_to_activate,
    command_to_deactivate,
    parse_status,
    format_title,
    initial_force_phase,
    force_step,
    force_commands,
)


def test_commands_to_activate_computes_delta():
    assert commands_to_activate(20, 80) == [
        ["limit", "80"],
        ["lower-limit-delta", "60"],
    ]


def test_command_to_deactivate():
    assert command_to_deactivate() == ["disable"]


# Estrutura real de `batt status --json` (campos aninhados).
SAMPLE = json.dumps(
    {
        "charging": {"allowCharging": False, "useAdapter": True, "pluggedIn": False},
        "battery": {
            "currentChargePercent": 52,
            "state": "discharging",
            "chargeRateWatts": -21.7,
        },
        "configuration": {
            "enabled": True,
            "upperLimitPercent": 80,
            "lowerLimitPercent": 20,
            "allowNonRootAccess": True,
        },
    }
)


def test_parse_status_extracts_fields():
    s = parse_status(SAMPLE)
    assert s["percent"] == 52
    assert s["state"] == "discharging"
    assert s["plugged_in"] is False
    assert s["enabled"] is True
    assert s["upper"] == 80
    assert s["lower"] == 20


def test_parse_status_tolerates_missing_keys():
    s = parse_status("{}")
    assert s["percent"] is None
    assert s["enabled"] is None


def test_format_title_active_shows_sail():
    title = format_title({"percent": 52, "enabled": True})
    assert "52%" in title and "⛵" in title


def test_format_title_inactive_no_sail():
    title = format_title({"percent": 52, "enabled": False})
    assert "52%" in title and "⛵" not in title


def test_format_title_minimalist_no_battery_emoji():
    # minimalista: só o número (sem o 🔋), badge só quando ativo
    assert format_title({"percent": 52, "enabled": False}) == "52%"


def test_format_title_handles_unknown_percent():
    assert format_title({"percent": None, "enabled": False}) == "—"


def test_format_title_uses_explicit_badge():
    assert format_title({"percent": 52}, badge="🔁") == "52% 🔁"


def test_format_title_empty_badge_has_no_suffix():
    assert format_title({"percent": 52}, badge="") == "52%"


# --- ciclo força-descarga (lógica pura) ------------------------------------


def test_initial_force_phase_above_lower_drains():
    # plugado a 37% com piso 20: começa drenando rumo aos 20 (intenção do usuário)
    assert initial_force_phase(37, 20, 80) == "draining"


def test_initial_force_phase_at_or_below_lower_charges():
    assert initial_force_phase(20, 20, 80) == "charging"
    assert initial_force_phase(15, 20, 80) == "charging"


def test_initial_force_phase_unknown_is_safe_charging():
    assert initial_force_phase(None, 20, 80) == "charging"


def test_force_step_draining_continues_above_lower():
    assert force_step("draining", 50, 20, 80) == ("draining", "drain")


def test_force_step_draining_flips_to_charge_at_lower():
    assert force_step("draining", 20, 20, 80) == ("charging", "charge")


def test_force_step_charging_continues_below_upper():
    assert force_step("charging", 50, 20, 80) == ("charging", "charge")


def test_force_step_charging_flips_to_drain_at_upper():
    assert force_step("charging", 80, 20, 80) == ("draining", "drain")


def test_force_step_unknown_percent_stops_draining():
    # carga desconhecida: nunca continuar drenando às cegas -> religar (charge)
    assert force_step("draining", None, 20, 80) == ("draining", "charge")


# --- comandos batt a partir da ação do ciclo (lógica pura) ------------------


def test_force_commands_charge_lifts_limit_and_enables_adapter():
    # CARGA precisa LEVANTAR o limite (deactivate), não só religar o adaptador,
    # senão o batt segura a carga (chargingEnabled=false) e trava no piso.
    assert force_commands("charge", True) == [
        ("deactivate", ()),
        ("adapter_enable", ()),
    ]


def test_force_commands_drain_disables_adapter():
    assert force_commands("drain", False) == [("adapter_disable", ())]


def test_force_commands_noop_when_already_in_state():
    assert force_commands("drain", True) == []
    assert force_commands("charge", False) == []


def test_force_commands_initial_unknown_state_applies():
    assert force_commands("charge", None) == [
        ("deactivate", ()),
        ("adapter_enable", ()),
    ]
    assert force_commands("drain", None) == [("adapter_disable", ())]
