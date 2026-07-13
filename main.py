"""Point d'entrée de l'application Enduraw Testing Tool."""
from __future__ import annotations

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
from core.app_paths import LEGACY_FILENAMES, is_legacy_data_root, prepare_app_storage
from core.legacy_data_migration import migrate_legacy_data


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


def _has_user_data(data_root: Path) -> bool:
    """Ignore les fichiers techniques et détecte uniquement les données métier."""
    sessions = Path(data_root) / "sessions"
    return (
        sessions.is_dir() and any(sessions.iterdir())
    ) or any((Path(data_root) / name).is_file() for name in LEGACY_FILENAMES)


def _normalize_legacy_source(selected: Path) -> Path | None:
    """Accepte la racine historique ou son sous-dossier `sessions`."""
    selected = Path(selected).expanduser().resolve()
    if is_legacy_data_root(selected):
        return selected
    if selected.name.lower() == "sessions" and is_legacy_data_root(selected.parent):
        return selected.parent
    return None


def _ask_legacy_source() -> Path | None:
    """Propose l'import Mac explicite sans modifier la source sélectionnée."""
    import tkinter as tk
    from tkinter import filedialog, messagebox

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        if not messagebox.askyesno(
            "Retrouver les données Enduraw",
            "Cette version stocke vos données dans un dossier protégé et durable.\n\n"
            "Avez-vous déjà utilisé Enduraw Testing Tool sur ce Mac ?\n\n"
            "Oui : choisissez ensuite l'ancien dossier Enduraw. Une sauvegarde "
            "sera créée avant la copie et aucun ancien fichier ne sera supprimé.\n"
            "Non : l'application démarrera avec un stockage vide.",
            parent=root,
        ):
            return None

        while True:
            selected = filedialog.askdirectory(
                title="Choisir l'ancien dossier Enduraw (celui qui contient sessions)",
                mustexist=True,
                parent=root,
            )
            if not selected:
                return None
            source = _normalize_legacy_source(Path(selected))
            if source is not None:
                return source
            retry = messagebox.askretrycancel(
                "Dossier Enduraw non reconnu",
                "Ce dossier ne contient ni le dossier ‘sessions’, ni une configuration "
                "Enduraw reconnue.\n\nChoisissez l'ancien dossier Enduraw ou directement "
                "son sous-dossier ‘sessions’.",
                parent=root,
            )
            if not retry:
                return None
    finally:
        root.destroy()


def _show_migration_success(data_root: Path, migration: dict) -> None:
    """Confirme l'import et indique l'emplacement du backup sans exposer de secret."""
    import tkinter as tk
    from tkinter import messagebox

    copied_sessions = sum(
        1
        for item in migration.get("operations", [])
        if item.get("type") == "session" and item.get("action") in {"copied", "renamed_conflict"}
    )
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        messagebox.showinfo(
            "Données Enduraw importées",
            f"Import terminé : {copied_sessions} session(s) copiée(s).\n\n"
            "L'ancien dossier est intact. Une sauvegarde vérifiée se trouve dans :\n"
            f"{Path(data_root) / 'backups'}",
            parent=root,
        )
    finally:
        root.destroy()


def _offer_macos_legacy_import(storage: dict) -> None:
    """Demande une source seulement au premier lancement Mac encore vide."""
    if (
        not _FROZEN
        or sys.platform != "darwin"
        or _STARTUP_SMOKE_TEST
        or storage["migration"].get("status") != "noop"
        or _has_user_data(storage["data_root"])
    ):
        return
    source = _ask_legacy_source()
    if source is None:
        return
    migration = migrate_legacy_data([source], storage["data_root"])
    storage["migration"] = migration
    _show_migration_success(storage["data_root"], migration)


def main() -> int:
    """Prépare le stockage puis lance l'interface, ou bloque sur erreur visible."""
    try:
        storage = prepare_app_storage(APP_VERSION)
        _offer_macos_legacy_import(storage)

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
