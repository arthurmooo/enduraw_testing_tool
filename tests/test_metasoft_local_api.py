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
from pathlib import Path
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
        "identity": {"last_name": "Mo", "first_name": "Arthur"},
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
        self.assertEqual(payload["warnings"][0]["code"], "identity_mismatch")
        self.assertEqual(payload["source_of_truth"]["markers"], "python.metasoft_markers")

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
        fingerprint = self.session_manager.build_match_fingerprint(
            self.session_manager.matches[-1]
        )
        saved = self.session_manager.get_manual_running_economy(match_id, fingerprint)
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
        fingerprint = self.session_manager.build_match_fingerprint(
            self.session_manager.matches[-1]
        )
        self.assertIsNone(self.session_manager.get_manual_running_economy(match_id, fingerprint))

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
        fingerprint = self.session_manager.build_match_fingerprint(match)
        data = {
            "source": "python.metasoft_analysis.manual_running_economy",
            "rows": [{"stage_index": 1, "ec_j_kg_m": 4.2}],
        }

        self.session_manager.save_manual_running_economy(match_id, data, fingerprint)
        self.assertEqual(
            self.session_manager.get_manual_running_economy(match_id, fingerprint),
            data,
        )
        stale = {**fingerprint, "xml": {**fingerprint["xml"], "size": 1}}
        self.assertIsNone(self.session_manager.get_manual_running_economy(match_id, stale))

        path = self.session_manager.current_session_path / "running_economy_manual.json"
        path.write_text(json.dumps({match_id: data}), encoding="utf-8")
        self.assertIsNone(self.session_manager.get_manual_running_economy(match_id, fingerprint))

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

    def test_report_conflict_does_not_persist_manual_running_economy(self) -> None:
        match_id = self._weighted_match_id()
        match = self.session_manager.matches[-1]
        fingerprint = self.session_manager.build_match_fingerprint(match)

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
        self.assertIsNone(
            self.session_manager.get_manual_running_economy(match_id, fingerprint)
        )

    def test_report_persists_manual_running_economy_with_final_fingerprint(self) -> None:
        match_id = self._weighted_match_id()
        match = self.session_manager.matches[-1]
        old_fingerprint = self.session_manager.build_match_fingerprint(match)

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
        self.assertIsNone(
            self.session_manager.get_manual_running_economy(match_id, old_fingerprint)
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
