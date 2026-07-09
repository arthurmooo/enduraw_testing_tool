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
from core.data_transformer import DataTransformer
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
    def test_valentin_json_contract_stays_separate_from_audit(self) -> None:
        output = DataTransformer().transform(
            {
                "patient_data": {"Nom": "Mo", "Prénom": "Arthur"},
                "filename_data": {"date": "2026-07-08"},
                "measurements": [],
            },
            {
                "email": "arthur@example.test",
                "identity": {"first_name": "Arthur", "last_name": "Mo"},
                "body_composition": {"current_weight": 68},
                "stress_test_results": {
                    "thresholds": {
                        "sv1": {
                            "hr_bpm": 142,
                            "pace_km_h": 11,
                            "vo2_ml_kg_min": 34.1,
                        },
                        "sv2": {
                            "hr_bpm": 152,
                            "pace_km_h": 13,
                            "vo2_ml_kg_min": 42.9,
                        },
                    },
                    "measured_vo2max": 44.8,
                    "max_hr": 164,
                    "vma": 14.7,
                },
            },
        )

        self.assertEqual(
            set(output),
            {
                "user_id",
                "athlete_name",
                "test_date",
                "test_type",
                "consentements",
                "seuils",
                "protocole",
                "test_lactate",
                "observations_lactate",
                "patient_info",
                "conseils_entrainements",
                "graphiques",
                "logos",
                "partenaires",
            },
        )
        for forbidden_key in ("markers", "metasoft", "audit", "running_economy"):
            self.assertNotIn(forbidden_key, output)
        self.assertEqual(output["seuils"]["SV1"]["fc"], 142)
        self.assertEqual(output["seuils"]["SV2"]["allure"], 13)

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
