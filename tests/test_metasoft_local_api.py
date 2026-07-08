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


def _metasoft_xml(include_weight: bool = False) -> bytes:
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
                        "t_seconds": None,
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

    def test_export_saves_json_sidecar_and_marks_match_exported(self) -> None:
        match_id = self._match_id()
        status, payload = self._post(
            f"/api/matches/{match_id}/export",
            {
                "marker_selections": [
                    {"name": "VMA", "mode": "point", "t_seconds": 120}
                ],
                "include_audit_points": True,
            },
        )

        self.assertEqual(status, 200)
        json_path = Path(payload["json"]["path"])
        audit_path = Path(payload["audit"]["path"])
        self.assertTrue(json_path.exists())
        self.assertTrue(audit_path.exists())
        self.assertEqual(payload["confirmed_markers"]["VMA"]["values"]["vma"], 10)

        exported = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertEqual(exported["seuils"]["VMA"]["valeur"], 10)
        sidecar = json.loads(audit_path.read_text(encoding="utf-8"))
        self.assertEqual(sidecar["markers"]["VMA"]["official_source"], "build_metasoft_marker")
        self.assertIn("audit_points", sidecar)

        self.session_manager._load_matches()
        self.assertTrue(self.session_manager.matches[0].exported)

    def _match_id(self) -> str:
        status, payload = self._get("/api/matches")
        self.assertEqual(status, 200)
        return payload["matches"][0]["match_id"]

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
