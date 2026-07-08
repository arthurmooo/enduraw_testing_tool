"""Tests du sidecar audit MetaSoft.

Les fixtures sont synthetiques. Elles verifient que le sidecar expose les
sources, unites et transformations deja calculees sans modifier le JSON
Valentin et sans serialiser les valeurs lissees de la future UI.
"""
import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

from core.metasoft_analysis import build_metasoft_analysis
from core.metasoft_audit_export import (
    RUNNING_ECONOMY_FORMULA,
    build_metasoft_audit_export,
    metasoft_audit_filename,
)
from core.metasoft_markers import build_metasoft_marker


def _point(t_seconds: int, phase: str, speed_kmh: float, fc_bpm: int) -> dict:
    vo2_l_min = 0.8 + speed_kmh / 8
    values = {
        "fc_bpm": fc_bpm,
        "vo2_l_min": vo2_l_min,
        "vco2_l_min": round(vo2_l_min * 0.9, 6),
        "vo2_ml_kg_min": 20 + speed_kmh,
        "rer": 0.9,
        "speed_kmh": speed_kmh,
    }
    return {
        "t_seconds": t_seconds,
        "phase": phase,
        "marker": None,
        "values": values,
        "value_sources": {"vco2_l_min": "derived_vo2_x_rer"},
        "smoothed_values": {"fc_bpm": 999},
    }


def _analysis() -> dict:
    parsed = {
        "file": {"filename": "TCP__VAN_DER_VEEN_Noor_2026.06.10_12.38.06_.xml"},
        "athlete": {
            "first_name": "Noor",
            "last_name": "VAN DER VEEN",
            "athlete_name": "VAN DER VEEN Noor",
            "weight_kg": 60,
        },
        "test": {"date": "2026-06-10", "type": "VO2max"},
        "metrics": {
            "vo2_l_min": {
                "source_label": "V'O2",
                "unit": "L/min",
                "source": "xml",
                "transform": "native",
            },
            "rer": {
                "source_label": "RER",
                "unit": None,
                "source": "xml",
                "transform": "native",
            },
            "vco2_l_min": {
                "source_label": "V'CO2",
                "unit": "L/min",
                "source": "derived_vo2_x_rer",
                "transform": "V'O2 L/min * RER",
            },
            "speed_kmh": {
                "source_label": "v",
                "unit": "km/h",
                "source": "xml",
                "transform": "native",
            },
        },
        "points": [
            _point(0, "Repos", 0, 80),
            _point(30, "Repos", 0, 82),
            _point(60, "Echauffement", 10, 120),
            _point(90, "Echauffement", 10, 122),
            _point(120, "Echauffement", 10, 124),
        ],
        "warnings": [{"code": "parser_note", "message": "warning source"}],
    }
    return build_metasoft_analysis(parsed)


def _profile() -> dict:
    return {"identity": {"first_name": "Arthur", "last_name": "Mo"}}


def _assert_no_smoothed_values(testcase: unittest.TestCase, value) -> None:
    if isinstance(value, dict):
        testcase.assertNotIn("smoothed_values", value)
        testcase.assertNotIn("smoothed", value)
        for child in value.values():
            _assert_no_smoothed_values(testcase, child)
    elif isinstance(value, list):
        for child in value:
            _assert_no_smoothed_values(testcase, child)


class MetaSoftAuditExportTest(unittest.TestCase):
    def test_filename_uses_json_stem_only(self) -> None:
        self.assertEqual(
            metasoft_audit_filename("output/Mo_Arthur_2026-07-08.json"),
            "Mo_Arthur_2026-07-08.metasoft_audit.json",
        )
        self.assertEqual(
            metasoft_audit_filename("Mo_Arthur_2026-07-08"),
            "Mo_Arthur_2026-07-08.metasoft_audit.json",
        )

    def test_sidecar_contains_ec_markers_sources_units_and_warnings(self) -> None:
        analysis = _analysis()
        marker = build_metasoft_marker(analysis["points"], "SV1", t_seconds=90)

        sidecar = build_metasoft_audit_export(
            analysis,
            profile=_profile(),
            markers={"SV1": marker},
            json_filename="Mo_Arthur_2026-07-08.json",
            profile_filename="Mo_Arthur.json",
            generated_at="2026-07-08T12:00:00Z",
            app_version="test",
            ui_warnings=[{"code": "ui_note", "message": "selection incomplete"}],
        )

        self.assertEqual(
            set(sidecar),
            {
                "export",
                "xml",
                "profile",
                "metrics",
                "markers",
                "running_economy",
                "warnings",
            },
        )
        self.assertEqual(
            sidecar["export"]["audit_filename"],
            "Mo_Arthur_2026-07-08.metasoft_audit.json",
        )
        self.assertEqual(sidecar["metrics"]["vo2_l_min"]["unit"], "L/min")
        self.assertEqual(sidecar["metrics"]["speed_kmh"]["source_label"], "v")
        self.assertEqual(
            sidecar["markers"]["SV1"]["official_source"],
            "build_metasoft_marker",
        )
        self.assertEqual(sidecar["markers"]["SV1"]["values"]["fc_bpm"], 122)
        self.assertEqual(sidecar["running_economy"]["formula"], RUNNING_ECONOMY_FORMULA)
        self.assertEqual(sidecar["running_economy"]["units"]["value"], "J/kg/m")
        self.assertEqual(
            sidecar["running_economy"]["sources"]["vco2"],
            "V'CO2 XML si present, sinon VO2 * RER",
        )
        self.assertIsNotNone(sidecar["running_economy"]["rest_baseline"])
        self.assertEqual(sidecar["running_economy"]["stages"][0]["unit"], "J/kg/m")
        self.assertEqual(sidecar["warnings"]["analysis"][0]["code"], "parser_note")
        self.assertEqual(sidecar["warnings"]["ui"][0]["code"], "ui_note")
        self.assertEqual(
            sidecar["profile"]["identity_mismatch_warning"]["code"],
            "identity_mismatch",
        )
        self.assertFalse(sidecar["profile"]["identity_mismatch_warning"]["blocking"])
        self.assertNotIn("audit_points", sidecar)
        _assert_no_smoothed_values(self, sidecar)

    def test_optional_audit_points_are_decimated_raw_values_only(self) -> None:
        sidecar = build_metasoft_audit_export(
            _analysis(),
            include_audit_points=True,
            audit_point_step=2,
        )

        self.assertEqual(len(sidecar["audit_points"]), 3)
        self.assertEqual(set(sidecar["audit_points"][0]), {
            "t_seconds",
            "phase",
            "marker",
            "values",
        })
        _assert_no_smoothed_values(self, sidecar)

    def test_identity_comparison_ignores_accents_like_ui(self) -> None:
        analysis = _analysis()
        analysis["athlete"] = {
            "first_name": "José",
            "last_name": "Été",
            "athlete_name": "Été José",
        }
        profile = {"identity": {"first_name": "Jose", "last_name": "Ete"}}

        sidecar = build_metasoft_audit_export(analysis, profile=profile)

        self.assertIsNone(sidecar["profile"]["identity_mismatch_warning"])
        self.assertEqual(sidecar["warnings"]["profile"], [])

    def test_ui_warnings_are_not_filled_from_analysis_warnings(self) -> None:
        sidecar = build_metasoft_audit_export(_analysis())

        self.assertEqual(sidecar["warnings"]["analysis"][0]["code"], "parser_note")
        self.assertEqual(sidecar["warnings"]["ui"], [])


if __name__ == "__main__":
    unittest.main()
