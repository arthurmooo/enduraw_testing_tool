"""Tests du sidecar MetaSoft cree par l'export historique de session.

La fixture evite Tk: on teste le helper pur appele apres `DataTransformer`.
Source: `xml_data["metasoft_analysis"]` deja calculee/recalculee. Unite:
les temps et l'EC restent ceux de l'analyse MetaSoft; aucun marqueur UI n'est
reconstruit dans ce flux.
"""
import sys
import types
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))


class _Widget:
    def __init__(self, *args, **kwargs):
        pass


class _CustomTkinterStub(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("set_"):
            return lambda *args, **kwargs: None
        if name == "CTkFont":
            return lambda *args, **kwargs: None
        return _Widget


try:
    import customtkinter  # noqa: F401
except ModuleNotFoundError:
    sys.modules["customtkinter"] = _CustomTkinterStub("customtkinter")

from core.metasoft_analysis import build_metasoft_analysis
from main_session import _save_metasoft_audit_sidecar


def _analysis() -> dict:
    parsed = {
        "file": {"filename": "test.xml"},
        "athlete": {
            "first_name": "Arthur",
            "last_name": "Mo",
            "athlete_name": "Mo Arthur",
            "weight_kg": 70,
        },
        "test": {"date": "2026-07-08", "type": "VO2max"},
        "metrics": {},
        "points": [],
        "warnings": [{"code": "parser_note", "message": "source XML"}],
    }
    return build_metasoft_analysis(parsed)


class _SessionManager:
    def __init__(self):
        self.saved = {}

    def save_output(self, filename, data):
        self.saved[filename] = data
        return f"/tmp/{filename}"


class MetaSoftMainSessionExportTest(unittest.TestCase):
    def test_historical_export_saves_sidecar_without_markers_or_ui_warnings(self) -> None:
        session_manager = _SessionManager()

        path = _save_metasoft_audit_sidecar(
            session_manager,
            {"metasoft_analysis": _analysis()},
            {
                "identity": {"first_name": "Arthur", "last_name": "Mo"},
                "email": "arthur@example.test",
            },
            "Mo_Arthur_2026-07-08.json",
            "Mo_Arthur.json",
        )

        audit_name = "Mo_Arthur_2026-07-08.metasoft_audit.json"
        self.assertEqual(path, f"/tmp/{audit_name}")
        self.assertIn(audit_name, session_manager.saved)
        sidecar = session_manager.saved[audit_name]
        self.assertEqual(
            sidecar["export"]["json_filename"],
            "Mo_Arthur_2026-07-08.json",
        )
        self.assertEqual(sidecar["profile"]["filename"], "Mo_Arthur.json")
        self.assertEqual(sidecar["markers"], {})
        self.assertEqual(sidecar["warnings"]["ui"], [])
        self.assertEqual(sidecar["warnings"]["analysis"][0]["code"], "parser_note")

    def test_historical_export_skips_sidecar_when_analysis_is_absent(self) -> None:
        session_manager = _SessionManager()

        path = _save_metasoft_audit_sidecar(
            session_manager,
            {},
            {"identity": {"first_name": "Arthur", "last_name": "Mo"}},
            "Mo_Arthur_2026-07-08.json",
            "Mo_Arthur.json",
        )

        self.assertIsNone(path)
        self.assertEqual(session_manager.saved, {})


if __name__ == "__main__":
    unittest.main()
