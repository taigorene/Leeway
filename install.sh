#!/usr/bin/env bash
# Setup do Leeway: verifica pré-requisitos, instala o batt e o venv.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Leeway — setup"

# 1. Apple Silicon
if [ "$(uname -m)" != "arm64" ]; then
  echo "ERRO: este app funciona só em Macs Apple Silicon (arm64)." >&2
  exit 1
fi

# 2. Homebrew
if ! command -v brew >/dev/null 2>&1; then
  echo "ERRO: Homebrew não encontrado. Instale em https://brew.sh e rode de novo." >&2
  exit 1
fi

# 3. batt (motor de controle de carga)
if ! command -v batt >/dev/null 2>&1; then
  echo "==> Instalando batt via Homebrew…"
  brew install batt
else
  echo "==> batt já instalado."
fi

# 4. venv + dependências Python
echo "==> Criando venv e instalando dependências…"
python3 -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/pip" install -q --upgrade pip
"$ROOT/.venv/bin/pip" install -q -r "$ROOT/requirements.txt"

# 5. Serviço de fundo do batt (LaunchDaemon de sistema).
#    A versão Homebrew do batt removeu o `batt install`, e o `brew services`
#    do Homebrew 6.x não reconhece o serviço root da fórmula (label custom +
#    require_root + plist externo sem diretiva `run`). Então carregamos o plist
#    do próprio batt — que já inclui --always-allow-non-root-access — direto
#    via launchctl. É exatamente o que o `batt install` faria por baixo.
PLIST_SRC="$(brew --prefix batt)/cc.chlc.batt.plist"
PLIST_DST="/Library/LaunchDaemons/cc.chlc.batt.plist"

echo "==> Instalando o serviço de fundo do batt (vai pedir sua senha)…"
sudo cp "$PLIST_SRC" "$PLIST_DST"
sudo chown root:wheel "$PLIST_DST"
sudo launchctl bootout system/cc.chlc.batt 2>/dev/null || true
sudo launchctl bootstrap system "$PLIST_DST" || true

echo "==> Verificando o daemon…"
daemon_ok=""
for _ in 1 2 3 4 5; do
  if batt status >/dev/null 2>&1; then daemon_ok=1; break; fi
  sleep 1
done

if [ -n "$daemon_ok" ]; then
  cat <<MSG

==> Tudo pronto! O daemon do batt está rodando (com acesso não-root).

Inicie o app com:

    ./bin/leeway

Para remover o serviço depois:
    sudo launchctl bootout system/cc.chlc.batt && sudo rm "$PLIST_DST"
MSG
else
  cat <<'MSG'

AVISO: o daemon do batt não respondeu a tempo.
Veja o log em /tmp/batt.log e tente novamente:

    batt status
MSG
fi
