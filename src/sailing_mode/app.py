"""App de barra de menus com 3 modos de carga, usando o ``batt`` como motor.

Modos:
- ``off``     — carga normal do macOS.
- ``sailing`` — para aos 80% e só recarrega aos 20% pelo uso (não força nada).
- ``force``   — ciclo ativo: drena (corta o adaptador) até 20% e recarrega até 80%.

Toda a lógica testável vive em :mod:`config`, :mod:`engine` e :mod:`batt`.
Aqui é a cola com o ``rumps`` + a rede de segurança do modo força-descarga.
"""

from __future__ import annotations

import atexit
import signal

import rumps

from .batt import BattError, BattRunner
from .config import load, save, validate
from .engine import format_title, force_step, initial_force_phase

REFRESH_SECONDS = 15

STATE_PT = {
    "charging": "carregando",
    "discharging": "descarregando",
    "notCharging": "carga pausada",
    "full": "cheia",
}

MODE_BADGES = {"off": "", "sailing": "⛵", "force": "🔁"}


class SailingModeApp(rumps.App):
    def __init__(self, batt: BattRunner | None = None):
        super().__init__("Sailing Mode", title="🔋", quit_button=None)
        self.batt = batt or BattRunner()
        self.settings = load()
        self.mode = "off"
        self._force_phase = "charging"
        self._adapter_disabled = False

        self.status_item = rumps.MenuItem("Verificando…")
        self.off_item = rumps.MenuItem(
            "Desligado (carga normal)", callback=self.on_off
        )
        self.sailing_item = rumps.MenuItem(
            "Sailing (segura em 80%)", callback=self.on_sailing
        )
        self.force_item = rumps.MenuItem(
            "Forçar descarga (ciclo 20–80%)", callback=self.on_force
        )
        self.set_lower_item = rumps.MenuItem("", callback=self.on_set_lower)
        self.set_upper_item = rumps.MenuItem("", callback=self.on_set_upper)
        self.setup_item = rumps.MenuItem(
            "Como instalar / atualizar o batt…", callback=self.on_setup
        )
        self.quit_item = rumps.MenuItem(
            "Sair (volta ao normal)", callback=self.on_quit
        )

        self.menu = [
            self.status_item,
            None,
            self.off_item,
            self.sailing_item,
            self.force_item,
            None,
            self.set_lower_item,
            self.set_upper_item,
            None,
            self.setup_item,
            self.quit_item,
        ]
        self._update_threshold_labels()
        self._update_mode_marks()

        # Segurança ao iniciar: garante estado normal (limpa um adaptador que
        # possa ter ficado cortado por um encerramento anterior).
        self._restore_normal()

        # Rede de segurança para saídas não-limpas (SIGTERM/SIGINT/atexit):
        # sempre religa o adaptador e remove o limite.
        atexit.register(self._restore_normal)
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            try:
                signal.signal(sig, self._on_signal)
            except (ValueError, OSError):
                pass

        self._timer = rumps.Timer(self.refresh, REFRESH_SECONDS)
        self._timer.start()
        self.refresh(None)

    # -- rendering ----------------------------------------------------------
    def _update_threshold_labels(self) -> None:
        self.set_lower_item.title = (
            f"Início da carga: {self.settings.lower}%  (alterar…)"
        )
        self.set_upper_item.title = (
            f"Fim da carga: {self.settings.upper}%  (alterar…)"
        )

    def _update_mode_marks(self) -> None:
        self.off_item.state = 1 if self.mode == "off" else 0
        self.sailing_item.state = 1 if self.mode == "sailing" else 0
        self.force_item.state = 1 if self.mode == "force" else 0

    def _status_line(self, status: dict) -> str:
        pct = status.get("percent")
        state = STATE_PT.get(status.get("state"), status.get("state") or "?")
        plug = "na tomada" if status.get("plugged_in") else "na bateria"
        head = f"{pct}%" if pct is not None else "?%"
        return f"{head} · {state} · {plug}"

    def refresh(self, _) -> None:
        if not self.batt.available():
            self.title = "🔋⚠️"
            self.status_item.title = "batt não instalado — rode o install.sh"
            return
        try:
            status = self.batt.status()
        except BattError:
            self.title = "🔋⚠️"
            self.status_item.title = "daemon do batt parado (rode o install.sh)"
            return

        if self.mode == "force":
            try:
                self._force_control(status.get("percent"))
            except BattError as exc:
                rumps.alert("Sailing Mode", str(exc))

        self.title = format_title(status, badge=MODE_BADGES.get(self.mode, ""))
        self.status_item.title = self._status_line(status)

    # -- modos --------------------------------------------------------------
    def on_off(self, _) -> None:
        self._set_mode("off")

    def on_sailing(self, _) -> None:
        self._set_mode("sailing")

    def on_force(self, _) -> None:
        self._set_mode("force")

    def _set_mode(self, mode: str) -> None:
        try:
            validate(self.settings.lower, self.settings.upper)
            if mode == "off":
                self._restore_normal()
            elif mode == "sailing":
                self._restore_adapter()
                self.batt.activate(self.settings.lower, self.settings.upper)
            elif mode == "force":
                if not self._confirm_force():
                    return
                self._start_force()
        except (BattError, ValueError) as exc:
            rumps.alert("Sailing Mode", str(exc))
            return
        self.mode = mode
        self._update_mode_marks()
        self.refresh(None)

    def _confirm_force(self) -> bool:
        resp = rumps.alert(
            title="Forçar descarga",
            message=(
                "Vou drenar a bateria até o início (mesmo na tomada) e depois "
                "recarregar até o fim, ciclando.\n\n"
                "• Mantenha o app aberto. Se ele fechar durante a descarga, o "
                "adaptador fica cortado até você reabrir (o macOS hiberna sozinho "
                "em bateria baixa, então não há dano).\n"
                "• Com a tampa fechada + monitor externo, o Mac vai dormir.\n\n"
                "Continuar?"
            ),
            ok="Continuar",
            cancel="Cancelar",
        )
        return resp == 1

    def _start_force(self) -> None:
        percent = self._read_percent()
        self.batt.set_limit(self.settings.upper)  # backstop: nunca passa do fim
        self._force_phase = initial_force_phase(
            percent, self.settings.lower, self.settings.upper
        )
        self._adapter_disabled = None  # estado desconhecido → força aplicar
        self._force_control(percent)

    def _force_control(self, percent) -> None:
        phase, action = force_step(
            self._force_phase, percent, self.settings.lower, self.settings.upper
        )
        self._force_phase = phase
        if action == "drain":
            if self._adapter_disabled is not True:
                self.batt.adapter_disable()
                self._adapter_disabled = True
        else:  # charge
            if self._adapter_disabled is not False:
                self.batt.adapter_enable()
                self._adapter_disabled = False

    def _read_percent(self):
        try:
            return self.batt.status().get("percent")
        except BattError:
            return None

    # -- segurança / restauração -------------------------------------------
    def _restore_adapter(self) -> None:
        try:
            self.batt.adapter_enable()
        except BattError:
            pass
        self._adapter_disabled = False

    def _restore_normal(self) -> None:
        self._restore_adapter()
        try:
            self.batt.deactivate()
        except BattError:
            pass

    def _on_signal(self, signum, frame) -> None:
        self._restore_normal()
        rumps.quit_application()

    # -- thresholds ---------------------------------------------------------
    def on_set_lower(self, _) -> None:
        self._ask_threshold("início", is_lower=True)

    def on_set_upper(self, _) -> None:
        self._ask_threshold("fim", is_lower=False)

    def _ask_threshold(self, name: str, *, is_lower: bool) -> None:
        current = self.settings.lower if is_lower else self.settings.upper
        window = rumps.Window(
            message=f"Novo valor para o {name} da carga (%):",
            title="Sailing Mode",
            default_text=str(current),
            ok="Salvar",
            cancel="Cancelar",
            dimensions=(120, 22),
        )
        response = window.run()
        if not response.clicked:
            return
        try:
            value = int(response.text.strip())
        except ValueError:
            rumps.alert("Sailing Mode", "Digite um número inteiro.")
            return

        lower = value if is_lower else self.settings.lower
        upper = self.settings.upper if is_lower else value
        try:
            validate(lower, upper)
        except ValueError as exc:
            rumps.alert("Valor inválido", str(exc))
            return

        self.settings.lower, self.settings.upper = lower, upper
        save(self.settings)
        self._update_threshold_labels()

        # reaplica o modo ativo com os novos limites
        try:
            if self.mode == "sailing":
                self.batt.activate(self.settings.lower, self.settings.upper)
            elif self.mode == "force":
                self._start_force()
        except BattError as exc:
            rumps.alert("Sailing Mode", str(exc))
        self.refresh(None)

    # -- diversos -----------------------------------------------------------
    def on_setup(self, _) -> None:
        rumps.alert(
            title="Instalar o batt",
            message=(
                "No Terminal, rode uma vez:\n\n"
                "./install.sh\n\n"
                "Ele instala o batt e registra o serviço de fundo (pede sua senha)."
            ),
        )

    def on_quit(self, _) -> None:
        self._restore_normal()
        rumps.quit_application()


def main() -> None:
    SailingModeApp().run()


if __name__ == "__main__":
    main()
