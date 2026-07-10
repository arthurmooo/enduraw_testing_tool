"""Marqueurs officiels MetaSoft calcules depuis les points XML bruts.

Le module ne lit aucun fichier et ne depend ni des graphes lisses, ni des
agregats 15 s. Source unique: `points`, la liste issue du parser MetaSoft
normalise, avec temps en secondes et valeurs natives dans `point["values"]`.
Les fenetres vides ou selections invalides restent bloquantes: aucune valeur
officielle n'est inventee par fallback.
"""
from copy import deepcopy
from math import isfinite
from statistics import mean
from typing import Optional


MARKER_VALUE_KEYS = ("fc_bpm", "vo2_l_min", "vo2_ml_kg_min", "speed_kmh")
MARKER_PROFILE_PATHS = {
    "SV1": (
        ("stress_test_results", "thresholds", "sv1", "hr_bpm"),
        ("stress_test_results", "thresholds", "sv1", "pace_km_h"),
        ("stress_test_results", "thresholds", "sv1", "vo2_ml_kg_min"),
    ),
    "SV2": (
        ("stress_test_results", "thresholds", "sv2", "hr_bpm"),
        ("stress_test_results", "thresholds", "sv2", "pace_km_h"),
        ("stress_test_results", "thresholds", "sv2", "vo2_ml_kg_min"),
    ),
    "VO2_max": (
        ("stress_test_results", "max_hr"),
        ("stress_test_results", "measured_vo2max"),
    ),
    "VMA": (("stress_test_results", "vma"),),
}


def metasoft_profile_marker_snapshot(profile: dict) -> dict:
    """Capture exactement les champs profil possedes par les marqueurs.

    La presence de chaque cle est conservee separement de sa valeur afin qu'une
    suppression ou l'ajout d'un `null` invalide aussi la provenance.
    """
    snapshot = {}
    for paths in MARKER_PROFILE_PATHS.values():
        for path in paths:
            present, value = _read_path_with_presence(profile, path)
            snapshot[".".join(path)] = {
                "present": present,
                "value": deepcopy(value) if present else None,
            }
    return snapshot


def metasoft_unproven_profile_markers(profile: dict, markers: dict) -> list[str]:
    """Liste les groupes profil non vides sans operation MetaSoft prouvee."""
    unproven = []
    for name, paths in MARKER_PROFILE_PATHS.items():
        has_value = any(
            present and value not in (None, "")
            for present, value in (_read_path_with_presence(profile, path) for path in paths)
        )
        marker = markers.get(name) if isinstance(markers, dict) else None
        if has_value and (
            not isinstance(marker, dict)
            or marker.get("action") == "delete"
            or marker.get("status") != "ok"
        ):
            unproven.append(name)
    return unproven


def build_metasoft_marker(
    points: list[dict],
    name: str,
    t_seconds: Optional[float] = None,
    window_start_seconds: Optional[float] = None,
    window_end_seconds: Optional[float] = None,
) -> dict:
    """Retourne un marqueur officiel depuis les points bruts MetaSoft.

    Mode point: conserve le temps clique et prend les valeurs du point XML le
    plus proche. Mode range: moyenne inclusive des points bruts dans la fenetre;
    les valeurs `None` sont ignorees par metrique, jamais remplacees par zero.
    """
    if t_seconds is not None and (
        window_start_seconds is not None or window_end_seconds is not None
    ):
        return _blocked_marker(
            name,
            "ambiguous_selection",
            "Selection MetaSoft ambigue: choisir point ou range, pas les deux.",
        )
    if t_seconds is not None:
        return _build_point_marker(points, name, t_seconds)
    if window_start_seconds is not None or window_end_seconds is not None:
        return _build_range_marker(
            points,
            name,
            window_start_seconds,
            window_end_seconds,
        )
    return _blocked_marker(name, "missing_selection", "Selection MetaSoft absente.")


def metasoft_marker_to_stress_patch(marker: dict) -> dict:
    """Mappe une operation marqueur vers ses champs de profil possedes."""
    if marker.get("action") == "delete" and marker.get("status") == "deleted":
        delete_paths = _marker_delete_paths(marker.get("name"))
        if delete_paths:
            return {
                "status": "ok",
                "patch": {"stress_test_results": {}},
                "delete_paths": delete_paths,
                "warnings": [],
            }
    if marker.get("status") != "ok":
        return {"status": "blocked", "patch": {}, "warnings": marker.get("warnings", [])}

    name = _normalise_marker_name(marker.get("name"))
    values = marker.get("values", {})
    stress = {}

    if name in ("sv1", "sv2"):
        threshold = {
            "hr_bpm": _round_bpm(values.get("fc_bpm")),
            "pace_km_h": values.get("speed_kmh"),
            "vo2_ml_kg_min": values.get("vo2_ml_kg_min"),
        }
        stress["thresholds"] = {name: threshold}
    elif name == "vo2_max":
        stress.update({
            "max_hr": _round_bpm(values.get("fc_bpm")),
            "measured_vo2max": values.get("vo2_ml_kg_min"),
        })
    elif name == "vma":
        stress["vma"] = values.get("speed_kmh")
    else:
        return {
            "status": "blocked",
            "patch": {},
            "warnings": [{
                "code": "unknown_marker",
                "message": f"Marqueur MetaSoft non mappe vers le profil: {marker.get('name')}",
            }],
        }

    missing_paths = [
        ".".join(path)
        for path, value in _flatten_values(stress)
        if value is None
    ]
    if missing_paths:
        return {
            "status": "blocked",
            "patch": {},
            "warnings": [{
                "code": "missing_marker_values",
                "message": "Marqueur incomplet: tous ses champs profil sont requis.",
                "fields": missing_paths,
            }],
        }
    return {
        "status": "ok",
        "patch": {"stress_test_results": stress},
        "delete_paths": [],
        "warnings": [],
    }


def apply_metasoft_stress_patch(profile: dict, patch_result: dict) -> dict:
    """Applique un patch MetaSoft sur une copie du profil.

    Le patch ne contient que les valeurs issues des marqueurs officiels MetaSoft,
    avec FC en bpm, vitesse en km/h et VO2 en ml/kg/min. Chaque marqueur remplace
    entierement ses champs possedes afin de ne jamais conserver une valeur issue
    d'une ancienne selection.
    """
    updated_profile = deepcopy(profile)
    if patch_result.get("status") != "ok":
        return updated_profile

    stress_patch = patch_result.get("patch", {}).get("stress_test_results", {})
    stress_results = updated_profile.setdefault("stress_test_results", {})

    thresholds_patch = stress_patch.get("thresholds", {})
    if thresholds_patch:
        thresholds = stress_results.setdefault("thresholds", {})
        for name, values in thresholds_patch.items():
            thresholds[name] = deepcopy(values)

    for key, value in stress_patch.items():
        if key != "thresholds":
            stress_results[key] = deepcopy(value)

    for path in patch_result.get("delete_paths", []):
        _delete_path(updated_profile, path)

    return updated_profile


def _build_point_marker(points: list[dict], name: str, t_seconds: float) -> dict:
    if (
        isinstance(t_seconds, bool)
        or not isinstance(t_seconds, (int, float))
        or not isfinite(t_seconds)
    ):
        marker = _blocked_marker(
            name,
            "invalid_point_time",
            "Temps point MetaSoft non fini: marqueur non calculable.",
        )
        marker.update({"mode": "point", "t_seconds": t_seconds})
        return marker

    # Le snap au point le plus proche reste interdit hors domaine temporel brut.
    bounds = _point_time_bounds(points)
    if bounds is None:
        marker = _blocked_marker(
            name,
            "missing_source_point",
            "Aucun point brut MetaSoft disponible pour ce marqueur.",
        )
        marker.update({"mode": "point", "t_seconds": t_seconds})
        return marker

    min_time, max_time = bounds
    if t_seconds < min_time or t_seconds > max_time:
        marker = _blocked_marker(
            name,
            "point_out_of_bounds",
            "Temps point MetaSoft hors bornes des points bruts.",
        )
        marker.update({
            "mode": "point",
            "t_seconds": t_seconds,
            "min_t_seconds": min_time,
            "max_t_seconds": max_time,
        })
        return marker

    point = _nearest_point(points, t_seconds)
    if point is None:
        marker = _blocked_marker(
            name,
            "missing_source_point",
            "Aucun point brut MetaSoft disponible pour ce marqueur.",
        )
        marker.update({"mode": "point", "t_seconds": t_seconds})
        return marker

    return {
        "name": name,
        "action": "upsert",
        "mode": "point",
        "status": "ok",
        "t_seconds": t_seconds,
        "selection_time_seconds": t_seconds,
        "window_start_seconds": None,
        "window_end_seconds": None,
        "point_count": 1,
        "phase": point.get("phase"),
        "source_point_t_seconds": point.get("t_seconds"),
        "values": _official_values(name, [point]),
        "warnings": [],
    }


def _point_time_bounds(points: list[dict]) -> Optional[tuple[float, float]]:
    times = []
    for point in points:
        time = _number(point.get("t_seconds"))
        if time is not None:
            times.append(time)
    if not times:
        return None
    return min(times), max(times)


def _build_range_marker(
    points: list[dict],
    name: str,
    start: Optional[float],
    end: Optional[float],
) -> dict:
    if start is None or end is None or end < start:
        marker = _blocked_marker(
            name,
            "invalid_window",
            "Fenetre MetaSoft invalide: debut et fin inclusifs requis.",
        )
        marker.update({
            "mode": "range",
            "window_start_seconds": start,
            "window_end_seconds": end,
            "point_count": 0,
        })
        return marker

    selected = [
        point for point in points
        if _number(point.get("t_seconds")) is not None
        and start <= point["t_seconds"] <= end
    ]
    if not selected:
        marker = _blocked_marker(
            name,
            "empty_window",
            "Fenetre MetaSoft sans point brut: marqueur non calculable.",
        )
        marker.update({
            "mode": "range",
            "window_start_seconds": start,
            "window_end_seconds": end,
            "point_count": 0,
        })
        return marker

    return {
        "name": name,
        "action": "upsert",
        "mode": "range",
        "status": "ok",
        "t_seconds": (start + end) / 2,
        "selection_time_seconds": (start + end) / 2,
        "window_start_seconds": start,
        "window_end_seconds": end,
        "point_count": len(selected),
        "phase": _common_phase(selected),
        "values": _official_values(name, selected),
        "warnings": [],
    }


def build_metasoft_marker_deletion(name: str) -> dict:
    """Retourne l'accuse canonique d'une suppression explicite."""
    return {
        "name": name,
        "action": "delete",
        "status": "deleted",
        "mode": "point",
        "t_seconds": None,
        "selection_time_seconds": None,
        "window_start_seconds": None,
        "window_end_seconds": None,
        "point_count": 0,
        "phase": None,
        "values": _official_values(name, []),
        "warnings": [],
    }


def _official_values(name: str, selected_points: list[dict]) -> dict:
    # Les valeurs officielles sont celles du point brut ou la moyenne brute range.
    values = {}
    for key in MARKER_VALUE_KEYS:
        samples = [
            point.get("values", {}).get(key)
            for point in selected_points
            if isinstance(point.get("values", {}).get(key), (int, float))
        ]
        values[key] = round(mean(samples), 3) if samples else None
    values["vma"] = values["speed_kmh"] if _normalise_marker_name(name) == "vma" else None
    return values


def _nearest_point(points: list[dict], t_seconds: float) -> Optional[dict]:
    candidates = [
        point for point in points
        if _number(point.get("t_seconds")) is not None
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda point: abs(point["t_seconds"] - t_seconds))


def _blocked_marker(name: str, code: str, message: str) -> dict:
    return {
        "name": name,
        "status": "blocked",
        "values": _official_values(name, []),
        "warnings": [{"code": code, "message": message}],
    }


def _normalise_marker_name(name) -> str:
    normalized = str(name or "").strip().lower().replace(" ", "_").replace("-", "_")
    return "vo2_max" if normalized == "vo2max" else normalized


def _marker_delete_paths(name) -> list[list[str]]:
    normalized = _normalise_marker_name(name)
    if normalized in ("sv1", "sv2"):
        return [["stress_test_results", "thresholds", normalized]]
    if normalized == "vo2_max":
        return [
            ["stress_test_results", "max_hr"],
            ["stress_test_results", "measured_vo2max"],
        ]
    if normalized == "vma":
        return [["stress_test_results", "vma"]]
    return []


def _flatten_values(data: dict, prefix=()):
    for key, value in data.items():
        path = (*prefix, key)
        if isinstance(value, dict):
            yield from _flatten_values(value, path)
        else:
            yield path, value


def _read_path_with_presence(data: dict, path: tuple[str, ...]) -> tuple[bool, object]:
    current = data
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return False, None
        current = current[key]
    return True, current


def _delete_path(data: dict, path: list[str]) -> None:
    parent = data
    for key in path[:-1]:
        if not isinstance(parent, dict) or key not in parent:
            return
        parent = parent[key]
    if isinstance(parent, dict):
        parent.pop(path[-1], None)


def _common_phase(points: list[dict]):
    phases = {point.get("phase") for point in points if point.get("phase") is not None}
    return phases.pop() if len(phases) == 1 else None


def _number(value) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if isfinite(number) else None


def _round_bpm(value) -> Optional[int]:
    number = _number(value)
    return int(number + 0.5) if number is not None else None
