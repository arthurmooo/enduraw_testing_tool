"""Migration non destructive des anciennes données locales Enduraw.

Les seules sources acceptées sont des dossiers explicitement fournis. Chaque
source est sauvegardée avant activation, puis sessions et configurations sont
copiées sans écrasement. Aucun fichier source n'est déplacé ou supprimé et les
manifests ne contiennent jamais le contenu des configurations MongoDB.
"""
import hashlib
import json
import os
import shutil
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional


MIGRATION_SCHEMA_VERSION = 1
PERSISTENT_FILES = ("mongo_config.json", "protocols.json")
STATE_FILENAME = "migration_state.json"


def migrate_legacy_data(
    source_roots: Iterable[Path],
    target_root: Path,
    timestamp: Optional[str] = None,
) -> dict:
    """Copie les données legacy vers `target_root` sans toucher aux sources.

    Une source déjà migrée avec le même contenu est ignorée. Une session cible
    différente est conservée et la copie legacy reçoit un suffixe daté.
    """
    sources = [Path(source) for source in source_roots]
    inventories = [item for item in (_inventory_source(source) for source in sources) if item]
    if not inventories:
        return {"status": "noop", "sources": [], "operations": []}

    target_root = Path(target_root)
    target_resolved = target_root.resolve()
    for inventory in inventories:
        source_resolved = inventory["root"].resolve()
        if target_resolved == source_resolved or source_resolved in target_resolved.parents:
            raise ValueError("La cible de migration ne peut pas etre dans une source legacy")
    target_root.mkdir(parents=True, exist_ok=True)
    sessions_root = target_root / "sessions"
    backups_root = target_root / "backups"
    sessions_root.mkdir(exist_ok=True)
    backups_root.mkdir(exist_ok=True)

    with _migration_lock(target_root):
        return _migrate_in_lock(
            inventories,
            target_root,
            sessions_root,
            backups_root,
            timestamp,
        )


def _migrate_in_lock(
    inventories: list[dict],
    target_root: Path,
    sessions_root: Path,
    backups_root: Path,
    timestamp: Optional[str],
) -> dict:
    """Exécute une migration après acquisition exclusive du verrou local."""
    state_path = target_root / STATE_FILENAME
    state = _load_state(state_path)
    run_timestamp = timestamp or datetime.now().strftime("%Y%m%d-%H%M%S")
    results = []
    all_operations = []

    for index, inventory in enumerate(inventories, start=1):
        source_key = str(inventory["root"].resolve())
        previous = state["sources"].get(source_key, {})
        if previous.get("fingerprint") == inventory["fingerprint"]:
            results.append({"source": source_key, "status": "already_migrated"})
            continue

        backup_root = _next_backup_root(backups_root, run_timestamp, index)
        _copy_backup(inventory["root"], backup_root)
        backup_inventory = _inventory_source(backup_root)
        if (
            not backup_inventory
            or backup_inventory["fingerprint"] != inventory["fingerprint"]
        ):
            raise OSError("La verification du backup legacy a echoue")
        backup_manifest = {
            "schema_version": MIGRATION_SCHEMA_VERSION,
            "created_at": run_timestamp,
            "source": source_key,
            "source_fingerprint": inventory["fingerprint"],
            "files": inventory["files"],
        }
        _atomic_write_json(backup_root / "manifest.json", backup_manifest)

        operations = _activate_source(
            inventory["root"],
            target_root,
            sessions_root,
            run_timestamp,
        )
        backup_manifest["operations"] = operations
        _atomic_write_json(backup_root / "manifest.json", backup_manifest)
        all_operations.extend(operations)
        state["sources"][source_key] = {
            "fingerprint": inventory["fingerprint"],
            "migrated_at": run_timestamp,
            "backup": str(backup_root.relative_to(target_root)),
        }
        _atomic_write_json(state_path, state)
        results.append({"source": source_key, "status": "migrated"})

    status = "noop" if not all_operations else "migrated"
    return {"status": status, "sources": results, "operations": all_operations}


@contextmanager
def _migration_lock(target_root: Path):
    """Empêche deux migrations concurrentes avec une création atomique O_EXCL."""
    lock_path = target_root / "migration.lock"
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise RuntimeError("Une migration locale est deja en cours") from error
    try:
        os.write(descriptor, str(os.getpid()).encode("ascii"))
        yield
    finally:
        os.close(descriptor)
        lock_path.unlink(missing_ok=True)


def _inventory_source(source_root: Path) -> Optional[dict]:
    """Inventorie uniquement les sessions et configurations reconnues."""
    if not source_root.is_dir():
        return None

    roots = []
    sessions = source_root / "sessions"
    if sessions.is_dir():
        if sessions.is_symlink():
            raise ValueError(f"Lien symbolique refuse pendant la migration: {sessions}")
        roots.append(sessions)
    roots.extend(
        path for name in PERSISTENT_FILES
        if (path := source_root / name).is_file()
    )
    if not roots:
        return None

    files = []
    for root in roots:
        candidates = [root] if root.is_file() else sorted(root.rglob("*"))
        for path in candidates:
            if path.is_symlink():
                raise ValueError(f"Lien symbolique refuse pendant la migration: {path}")
            if not path.is_file():
                continue
            files.append({
                "path": path.relative_to(source_root).as_posix(),
                "size": path.stat().st_size,
                "sha256": _file_hash(path),
            })
    if not files:
        return None

    digest = hashlib.sha256()
    for item in files:
        digest.update(item["path"].encode("utf-8"))
        digest.update(b"\0")
        digest.update(item["sha256"].encode("ascii"))
        digest.update(b"\0")
    return {
        "root": source_root,
        "files": files,
        "fingerprint": digest.hexdigest(),
    }


def _copy_backup(source_root: Path, backup_root: Path) -> None:
    """Copie les données reconnues vers un backup neuf avant activation."""
    backup_root.mkdir(parents=True)
    source_sessions = source_root / "sessions"
    if source_sessions.is_dir():
        shutil.copytree(source_sessions, backup_root / "sessions", copy_function=shutil.copy2)
    for name in PERSISTENT_FILES:
        source_file = source_root / name
        if source_file.is_file():
            shutil.copy2(source_file, backup_root / name)


def _activate_source(
    source_root: Path,
    target_root: Path,
    sessions_root: Path,
    timestamp: str,
) -> list[dict]:
    """Active les copies en conservant systématiquement les cibles existantes."""
    operations = []
    source_sessions = source_root / "sessions"
    if source_sessions.is_dir():
        for source_session in sorted(source_sessions.iterdir()):
            if not source_session.is_dir():
                continue
            destination, action = _session_destination(
                source_session,
                sessions_root,
                timestamp,
            )
            if destination is not None:
                shutil.copytree(source_session, destination, copy_function=shutil.copy2)
            operations.append({
                "type": "session",
                "name": source_session.name,
                "action": action,
                "destination": destination.name if destination else source_session.name,
            })

    for name in PERSISTENT_FILES:
        source_file = source_root / name
        if not source_file.is_file():
            continue
        target_file = target_root / name
        if target_file.exists():
            action = "kept_target"
        else:
            shutil.copy2(source_file, target_file)
            action = "copied"
        operations.append({"type": "config", "name": name, "action": action})
    return operations


def _session_destination(
    source_session: Path,
    sessions_root: Path,
    timestamp: str,
) -> tuple[Optional[Path], str]:
    """Résout une copie normale, identique ou conflictuelle par hash d'arbre."""
    destination = sessions_root / source_session.name
    source_hash = _tree_hash(source_session)
    if not destination.exists():
        return destination, "copied"
    if destination.is_dir() and _tree_hash(destination) == source_hash:
        return None, "identical"

    for candidate in sorted(sessions_root.glob(f"{source_session.name}__legacy_*")):
        if candidate.is_dir() and _tree_hash(candidate) == source_hash:
            return None, "identical_conflict"

    conflict = sessions_root / f"{source_session.name}__legacy_{timestamp}"
    suffix = 2
    while conflict.exists():
        conflict = sessions_root / f"{source_session.name}__legacy_{timestamp}_{suffix}"
        suffix += 1
    return conflict, "renamed_conflict"


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Lien symbolique refuse pendant la migration: {path}")
        if not path.is_file():
            continue
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(_file_hash(path).encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _next_backup_root(backups_root: Path, timestamp: str, index: int) -> Path:
    candidate = backups_root / f"legacy-{timestamp}-source-{index}"
    suffix = 2
    while candidate.exists():
        candidate = backups_root / f"legacy-{timestamp}-source-{index}-{suffix}"
        suffix += 1
    return candidate


def _load_state(path: Path) -> dict:
    if not path.exists():
        return {"schema_version": MIGRATION_SCHEMA_VERSION, "sources": {}}
    with open(path, "r", encoding="utf-8") as file_handle:
        state = json.load(file_handle)
    if (
        not isinstance(state, dict)
        or state.get("schema_version") != MIGRATION_SCHEMA_VERSION
        or not isinstance(state.get("sources"), dict)
    ):
        raise ValueError("Etat de migration local invalide ou non supporte")
    return state


def _atomic_write_json(path: Path, data: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with open(temporary, "w", encoding="utf-8") as file_handle:
            json.dump(data, file_handle, indent=2, ensure_ascii=False)
            file_handle.flush()
            os.fsync(file_handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
