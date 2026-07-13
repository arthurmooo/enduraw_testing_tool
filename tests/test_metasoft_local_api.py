"""Tests de l'API locale MetaSoft.

Les fixtures creent une session temporaire complete: profil local, XML importe,
match, puis appels HTTP vers le serveur 127.0.0.1. Les ecritures verifiees
restent dans le dossier de session temporaire: export JSON, sidecar audit et
marquage local du match exporte.
"""
import json
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

from core.metasoft_markers import build_metasoft_marker
from core.session_manager import SessionManager
from local_api.metasoft_server import LocalMetaSoftServer


def _cell(value: str) -> str:
    return f'<Cell><Data ss:Type="String">{value}</Data></Cell>'


def _metasoft_xml(include_weight: bool = False, two_stages: bool = False) -> bytes:
    headers = [
        "t", "Phase", "Marqueur", "FC", "V'O2", "V'O2/kg", "RER",
        "V'E", "V'E/V'O2", "V'E/V'CO2", "BF", "v", "DE",
    ]
    units = [
        "s", "", "", "bpm", "L/min", "ml/min/kg", "", "L/min",
        "", "", "/min", "km/h", "kcal/h",
    ]
    rows = [
        [_cell("Nom"), _cell("VAN DER VEEN")],
        [_cell("Prénom"), _cell("Noor")],
    ]
    if include_weight:
        rows.append([_cell("Poids"), _cell("60,0 kg")])
    rows.extend([
        [_cell(value) for value in headers],
        [_cell(value) for value in units],
        [_cell(value) for value in [
            "0:00:00,000", "Repos", "", "80", "0,30", "5", "0,80",
            "8", "26,6", "33,3", "12", "0", "220",
        ]],
        [_cell(value) for value in [
            "0:00:30,000", "Repos", "", "82", "0,32", "5,2", "0,81",
            "8,5", "26,5", "32,7", "13", "0", "230",
        ]],
        [_cell(value) for value in [
            "0:01:00,000", "Echauffement", "", "120", "2,00", "32",
            "0,90", "40", "20", "22,2", "28", "10", "700",
        ]],
        [_cell(value) for value in [
            "0:01:30,000", "Echauffement", "", "124", "2,20", "36",
            "0,92", "42", "19,1", "20,7", "30", "10", "720",
        ]],
        [_cell(value) for value in [
            "0:02:00,000", "Echauffement", "", "130", "2,40", "39",
            "0,95", "50", "20,8", "21,9", "31", "10", "760",
        ]],
    ])
    if two_stages:
        rows.extend([
            [_cell(value) for value in [
                "0:02:30,000", "Echauffement", "", "136", "2,60", "42",
                "0,96", "54", "20,8", "21,6", "32", "12", "820",
            ]],
            [_cell(value) for value in [
                "0:03:00,000", "Echauffement", "", "140", "2,80", "45",
                "0,97", "58", "20,7", "21,3", "33", "12", "860",
            ]],
            [_cell(value) for value in [
                "0:03:30,000", "Echauffement", "", "145", "3,00", "48",
                "0,98", "62", "20,7", "21,1", "34", "12", "900",
            ]],
        ])
    xml_rows = "\n".join(f"<Row>{''.join(row)}</Row>" for row in rows)
    return f"""<?xml version="1.0"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
 <Worksheet ss:Name="MetasoftStudio"><Table>{xml_rows}</Table></Worksheet>
</Workbook>""".encode("utf-8")


def _profile() -> dict:
    return {
        "email": "coach@example.test",
        "identity": {"last_name": "VAN DER VEEN", "first_name": "Noor"},
        "body_composition": {"height_cm": 180, "current_weight": 62},
        "professional_life": {},
        "equipment_and_tracking": {},
        "history_and_goals": {},
        "stress_test_results": {
            "thresholds": {
                "sv1": {"hr_bpm": 99, "pace_km_h": 9, "vo2_ml_kg_min": 20},
                "sv2": {"hr_bpm": 130, "pace_km_h": 12, "vo2_ml_kg_min": 39},
            },
            "measured_vo2max": 52,
            "max_hr": 180,
            "vma": 16,
        },
    }


class MetaSoftLocalApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.session_manager = SessionManager(str(self.base))
        self.session_manager.create_session("2026-07-08", "contas")
        self.profile_name = self.session_manager.add_profile(_profile())
        source_xml = self.base / "TCP__VAN DER VEEN_Noor_2026.06.10_12.38.06_.xml"
        source_xml.write_bytes(_metasoft_xml())
        self.xml_filename = self.session_manager.import_xml(str(source_xml))
        self.match = self.session_manager.create_match(self.profile_name, self.xml_filename)
        self.server = LocalMetaSoftServer(self.session_manager).start()
        self.base_url = f"http://127.0.0.1:{self.server.port}"

    def tearDown(self) -> None:
        self.server.stop()
        self.tmp.cleanup()

    def test_token_health_matches_and_analysis(self) -> None:
        status, payload = self._get("/api/health", token="bad-token")
        self.assertEqual(status, 403)
        self.assertEqual(payload["error"]["code"], "invalid_token")

        status, payload = self._get("/api/health")
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])

        status, payload = self._get("/api/session")
        self.assertEqual(status, 200)
        self.assertEqual(payload["session"]["name"], "2026-07-08_contas")

        status, payload = self._get("/api/matches")
        self.assertEqual(status, 200)
        self.assertEqual(len(payload["matches"]), 1)
        match_id = payload["matches"][0]["match_id"]
        self.assertEqual(payload["matches"][0]["profile_name"], self.profile_name)
        self.assertNotIn("/", match_id)

        status, payload = self._get(f"/api/matches/{match_id}/analysis")
        self.assertEqual(status, 200)
        self.assertEqual(payload["match"]["xml_filename"], self.xml_filename)
        self.assertEqual(payload["profile"]["body_composition"]["current_weight"], 62)
        economy = payload["analysis"]["computed"]["running_economy"][0]
        self.assertEqual(economy["mass_kg"], 62)
        self.assertEqual(payload["warnings"][0]["code"], "marker_provenance_missing")
        self.assertTrue(payload["warnings"][0]["blocking"])
        self.assertEqual(payload["source_of_truth"]["markers"], "python.metasoft_markers")

    def test_draft_survives_refresh_and_report_clears_it(self) -> None:
        match_id = self._match_id()
        draft = {
            "marker_selections": [{
                "name": "SV1",
                "action": "upsert",
                "mode": "previous",
                "t_seconds": 90,
                "window_start_seconds": 80,
                "window_end_seconds": 90,
            }],
        }

        status, payload = self._post(f"/api/matches/{match_id}/draft", draft)
        self.assertEqual(status, 200)
        self.assertTrue(payload["saved"])

        status, payload = self._get(f"/api/matches/{match_id}/analysis")
        self.assertEqual(status, 200)
        self.assertEqual(payload["metasoft_draft"], draft)
        self.assertEqual(
            self.session_manager.get_profile(self.profile_name),
            _profile(),
        )

        status, _payload = self._post(
            f"/api/matches/{match_id}/profile/report",
            {"marker_selections": [], "conflict_policy": "overwrite"},
        )
        self.assertEqual(status, 200)
        status, payload = self._get(f"/api/matches/{match_id}/analysis")
        self.assertEqual(status, 200)
        self.assertIsNone(payload["metasoft_draft"])

    def test_draft_is_ignored_after_xml_source_changes(self) -> None:
        match_id = self._match_id()
        status, _payload = self._post(
            f"/api/matches/{match_id}/draft",
            {"marker_selections": []},
        )
        self.assertEqual(status, 200)
        xml_path = Path(self.session_manager.get_xml_path(self.xml_filename))
        xml_path.write_bytes(xml_path.read_bytes() + b"\n")

        status, payload = self._get(f"/api/matches/{match_id}/analysis")

        self.assertEqual(status, 200)
        self.assertIsNone(payload["metasoft_draft"])
        self.assertTrue(any(
            warning["code"] == "metasoft_draft_stale"
            for warning in payload["warnings"]
        ))

    def test_identity_mismatch_blocks_preview_and_report_without_profile_write(self) -> None:
        profile = self.session_manager.get_profile(self.profile_name)
        profile["identity"] = {"last_name": "Mo", "first_name": "Arthur"}
        profile_path = self.session_manager.profile_path(self.profile_name)
        profile_path.write_text(json.dumps(profile), encoding="utf-8")
        original = self.session_manager.get_profile(self.profile_name)
        match_id = self._match_id()

        status, analysis = self._get(f"/api/matches/{match_id}/analysis")
        self.assertEqual(status, 200)
        self.assertEqual(analysis["warnings"][0]["code"], "identity_mismatch")
        self.assertTrue(analysis["warnings"][0]["blocking"])

        for suffix in ("report-preview", "report"):
            status, payload = self._post(
                f"/api/matches/{match_id}/profile/{suffix}",
                {"marker_selections": []},
            )
            self.assertEqual(status, 409)
            self.assertEqual(payload["error"]["code"], "identity_mismatch")
        self.assertEqual(self.session_manager.get_profile(self.profile_name), original)

    def test_missing_profile_identity_blocks_report_as_unverifiable(self) -> None:
        profile = self.session_manager.get_profile(self.profile_name)
        profile["identity"] = {}
        profile_path = self.session_manager.profile_path(self.profile_name)
        profile_path.write_text(json.dumps(profile), encoding="utf-8")

        status, payload = self._post(
            f"/api/matches/{self._match_id()}/profile/report",
            {"marker_selections": []},
        )

        self.assertEqual(status, 409)
        self.assertEqual(payload["error"]["code"], "identity_unverifiable")

    def test_post_officialize_with_invalid_token_returns_403(self) -> None:
        match_id = self._match_id()
        status, payload = self._post(
            f"/api/matches/{match_id}/markers/officialize",
            {"marker_selections": []},
            token="bad-token",
        )

        self.assertEqual(status, 403)
        self.assertEqual(payload["error"]["code"], "invalid_token")

    def test_metasoft_page_with_invalid_query_token_returns_403(self) -> None:
        match_id = self._match_id()
        status, payload = self._get(f"/metasoft?match_id={match_id}&token=bad-token")

        self.assertEqual(status, 403)
        self.assertEqual(payload["error"]["code"], "invalid_token")

    def test_static_traversal_returns_404_without_file_leak(self) -> None:
        status, payload = self._get("/%2e%2e/README.md")

        self.assertEqual(status, 404)
        self.assertEqual(payload["error"]["code"], "match_not_found")
        self.assertNotIn("Enduraw Testing Tool", json.dumps(payload))

    def test_officialize_point_and_range_ignore_preview_values(self) -> None:
        match_id = self._match_id()
        status, payload = self._post(
            f"/api/matches/{match_id}/markers/officialize",
            {
                "marker_selections": [
                    {
                        "name": "SV1",
                        "mode": "point",
                        "t_seconds": 62,
                        "window_start_seconds": None,
                        "window_end_seconds": None,
                        "values": {"fc_bpm": 999},
                    },
                    {
                        "name": "SV2",
                        "mode": "range",
                        "window_start_seconds": 60,
                        "window_end_seconds": 90,
                        "preview": {"fc_bpm": 999},
                    },
                ]
            },
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload["markers"]["SV1"]["values"]["fc_bpm"], 120)
        self.assertEqual(payload["markers"]["SV2"]["point_count"], 2)
        self.assertEqual(payload["markers"]["SV2"]["values"]["fc_bpm"], 122)
        self.assertEqual(payload["source"], "python.build_metasoft_marker")

    def test_officialize_previous_uses_window_and_keeps_clicked_time(self) -> None:
        match_id = self._match_id()

        status, payload = self._post(
            f"/api/matches/{match_id}/markers/officialize",
            {
                "marker_selections": [{
                    "name": "SV1",
                    "mode": "previous",
                    "t_seconds": 120,
                    "window_start_seconds": 90,
                    "values": {"fc_bpm": 999},
                }]
            },
        )

        marker = payload["markers"]["SV1"]
        self.assertEqual(status, 200)
        self.assertEqual(marker["mode"], "previous")
        self.assertEqual(marker["t_seconds"], 120)
        self.assertEqual(marker["window_start_seconds"], 90)
        self.assertEqual(marker["window_end_seconds"], 120)
        self.assertEqual(marker["point_count"], 2)
        self.assertEqual(marker["values"]["fc_bpm"], 127)

    def test_analysis_payload_is_slim_and_officialize_still_uses_python(self) -> None:
        match_id = self._match_id()
        status, payload = self._get(f"/api/matches/{match_id}/analysis")

        self.assertEqual(status, 200)
        point = payload["analysis"]["points"][0]
        self.assertNotIn("raw", point)
        self.assertNotIn("value_sources", point)

        status, payload = self._post(
            f"/api/matches/{match_id}/markers/officialize",
            {"marker_selections": [{"name": "SV1", "mode": "point", "t_seconds": 60}]},
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload["markers"]["SV1"]["values"]["fc_bpm"], 120)

    def test_manual_running_economy_ignores_react_calculated_values(self) -> None:
        match_id = self._weighted_match_id()
        row = {
            "stage_index": 1,
            "speed_kmh": 10,
            "start_seconds": 60,
            "end_seconds": 120,
            "exclusions": [{"start_seconds": 80, "end_seconds": 90}],
            "point_count": 3,
            "vo2_l_min": 999,
            "vco2_l_min": 999,
            "ec_j_kg_m": 999,
            "percent_vo2max": 999,
            "sources": {"selection": "manual_stable_stage"},
        }

        status, payload = self._post(
            f"/api/matches/{match_id}/running-economy/manual",
            {"selections": [row]},
        )

        self.assertEqual(status, 200)
        saved_row = payload["manual_running_economy"]["rows"][0]
        self.assertNotEqual(saved_row["ec_j_kg_m"], 999)
        self.assertNotEqual(saved_row["percent_vo2max"], 999)
        self.assertEqual(
            payload["manual_running_economy"]["source"],
            "python.metasoft_analysis.manual_running_economy",
        )

        status, payload = self._get(f"/api/matches/{match_id}/analysis")
        self.assertEqual(status, 200)
        self.assertEqual(payload["manual_running_economy"]["rows"][0]["stage_index"], 1)

    def test_manual_running_economy_percent_uses_vo2max_marker_range(self) -> None:
        match_id = self._weighted_match_id()

        status, payload = self._post(
            f"/api/matches/{match_id}/running-economy/manual",
            {
                "selections": [{
                    "stage_index": 1,
                    "start_seconds": 60,
                    "end_seconds": 120,
                    "exclusions": [],
                }],
                "marker_selections": [{
                    "name": "VO2_max",
                    "mode": "range",
                    "window_start_seconds": 60,
                    "window_end_seconds": 120,
                }],
            },
        )

        self.assertEqual(status, 200)
        row = payload["manual_running_economy"]["rows"][0]
        self.assertAlmostEqual(row["percent_vo2max"], 100, places=2)
        self.assertEqual(row["sources"]["vo2max"], "metasoft_marker.vo2_max")

    def test_manual_running_economy_persists_disabled_stage_adjustments(self) -> None:
        match_id = self._weighted_two_stage_match_id()
        stage_selections = [
            {"stage_index": 1, "enabled": False},
            {"stage_index": 2, "enabled": True},
        ]

        status, payload = self._post(
            f"/api/matches/{match_id}/running-economy/manual",
            {
                "selections": [
                    {
                        "stage_index": 1,
                        "start_seconds": 60,
                        "end_seconds": 90,
                        "exclusions": [{"start_seconds": 70, "end_seconds": 80}],
                    },
                    {
                        "stage_index": 2,
                        "start_seconds": 180,
                        "end_seconds": 210,
                        "exclusions": [{"start_seconds": 190, "end_seconds": 200}],
                    },
                ],
                "stage_selections": stage_selections,
            },
        )

        self.assertEqual(status, 200)
        rows = payload["manual_running_economy"]["rows"]
        self.assertEqual([row["stage_index"] for row in rows], [1, 2])
        self.assertEqual(rows[0]["start_seconds"], 60)
        self.assertEqual(rows[0]["end_seconds"], 90)
        self.assertEqual(
            rows[0]["exclusions"],
            [{"start_seconds": 70.0, "end_seconds": 80.0}],
        )
        self.assertEqual(rows[1]["start_seconds"], 180)
        self.assertEqual(rows[1]["end_seconds"], 210)
        self.assertEqual(
            rows[1]["exclusions"],
            [{"start_seconds": 190.0, "end_seconds": 200.0}],
        )
        self.assertEqual(
            payload["manual_running_economy"]["stage_selections"],
            stage_selections,
        )
        saved = self.session_manager.get_manual_running_economy(
            match_id,
            self.session_manager.matches[-1],
        )
        self.assertEqual(saved, payload["manual_running_economy"])

        status, analysis_payload = self._get(f"/api/matches/{match_id}/analysis")

        self.assertEqual(status, 200)
        self.assertEqual(
            analysis_payload["manual_running_economy"],
            payload["manual_running_economy"],
        )

    def test_manual_running_economy_rejects_invalid_bounds_without_writing(self) -> None:
        match_id = self._weighted_match_id()

        status, payload = self._post(
            f"/api/matches/{match_id}/running-economy/manual",
            {
                "selections": [{
                    "stage_index": 1,
                    "start_seconds": 120,
                    "end_seconds": 60,
                    "exclusions": [],
                }]
            },
        )

        self.assertEqual(status, 400)
        self.assertEqual(payload["error"]["code"], "invalid_running_economy_manual")
        self.assertEqual(
            self.session_manager.manual_running_economy_state(
                match_id,
                self.session_manager.matches[-1],
            )["status"],
            "missing",
        )

    def test_manual_running_economy_clear_removes_sidecar(self) -> None:
        match_id = self._weighted_match_id()
        status, payload = self._post(
            f"/api/matches/{match_id}/running-economy/manual",
            {
                "selections": [{
                    "stage_index": 1,
                    "start_seconds": 60,
                    "end_seconds": 120,
                    "exclusions": [],
                }]
            },
        )
        self.assertEqual(status, 200)

        status, payload = self._post(
            f"/api/matches/{match_id}/running-economy/manual",
            {"selections": []},
        )

        self.assertEqual(status, 200)
        self.assertIsNone(payload["manual_running_economy"])
        status, payload = self._get(f"/api/matches/{match_id}/analysis")
        self.assertEqual(status, 200)
        self.assertIsNone(payload["manual_running_economy"])

    def test_manual_running_economy_without_xml_weight_has_no_profile_fallback(self) -> None:
        match_id = self._match_id()

        status, payload = self._post(
            f"/api/matches/{match_id}/running-economy/manual",
            {
                "selections": [{
                    "stage_index": 1,
                    "start_seconds": 60,
                    "end_seconds": 120,
                    "exclusions": [],
                }]
            },
        )

        self.assertEqual(status, 200)
        row = payload["manual_running_economy"]["rows"][0]
        self.assertIsNone(row["ec_j_kg_m"])
        self.assertIn(
            "missing_xml_mass_kg",
            {warning["code"] for warning in payload["manual_running_economy"]["warnings"]},
        )

    def test_manual_running_economy_fingerprint_rejects_stale_and_legacy(self) -> None:
        match_id = self._weighted_match_id()
        match = self.session_manager.matches[-1]
        data = {
            "source": "python.metasoft_analysis.manual_running_economy",
            "rows": [{
                "stage_index": 1,
                "ec_j_kg_m": 4.2,
                "sources": {"vo2max": "metasoft_marker.vo2_max"},
            }],
        }
        fingerprint = self.session_manager.build_manual_running_economy_fingerprint(
            match,
            data,
        )

        self.session_manager.save_manual_running_economy(match_id, data, fingerprint)
        self.assertEqual(
            self.session_manager.get_manual_running_economy(match_id, match),
            data,
        )
        xml_path = self.session_manager.xml_path(match.xml_filename)
        xml_path.write_bytes(xml_path.read_bytes() + b"\n")
        self.assertEqual(
            self.session_manager.manual_running_economy_state(match_id, match)["status"],
            "stale",
        )

        path = self.session_manager.current_session_path / "running_economy_manual.json"
        path.write_text(json.dumps({match_id: {"fingerprint": {}, "data": data}}), encoding="utf-8")
        state = self.session_manager.manual_running_economy_state(match_id, match)
        self.assertEqual(state["status"], "stale")
        self.assertEqual(state["reason"], "legacy_fingerprint")

    def test_manual_economy_fingerprint_ignores_unrelated_profile_change(self) -> None:
        match_id = self._weighted_match_id()
        match = self.session_manager.matches[-1]
        status, payload = self._post(
            f"/api/matches/{match_id}/running-economy/manual",
            {"selections": [{
                "stage_index": 1,
                "start_seconds": 60,
                "end_seconds": 120,
                "exclusions": [],
            }]},
        )
        self.assertEqual(status, 200)

        profile = self.session_manager.get_profile(match.profile_name)
        profile["professional_life"]["occupation"] = "Coach"
        self.session_manager.update_profile(match.profile_name, profile)

        state = self.session_manager.manual_running_economy_state(match_id, match)
        self.assertEqual(state["status"], "ok")
        self.assertEqual(state["data"], payload["manual_running_economy"])

    def test_manual_economy_stale_is_blocking_for_xml_or_profile_vo2max_change(self) -> None:
        for change in ("xml", "vo2max"):
            with self.subTest(change=change):
                match_id = self._weighted_match_id()
                match = self.session_manager.matches[-1]
                status, _payload = self._post(
                    f"/api/matches/{match_id}/running-economy/manual",
                    {"selections": [{
                        "stage_index": 1,
                        "start_seconds": 60,
                        "end_seconds": 120,
                        "exclusions": [],
                    }]},
                )
                self.assertEqual(status, 200)
                if change == "xml":
                    xml_path = self.session_manager.xml_path(match.xml_filename)
                    xml_path.write_bytes(xml_path.read_bytes() + b"\n")
                else:
                    profile = self.session_manager.get_profile(match.profile_name)
                    profile["stress_test_results"]["measured_vo2max"] = 60
                    self.session_manager.update_profile(match.profile_name, profile)

                status, payload = self._get(f"/api/matches/{match_id}/analysis")
                self.assertEqual(status, 200)
                warning = next(
                    item for item in payload["warnings"]
                    if item["code"] == "manual_running_economy_stale"
                )
                self.assertTrue(warning["blocking"])
                self.assertIsNone(payload["manual_running_economy"])
                self.session_manager.clear_manual_running_economy(match_id)

    def test_corrupt_manual_economy_warns_and_blocks_report_without_overwrite(self) -> None:
        match_id = self._weighted_match_id()
        match = self.session_manager.matches[-1]
        path = self.session_manager.current_session_path / "running_economy_manual.json"
        path.write_text("{broken", encoding="utf-8")
        original_profile = self.session_manager.get_profile(match.profile_name)

        status, payload = self._get(f"/api/matches/{match_id}/analysis")
        self.assertEqual(status, 200)
        self.assertTrue(any(
            warning["code"] == "manual_running_economy_corrupt" and warning["blocking"]
            for warning in payload["warnings"]
        ))
        status, payload = self._post(
            f"/api/matches/{match_id}/profile/report",
            {
                "marker_selections": [{"name": "SV1", "mode": "point", "t_seconds": 60}],
                "conflict_policy": "overwrite",
            },
        )
        self.assertEqual(status, 409)
        self.assertEqual(payload["error"]["code"], "manual_running_economy_corrupt")
        self.assertEqual(self.session_manager.get_profile(match.profile_name), original_profile)
        self.assertEqual(path.read_text(encoding="utf-8"), "{broken")

    def test_manual_economy_atomic_replace_failure_preserves_old_bytes(self) -> None:
        match_id = self._weighted_match_id()
        match = self.session_manager.matches[-1]
        status, payload = self._post(
            f"/api/matches/{match_id}/running-economy/manual",
            {"selections": [{
                "stage_index": 1,
                "start_seconds": 60,
                "end_seconds": 120,
                "exclusions": [],
            }]},
        )
        self.assertEqual(status, 200)
        path = self.session_manager.current_session_path / "running_economy_manual.json"
        original_bytes = path.read_bytes()
        data = payload["manual_running_economy"]
        fingerprint = self.session_manager.build_manual_running_economy_fingerprint(
            match,
            data,
        )

        with patch("core.session_manager.os.replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.session_manager.save_manual_running_economy(match_id, data, fingerprint)

        self.assertEqual(path.read_bytes(), original_bytes)
        self.assertEqual(list(path.parent.glob(f".{path.name}.*.tmp")), [])

    def test_officialize_rejects_point_times_outside_raw_bounds(self) -> None:
        match_id = self._match_id()
        for t_seconds in (-1, 121):
            with self.subTest(t_seconds=t_seconds):
                status, payload = self._post(
                    f"/api/matches/{match_id}/markers/officialize",
                    {
                        "marker_selections": [
                            {"name": "SV1", "mode": "point", "t_seconds": t_seconds}
                        ]
                    },
                )

                self.assertEqual(status, 422)
                self.assertEqual(payload["error"]["code"], "marker_blocked")
                marker = payload["error"]["details"]["marker"]
                self.assertEqual(marker["status"], "blocked")
                self.assertEqual(marker["warnings"][0]["code"], "point_out_of_bounds")

    def test_officialize_rejects_non_finite_point_time(self) -> None:
        match_id = self._match_id()
        status, payload = self._post(
            f"/api/matches/{match_id}/markers/officialize",
            {
                "marker_selections": [
                    {"name": "SV1", "mode": "point", "t_seconds": "nan"}
                ]
            },
        )

        self.assertEqual(status, 400)
        self.assertEqual(payload["error"]["code"], "invalid_marker_selection")

    def test_core_marker_blocks_non_finite_point_time(self) -> None:
        marker = build_metasoft_marker(
            [{"t_seconds": 0, "values": {"fc_bpm": 80}}],
            "SV1",
            t_seconds=float("inf"),
        )

        self.assertEqual(marker["status"], "blocked")
        self.assertEqual(marker["warnings"][0]["code"], "invalid_point_time")

    def test_core_marker_blocks_bool_point_time(self) -> None:
        marker = build_metasoft_marker(
            [{"t_seconds": 0, "values": {"fc_bpm": 80}}],
            "SV1",
            t_seconds=True,
        )

        self.assertEqual(marker["status"], "blocked")
        self.assertEqual(marker["warnings"][0]["code"], "invalid_point_time")

    def test_report_preview_reports_conflicts_without_writing_profile(self) -> None:
        match_id = self._match_id()
        status, payload = self._post(
            f"/api/matches/{match_id}/profile/report-preview",
            {"marker_selections": [{"name": "SV1", "mode": "point", "t_seconds": 60}]},
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "conflict")
        conflict_paths = {conflict["path"] for conflict in payload["conflicts"]}
        self.assertIn("stress_test_results.thresholds.sv1.hr_bpm", conflict_paths)
        current_profile = self.session_manager.get_profile(self.profile_name)
        self.assertEqual(current_profile["stress_test_results"]["thresholds"]["sv1"]["hr_bpm"], 99)

    def test_report_conflict_requires_overwrite_before_writing_profile(self) -> None:
        match_id = self._match_id()
        selection = {"name": "SV1", "mode": "point", "t_seconds": 60}

        status, payload = self._post(
            f"/api/matches/{match_id}/profile/report",
            {"marker_selections": [selection]},
        )

        self.assertEqual(status, 409)
        self.assertEqual(payload["error"]["code"], "profile_conflict")
        current_profile = self.session_manager.get_profile(self.profile_name)
        self.assertEqual(current_profile["stress_test_results"]["thresholds"]["sv1"]["hr_bpm"], 99)
        self.assertEqual(self.server.consume_pending_profile_updates(), [])

        status, payload = self._post(
            f"/api/matches/{match_id}/profile/report",
            {"marker_selections": [selection], "conflict_policy": "overwrite"},
        )

        self.assertEqual(status, 200)
        self.assertIn("stress_test_results.thresholds.sv1.hr_bpm", payload["updated_paths"])
        updated_profile = self.session_manager.get_profile(payload["profile_name"])
        self.assertEqual(updated_profile["stress_test_results"]["thresholds"]["sv1"]["hr_bpm"], 120)
        self.assertEqual(self.server.consume_pending_profile_updates(), [payload["profile_name"]])
        self.assertEqual(self.server.consume_pending_profile_updates(), [])

    def test_profile_atomic_write_failure_preserves_existing_bytes(self) -> None:
        profile_path = self.session_manager.profile_path(self.profile_name)
        original_bytes = profile_path.read_bytes()
        profile = self.session_manager.get_profile(self.profile_name)
        profile["professional_life"]["occupation"] = "Coach"

        with patch("core.session_manager.os.replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.session_manager.update_profile(self.profile_name, profile)

        self.assertEqual(profile_path.read_bytes(), original_bytes)
        self.assertEqual(list(profile_path.parent.glob(f".{profile_path.name}.*.tmp")), [])

    def test_report_rejects_duplicate_marker_names_without_writing(self) -> None:
        match_id = self._match_id()
        original = self.session_manager.get_profile(self.profile_name)

        status, payload = self._post(
            f"/api/matches/{match_id}/profile/report",
            {
                "marker_selections": [
                    {"name": "SV1", "action": "upsert", "mode": "point", "t_seconds": 60},
                    {"name": "sv1", "action": "delete"},
                ],
                "conflict_policy": "overwrite",
            },
        )

        self.assertEqual(status, 400)
        self.assertEqual(payload["error"]["code"], "duplicate_marker_selection")
        self.assertEqual(self.session_manager.get_profile(self.profile_name), original)
        self.assertEqual(self.server.consume_pending_profile_updates(), [])

    def test_report_is_atomic_when_one_marker_mapping_is_incomplete(self) -> None:
        match_id = self._match_id()
        context = self.server._match_context(match_id)
        point = next(
            item for item in context["analysis"]["points"]
            if item["t_seconds"] == 60
        )
        point["values"]["fc_bpm"] = None
        original = self.session_manager.get_profile(self.profile_name)

        status, payload = self._post(
            f"/api/matches/{match_id}/profile/report",
            {
                "marker_selections": [
                    {"name": "SV1", "action": "upsert", "mode": "point", "t_seconds": 60},
                    {"name": "VMA", "action": "upsert", "mode": "point", "t_seconds": 120},
                ],
                "conflict_policy": "overwrite",
            },
        )

        self.assertEqual(status, 422)
        self.assertEqual(payload["error"]["code"], "marker_blocked")
        self.assertEqual(self.session_manager.get_profile(self.profile_name), original)
        self.assertEqual(self.server.consume_pending_profile_updates(), [])

    def test_report_delete_requires_overwrite_and_removes_only_owned_fields(self) -> None:
        match_id = self._match_id()
        selection = {"name": "SV1", "action": "delete"}

        status, payload = self._post(
            f"/api/matches/{match_id}/profile/report",
            {"marker_selections": [selection]},
        )

        self.assertEqual(status, 409)
        self.assertEqual(payload["error"]["code"], "profile_conflict")
        self.assertEqual(
            payload["error"]["details"]["conflicts"][0]["path"],
            "stress_test_results.thresholds.sv1",
        )

        status, payload = self._post(
            f"/api/matches/{match_id}/profile/report",
            {"marker_selections": [selection], "conflict_policy": "overwrite"},
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload["confirmed_markers"]["SV1"]["status"], "deleted")
        self.assertEqual(payload["confirmed_markers"]["SV1"]["action"], "delete")
        self.assertIn("stress_test_results.thresholds.sv1", payload["updated_paths"])
        updated = self.session_manager.get_profile(self.profile_name)
        self.assertNotIn("sv1", updated["stress_test_results"]["thresholds"])
        self.assertEqual(
            updated["stress_test_results"]["thresholds"]["sv2"],
            _profile()["stress_test_results"]["thresholds"]["sv2"],
        )
        self.assertEqual(updated["stress_test_results"]["vma"], 16)

    def test_report_returns_canonical_range_used_by_profile_and_ui(self) -> None:
        match_id = self._match_id()

        status, payload = self._post(
            f"/api/matches/{match_id}/profile/report",
            {
                "marker_selections": [{
                    "name": "VO2_max",
                    "action": "upsert",
                    "mode": "range",
                    "t_seconds": 75,
                    "window_start_seconds": 60,
                    "window_end_seconds": 90,
                }],
                "conflict_policy": "overwrite",
            },
        )

        self.assertEqual(status, 200)
        marker = payload["confirmed_markers"]["VO2_max"]
        self.assertEqual(marker["action"], "upsert")
        self.assertEqual(marker["mode"], "range")
        self.assertEqual(marker["t_seconds"], 75)
        self.assertEqual(marker["window_start_seconds"], 60)
        self.assertEqual(marker["window_end_seconds"], 90)
        self.assertEqual(marker["values"]["fc_bpm"], 122)
        updated = self.session_manager.get_profile(self.profile_name)
        self.assertEqual(updated["stress_test_results"]["max_hr"], 122)
        self.assertEqual(
            updated["stress_test_results"]["measured_vo2max"],
            marker["values"]["vo2_ml_kg_min"],
        )

    def test_analysis_reloads_cumulative_confirmed_and_deleted_markers(self) -> None:
        match_id = self._match_id()
        status, _payload = self._post(
            f"/api/matches/{match_id}/profile/report",
            {
                "marker_selections": [
                    {"name": "SV1", "mode": "point", "t_seconds": 60},
                ],
                "conflict_policy": "overwrite",
            },
        )
        self.assertEqual(status, 200)
        status, _payload = self._post(
            f"/api/matches/{match_id}/profile/report",
            {
                "marker_selections": [{"name": "VMA", "action": "delete"}],
                "conflict_policy": "overwrite",
            },
        )
        self.assertEqual(status, 200)

        self.session_manager._load_matches()
        status, payload = self._get(f"/api/matches/{match_id}/analysis")

        self.assertEqual(status, 200)
        self.assertEqual(payload["confirmed_markers"]["SV1"]["values"]["fc_bpm"], 120)
        self.assertEqual(payload["deleted_markers"], ["VMA"])
        self.assertNotIn("VMA", payload["confirmed_markers"])

    def test_marker_provenance_ignores_unrelated_profile_change_but_not_threshold_change(self) -> None:
        match_id = self._match_id()
        status, _payload = self._post(
            f"/api/matches/{match_id}/profile/report",
            {
                "marker_selections": [
                    {"name": "SV1", "mode": "point", "t_seconds": 60},
                ],
                "conflict_policy": "overwrite",
            },
        )
        self.assertEqual(status, 200)
        match = self.session_manager.matches[0]

        profile = self.session_manager.get_profile(self.profile_name)
        profile["professional_life"]["occupation"] = "Coach"
        self.session_manager.update_profile(self.profile_name, profile)
        self.assertTrue(
            self.session_manager.validate_metasoft_report(match, profile)["valid"]
        )

        profile["stress_test_results"]["thresholds"]["sv1"]["hr_bpm"] = 999
        self.session_manager.update_profile(self.profile_name, profile)
        validation = self.session_manager.validate_metasoft_report(match, profile)
        self.assertFalse(validation["valid"])
        self.assertEqual(validation["reason"], "profile_markers_changed")

    def test_marker_provenance_becomes_stale_when_xml_changes(self) -> None:
        match_id = self._match_id()
        status, _payload = self._post(
            f"/api/matches/{match_id}/profile/report",
            {
                "marker_selections": [
                    {"name": "SV1", "mode": "point", "t_seconds": 60},
                ],
                "conflict_policy": "overwrite",
            },
        )
        self.assertEqual(status, 200)
        xml_path = self.session_manager.xml_path(self.xml_filename)
        xml_path.write_bytes(xml_path.read_bytes() + b"\n")

        status, payload = self._get(f"/api/matches/{match_id}/analysis")

        self.assertEqual(status, 200)
        warnings = {warning["code"]: warning for warning in payload["warnings"]}
        self.assertEqual(warnings["marker_provenance_stale"]["reason"], "source_changed")
        self.assertTrue(warnings["marker_provenance_stale"]["blocking"])
        self.assertEqual(payload["confirmed_markers"], {})
        self.assertEqual(payload["deleted_markers"], [])

    def test_provenance_write_failure_returns_error_and_keeps_export_blocked(self) -> None:
        match_id = self._match_id()
        original_save = self.session_manager._save_matches
        save_calls = 0

        def fail_final_save():
            nonlocal save_calls
            save_calls += 1
            if save_calls == 1:
                raise OSError("disk full")
            original_save()

        with patch.object(
            self.session_manager,
            "_save_matches",
            side_effect=fail_final_save,
        ):
            status, payload = self._post(
                f"/api/matches/{match_id}/profile/report",
                {
                    "marker_selections": [
                        {"name": "SV1", "mode": "point", "t_seconds": 60},
                    ],
                    "conflict_policy": "overwrite",
                },
            )

        self.assertEqual(status, 500)
        self.assertEqual(payload["error"]["code"], "metasoft_report_failed")
        profile = self.session_manager.get_profile(self.profile_name)
        self.assertEqual(profile["stress_test_results"]["thresholds"]["sv1"]["hr_bpm"], 99)
        self.assertEqual(self.server.consume_pending_profile_updates(), [])
        validation = self.session_manager.validate_metasoft_report(
            self.session_manager.matches[0],
            profile,
        )
        self.assertFalse(validation["valid"])
        self.session_manager._load_matches()
        persisted = self.session_manager.validate_metasoft_report(
            self.session_manager.matches[0],
            profile,
        )
        self.assertFalse(persisted["valid"])

    def test_manual_save_failure_rolls_back_profile_ec_and_pending_update(self) -> None:
        match_id = self._weighted_match_id()
        match = self.session_manager.matches[-1]
        original_profile = self.session_manager.get_profile(match.profile_name)
        original_report = deepcopy(match.metasoft_report)
        sidecar = self.session_manager.current_session_path / "running_economy_manual.json"

        with patch.object(
            self.session_manager,
            "save_manual_running_economy",
            side_effect=OSError("disk full"),
        ):
            status, payload = self._post(
                f"/api/matches/{match_id}/profile/report",
                {
                    "marker_selections": [{"name": "SV1", "mode": "point", "t_seconds": 60}],
                    "manual_running_economy_selections": [{
                        "stage_index": 1,
                        "start_seconds": 60,
                        "end_seconds": 120,
                        "exclusions": [],
                    }],
                    "manual_running_economy_stage_selections": [
                        {"stage_index": 1, "enabled": True},
                    ],
                    "conflict_policy": "overwrite",
                },
            )

        self.assertEqual(status, 500)
        self.assertEqual(payload["error"]["code"], "metasoft_report_failed")
        self.assertEqual(self.session_manager.get_profile(match.profile_name), original_profile)
        self.assertEqual(match.metasoft_report, original_report)
        self.assertFalse(sidecar.exists())
        self.assertEqual(self.server.consume_pending_profile_updates(), [])

    def test_provenance_failure_restores_previous_cumulative_report(self) -> None:
        match_id = self._match_id()
        status, _payload = self._post(
            f"/api/matches/{match_id}/profile/report",
            {
                "marker_selections": [{"name": "SV1", "mode": "point", "t_seconds": 60}],
                "conflict_policy": "overwrite",
            },
        )
        self.assertEqual(status, 200)
        self.server.consume_pending_profile_updates()
        match = self.session_manager.matches[0]
        original_profile = self.session_manager.get_profile(match.profile_name)
        original_report = deepcopy(match.metasoft_report)

        with patch.object(
            self.session_manager,
            "record_metasoft_report",
            side_effect=OSError("disk full"),
        ):
            status, payload = self._post(
                f"/api/matches/{match_id}/profile/report",
                {
                    "marker_selections": [{"name": "SV2", "mode": "point", "t_seconds": 90}],
                    "conflict_policy": "overwrite",
                },
            )

        self.assertEqual(status, 500)
        self.assertEqual(payload["error"]["code"], "metasoft_report_failed")
        self.assertEqual(self.session_manager.get_profile(match.profile_name), original_profile)
        self.assertEqual(match.metasoft_report, original_report)
        validation = self.session_manager.validate_metasoft_report(match, original_profile)
        self.assertTrue(validation["valid"])
        self.assertEqual(set(validation["markers"]), {"SV1"})
        self.assertEqual(self.server.consume_pending_profile_updates(), [])

    def test_tampered_canonical_marker_projection_invalidates_provenance(self) -> None:
        match_id = self._match_id()
        status, _payload = self._post(
            f"/api/matches/{match_id}/profile/report",
            {
                "marker_selections": [{"name": "SV1", "mode": "point", "t_seconds": 60}],
                "conflict_policy": "overwrite",
            },
        )
        self.assertEqual(status, 200)
        match = self.session_manager.matches[0]
        match.metasoft_report["markers"]["SV1"]["values"]["fc_bpm"] = 999
        self.session_manager._save_matches()

        validation = self.session_manager.validate_metasoft_report(
            match,
            self.session_manager.get_profile(match.profile_name),
        )
        self.assertFalse(validation["valid"])
        self.assertEqual(validation["reason"], "marker_profile_mismatch")

    def test_matches_without_metasoft_report_remain_loadable(self) -> None:
        matches_path = self.session_manager.current_session_path / "matches.json"
        raw = json.loads(matches_path.read_text(encoding="utf-8"))
        self.assertNotIn("metasoft_report", raw[0])

        self.session_manager._load_matches()

        self.assertIsNone(self.session_manager.matches[0].metasoft_report)

    def test_report_conflict_does_not_persist_manual_running_economy(self) -> None:
        match_id = self._weighted_match_id()
        match = self.session_manager.matches[-1]
        status, payload = self._post(
            f"/api/matches/{match_id}/profile/report",
            {
                "marker_selections": [{"name": "SV1", "mode": "point", "t_seconds": 60}],
                "manual_running_economy_selections": [{
                    "stage_index": 1,
                    "start_seconds": 60,
                    "end_seconds": 120,
                    "exclusions": [],
                }],
                "manual_running_economy_stage_selections": [
                    {"stage_index": 1, "enabled": True},
                ],
            },
        )

        self.assertEqual(status, 409)
        self.assertEqual(payload["error"]["code"], "profile_conflict")
        self.assertEqual(
            self.session_manager.manual_running_economy_state(match_id, match)["status"],
            "missing",
        )

    def test_report_persists_manual_running_economy_with_final_fingerprint(self) -> None:
        match_id = self._weighted_match_id()
        match = self.session_manager.matches[-1]
        status, payload = self._post(
            f"/api/matches/{match_id}/profile/report",
            {
                "marker_selections": [{"name": "SV1", "mode": "point", "t_seconds": 60}],
                "manual_running_economy_selections": [{
                    "stage_index": 1,
                    "start_seconds": 60,
                    "end_seconds": 120,
                    "exclusions": [],
                }],
                "manual_running_economy_stage_selections": [
                    {"stage_index": 1, "enabled": True},
                ],
                "conflict_policy": "overwrite",
            },
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload["manual_running_economy"]["rows"][0]["stage_index"], 1)
        self.assertEqual(
            payload["manual_running_economy"]["rows"][0]["sources"]["vo2max"],
            "profile.stress_test_results.measured_vo2max",
        )
        self.assertEqual(
            self.session_manager.manual_running_economy_state(match_id, match)["status"],
            "ok",
        )

        status, payload = self._get(f"/api/matches/{match_id}/analysis")

        self.assertEqual(status, 200)
        self.assertEqual(payload["manual_running_economy"]["rows"][0]["stage_index"], 1)
        self.assertEqual(
            payload["manual_running_economy"]["stage_selections"],
            [{"stage_index": 1, "enabled": True}],
        )

    def test_react_export_endpoint_is_removed(self) -> None:
        match_id = self._match_id()
        status, payload = self._post(
            f"/api/matches/{match_id}/export",
            {
                "marker_selections": [
                    {"name": "VMA", "mode": "point", "t_seconds": 120}
                ],
            },
        )

        self.assertEqual(status, 404)
        self.assertEqual(payload["error"]["code"], "match_not_found")
        self.session_manager._load_matches()
        self.assertFalse(self.session_manager.matches[0].exported)

    def _match_id(self) -> str:
        status, payload = self._get("/api/matches")
        self.assertEqual(status, 200)
        return payload["matches"][0]["match_id"]

    def _weighted_match_id(self) -> str:
        profile_name = self.session_manager.add_profile(_profile())
        source_xml = self.base / "weighted_metasoft.xml"
        source_xml.write_bytes(_metasoft_xml(include_weight=True))
        xml_filename = self.session_manager.import_xml(str(source_xml))
        self.session_manager.create_match(profile_name, xml_filename)
        return self.server.url_for_match({
            "profile_name": profile_name,
            "xml_filename": xml_filename,
        }).split("match_id=", 1)[1].split("&", 1)[0]

    def _weighted_two_stage_match_id(self) -> str:
        profile_name = self.session_manager.add_profile(_profile())
        source_xml = self.base / "weighted_two_stage_metasoft.xml"
        source_xml.write_bytes(_metasoft_xml(include_weight=True, two_stages=True))
        xml_filename = self.session_manager.import_xml(str(source_xml))
        self.session_manager.create_match(profile_name, xml_filename)
        return self.server.url_for_match({
            "profile_name": profile_name,
            "xml_filename": xml_filename,
        }).split("match_id=", 1)[1].split("&", 1)[0]

    def _get(self, path: str, token: str | None = None):
        return self._request("GET", path, None, token)

    def _post(self, path: str, payload: dict, token: str | None = None):
        return self._request("POST", path, payload, token)

    def _request(self, method: str, path: str, payload: dict | None, token: str | None):
        headers = {"X-Enduraw-Local-Token": self.server.token if token is None else token}
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(f"{self.base_url}{path}", data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
