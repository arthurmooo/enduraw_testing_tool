"""Point d'entrée de l'application Enduraw Testing Tool."""
import os
import sys
from pathlib import Path


_FROZEN = bool(getattr(sys, "frozen", False))
_STARTUP_SMOKE_TEST = os.environ.get("ENDURAW_STARTUP_SMOKE_TEST") == "1"
_BOOTSTRAP_ROOT = Path(
    getattr(sys, "_MEIPASS", Path(sys.executable).parent)
    if _FROZEN
    else Path(__file__).parent
)
if not _FROZEN:
    sys.path.insert(0, str(_BOOTSTRAP_ROOT / "src"))

from config import APP_VERSION
from core.app_paths import prepare_app_storage


def _load_dotenv(directory: Path) -> None:
    """Charge un `.env` autorisé sans remplacer l'environnement du processus."""
    env_file = Path(directory) / ".env"
    if not env_file.is_file():
        return
    with open(env_file, encoding="utf-8") as file_handle:
        for line in file_handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(
                key.strip(),
                value.strip().strip('"').strip("'"),
            )


def _show_startup_error(error: Exception) -> None:
    """Affiche une erreur bloquante même depuis l'exécutable sans console."""
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Enduraw Testing Tool - démarrage impossible",
            "Les données locales n'ont pas pu être préparées.\n\n"
            f"{error}\n\nAucune migration destructive n'a été effectuée.",
            parent=root,
        )
        root.destroy()
    except Exception:
        # Le build windowed doit embarquer Tk; cette branche reste un dernier recours.
        return


def main() -> int:
    """Prépare le stockage puis lance l'interface, ou bloque sur erreur visible."""
    try:
        storage = prepare_app_storage(APP_VERSION)

        # En bundle, seule la configuration utilisateur est autorisée. Le repo
        # reste une source .env supplémentaire uniquement en développement.
        _load_dotenv(storage["data_root"])
        if not _FROZEN:
            _load_dotenv(storage["resources"])

        from main_session import TCPDataProcessorSession

        app = TCPDataProcessorSession(
            data_root=storage["data_root"],
            resources=storage["resources"],
        )
        if _STARTUP_SMOKE_TEST:
            app.update_idletasks()
            app.destroy()
            return 0
        app.mainloop()
        return 0
    except Exception as error:
        if not _STARTUP_SMOKE_TEST:
            _show_startup_error(error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
