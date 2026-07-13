"""Tests des helpers purs de graphes MetaSoft locaux.

Les donnees sont synthetiques: elles verifient uniquement les contrats UI purs,
sans Tk ni matplotlib. Le lissage reste une transformation visuelle, la vitesse
MetaSoft `km/h` reste brute, et les clics sont bornes en temps sans officialiser
de valeur physiologique.
"""
import sys
import types
import unittest
from copy import deepcopy
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

try:
    import customtkinter  # noqa: F401
except ModuleNotFoundError:
    customtkinter_stub = types.SimpleNamespace(CTkToplevel=object)
    sys.modules["customtkinter"] = customtkinter_stub

from ui.metasoft_graphs import (
    GRAPH_CONFIGS,
    GRAPH_CONFIGS_BY_ID,
    MARKER_CONFIGS,
    build_graph_render_data,
    clamp_time_range,
    click_x_to_time_seconds,
    get_point_series_availability,
    smooth_series_by_time,
)
from ui.metasoft_analysis_window import (
    _format_time_seconds,
    _merge_patch_results,
    _parse_time_seconds,
    _patch_conflicts,
)
from ui.profile_metasoft_summary import build_profile_metasoft_summary


class MetaSoftUiHelpersTest(unittest.TestCase):
    def test_graph_configs_cover_nine_metasoft_graphs_plus_running_economy(self) -> None:
        self.assertEqual(len(GRAPH_CONFIGS), 13)
        self.assertEqual(
            [config["id"] for config in GRAPH_CONFIGS if config["source"] == "points"],
            [
                "ve_vo2_peto2_time",
                "ve_vco2_petco2_time",
                "ve_time",
                "hr_vo2_fc_time",
                "vo2_vco2_time",
                "de_time",
                "ve_vco2_scatter",
                "vco2_hr_scatter",
                "ve_ratios_time",
                "vt_ve_scatter",
                "rer_time",
                "pet_time",
            ],
        )
        self.assertEqual(
            {config["id"] for config in GRAPH_CONFIGS},
            {
                "ve_vo2_peto2_time",
                "ve_vco2_petco2_time",
                "ve_time",
                "hr_vo2_fc_time",
                "vo2_vco2_time",
                "de_time",
                "ve_vco2_scatter",
                "vco2_hr_scatter",
                "ve_ratios_time",
                "vt_ve_scatter",
                "rer_time",
                "pet_time",
                "running_economy",
            },
        )
        self.assertEqual(MARKER_CONFIGS["VO2_max"]["label"], "VO2max")
        self.assertEqual(
            [series["label"] for series in GRAPH_CONFIGS_BY_ID["de_time"]["series"]],
            ["DE", "CHOx", "FATOx", "PROx"],
        )

        scatter_configs = [config for config in GRAPH_CONFIGS if config.get("kind") == "scatter"]
        self.assertEqual(
            [(config["id"], config["x_axis"]["key"]) for config in scatter_configs],
            [
                ("ve_vco2_scatter", "vco2_l_min"),
                ("vco2_hr_scatter", "vo2_l_min"),
                ("vt_ve_scatter", "ve_l_min"),
            ],
        )
        self.assertTrue(
            all(not series["smoothable"] for config in scatter_configs for series in config["series"])
        )

    def test_smooth_series_zero_seconds_returns_raw_copy(self) -> None:
        values = [1, None, 3]
        result = smooth_series_by_time([0, 10, 20], values, 0)

        self.assertEqual(result, values)
        self.assertIsNot(result, values)

    def test_smooth_series_uses_centered_time_window_and_ignores_none(self) -> None:
        result = smooth_series_by_time(
            [0, 10, 20, 30],
            [1, None, 3, 5],
            20,
        )

        self.assertEqual(result, [1, 2, 4, 4])

    def test_point_series_availability_uses_normalised_values_only(self) -> None:
        points = [
            {"t_seconds": 0, "values": {"vo2_l_min": 2.0, "vco2_l_min": None}},
            {"t_seconds": 10, "values": {"vo2_l_min": None}},
        ]

        availability = get_point_series_availability(points, "vo2_vco2_time")

        self.assertEqual([series["key"] for series in availability["available"]], ["vo2_l_min"])
        self.assertEqual([series["key"] for series in availability["missing"]], ["vco2_l_min"])

    def test_render_data_smoothes_visual_series_without_mutating_analysis(self) -> None:
        analysis = {
            "points": [
                {
                    "t_seconds": 0,
                    "values": {"fc_bpm": 120, "vo2_fc_ml": 16, "speed_kmh": 10},
                },
                {
                    "t_seconds": 10,
                    "values": {"fc_bpm": None, "vo2_fc_ml": None, "speed_kmh": 11},
                },
                {
                    "t_seconds": 20,
                    "values": {"fc_bpm": 140, "vo2_fc_ml": 18, "speed_kmh": 12},
                },
            ],
        }
        original = deepcopy(analysis)

        render_data = build_graph_render_data(analysis, "hr_vo2_fc_time", 20)
        by_key = {series["key"]: series for series in render_data["series"]}

        self.assertEqual(analysis, original)
        self.assertEqual(by_key["fc_bpm"]["raw_values"], [120, None, 140])
        self.assertEqual(by_key["fc_bpm"]["render_values"], [120, 130, 140])
        self.assertTrue(by_key["fc_bpm"]["smoothed"])
        self.assertEqual(by_key["vo2_fc_ml"]["render_values"], [16, 17, 18])
        self.assertTrue(by_key["vo2_fc_ml"]["smoothed"])

    def test_scatter_render_data_uses_metric_x_and_never_smoothes(self) -> None:
        analysis = {
            "points": [
                {"t_seconds": 0, "values": {"vco2_l_min": 1.8, "ve_l_min": 40}},
                {"t_seconds": 10, "values": {"vco2_l_min": 2.0, "ve_l_min": None}},
                {"t_seconds": 20, "values": {"vco2_l_min": 2.2, "ve_l_min": 48}},
            ],
        }

        render_data = build_graph_render_data(analysis, "ve_vco2_scatter", 60)
        series = render_data["series"][0]

        self.assertEqual(render_data["kind"], "scatter")
        self.assertEqual(render_data["x_values"], [1.8, 2.0, 2.2])
        self.assertEqual(series["raw_values"], [40, None, 48])
        self.assertEqual(series["render_values"], [40, None, 48])
        self.assertFalse(series["smoothed"])

    def test_running_economy_render_data_uses_computed_analysis_without_smoothing(self) -> None:
        analysis = {
            "computed": {
                "running_economy": [
                    {"stage_index": 1, "speed_kmh": 10, "value_j_kg_m": 4.2},
                    {"stage_index": 2, "speed_kmh": 12, "value_j_kg_m": None},
                ]
            }
        }

        render_data = build_graph_render_data(analysis, GRAPH_CONFIGS_BY_ID["running_economy"], 120)

        self.assertEqual(render_data["x_values"], [1, 2])
        self.assertEqual(render_data["stage_speeds_kmh"], [10, 12])
        self.assertEqual(render_data["series"][0]["render_values"], [4.2, None])
        self.assertFalse(render_data["series"][0]["smoothed"])

    def test_click_and_zoom_ranges_are_bounded_without_snapping_inside_bounds(self) -> None:
        times = [10, 20, 40]

        self.assertEqual(click_x_to_time_seconds(25.5, times), 25.5)
        self.assertEqual(click_x_to_time_seconds(0, times), 10)
        self.assertEqual(click_x_to_time_seconds(50, times), 40)
        self.assertEqual(clamp_time_range(50, 0, times), (10, 40))
        self.assertIsNone(click_x_to_time_seconds(12, []))

    def test_marker_time_fields_accept_seconds_and_hhmmss(self) -> None:
        self.assertEqual(_parse_time_seconds("0"), 0)
        self.assertEqual(_parse_time_seconds("240"), 240)
        self.assertEqual(_parse_time_seconds("4:00"), 240)
        self.assertEqual(_parse_time_seconds("0:04:00.123"), 240.123)
        self.assertEqual(_parse_time_seconds("1:02:03"), 3723)
        self.assertIsNone(_parse_time_seconds("-1"))
        self.assertEqual(_format_time_seconds(240), "0:04:00")
        self.assertEqual(_format_time_seconds(240.123), "0:04:00.123")
        self.assertEqual(_format_time_seconds(239.9999), "0:04:00")

    def test_marker_profile_patches_merge_and_conflicts_skip_empty_or_equal(self) -> None:
        patch_result = _merge_patch_results([
            {
                "status": "ok",
                "patch": {
                    "stress_test_results": {
                        "thresholds": {"sv1": {"hr_bpm": 140}},
                    },
                },
                "warnings": [],
            },
            {
                "status": "ok",
                "patch": {
                    "stress_test_results": {
                        "thresholds": {"sv2": {"hr_bpm": 160}},
                        "vma": 18,
                    },
                },
                "warnings": [],
            },
        ])

        self.assertEqual(
            patch_result["patch"]["stress_test_results"]["thresholds"]["sv1"]["hr_bpm"],
            140,
        )
        self.assertEqual(
            patch_result["patch"]["stress_test_results"]["thresholds"]["sv2"]["hr_bpm"],
            160,
        )

        blocked_result = _merge_patch_results([
            patch_result,
            {
                "status": "blocked",
                "patch": {},
                "warnings": [{"message": "Marqueur incomplet."}],
            },
        ])
        self.assertEqual(blocked_result["status"], "blocked")
        self.assertEqual(blocked_result["warnings"][0]["message"], "Marqueur incomplet.")

        profile = {
            "stress_test_results": {
                "thresholds": {
                    "sv1": {"hr_bpm": 140},
                    "sv2": {"hr_bpm": 155},
                },
                "vma": None,
            },
        }
        conflicts = _patch_conflicts(profile, patch_result)

        self.assertEqual(
            conflicts,
            [{
                "path": "stress_test_results.thresholds.sv2.hr_bpm",
                "old": 155,
                "new": 160,
            }],
        )

    def test_profile_summary_reads_lactates_and_ec_without_recalculation(self) -> None:
        profile = {
            "stress_test_results": {
                "lactate_profile": [
                    {
                        "type": "rest_before",
                        "enabled": True,
                        "speed": 0,
                        "lactate_mmol_l": 1.1,
                    },
                    {
                        "type": "stage",
                        "enabled": False,
                        "label": "Bandelette ratée",
                        "speed": 10,
                        "lactate_mmol_l": None,
                    },
                    {
                        "type": "stage",
                        "enabled": True,
                        "label": "Palier 12 km/h",
                        "speed": 12,
                        "lactate_mmol_l": 3.5,
                        "stage_index": 2,
                    },
                ],
                "lactate_thresholds": {
                    "sl1": {"measurement_index": 2},
                },
            },
        }
        economy_state = {
            "status": "ok",
            "data": {
                "rows": [
                    {
                        "stage_index": 1,
                        "speed_kmh": 10,
                        "start_seconds": 60,
                        "end_seconds": 90,
                        "ec_j_kg_m": 3.8,
                        "vo2_l_min": 2.1,
                        "vco2_l_min": 2.0,
                        "percent_vo2max": 62.5,
                        "point_count": 12,
                        "exclusions": [],
                        "sources": {"selection": "manual_stable_stage"},
                    },
                    {
                        "stage_index": 2,
                        "speed_kmh": 12,
                        "start_seconds": 180,
                        "end_seconds": 210,
                        "ec_j_kg_m": 4.532,
                        "vo2_l_min": 2.9,
                        "vco2_l_min": 2.828,
                        "percent_vo2max": 100,
                        "point_count": 18,
                        "exclusions": [{"start_seconds": 190, "end_seconds": 200}],
                        "sources": {"selection": "manual_stable_stage"},
                    },
                ],
                "stage_selections": [
                    {"stage_index": 1, "enabled": False},
                    {"stage_index": 2, "enabled": True},
                ],
                "rest_baseline": {
                    "start_seconds": 0,
                    "end_seconds": 30,
                    "point_count": 8,
                    "exclusions": [],
                },
            },
        }

        summary = build_profile_metasoft_summary(profile, economy_state, matched=True)

        self.assertEqual(summary["lactate"]["status"], "2 incluse(s) · 1 écartée(s)")
        self.assertIn(
            "[Incluse] Palier 12 km/h — 12 km/h · 3,5 mmol/L · SL1",
            summary["lactate"]["lines"],
        )
        self.assertEqual(summary["running_economy"]["status"], "1 inclus · 1 écarté(s)")
        self.assertIn(
            "[Incluse] Palier 2 — 12 km/h · 3:00–3:30 · EC 4,532 J/kg/m",
            summary["running_economy"]["lines"],
        )
        self.assertIn(
            "Repos — 0:00–0:30 · 8 pts · 0 exclusion(s)",
            summary["running_economy"]["lines"],
        )

    def test_profile_summary_surfaces_unmatched_and_stale_ec_states(self) -> None:
        unmatched = build_profile_metasoft_summary(
            {},
            {"status": "missing"},
            matched=False,
        )
        stale = build_profile_metasoft_summary(
            {},
            {"status": "stale", "reason": "source_changed"},
            matched=True,
        )

        self.assertEqual(unmatched["running_economy"]["status"], "Aucun XML associé")
        self.assertEqual(stale["running_economy"]["status"], "À recalculer")
        self.assertEqual(stale["running_economy"]["tone"], "danger")


if __name__ == "__main__":
    unittest.main()
