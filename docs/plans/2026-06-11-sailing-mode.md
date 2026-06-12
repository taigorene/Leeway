# Sailing Mode — Plano de Implementação

> **For Claude:** REQUIRED SUB-SKILL: usar superpowers:test-driven-development nas partes puras.

**Goal:** App de barra de menus no macOS (Apple Silicon) que mantém a bateria "navegando" entre um limite inferior (início da carga, padrão 20%) e superior (fim da carga, padrão 80%), usando o `batt` como motor. Ao sair do app, a carga volta ao normal.

**Architecture:** O `batt` (daemon root via launchd) faz todo o trabalho de SMC. Nosso app Python (`rumps`) é uma interface fina que lê `batt status --json` e aplica/retira limites via CLI (sem sudo, graças a `--allow-non-root-access`). Lógica pura (validação, tradução de thresholds → comandos, parse do status) fica separada das chamadas de subprocess para ser 100% testável.

**Tech Stack:** Python 3 (venv), `rumps` (barra de menus), `pytest` (testes), `batt` 0.7.3 (Homebrew), `subprocess` para a CLI.

---

## Comandos `batt` confirmados na fonte

- `sudo batt install --allow-non-root-access` — instala o daemon (único passo com senha).
- `batt limit <upper>` — limite superior (10–100).
- `batt lower-limit-delta <delta>` — piso = `upper − delta` (sem cap máximo no delta).
- `batt status --json` — campos: `currentChargePercent`, `state`, `pluggedIn`, `enabled`, `upperLimitPercent`, `lowerLimitPercent`, `allowCharging`.
- `batt disable` — volta ao carregamento normal.
- `sudo batt uninstall` — remove o daemon.

## Estrutura de arquivos

```
sailing-mode/
├── README.md
├── install.sh                      # setup one-shot (brew, batt, venv)
├── Makefile                        # make run / make test
├── requirements.txt                # rumps
├── requirements-dev.txt            # pytest
├── bin/sailing-mode                # launcher (venv + app)
├── src/sailing_mode/
│   ├── __init__.py
│   ├── config.py                   # Settings: load/save/validate (puro + IO)
│   ├── engine.py                   # puro: thresholds→comandos, parse status, título
│   ├── batt.py                     # BattRunner: wrapper fino de subprocess
│   └── app.py                      # rumps app (fia tudo)
└── tests/
    ├── test_config.py
    └── test_engine.py
```

## Regras de validação (centralizadas em `config.py`)

- `upper`: inteiro em [10, 100].
- `lower`: inteiro em [5, upper-1].
- `lower >= upper` → erro.
- valor não-inteiro / fora de faixa → `ValueError` com mensagem clara.

---

## Task 1: Scaffolding do projeto

**Files:**
- Create: `requirements.txt`, `requirements-dev.txt`, `src/sailing_mode/__init__.py`, `tests/__init__.py`, `pytest.ini`, `.gitignore`

**Passos:**
1. `.gitignore` com `.venv/`, `__pycache__/`, `*.pyc`.
2. `requirements.txt` → `rumps>=0.4.0`. `requirements-dev.txt` → `pytest>=8`.
3. `pytest.ini` apontando `pythonpath = src`.
4. Commit: `chore: project scaffolding`.

## Task 2: `config.py` — validação (TDD)

**Files:**
- Create: `src/sailing_mode/config.py`, `tests/test_config.py`

**Step 1 — testes que falham:**
```python
import pytest
from sailing_mode.config import Settings, validate

def test_defaults():
    s = Settings()
    assert (s.lower, s.upper) == (20, 80)

def test_valid_passes():
    validate(20, 80)  # não levanta

@pytest.mark.parametrize("lo,hi", [(80, 80), (81, 80), (4, 80), (20, 9), (20, 101)])
def test_invalid_raises(lo, hi):
    with pytest.raises(ValueError):
        validate(lo, hi)
```

**Step 2:** `pytest -q` → FAIL (import).

**Step 3 — implementar:** `Settings` dataclass (lower=20, upper=80) + `validate(lower, upper)` aplicando as regras acima.

**Step 4:** `pytest -q` → PASS.

**Step 5:** Commit `feat: settings validation`.

## Task 3: `config.py` — load/save (TDD)

**Step 1 — teste:** salvar e recarregar via `tmp_path` (parametrizar `CONFIG_PATH`); arquivo ausente → defaults; JSON corrompido → defaults.

**Step 2:** FAIL.

**Step 3:** `load(path=...)` e `save(settings, path=...)`; `mkdir -p`; try/except → defaults em erro; valida no load, cai pra defaults se inválido.

**Step 4:** PASS. **Step 5:** Commit `feat: settings persistence`.

## Task 4: `engine.py` — tradução de comandos (TDD)

**Step 1 — teste:**
```python
from sailing_mode.engine import commands_to_activate, command_to_deactivate

def test_activate():
    assert commands_to_activate(20, 80) == [["limit", "80"], ["lower-limit-delta", "60"]]

def test_deactivate():
    assert command_to_deactivate() == ["disable"]
```

**Step 2:** FAIL. **Step 3:** implementar (delta = upper-lower). **Step 4:** PASS. **Step 5:** Commit `feat: command translation`.

## Task 5: `engine.py` — parse de status + título (TDD)

**Step 1 — teste:** dado o JSON do `batt`, `parse_status` retorna dict normalizado (`percent`, `state`, `plugged_in`, `enabled`, `upper`, `lower`); tolerante a chaves ausentes. `format_title(status)` → ex. `"🔋 52% ⛵"` quando enabled, `"🔋 52%"` quando não.

**Step 2:** FAIL. **Step 3:** implementar com `.get()` tolerante. **Step 4:** PASS. **Step 5:** Commit `feat: status parsing + title`.

## Task 6: `batt.py` — BattRunner (wrapper fino, sem teste de hardware)

**Files:** Create `src/sailing_mode/batt.py`

- `available()` via `shutil.which`.
- `daemon_ready()` → tenta `status --json`, captura erro.
- `run(args)` → `subprocess.run`, levanta `BattError(stderr)` se rc≠0.
- `status_json()`, `activate(lower, upper)` (usa `engine.commands_to_activate`), `deactivate()`.
- Erros tipados: `BattError`, `BattNotInstalled`.
- Teste leve com `subprocess` mockado para `activate` chamar os comandos certos na ordem certa.

Commit `feat: batt runner`.

## Task 7: `app.py` — barra de menus (rumps)

**Files:** Create `src/sailing_mode/app.py`

- Classe `SailingModeApp(rumps.App)`, título inicial `🔋`.
- Menu: linha de status (desabilitada), separador, toggle "Sailing mode" (`rumps.MenuItem` com state), "Definir início (%)…", "Definir fim (%)…", separador, "Abrir setup…" (quando daemon ausente), Quit.
- `rumps.Timer(self.refresh, 15)` → lê status, atualiza título e linha.
- Toggle ON → valida + `batt.activate(lower, upper)`; OFF → `batt.deactivate()`.
- "Definir…" → `rumps.Window` com valor atual, valida via `config.validate`, salva, reaplica se ativo.
- `@rumps.clicked("Quit")` → `batt.deactivate()` então `rumps.quit_application()`. Também tratar saída limpa.
- Daemon ausente/erro → linha de status vira aviso e item "Abrir setup…".

Commit `feat: menu bar app`.

## Task 8: Launcher, install.sh, Makefile, README

- `bin/sailing-mode`: cria/ativa `.venv`, garante deps, roda `python -m sailing_mode.app`.
- `install.sh`: checa Apple Silicon; `brew install batt`; instrui `sudo batt install --allow-non-root-access`; cria venv + deps.
- `Makefile`: `run`, `test`, `setup`.
- `README.md`: requisitos, setup (com nota sobre a senha do sudo), uso, "sair = volta ao normal", limitação de verificação real de hardware, como desinstalar (`sudo batt uninstall`).

Commit `docs: readme + launcher + install`.

## Task 9: Verificação final

- `make test` → todos passam.
- `python -c "import sailing_mode.app"` (com rumps instalado) → importa sem erro.
- Smoke manual: rodar o app, ver o ícone, alternar toggle (requer `batt` instalado — passo do usuário com senha).
- Usar superpowers:verification-before-completion antes de declarar pronto.

---

## Notas de honestidade

- Não dá pra verificar 100% o ciclo real de carga sem plugar/desplugar e esperar; `sudo batt install` é interativo (senha do usuário).
- Se o app crashar sem Quit, o `batt` mantém a proteção (daemon persiste) — mais seguro; o app sincroniza o toggle ao reabrir.
- `--allow-non-root-access` deixa qualquer usuário local mudar limites; aceitável em laptop pessoal de usuário único.
