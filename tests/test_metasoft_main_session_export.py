"""Tests du sidecar MetaSoft cree par l'export historique de session.

La fixture evite Tk: on teste le helper pur appele apres `DataTransformer`.
Source: `xml_data["metasoft_analysis"]` deja calculee/recalculee. Unite:
les temps et l'EC restent ceux de l'analyse MetaSoft; aucun marqueur UI n'est
reconstruit dans ce flux.
"""
from copy import deepcopy
import sys
import tempfile
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
from core.session_manager import SessionManager
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
                            "hr_bpm": 142.6,
                            "pace_km_h": 11,
                            "vo2_ml_kg_min": 34.1,
                        },
                        "sv2": {
                            "hr_bpm": 151.4,
                            "pace_km_h": 13,
                            "vo2_ml_kg_min": 42.9,
                        },
                    },
                    "measured_vo2max": 44.8,
                    "max_hr": 164.5,
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
        self.assertEqual(output["seuils"]["SV1"]["fc"], 143)
        self.assertEqual(output["seuils"]["SV2"]["fc"], 151)
        self.assertEqual(output["seuils"]["VO2_max"]["fc_max"], 165)
        self.assertEqual(output["seuils"]["SV2"]["allure"], 13)

    def test_valentin_json_keeps_all_legacy_manual_running_economy_rows(self) -> None:
        manual_ec = {
            "source": "python.metasoft_analysis.manual_running_economy",
            "match_id": "abc123",
            "rows": [
                {"stage_index": 1, "ec_j_kg_m": 4.23},
                {"stage_index": 2, "ec_j_kg_m": 4.67},
            ],
        }

        output = DataTransformer().transform(
            {
                "patient_data": {"Nom": "Mo", "Prénom": "Arthur"},
                "filename_data": {"date": "2026-07-08"},
                "measurements": [],
            },
            {
                "email": "arthur@example.test",
                "identity": {"first_name": "Arthur", "last_name": "Mo"},
                "stress_test_results": {},
            },
            manual_ec,
        )

        self.assertEqual(output["running_economy_manual"], manual_ec)

    def test_valentin_json_exports_only_last_explicitly_enabled_stages(self) -> None:
        manual_ec = {
            "source": "python.metasoft_analysis.manual_running_economy",
            "match_id": "abc123",
            "rows": [
                {"stage_index": 1, "ec_j_kg_m": 4.23},
                {"stage_index": 2, "ec_j_kg_m": 4.67},
            ],
            "warnings": [{"code": "manual_warning"}],
            "stage_selections": [
                {"stage_index": 1, "enabled": True},
                {"stage_index": 2, "enabled": False},
                {"stage_index": 1, "enabled": False},
                {"stage_index": 2, "enabled": True},
            ],
        }
        original = deepcopy(manual_ec)

        output = DataTransformer().transform(
            {
                "patient_data": {"Nom": "Mo", "Prénom": "Arthur"},
                "filename_data": {"date": "2026-07-08"},
                "measurements": [],
            },
            {
                "email": "arthur@example.test",
                "identity": {"first_name": "Arthur", "last_name": "Mo"},
                "stress_test_results": {},
            },
            manual_ec,
        )

        self.assertEqual(
            output["running_economy_manual"],
            {**manual_ec, "rows": [manual_ec["rows"][1]]},
        )
        self.assertEqual(manual_ec, original)

    def test_valentin_json_omits_manual_running_economy_when_all_stages_disabled(self) -> None:
        manual_ec = {
            "source": "python.metasoft_analysis.manual_running_economy",
            "match_id": "abc123",
            "rows": [
                {"stage_index": 1, "ec_j_kg_m": 4.23},
                {"stage_index": 2, "ec_j_kg_m": 4.67},
            ],
            "stage_selections": [
                {"stage_index": 1, "enabled": False},
                {"stage_index": 2, "enabled": False},
            ],
        }

        output = DataTransformer().transform(
            {
                "patient_data": {"Nom": "Mo", "Prénom": "Arthur"},
                "filename_data": {"date": "2026-07-08"},
                "measurements": [],
            },
            {
                "email": "arthur@example.test",
                "identity": {"first_name": "Arthur", "last_name": "Mo"},
                "stress_test_results": {},
            },
            manual_ec,
        )

        self.assertNotIn("running_economy_manual", output)

    def test_valentin_json_uses_only_fingerprint_compatible_manual_ec(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            manager = SessionManager(tmp_dir)
            manager.create_session("2026-07-08", "contas")
            profile_name = manager.add_profile({
                "email": "arthur@example.test",
                "identity": {"first_name": "Arthur", "last_name": "Mo"},
            })
            source_xml = Path(tmp_dir) / "metasoft.xml"
            source_xml.write_text("<xml />", encoding="utf-8")
            xml_filename = manager.import_xml(str(source_xml))
            match = manager.create_match(profile_name, xml_filename)
            fingerprint = manager.build_match_fingerprint(match)
            manual_ec = {
                "source": "python.metasoft_analysis.manual_running_economy",
                "rows": [{"stage_index": 1, "ec_j_kg_m": 4.23}],
            }
            manager.save_manual_running_economy("match", manual_ec, fingerprint)
            stale = {**fingerprint, "xml": {**fingerprint["xml"], "size": 1}}

            compatible = manager.get_manual_running_economy("match", fingerprint)
            stale_payload = manager.get_manual_running_economy("match", stale)
            output = DataTransformer().transform(
                {"patient_data": {}, "filename_data": {}, "measurements": []},
                {"email": "arthur@example.test", "stress_test_results": {}},
                stale_payload,
            )

        self.assertEqual(compatible, manual_ec)
        self.assertIsNone(stale_payload)
        self.assertNotIn("running_economy_manual", output)

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
