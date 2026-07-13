"""Tests purs du branchement de migration au premier lancement Mac."""
import tempfile
import unittest
from pathlib import Path


import main


class MainStorageTest(unittest.TestCase):
    def test_normalize_accepts_legacy_root_or_sessions_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            legacy = Path(tmp_dir) / "ancienne app"
            sessions = legacy / "sessions"
            sessions.mkdir(parents=True)

            self.assertEqual(main._normalize_legacy_source(legacy), legacy.resolve())
            self.assertEqual(main._normalize_legacy_source(sessions), legacy.resolve())

    def test_normalize_rejects_unrelated_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            self.assertIsNone(main._normalize_legacy_source(Path(tmp_dir)))

    def test_has_user_data_ignores_empty_scaffold(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "sessions").mkdir()
            (root / "data_schema.json").write_text("{}", encoding="utf-8")

            self.assertFalse(main._has_user_data(root))
            (root / "sessions" / "test").mkdir()
            self.assertTrue(main._has_user_data(root))


if __name__ == "__main__":
    unittest.main()
