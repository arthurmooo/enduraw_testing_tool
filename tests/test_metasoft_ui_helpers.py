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


class MetaSoftUiHelpersTest(unittest.TestCase):
    def test_graph_configs_cover_nine_graphs_and_speed_is_never_smoothable(self) -> None:
        self.assertEqual(len(GRAPH_CONFIGS), 9)
        self.assertEqual(
            {config["id"] for config in GRAPH_CONFIGS},
            {
                "fc_vo2",
                "vo2kg_speed",
                "ve_bf",
                "rer",
                "ve_ratios",
                "pet",
                "de",
                "running_economy",
                "thresholds",
            },
        )
        self.assertEqual(MARKER_CONFIGS["VO2_max"]["label"], "VO2max")

        speed_series = [
            series
            for config in GRAPH_CONFIGS
            for series in config["series"]
            if series["key"] == "speed_kmh"
        ]

        self.assertTrue(speed_series)
        self.assertTrue(all(series["smoothable"] is False for series in speed_series))

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
            {"t_seconds": 0, "values": {"fc_bpm": 100, "vo2_l_min": None}},
            {"t_seconds": 10, "values": {"fc_bpm": None}},
        ]

        availability = get_point_series_availability(points, "fc_vo2")

        self.assertEqual([series["key"] for series in availability["available"]], ["fc_bpm"])
        self.assertEqual([series["key"] for series in availability["missing"]], ["vo2_l_min"])

    def test_render_data_smoothes_visual_series_without_mutating_analysis(self) -> None:
        analysis = {
            "points": [
                {
                    "t_seconds": 0,
                    "values": {"vo2_ml_kg_min": 40, "speed_kmh": 10},
                },
                {
                    "t_seconds": 10,
                    "values": {"vo2_ml_kg_min": None, "speed_kmh": 11},
                },
                {
                    "t_seconds": 20,
                    "values": {"vo2_ml_kg_min": 50, "speed_kmh": 12},
                },
            ],
        }
        original = deepcopy(analysis)

        render_data = build_graph_render_data(analysis, "vo2kg_speed", 20)
        by_key = {series["key"]: series for series in render_data["series"]}

        self.assertEqual(analysis, original)
        self.assertEqual(by_key["vo2_ml_kg_min"]["raw_values"], [40, None, 50])
        self.assertEqual(by_key["vo2_ml_kg_min"]["render_values"], [40, 45, 50])
        self.assertTrue(by_key["vo2_ml_kg_min"]["smoothed"])
        self.assertEqual(by_key["speed_kmh"]["render_values"], [10, 11, 12])
        self.assertFalse(by_key["speed_kmh"]["smoothed"])

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


if __name__ == "__main__":
    unittest.main()
