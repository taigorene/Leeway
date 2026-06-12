import json

import pytest

from leeway.config import Settings, validate, load, save


def test_defaults():
    s = Settings()
    assert (s.lower, s.upper) == (20, 80)


def test_valid_passes():
    validate(20, 80)  # não deve levantar


@pytest.mark.parametrize(
    "lo,hi",
    [
        (80, 80),   # lower == upper
        (81, 80),   # lower > upper
        (4, 80),    # lower abaixo do mínimo (5)
        (20, 9),    # upper abaixo do mínimo (10)
        (20, 101),  # upper acima do máximo (100)
    ],
)
def test_invalid_raises(lo, hi):
    with pytest.raises(ValueError):
        validate(lo, hi)


def test_save_then_load_roundtrip(tmp_path):
    path = tmp_path / "config.json"
    save(Settings(lower=15, upper=85), path=path)
    loaded = load(path=path)
    assert (loaded.lower, loaded.upper) == (15, 85)


def test_load_missing_file_returns_defaults(tmp_path):
    loaded = load(path=tmp_path / "naoexiste.json")
    assert (loaded.lower, loaded.upper) == (20, 80)


def test_load_corrupt_file_returns_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{ isso não é json válido")
    loaded = load(path=path)
    assert (loaded.lower, loaded.upper) == (20, 80)


def test_load_invalid_values_returns_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"lower": 90, "upper": 80}))
    loaded = load(path=path)
    assert (loaded.lower, loaded.upper) == (20, 80)


def test_keep_awake_defaults_false():
    assert Settings().keep_awake is False


def test_save_load_keep_awake_roundtrip(tmp_path):
    path = tmp_path / "config.json"
    save(Settings(lower=20, upper=80, keep_awake=True), path=path)
    assert load(path=path).keep_awake is True


def test_load_missing_keep_awake_defaults_false(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"lower": 20, "upper": 80}))
    assert load(path=path).keep_awake is False
