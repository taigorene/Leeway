import json

import pytest

from leeway.batt import BattRunner, BattError, BattNotInstalled, resolve_batt


def test_resolve_batt_prefers_which():
    found = resolve_batt("batt", which=lambda b: "/x/batt", exists=lambda p: False)
    assert found == "/x/batt"


def test_resolve_batt_falls_back_to_homebrew_path():
    # PATH não tem batt (which=None), mas existe em /opt/homebrew/bin
    found = resolve_batt(
        "batt",
        which=lambda b: None,
        exists=lambda p: p == "/opt/homebrew/bin/batt",
    )
    assert found == "/opt/homebrew/bin/batt"


def test_resolve_batt_none_when_missing_everywhere():
    assert resolve_batt("batt", which=lambda b: None, exists=lambda p: False) is None


def recording_runner():
    calls = []

    def run(args):
        calls.append(args)
        return ""

    return calls, run


def test_activate_runs_commands_in_order():
    calls, run = recording_runner()
    BattRunner(runner=run).activate(20, 80)
    assert calls == [["limit", "80"], ["lower-limit-delta", "60"]]


def test_deactivate_runs_disable():
    calls, run = recording_runner()
    BattRunner(runner=run).deactivate()
    assert calls == [["disable"]]


def test_status_parses_json():
    payload = json.dumps(
        {"battery": {"currentChargePercent": 73}, "configuration": {"enabled": True}}
    )
    runner = BattRunner(runner=lambda args: payload)
    status = runner.status()
    assert status["percent"] == 73
    assert status["enabled"] is True


def test_daemon_ready_true_when_status_succeeds():
    runner = BattRunner(runner=lambda args: "{}")
    assert runner.daemon_ready() is True


def test_daemon_ready_false_when_run_raises():
    def boom(args):
        raise BattError("daemon não está rodando")

    assert BattRunner(runner=boom).daemon_ready() is False


def test_set_limit_runs_limit_command():
    calls, run = recording_runner()
    BattRunner(runner=run).set_limit(80)
    assert calls == [["limit", "80"]]


def test_adapter_disable_then_enable():
    calls, run = recording_runner()
    r = BattRunner(runner=run)
    r.adapter_disable()
    r.adapter_enable()
    assert calls == [["adapter", "disable"], ["adapter", "enable"]]


def test_run_missing_binary_raises_not_installed():
    # binário inexistente: o subprocess lança FileNotFoundError, que deve
    # virar BattNotInstalled (subclasse de BattError) para não furar o cleanup.
    with pytest.raises(BattNotInstalled):
        BattRunner(binary="batt-nao-existe-xyz").status_json()
