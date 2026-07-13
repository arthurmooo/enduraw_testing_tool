"""Tests des chemins de ressources et de données sans écriture hors tempdir."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

from core import app_paths
from core.app_paths import (
    ensure_data_schema,
    ensure_user_data_dirs,
    is_legacy_data_root,
    legacy_data_candidates,
    prepare_app_storage,
    resource_root,
    user_data_root,
)


class AppPathsTest(unittest.TestCase):
    def test_resource_root_uses_repo_in_development(self) -> None:
        with patch.object(app_paths.sys, "frozen", False, create=True):
            self.assertEqual(resource_root(), ROOT_DIR)

    def test_resource_root_uses_pyinstaller_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with (
                patch.object(app_paths.sys, "frozen", True, create=True),
                patch.object(app_paths.sys, "_MEIPASS", tmp_dir, create=True),
            ):
                self.assertEqual(resource_root(), Path(tmp_dir))

    def test_windows_uses_local_app_data(self) -> None:
        root = user_data_root(
            environment={"LOCALAPPDATA": "C:/Users/Kylian/AppData/Local"},
            platform_name="win32",
            home=Path("C:/Users/Kylian"),
        )

        self.assertEqual(
            root,
            Path("C:/Users/Kylian/AppData/Local") / "EndurawTestingTool",
        )

    def test_macos_uses_application_support(self) -> None:
        root = user_data_root(
            environment={},
            platform_name="darwin",
            home=Path("/Users/thibaut"),
        )

        self.assertEqual(
            root,
            Path("/Users/thibaut/Library/Application Support/EndurawTestingTool"),
        )

    def test_override_does_not_create_until_explicit_call(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "custom-data"
            resolved = user_data_root(
                environment={"ENDURAW_DATA_DIR": str(root)},
                platform_name="darwin",
            )

            self.assertEqual(resolved, root)
            self.assertFalse(root.exists())

            paths = ensure_user_data_dirs(resolved)

            self.assertTrue(paths["sessions"].is_dir())
            self.assertTrue(paths["backups"].is_dir())
            self.assertTrue(paths["logs"].is_dir())

    def test_schema_is_created_once_without_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            schema = ensure_data_schema(root, "1.0.0")
            original = schema.read_bytes()

            ensure_data_schema(root, "2.0.0")

            self.assertEqual(schema.read_bytes(), original)
            self.assertEqual(
                json.loads(original),
                {"schema_version": 1, "app_version": "1.0.0"},
            )

    def test_legacy_candidates_are_bounded_to_known_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            resources = root / "repo"
            data_root = root / "data"
            executable = root / "Programs" / "Enduraw" / "Enduraw.exe"
            (resources / "sessions").mkdir(parents=True)
            (executable.parent.parent / "sessions").mkdir(parents=True)

            dev = legacy_data_candidates(resources, data_root, frozen=False)
            frozen = legacy_data_candidates(
                resources,
                data_root,
                frozen=True,
                executable=executable,
            )

            self.assertEqual(dev, [resources.resolve()])
            self.assertEqual(frozen, [executable.parent.parent.resolve()])

    def test_fresh_frozen_install_has_no_legacy_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            executable = root / "Programs" / "Enduraw" / "Enduraw.exe"
            data_root = root / "LocalAppData" / "EndurawTestingTool"

            candidates = legacy_data_candidates(
                root / "bundle",
                data_root,
                frozen=True,
                executable=executable,
            )
            storage = prepare_app_storage(
                "1.0.0",
                resources=root / "bundle",
                data_root=data_root,
                frozen=True,
                executable=executable,
            )

            self.assertEqual(candidates, [])
            self.assertEqual(storage["migration"]["status"], "noop")

    def test_explicit_legacy_env_is_recognized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / ".env").write_text("MONGO_URI=mongodb://secret", encoding="utf-8")

            self.assertTrue(is_legacy_data_root(root))

    def test_prepare_storage_migrates_only_explicit_dev_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            resources = root / "repo"
            data_root = root / "data"
            session = resources / "sessions" / "session-a"
            session.mkdir(parents=True)
            (session / "session.json").write_text("{}", encoding="utf-8")

            result = prepare_app_storage(
                "1.0.0",
                resources=resources,
                data_root=data_root,
                frozen=False,
            )

            self.assertEqual(result["migration"]["status"], "migrated")
            self.assertTrue((data_root / "data_schema.json").is_file())
            self.assertTrue((data_root / "sessions" / "session-a" / "session.json").is_file())


if __name__ == "__main__":
    unittest.main()
