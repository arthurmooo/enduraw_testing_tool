"""Tests du sidecar MetaSoft cree par l'export historique de session.

La fixture evite Tk: on teste le helper pur appele apres `DataTransformer`.
Source: `xml_data["metasoft_analysis"]` deja calculee/recalculee. Unite:
les temps et l'EC restent ceux de l'analyse MetaSoft; aucun marqueur UI n'est
reconstruit dans ce flux.
"""
from copy import deepcopy
import json
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
from core.metasoft_identity import metasoft_identity_check
from core.session_manager import SessionManager
from main_session import (
    _save_metasoft_audit_sidecar,
    _validated_manual_running_economy,
    _validated_metasoft_export_markers,
)


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
    def test_identity_normalises_accents_case_and_spaces(self) -> None:
        result = metasoft_identity_check(
            {"athlete_name": "  MÔ   Arthur "},
            {"identity": {"last_name": "mo", "first_name": "ARTHUR"}},
        )

        self.assertTrue(result["ok"])

    def test_non_metasoft_export_keeps_legacy_path_without_provenance(self) -> None:
        class _LegacyManager:
            def validate_metasoft_report(self, *_args):
                raise AssertionError("La provenance MetaSoft ne doit pas etre lue")

        markers = _validated_metasoft_export_markers(
            _LegacyManager(),
            object(),
            {"patient_data": {"Nom": "Mo", "Prénom": "Arthur"}},
            {"identity": {"last_name": "Mo", "first_name": "Arthur"}},
        )

        self.assertEqual(markers, {})

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
            manual_ec = {
                "source": "python.metasoft_analysis.manual_running_economy",
                "rows": [{
                    "stage_index": 1,
                    "ec_j_kg_m": 4.23,
                    "sources": {"vo2max": "metasoft_marker.vo2_max"},
                }],
            }
            fingerprint = manager.build_manual_running_economy_fingerprint(match, manual_ec)
            manager.save_manual_running_economy("match", manual_ec, fingerprint)

            compatible = manager.get_manual_running_economy("match", match)
            manager.xml_path(xml_filename).write_text("<xml changed />", encoding="utf-8")
            stale = manager.manual_running_economy_state("match", match)

        self.assertEqual(compatible, manual_ec)
        self.assertEqual(stale["status"], "stale")

    def test_export_blocks_stale_or_corrupt_manual_ec_before_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            manager = SessionManager(tmp_dir)
            manager.create_session("2026-07-08", "contas")
            profile_name = manager.add_profile({
                "identity": {"first_name": "Arthur", "last_name": "Mo"},
                "stress_test_results": {"measured_vo2max": 50},
            })
            source_xml = Path(tmp_dir) / "metasoft.xml"
            source_xml.write_text("<xml />", encoding="utf-8")
            xml_filename = manager.import_xml(str(source_xml))
            match = manager.create_match(profile_name, xml_filename)
            match_id = "match"
            manual_ec = {
                "source": "python.metasoft_analysis.manual_running_economy",
                "rows": [{
                    "stage_index": 1,
                    "ec_j_kg_m": 4.23,
                    "sources": {"vo2max": "profile.stress_test_results.measured_vo2max"},
                }],
            }
            fingerprint = manager.build_manual_running_economy_fingerprint(match, manual_ec)
            manager.save_manual_running_economy(match_id, manual_ec, fingerprint)
            profile = manager.get_profile(profile_name)
            profile["stress_test_results"]["measured_vo2max"] = 55
            manager.update_profile(profile_name, profile)

            with self.assertRaisesRegex(ValueError, "manual_running_economy_stale"):
                _validated_manual_running_economy(manager, match, match_id)
            path = manager.current_session_path / "running_economy_manual.json"
            path.write_text("{broken", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "manual_running_economy_corrupt"):
                _validated_manual_running_economy(manager, match, match_id)
            self.assertEqual(list(Path(manager.get_output_dir()).iterdir()), [])

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

    def test_export_guard_blocks_mismatch_unproven_and_stale_before_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            manager = SessionManager(tmp_dir)
            manager.create_session("2026-07-08", "contas")
            profile = {
                "email": "arthur@example.test",
                "identity": {"first_name": "Arthur", "last_name": "Mo"},
                "stress_test_results": {
                    "thresholds": {
                        "sv1": {
                            "hr_bpm": 143,
                            "pace_km_h": 11,
                            "vo2_ml_kg_min": 34.1,
                        },
                    },
                },
            }
            profile_name = manager.add_profile(profile)
            source_xml = Path(tmp_dir) / "metasoft.xml"
            source_xml.write_text("<xml />", encoding="utf-8")
            xml_filename = manager.import_xml(str(source_xml))
            match = manager.create_match(profile_name, xml_filename)

            with self.assertRaisesRegex(ValueError, "identity_mismatch"):
                _validated_metasoft_export_markers(
                    manager,
                    match,
                    {"metasoft_analysis": {"athlete": {"athlete_name": "Doe John"}}},
                    profile,
                )
            with self.assertRaisesRegex(ValueError, "marker_provenance_stale"):
                _validated_metasoft_export_markers(
                    manager,
                    match,
                    {"metasoft_analysis": {"athlete": {"athlete_name": "Mo Arthur"}}},
                    profile,
                )

            marker = {
                "name": "SV1",
                "action": "upsert",
                "status": "ok",
                "mode": "point",
                "t_seconds": 60,
                "window_start_seconds": None,
                "window_end_seconds": None,
                "point_count": 1,
                "values": {
                    "fc_bpm": 143,
                    "vo2_ml_kg_min": 34.1,
                    "speed_kmh": 11,
                },
            }
            manager.record_metasoft_report(match, profile, {"SV1": marker})
            profile["stress_test_results"]["thresholds"]["sv1"]["hr_bpm"] = 144
            manager.update_profile(profile_name, profile)
            with self.assertRaisesRegex(ValueError, "marker_provenance_stale"):
                _validated_metasoft_export_markers(
                    manager,
                    match,
                    {"metasoft_analysis": {"athlete": {"athlete_name": "Mo Arthur"}}},
                    profile,
                )

            output_dir = Path(manager.get_output_dir())
            self.assertEqual(list(output_dir.iterdir()), [])

    def test_valid_export_uses_exact_proven_profile_and_sidecar_markers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            manager = SessionManager(tmp_dir)
            manager.create_session("2026-07-08", "contas")
            profile = {
                "email": "arthur@example.test",
                "identity": {"first_name": "Arthur", "last_name": "Mo"},
                "stress_test_results": {
                    "thresholds": {
                        "sv1": {
                            "hr_bpm": 143,
                            "pace_km_h": 11,
                            "vo2_ml_kg_min": 34.1,
                        },
                    },
                },
            }
            profile_name = manager.add_profile(profile)
            source_xml = Path(tmp_dir) / "metasoft.xml"
            source_xml.write_text("<xml />", encoding="utf-8")
            xml_filename = manager.import_xml(str(source_xml))
            match = manager.create_match(profile_name, xml_filename)
            marker = {
                "name": "SV1",
                "action": "upsert",
                "status": "ok",
                "mode": "point",
                "t_seconds": 60,
                "window_start_seconds": None,
                "window_end_seconds": None,
                "point_count": 1,
                "values": {
                    "fc_bpm": 143,
                    "vo2_ml_kg_min": 34.1,
                    "speed_kmh": 11,
                },
            }
            manager.record_metasoft_report(match, profile, {"SV1": marker})
            xml_data = {
                "patient_data": {"Nom": "Mo", "Prénom": "Arthur"},
                "filename_data": {"date": "2026-07-08"},
                "measurements": [],
                "metasoft_analysis": _analysis(),
            }

            markers = _validated_metasoft_export_markers(
                manager,
                match,
                xml_data,
                profile,
            )
            output = DataTransformer().transform(xml_data, profile)
            _save_metasoft_audit_sidecar(
                manager,
                xml_data,
                profile,
                "Mo_Arthur_2026-07-08.json",
                profile_name,
                markers,
            )
            sidecar = json.loads(
                (
                    Path(manager.get_output_dir())
                    / "Mo_Arthur_2026-07-08.metasoft_audit.json"
                ).read_text(encoding="utf-8")
            )

        self.assertEqual(output["seuils"]["SV1"]["fc"], 143)
        self.assertEqual(output["seuils"]["SV1"]["allure"], 11)
        self.assertEqual(sidecar["markers"]["SV1"]["values"], marker["values"])


if __name__ == "__main__":
    unittest.main()
