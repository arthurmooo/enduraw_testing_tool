"""Tests du coeur MetaSoft local sans fixture patient privee.

Les fixtures XML sont minimales et synthetiques. Elles verifient les contrats
critiques: parsing Spreadsheet avec `ss:Index`, unites natives, calcul EC avec
VO2 L/min -> ml/min, VCO2 derive depuis RER si absent, et export JSON Valentin
alimente par les points normalises.
"""
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

from core.data_transformer import DataTransformer
from core.metasoft_analysis import build_metasoft_analysis
from core.metasoft_markers import (
    apply_metasoft_stress_patch,
    build_metasoft_marker,
    metasoft_marker_to_stress_patch,
)
from utils.xml_parser import TCPXmlParser, parse_metasoft_xml_bytes, parse_spreadsheet_rows


def _cell(value: str, index: int | None = None) -> str:
    index_attr = f' ss:Index="{index}"' if index else ""
    return f'<Cell{index_attr}><Data ss:Type="String">{value}</Data></Cell>'


def _metasoft_xml(include_weight: bool = True, test_start: str = "") -> bytes:
    headers = [
        "t", "Phase", "Marqueur", "FC", "V'O2", "V'O2/FC", "RER",
        "V'E", "VT", "V'E/V'O2", "V'E/V'CO2", "PetO2", "PetCO2", "BF", "v", "DE",
    ]
    units = [
        "s", "", "", "bpm", "L/min", "ml", "", "L/min", "L", "", "",
        "mmHg", "mmHg", "/min", "km/h", "kcal/h",
    ]
    rows = []
    if test_start:
        rows.append([_cell("Données administratives")])
    rows.extend([
        [_cell("Nom"), _cell("VAN DER VEEN")],
        [_cell("Prénom"), _cell("Noor")],
    ])
    if include_weight:
        rows.append([_cell("Poids"), _cell("60,0 kg")])
    if test_start:
        rows.extend([
            [_cell("Données test")],
            [_cell("Heure de début"), _cell(""), _cell(test_start)],
            [_cell("Tableau Résumé")],
            [_cell("Variable"), _cell("Unité"), _cell("Repos")],
            [_cell("V'O2"), _cell("L/min"), _cell("0,30")],
            [_cell("Measurement Data")],
        ])
    rows.extend([
        [_cell(value) for value in headers],
        [_cell(value) for value in units],
    ])
    data_rows = [
        ["0:00:00,000", "Repos", "", "80", "0,30", "3,8", "0,80",
         "8", "0,7", "26,6", "33,3", "100", "36", "12", "0", "220"],
        ["0:00:10,000", "Repos", "", "82", "0,32", "3,9", "0,81",
         "8,5", "0,7", "26,5", "32,7", "101", "37", "13", "0", "230"],
        ["0:01:00,000", "Echauffement", "", "120", "2,00", "16,7", "0,90",
         "40", "1,4", "20", "22,2", "104", "39", "28", "10", "700"],
        ["0:01:30,000", "Echauffement", "", "122", "2,10", "17,2", "0,91",
         "41", "1,4", "19,5", "21,4", "105", "40", "29", "10", "710"],
        ["0:02:00,000", "Echauffement", "", "124", "2,20", "17,7", "0,92",
         "42", "1,4", "19,1", "20,7", "106", "41", "30", "10", "720"],
        ["0:03:00,000", "Echauffement", "", "130", "2,40", "18,5", "0,95",
         "50", "1,6", "20,8", "21,9", "108", "42", "31", "12", "760"],
        ["0:03:30,000", "Echauffement", "", "132", "2,50", "18,9", "0,96",
         "51", "1,6", "20,4", "21,2", "109", "43", "32", "12", "770"],
        ["0:04:00,000", "Echauffement", "", "134", "2,60", "19,4", "0,97",
         "52", "1,6", "20,0", "20,6", "110", "44", "33", "12", "780"],
    ]
    rows.extend([[_cell(value) for value in row] for row in data_rows])
    xml_rows = "\n".join(f"<Row>{''.join(row)}</Row>" for row in rows)
    return f"""<?xml version="1.0"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
 <Worksheet ss:Name="MetasoftStudio"><Table>{xml_rows}</Table></Worksheet>
</Workbook>""".encode("utf-8")


def _manual_profile() -> dict:
    return {
        "email": "coach@example.com",
        "identity": {"last_name": "", "first_name": ""},
        "body_composition": {"height_cm": 180, "current_weight": None},
        "professional_life": {},
        "equipment_and_tracking": {},
        "history_and_goals": {},
        "stress_test_results": {
            "thresholds": {
                "sv1": {"hr_bpm": 124, "pace_km_h": 10, "vo2_ml_kg_min": 36},
                "sv2": {"hr_bpm": 134, "pace_km_h": 12, "vo2_ml_kg_min": 43},
            },
            "measured_vo2max": 50,
            "max_hr": 180,
            "vma": 16,
        },
    }


def _point(t_seconds: int, phase: str, speed: float) -> dict:
    vo2_l_min = 1.0 + speed / 10
    return {
        "t_seconds": t_seconds,
        "phase": phase,
        "values": {
            "vo2_l_min": vo2_l_min,
            "vco2_l_min": round(vo2_l_min * 0.9, 6),
            "rer": 0.9,
            "speed_kmh": speed,
        },
        "value_sources": {"vco2_l_min": "derived_vo2_x_rer"},
    }


def _marker_point(
    t_seconds: int,
    fc_bpm: int | None,
    vo2_l_min: float | None,
    vo2_ml_kg_min: float | None,
    speed_kmh: float | None,
) -> dict:
    values = {
        "fc_bpm": fc_bpm,
        "vo2_l_min": vo2_l_min,
        "vo2_ml_kg_min": vo2_ml_kg_min,
        "speed_kmh": speed_kmh,
    }
    return {
        "t_seconds": t_seconds,
        "values": values,
        "smoothed_values": {
            "fc_bpm": 999,
            "vo2_ml_kg_min": 999,
            "speed_kmh": 999,
        },
    }


class MetaSoftLocalCoreTest(unittest.TestCase):
    def test_spreadsheet_rows_respect_ss_index(self) -> None:
        root = ET.fromstring(
            b"""<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
            xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
            <Worksheet><Table><Row>
            <Cell><Data ss:Type="String">A</Data></Cell>
            <Cell ss:Index="3"><Data ss:Type="String">C</Data></Cell>
            </Row></Table></Worksheet></Workbook>"""
        )

        self.assertEqual(parse_spreadsheet_rows(root), [["A", "", "C"]])

    def test_parse_analysis_and_export_use_normalised_metasoft_points(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            xml_path = Path(tmp_dir) / "TCP__VAN DER VEEN_Noor_2026.06.10_12.38.06_.xml"
            xml_path.write_bytes(_metasoft_xml())

            xml_data = TCPXmlParser().parse_file(str(xml_path))
            analysis = xml_data["metasoft_analysis"]
            payload = DataTransformer().transform(xml_data, _manual_profile())

        self.assertEqual(xml_data["filename_data"]["last_name"], "VAN DER VEEN")
        self.assertEqual(analysis["athlete"]["weight_kg"], 60)
        self.assertEqual([stage["speed_kmh"] for stage in analysis["warmup_stages"]], [10, 12])
        self.assertEqual(
            analysis["computed"]["running_economy"][0]["vco2_source"],
            "derived_vo2_x_rer",
        )
        self.assertEqual(analysis["metrics"]["vo2_fc_ml"]["source_label"], "V'O2/FC")
        self.assertEqual(analysis["metrics"]["vco2_l_min"]["source"], "derived_vo2_x_rer")
        self.assertEqual(analysis["points"][0]["values"]["vco2_l_min"], 0.24)
        self.assertEqual(
            analysis["points"][0]["value_sources"]["vco2_l_min"],
            "derived_vo2_x_rer",
        )
        self.assertTrue(
            any(warning["code"] == "derived_vco2_l_min" for warning in analysis["warnings"])
        )
        self.assertEqual(payload["patient_info"]["nom"], "VAN DER VEEN")
        self.assertEqual(payload["patient_info"]["poids_actuel"], 60)
        self.assertEqual(payload["graphiques"]["graphique_1"]["titre"], "FC et V'O2")

    def test_transform_uses_metadata_date_and_manual_mass_when_xml_has_none(self) -> None:
        profile = _manual_profile()
        profile["body_composition"]["current_weight"] = 62
        with tempfile.TemporaryDirectory() as tmp_dir:
            xml_path = Path(tmp_dir) / "export_metasoft_local.xml"
            xml_path.write_bytes(_metasoft_xml(
                include_weight=False,
                test_start="02/04/2026 07:53",
            ))

            xml_data = TCPXmlParser().parse_file(str(xml_path))
            payload = DataTransformer().transform(xml_data, profile)

        economy = xml_data["metasoft_analysis"]["computed"]["running_economy"][0]
        self.assertEqual(payload["test_date"], "2026-04-02")
        self.assertEqual(economy["mass_kg"], 62)
        self.assertIsNotNone(economy["value_j_kg_m"])
        self.assertNotIn("Variable", xml_data["test_metadata"])
        self.assertNotIn("V'O2", xml_data["test_metadata"])

    def test_analysis_keeps_ec_unavailable_without_rest_or_vco2_source(self) -> None:
        parsed = parse_metasoft_xml_bytes(_metasoft_xml(), "test.xml")
        for point in parsed["points"]:
            point["values"].pop("vco2_l_min", None)
            point.get("value_sources", {}).pop("vco2_l_min", None)
        analysis = build_metasoft_analysis(parsed)

        self.assertIsNone(analysis["computed"]["rest_baseline"])
        self.assertIsNone(analysis["computed"]["running_economy"][0]["value_j_kg_m"])
        self.assertTrue(
            any(warning["code"] == "missing_rest_phase" for warning in analysis["warnings"])
        )

    def test_analysis_qualifies_zero_and_low_speed_warmup_stages(self) -> None:
        parsed = {
            "athlete": {"weight_kg": 60},
            "points": [
                _point(0, "Repos", 0),
                _point(30, "Repos", 0),
                _point(60, "Echauffement", 0),
                _point(120, "Echauffement", 0),
                _point(130, "Echauffement", 4),
                _point(190, "Echauffement", 4),
                _point(200, "Echauffement", 10),
                _point(260, "Echauffement", 10),
            ],
            "warnings": [],
        }

        analysis = build_metasoft_analysis(parsed)
        stages = analysis["warmup_stages"]
        economy = analysis["computed"]["running_economy"]
        warning_codes = {warning["code"] for warning in analysis["warnings"]}

        self.assertEqual([stage["speed_kmh"] for stage in stages], [0, 4, 10])
        self.assertEqual(stages[0]["status"], "non_running_zero_speed")
        self.assertEqual(stages[1]["status"], "low_speed_non_running")
        self.assertIsNone(economy[0]["value_j_kg_m"])
        self.assertIsNotNone(economy[1]["value_j_kg_m"])
        self.assertIn("warmup_zero_speed_stage", warning_codes)
        self.assertIn("warmup_low_speed_stage", warning_codes)

    def test_marker_point_keeps_clicked_time_and_snaps_to_raw_point(self) -> None:
        points = [
            _marker_point(10, 120, 2.0, 40, 12),
            _marker_point(20, 140, 3.0, 50, 14),
        ]

        marker = build_metasoft_marker(points, "SV1", t_seconds=14)

        self.assertEqual(marker["status"], "ok")
        self.assertEqual(marker["mode"], "point")
        self.assertEqual(marker["t_seconds"], 14)
        self.assertEqual(marker["selection_time_seconds"], 14)
        self.assertEqual(marker["source_point_t_seconds"], 10)
        self.assertEqual(marker["values"]["fc_bpm"], 120)
        self.assertEqual(marker["values"]["vo2_ml_kg_min"], 40)

    def test_marker_range_averages_inclusive_raw_points_and_ignores_nulls(self) -> None:
        points = [
            _marker_point(10, 120, 2.0, 40, 12),
            _marker_point(20, None, None, 50, 14),
            _marker_point(30, 150, 4.0, None, 16),
            _marker_point(40, 180, 8.0, 90, 20),
        ]

        marker = build_metasoft_marker(
            points,
            "SV2",
            window_start_seconds=10,
            window_end_seconds=30,
        )

        self.assertEqual(marker["status"], "ok")
        self.assertEqual(marker["mode"], "range")
        self.assertEqual(marker["point_count"], 3)
        self.assertEqual(marker["window_start_seconds"], 10)
        self.assertEqual(marker["window_end_seconds"], 30)
        self.assertEqual(marker["values"]["fc_bpm"], 135)
        self.assertEqual(marker["values"]["vo2_l_min"], 3)
        self.assertEqual(marker["values"]["vo2_ml_kg_min"], 45)
        self.assertEqual(marker["values"]["speed_kmh"], 14)

    def test_marker_ignores_smoothed_or_aggregated_values(self) -> None:
        points = [_marker_point(10, 120, 2.0, 40, 12)]

        marker = build_metasoft_marker(points, "VO2_max", t_seconds=10)

        self.assertEqual(marker["values"]["fc_bpm"], 120)
        self.assertEqual(marker["values"]["vo2_ml_kg_min"], 40)
        self.assertEqual(marker["values"]["speed_kmh"], 12)

    def test_marker_mapping_uses_ml_kg_vo2_and_speed_for_vma(self) -> None:
        sv1_marker = build_metasoft_marker(
            [_marker_point(10, 150, 3.0, 45, 14)],
            "SV1",
            t_seconds=10,
        )
        vo2_marker = build_metasoft_marker(
            [_marker_point(10, 180, 4.2, 62, 18)],
            "VO2max",
            t_seconds=10,
        )
        vma_marker = build_metasoft_marker(
            [_marker_point(10, 180, 4.2, 62, 18)],
            "VMA",
            t_seconds=10,
        )

        sv1_patch = metasoft_marker_to_stress_patch(sv1_marker)
        vo2_patch = metasoft_marker_to_stress_patch(vo2_marker)
        vma_patch = metasoft_marker_to_stress_patch(vma_marker)

        self.assertEqual(
            sv1_patch["patch"]["stress_test_results"]["thresholds"]["sv1"],
            {"hr_bpm": 150, "pace_km_h": 14, "vo2_ml_kg_min": 45},
        )
        self.assertEqual(vo2_patch["status"], "ok")
        self.assertEqual(
            vo2_patch["patch"]["stress_test_results"]["measured_vo2max"],
            62,
        )
        self.assertEqual(vo2_patch["patch"]["stress_test_results"]["max_hr"], 180)
        self.assertEqual(vma_patch["patch"]["stress_test_results"]["vma"], 18)

    def test_apply_marker_patch_preserves_existing_stress_results(self) -> None:
        profile = _manual_profile()
        patch_result = metasoft_marker_to_stress_patch(build_metasoft_marker(
            [_marker_point(10, 150, 3.0, 45, 14)],
            "SV1",
            t_seconds=10,
        ))

        updated = apply_metasoft_stress_patch(profile, patch_result)

        self.assertIsNot(updated, profile)
        self.assertEqual(
            updated["stress_test_results"]["thresholds"]["sv1"],
            {"hr_bpm": 150, "pace_km_h": 14, "vo2_ml_kg_min": 45},
        )
        self.assertEqual(
            updated["stress_test_results"]["thresholds"]["sv2"],
            profile["stress_test_results"]["thresholds"]["sv2"],
        )
        self.assertEqual(updated["stress_test_results"]["vma"], 16)
        self.assertEqual(updated["stress_test_results"]["measured_vo2max"], 50)
        self.assertEqual(profile["stress_test_results"]["thresholds"]["sv1"]["hr_bpm"], 124)

    def test_apply_blocked_marker_patch_leaves_profile_unchanged(self) -> None:
        profile = _manual_profile()
        patch_result = metasoft_marker_to_stress_patch(build_metasoft_marker(
            [_marker_point(10, None, None, None, None)],
            "SV1",
            t_seconds=10,
        ))

        updated = apply_metasoft_stress_patch(profile, patch_result)

        self.assertEqual(patch_result["status"], "blocked")
        self.assertIsNot(updated, profile)
        self.assertEqual(updated, profile)

    def test_marker_empty_window_is_blocking_without_invented_values(self) -> None:
        marker = build_metasoft_marker(
            [_marker_point(10, 120, 2.0, 40, 12)],
            "SV1",
            window_start_seconds=20,
            window_end_seconds=30,
        )

        self.assertEqual(marker["status"], "blocked")
        self.assertEqual(marker["point_count"], 0)
        self.assertEqual(marker["warnings"][0]["code"], "empty_window")
        self.assertIsNone(marker["values"]["fc_bpm"])
        self.assertIsNone(marker["values"]["speed_kmh"])

    def test_graph_exports_keep_none_instead_of_zero_old_and_new_paths(self) -> None:
        transformer = DataTransformer()
        old_graphs = transformer._build_graphiques(
            [
                {"t_seconds": 1, "FC": 100, "V'O2": 2.0},
                {"t_seconds": 16, "FC": None, "V'O2": None},
            ],
            {},
        )
        new_graphs = transformer._build_graphiques_from_metasoft_points(
            [
                {"t_seconds": 1, "values": {"fc_bpm": 100, "vo2_l_min": 2.0}},
                {"t_seconds": 16, "values": {"fc_bpm": None, "vo2_l_min": None}},
            ],
            {},
        )

        old_fc = old_graphs["graphique_1"]["courbes"][0]["valeurs"]
        new_fc = new_graphs["graphique_1"]["courbes"][0]["valeurs"]

        self.assertEqual(old_fc, [100, None])
        self.assertEqual(new_fc, [100, None])


if __name__ == "__main__":
    unittest.main()
