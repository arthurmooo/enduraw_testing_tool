"""Résolution séparée des ressources applicatives et des données utilisateur.

Les ressources sont lues depuis le repo en développement ou depuis `_MEIPASS`
dans un bundle PyInstaller. Les données sont placées dans le dossier utilisateur
standard de la plateforme. Aucun dossier n'est créé pendant la résolution.
"""
import os
import json
import sys
from pathlib import Path
from typing import Mapping, Optional


APP_DATA_DIRNAME = "EndurawTestingTool"
DATA_SCHEMA_FILENAME = "data_schema.json"
DATA_SCHEMA_VERSION = 1
LEGACY_FILENAMES = ("mongo_config.json", "protocols.json", ".env")


def resource_root() -> Path:
    """Retourne la racine immuable contenant le code et les assets packagés."""
    if getattr(sys, "frozen", False):
        bundle_root = getattr(sys, "_MEIPASS", None)
        if not bundle_root:
            raise RuntimeError("Racine de ressources PyInstaller indisponible")
        return Path(bundle_root)
    return Path(__file__).resolve().parents[2]


def user_data_root(
    environment: Optional[Mapping[str, str]] = None,
    platform_name: Optional[str] = None,
    home: Optional[Path] = None,
) -> Path:
    """Retourne la racine persistante sans créer de dossier.

    `ENDURAW_DATA_DIR` reste prioritaire pour les tests, le support et les
    installations qui imposent un emplacement explicite.
    """
    environment = os.environ if environment is None else environment
    platform_name = sys.platform if platform_name is None else platform_name
    home = Path.home() if home is None else Path(home)

    override = str(environment.get("ENDURAW_DATA_DIR", "")).strip()
    if override:
        return Path(override).expanduser()

    if platform_name.startswith("win"):
        local_app_data = str(environment.get("LOCALAPPDATA", "")).strip()
        base = Path(local_app_data) if local_app_data else home / "AppData" / "Local"
        return base / APP_DATA_DIRNAME

    if platform_name == "darwin":
        return home / "Library" / "Application Support" / APP_DATA_DIRNAME

    xdg_data_home = str(environment.get("XDG_DATA_HOME", "")).strip()
    base = Path(xdg_data_home).expanduser() if xdg_data_home else home / ".local" / "share"
    return base / APP_DATA_DIRNAME


def ensure_user_data_dirs(root: Optional[Path] = None) -> dict[str, Path]:
    """Crée explicitement la racine et ses dossiers persistants standards."""
    root = user_data_root() if root is None else Path(root)
    paths = {
        "root": root,
        "sessions": root / "sessions",
        "backups": root / "backups",
        "logs": root / "logs",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def ensure_data_schema(root: Path, app_version: str) -> Path:
    """Crée atomiquement le schéma V1 s'il n'existe pas, sans le réécrire."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    schema_path = root / DATA_SCHEMA_FILENAME
    if schema_path.exists():
        return schema_path

    lock_path = root / f".{DATA_SCHEMA_FILENAME}.lock"
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        if schema_path.exists():
            return schema_path
        raise RuntimeError("Initialisation du schema de donnees deja en cours") from error

    temporary = root / f".{DATA_SCHEMA_FILENAME}.tmp"
    try:
        if schema_path.exists():
            return schema_path
        with open(temporary, "w", encoding="utf-8") as file_handle:
            json.dump(
                {
                    "schema_version": DATA_SCHEMA_VERSION,
                    "app_version": str(app_version),
                },
                file_handle,
                indent=2,
                ensure_ascii=False,
            )
            file_handle.flush()
            os.fsync(file_handle.fileno())
        os.replace(temporary, schema_path)
    finally:
        temporary.unlink(missing_ok=True)
        os.close(descriptor)
        lock_path.unlink(missing_ok=True)
    return schema_path


def legacy_data_candidates(
    resources: Path,
    data_root: Path,
    frozen: Optional[bool] = None,
    executable: Optional[Path] = None,
) -> list[Path]:
    """Retourne les seules racines legacy sûres et reconnues.

    En développement, seul le repo est candidat. En bundle, seul le parent du
    dossier contenant l'exécutable couvre l'ancien calcul de `main_session`.
    Aucun parcours du disque ou du dossier utilisateur n'est effectué.
    """
    frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    if frozen:
        executable = Path(sys.executable) if executable is None else Path(executable)
        candidates = [executable.resolve().parent.parent]
    else:
        candidates = [Path(resources).resolve()]

    data_resolved = Path(data_root).resolve()
    result = []
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate == data_resolved or candidate in data_resolved.parents:
            continue
        if is_legacy_data_root(candidate):
            result.append(candidate)
    return result


def prepare_app_storage(
    app_version: str,
    resources: Optional[Path] = None,
    data_root: Optional[Path] = None,
    frozen: Optional[bool] = None,
    executable: Optional[Path] = None,
) -> dict:
    """Prépare schéma et migration avant que l'UI accède aux stores locaux."""
    resources = resource_root() if resources is None else Path(resources)
    data_root = user_data_root() if data_root is None else Path(data_root)
    paths = ensure_user_data_dirs(data_root)
    schema_path = ensure_data_schema(data_root, app_version)
    candidates = legacy_data_candidates(
        resources,
        data_root,
        frozen=frozen,
        executable=executable,
    )

    # Import local pour garder la simple résolution de chemins sans dépendance I/O.
    from core.legacy_data_migration import migrate_legacy_data

    migration = migrate_legacy_data(candidates, data_root)
    return {
        "resources": resources,
        "data_root": data_root,
        "paths": paths,
        "schema": schema_path,
        "legacy_sources": candidates,
        "migration": migration,
    }


def is_legacy_data_root(root: Path) -> bool:
    """Indique si `root` contient une ancienne installation importable."""
    if (root / "sessions").is_dir():
        return True
    return any((root / name).is_file() for name in LEGACY_FILENAMES)
