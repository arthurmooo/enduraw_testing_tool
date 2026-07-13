"""Tests de migration legacy exclusivement dans des dossiers temporaires."""
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

from core.legacy_data_migration import migrate_legacy_data


TIMESTAMP = "20260710-120000"


def _write_json(path: Path, data: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _create_source(root: Path, session_value: str = "source") -> None:
    session = root / "sessions" / "2026-07-10_test"
    _write_json(session / "session.json", {"name": session_value})
    _write_json(session / "profiles" / "forms_test.json", {"email": "test@example.test"})
    (session / "xml").mkdir()
    (session / "xml" / "test.xml").write_text("<xml />", encoding="utf-8")
    _write_json(root / "mongo_config.json", {"uri": "mongodb://secret-source"})
    _write_json(root / "protocols.json", [{"name": "Paliers"}])
    (root / ".env").write_text("MONGO_URI=mongodb://secret-env", encoding="utf-8")


class LegacyDataMigrationTest(unittest.TestCase):
    def test_empty_sources_are_noop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "target"

            result = migrate_legacy_data([], target, timestamp=TIMESTAMP)

            self.assertEqual(result["status"], "noop")
            self.assertFalse(target.exists())

    def test_copy_creates_backup_manifest_and_preserves_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "source"
            target = Path(tmp_dir) / "target"
            _create_source(source)
            source_before = (source / "sessions" / "2026-07-10_test" / "session.json").read_bytes()

            result = migrate_legacy_data([source], target, timestamp=TIMESTAMP)

            self.assertEqual(result["status"], "migrated")
            self.assertTrue((target / "sessions" / "2026-07-10_test" / "session.json").is_file())
            self.assertTrue((target / "mongo_config.json").is_file())
            self.assertTrue((target / ".env").is_file())
            backups = list((target / "backups").glob("legacy-*"))
            self.assertEqual(len(backups), 1)
            self.assertTrue((backups[0] / "manifest.json").is_file())
            self.assertTrue((target / "migration_state.json").is_file())
            self.assertFalse((target / "migration_state.json.tmp").exists())
            self.assertFalse((target / "migration.lock").exists())
            manifest = json.loads((backups[0] / "manifest.json").read_text(encoding="utf-8"))
            self.assertNotIn("mongodb://secret-source", json.dumps(manifest))
            self.assertNotIn("mongodb://secret-env", json.dumps(manifest))
            self.assertEqual(
                (source / "sessions" / "2026-07-10_test" / "session.json").read_bytes(),
                source_before,
            )

    def test_rerun_with_same_source_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "source"
            target = Path(tmp_dir) / "target"
            _create_source(source)
            migrate_legacy_data([source], target, timestamp=TIMESTAMP)

            result = migrate_legacy_data([source], target, timestamp="20260710-130000")

            self.assertEqual(result["status"], "noop")
            self.assertEqual(result["sources"][0]["status"], "already_migrated")
            self.assertEqual(len(list((target / "backups").glob("legacy-*"))), 1)
            self.assertEqual(len(list((target / "sessions").iterdir())), 1)

    def test_different_session_is_copied_with_legacy_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "source"
            target = Path(tmp_dir) / "target"
            _create_source(source, session_value="source")
            target_session = target / "sessions" / "2026-07-10_test"
            _write_json(target_session / "session.json", {"name": "target"})

            migrate_legacy_data([source], target, timestamp=TIMESTAMP)

            original = json.loads((target_session / "session.json").read_text(encoding="utf-8"))
            conflict = target / "sessions" / f"2026-07-10_test__legacy_{TIMESTAMP}"
            copied = json.loads((conflict / "session.json").read_text(encoding="utf-8"))
            self.assertEqual(original, {"name": "target"})
            self.assertEqual(copied, {"name": "source"})
            self.assertTrue((source / "sessions" / "2026-07-10_test").is_dir())

    def test_existing_target_configs_win(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "source"
            target = Path(tmp_dir) / "target"
            _create_source(source)
            _write_json(target / "mongo_config.json", {"uri": "mongodb://target"})
            _write_json(target / "protocols.json", [{"name": "Target"}])
            (target / ".env").write_text("MONGO_URI=mongodb://target-env", encoding="utf-8")

            result = migrate_legacy_data([source], target, timestamp=TIMESTAMP)

            mongo = json.loads((target / "mongo_config.json").read_text(encoding="utf-8"))
            protocols = json.loads((target / "protocols.json").read_text(encoding="utf-8"))
            dotenv = (target / ".env").read_text(encoding="utf-8")
            self.assertEqual(mongo, {"uri": "mongodb://target"})
            self.assertEqual(protocols, [{"name": "Target"}])
            self.assertEqual(dotenv, "MONGO_URI=mongodb://target-env")
            kept = [
                item for item in result["operations"]
                if item.get("action") == "kept_target"
            ]
            self.assertEqual({item["name"] for item in kept}, set((
                "mongo_config.json",
                "protocols.json", ".env",
            )))

    def test_existing_lock_blocks_migration_without_activating_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "source"
            target = Path(tmp_dir) / "target"
            _create_source(source)
            target.mkdir()
            (target / "migration.lock").write_text("other-process", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "deja en cours"):
                migrate_legacy_data([source], target, timestamp=TIMESTAMP)

            self.assertFalse((target / "sessions" / "2026-07-10_test").exists())
            self.assertTrue((source / "sessions" / "2026-07-10_test").is_dir())


if __name__ == "__main__":
    unittest.main()
