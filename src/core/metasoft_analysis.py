"""Calculs MetaSoft locaux pour l'app de testing.

Le module enrichit le parser XML sans persistance: phases, paliers
d'echauffement, depense energetique native et economie de course. Les unites
sont explicites: `V'O2` XML en L/min devient ml/min pour l'EC, la vitesse
`km/h` devient `m/min`, et le resultat d'EC est en `J/kg/m`. Aucune valeur
absente n'est reconstruite depuis une equation de confort.
"""
from statistics import mean
from typing import Optional
from math import isfinite


MIN_STABLE_SPEED_STAGE_SECONDS = 60
MIN_RUNNING_SPEED_KMH = 6.0
MIN_MANUAL_ECONOMY_SECONDS = 30


def build_metasoft_analysis(parsed: dict, manual_mass_kg: Optional[float] = None) -> dict:
    """Retourne l'analyse MetaSoft complete sans modifier le payload parse.

    La masse vient du XML si presente, sinon du champ manuel optionnel. Si repos,
    vitesse, VO2 ou VCO2/RER manquent, l'EC reste indisponible avec warning.
    """
    points = parsed.get("points", [])
    analysis = {
        **parsed,
        "phases": build_phase_segments(points),
        "warmup_stages": [],
        "computed": {},
        "warnings": list(parsed.get("warnings", [])),
    }
    mass = _first_number(parsed.get("athlete", {}).get("weight_kg"), manual_mass_kg)
    stages = detect_warmup_stages(points)
    rest = compute_rest_baseline(points)
    running_economy = []

    if mass is None:
        analysis["warnings"].append({
            "code": "missing_mass_kg",
            "message": "Masse absente: economie de course impossible sans poids.",
        })
    if rest is None:
        analysis["warnings"].append({
            "code": "missing_rest_phase",
            "message": "Phase Repos absente: economie de course impossible sans repos.",
        })

    for stage in stages:
        qualification = qualify_stage_speed(stage)
        stage["status"] = qualification["status"]
        if qualification.get("warning"):
            analysis["warnings"].append(qualification["warning"])
        stage["native_de"] = summarize_native_de(stage["points"])
        economy = compute_running_economy(stage, rest, mass)
        if economy.get("warning"):
            analysis["warnings"].append(economy["warning"])
        running_economy.append(economy)
        del stage["points"]

    analysis["warmup_stages"] = stages
    analysis["computed"] = {
        "rest_baseline": rest,
        "running_economy": running_economy,
        "ventilatory_consistency": check_ventilatory_consistency(points),
    }
    analysis["warnings"].extend(analysis["computed"]["ventilatory_consistency"])
    return analysis


def build_phase_segments(points: list[dict]) -> list[dict]:
    """Construit les segments depuis les labels de phase MetaSoft."""
    segments = []
    current = None
    for point in points:
        phase = point.get("phase")
        if not phase:
            continue
        if current and current["phase"] == phase:
            current["end_seconds"] = point.get("t_seconds")
            current["point_count"] += 1
            continue
        if current:
            segments.append(current)
        current = {
            "phase": phase,
            "start_seconds": point.get("t_seconds"),
            "end_seconds": point.get("t_seconds"),
            "point_count": 1,
        }
    if current:
        segments.append(current)
    return segments


def detect_warmup_stages(points: list[dict]) -> list[dict]:
    """Groupe les vitesses stabilisees d'echauffement, hors transitions courtes."""
    stages = []
    current = None
    for point in points:
        if point.get("phase") != "Echauffement":
            continue
        speed = _number(point, "speed_kmh")
        if speed is None:
            continue
        speed = round(speed, 2)
        if current and current["speed_kmh"] == speed:
            current["end_seconds"] = point.get("t_seconds")
            current["point_count"] += 1
            current["points"].append(point)
            continue
        if current:
            stages.append(current)
        current = {
            "stage_index": len(stages) + 1,
            "speed_kmh": speed,
            "start_seconds": point.get("t_seconds"),
            "end_seconds": point.get("t_seconds"),
            "point_count": 1,
            "points": [point],
        }
    if current:
        stages.append(current)

    stable_stages = [
        stage for stage in stages
        if _stage_duration_seconds(stage) >= MIN_STABLE_SPEED_STAGE_SECONDS
    ]
    for index, stage in enumerate(stable_stages, start=1):
        stage["stage_index"] = index
    return stable_stages


def compute_rest_baseline(points: list[dict]) -> Optional[dict]:
    """Moyenne le repos XML pour VO2/VCO2, sans reconstruire un repos absent."""
    rest_points = [point for point in points if point.get("phase") == "Repos"]
    vo2 = [_vo2_ml_min(point) for point in rest_points]
    vco2 = [_vco2_ml_min(point) for point in rest_points]
    vo2 = [value for value in vo2 if value is not None]
    vco2_values = [item["value"] for item in vco2 if item["value"] is not None]
    if not vo2 or not vco2_values:
        return None
    return {
        "vo2_ml_min": round(mean(vo2), 3),
        "vco2_ml_min": round(mean(vco2_values), 3),
        "vco2_source": _vco2_source(vco2),
        "point_count": len(rest_points),
        "source": "phase_xml_repos",
    }


def compute_manual_rest_baseline(points: list[dict], selection: dict) -> dict:
    """Calcule le repos officiel sur la plage choisie et ses exclusions."""
    if not isinstance(selection, dict):
        raise ValueError("Selection de repos EC invalide.")
    rest_points = [point for point in points if point.get("phase") == "Repos"]
    rest_times = [point.get("t_seconds") for point in rest_points]
    rest_times = [value for value in rest_times if isinstance(value, (int, float))]
    if not rest_times:
        raise ValueError("Phase Repos absente.")
    start = _finite_number(selection.get("start_seconds"), "rest.start_seconds")
    end = _finite_number(selection.get("end_seconds"), "rest.end_seconds")
    if start < min(rest_times) or end > max(rest_times) or start >= end:
        raise ValueError("Bornes de repos EC invalides.")
    exclusions = _normalise_manual_exclusions(selection.get("exclusions", []), start, end)
    selected = [
        point for point in _points_between(rest_points, start, end)
        if not _manual_is_excluded(point.get("t_seconds"), exclusions)
    ]
    usable = [
        point for point in selected
        if _vo2_ml_min(point) is not None and _vco2_ml_min(point)["value"] is not None
    ]
    if not usable:
        raise ValueError("Aucun point VO2/VCO2 utilisable dans le repos choisi.")
    vco2 = [_vco2_ml_min(point) for point in usable]
    return {
        "vo2_ml_min": round(mean(_vo2_ml_min(point) for point in usable), 3),
        "vco2_ml_min": round(mean(item["value"] for item in vco2), 3),
        "vco2_source": _vco2_source(vco2),
        "point_count": len(usable),
        "start_seconds": round(start, 3),
        "end_seconds": round(end, 3),
        "exclusions": exclusions,
        "source": "manual_rest_selection",
    }


def compute_running_economy(
    stage: dict,
    rest_baseline: Optional[dict],
    mass_kg: Optional[float],
) -> dict:
    """Calcule l'EC: VO2/VCO2 ml/min, masse kg, vitesse m/min, sortie J/kg/m."""
    result = {
        "stage_index": stage["stage_index"],
        "speed_kmh": stage["speed_kmh"],
        "speed_m_min": round(stage["speed_kmh"] * 1000 / 60, 3),
        "value_j_kg_m": None,
        "unit": "J/kg/m",
        "point_count": stage["point_count"],
        "vco2_source": None,
        "status": stage.get("status", "running_stage"),
    }
    if mass_kg is None or mass_kg <= 0 or rest_baseline is None or result["speed_m_min"] <= 0:
        result["warning"] = _stage_warning(stage, "running_economy_missing_inputs")
        return result

    vo2_values = [_vo2_ml_min(point) for point in stage["points"]]
    vco2_values = [_vco2_ml_min(point) for point in stage["points"]]
    vo2_values = [value for value in vo2_values if value is not None]
    vco2_valid = [item for item in vco2_values if item["value"] is not None]
    if not vo2_values or not vco2_valid:
        result["warning"] = _stage_warning(stage, "running_economy_missing_vo2_vco2")
        return result

    vo2 = mean(vo2_values)
    vco2 = mean(item["value"] for item in vco2_valid)
    value = _running_economy_j_kg_m(vo2, vco2, rest_baseline, mass_kg, result["speed_m_min"])
    result.update({
        "value_j_kg_m": round(value, 3),
        "vo2_ml_min": round(vo2, 3),
        "vco2_ml_min": round(vco2, 3),
        "mass_kg": mass_kg,
        "vco2_source": _vco2_source(vco2_valid),
    })
    return result


def build_manual_running_economy(
    analysis: dict,
    selections: list[dict],
    profile_vo2max_ml_kg_min: Optional[float] = None,
    vo2max_source: str = "profile.stress_test_results.measured_vo2max",
    rest_selection: Optional[dict] = None,
) -> dict:
    """Recalcule l'EC manuelle officielle depuis les selections UI.

    Source officielle: points et masse XML MetaSoft deja normalises dans
    `analysis`. Unite entree VO2/VCO2: L/min dans les points, ml/min pour la
    formule EC. Aucun poids profil ni valeur calculee par React n'est accepte.
    """
    if not isinstance(selections, list):
        raise ValueError("selections doit etre une liste.")
    stages = {stage.get("stage_index"): stage for stage in analysis.get("warmup_stages", [])}
    points = analysis.get("points", [])
    rest = (
        compute_manual_rest_baseline(points, rest_selection)
        if rest_selection is not None
        else analysis.get("computed", {}).get("rest_baseline")
    )
    xml_mass = _positive_number(analysis.get("athlete", {}).get("weight_kg"))
    vo2max = _positive_number(profile_vo2max_ml_kg_min)
    rows = []
    warnings = []

    for selection in selections:
        if not isinstance(selection, dict):
            raise ValueError("selection EC invalide.")
        row, row_warnings = _manual_running_economy_row(
            points,
            stages,
            rest,
            xml_mass,
            vo2max,
            vo2max_source,
            selection,
        )
        rows.append(row)
        warnings.extend(row_warnings)

    return {
        "source": "python.metasoft_analysis.manual_running_economy",
        "rest_baseline": rest,
        "rows": rows,
        "warnings": warnings,
    }


def _manual_running_economy_row(
    points: list[dict],
    stages: dict,
    rest_baseline: Optional[dict],
    mass_kg: Optional[float],
    vo2max_ml_kg_min: Optional[float],
    vo2max_source: str,
    selection: dict,
) -> tuple[dict, list[dict]]:
    stage_index = _selection_int(selection.get("stage_index"), "stage_index")
    selection_source = selection.get("source", "detected")
    if selection_source not in {"detected", "manual"}:
        raise ValueError("Source de selection EC invalide.")
    stage = stages.get(stage_index)
    start = _finite_number(selection.get("start_seconds"), "start_seconds")
    end = _finite_number(selection.get("end_seconds"), "end_seconds")
    if selection_source == "detected":
        if not stage:
            raise ValueError(f"Palier EC inconnu: {stage_index}.")
        stage_start = _finite_number(stage.get("start_seconds"), "stage.start_seconds")
        stage_end = _finite_number(stage.get("end_seconds"), "stage.end_seconds")
        if start < stage_start or end > stage_end or start >= end:
            raise ValueError("Bornes EC manuelle invalides.")
    else:
        times = [point.get("t_seconds") for point in points]
        times = [value for value in times if isinstance(value, (int, float))]
        if not times or start < min(times) or end > max(times) or end - start < MIN_MANUAL_ECONOMY_SECONDS:
            raise ValueError("Une zone EC libre doit durer au moins 30 s et rester dans le test.")

    exclusions = _normalise_manual_exclusions(
        selection.get("exclusions", []),
        start,
        end,
    )
    selected_points = _points_between(points, start, end)
    # Les artefacts EC sont exclus du calcul officiel: aucune interpolation ni
    # fallback brut. La population unique de row est VO2+VCO2 exploitables,
    # pour que `point_count`, VO2/VCO2 et DE portent sur les memes points.
    included_points = [
        point for point in selected_points
        if not _manual_is_excluded(point.get("t_seconds"), exclusions)
    ]
    usable_points = [
        point for point in included_points
        if _number(point, "vo2_l_min") is not None and _number(point, "vco2_l_min") is not None
    ]
    warnings = []
    speed_values = [
        value for point in usable_points
        if (value := _number(point, "speed_kmh")) is not None
    ]
    speed_kmh = stage.get("speed_kmh") if stage else (mean(speed_values) if speed_values else None)
    if speed_kmh is None or speed_kmh <= 0:
        raise ValueError(f"Vitesse positive absente de la zone EC {stage_index}.")
    speed_m_min = round(speed_kmh * 1000 / 60, 3)
    vo2_l_min = _average_metric(usable_points, "vo2_l_min")
    vo2_ml_kg_min = _average_metric(usable_points, "vo2_ml_kg_min")
    vco2_l_min = _average_metric(usable_points, "vco2_l_min")
    row = {
        "stage_index": stage_index,
        "speed_kmh": round(speed_kmh, 3),
        "speed_m_min": speed_m_min,
        "start_seconds": round(start, 3),
        "end_seconds": round(end, 3),
        "exclusions": exclusions,
        "point_count": len(usable_points),
        "vo2_l_min": _round_optional(vo2_l_min, 3),
        "vco2_l_min": _round_optional(vco2_l_min, 3),
        "ec_j_kg_m": None,
        "percent_vo2max": None,
        "sources": {
            "selection": "manual_free_zone" if selection_source == "manual" else "manual_stable_stage",
            "calculation": "python.metasoft_analysis.manual_running_economy",
            "mass": "xml_metasoft",
            "vo2max": vo2max_source,
            "artefacts": "excluded_raw_points",
        },
        "warnings": [],
    }
    for key in ("de_kcal_h", "decho_kcal_h", "defat_kcal_h", "depro_kcal_h"):
        row[key] = _round_optional(_average_metric(usable_points, key), 3)

    if selection_source == "manual" and speed_values and max(speed_values) - min(speed_values) > 0.5:
        warning = _manual_warning(stage_index, "manual_speed_unstable")
        warnings.append(warning)
        row["warnings"].append(warning)

    if mass_kg is None:
        warning = _manual_warning(stage_index, "missing_xml_mass_kg")
        warnings.append(warning)
        row["warnings"].append(warning)
    if rest_baseline is None:
        warning = _manual_warning(stage_index, "missing_rest_phase")
        warnings.append(warning)
        row["warnings"].append(warning)
    no_usable_vo2_vco2 = bool(selected_points) and not usable_points
    if vo2_l_min is None or vco2_l_min is None or no_usable_vo2_vco2:
        code = (
            "manual_exclusions_no_usable_vo2_vco2"
            if no_usable_vo2_vco2 else "missing_vo2_vco2"
        )
        warning = _manual_warning(stage_index, code)
        warnings.append(warning)
        row["warnings"].append(warning)

    can_compute_ec = (
        mass_kg is not None
        and rest_baseline is not None
        and speed_m_min > 0
        and bool(usable_points)
        and vo2_l_min is not None
        and vco2_l_min is not None
    )
    if can_compute_ec:
        row["ec_j_kg_m"] = round(_running_economy_j_kg_m(
            vo2_l_min * 1000,
            vco2_l_min * 1000,
            rest_baseline,
            mass_kg,
            speed_m_min,
        ), 3)
    if vo2max_ml_kg_min is not None:
        percent_vo2 = vo2_ml_kg_min
        if percent_vo2 is None and mass_kg is not None and vo2_l_min is not None:
            percent_vo2 = vo2_l_min * 1000 / mass_kg
        if percent_vo2 is not None:
            row["percent_vo2max"] = round(percent_vo2 / vo2max_ml_kg_min * 100, 3)
    return row, warnings


def _running_economy_j_kg_m(
    vo2_ml_min: float,
    vco2_ml_min: float,
    rest_baseline: dict,
    mass_kg: float,
    speed_m_min: float,
) -> float:
    # Formule Notion: VO2/VCO2 en ml/min, vitesse en m/min, masse en kg.
    return (
        ((0.00055 * (vco2_ml_min - rest_baseline["vco2_ml_min"]))
        + (0.004471 * (vo2_ml_min - rest_baseline["vo2_ml_min"])))
        * 4184
        / (mass_kg * speed_m_min)
    )


def summarize_native_de(points: list[dict]) -> dict:
    """Moyenne les champs DE* MetaSoft natifs en kcal/h s'ils existent."""
    summary = {}
    for key in ("de_kcal_h", "decho_kcal_h", "defat_kcal_h", "depro_kcal_h"):
        values = [_number(point, key) for point in points]
        values = [value for value in values if value is not None]
        if values:
            summary[key] = {
                "value": round(mean(values), 3),
                "unit": "kcal/h",
                "source": "xml_native",
            }
    return summary


def check_ventilatory_consistency(points: list[dict]) -> list[dict]:
    """Controle V'E/(V'E/V'O2) sans remplacer la valeur VO2 XML."""
    diffs = []
    for point in points:
        vo2 = _number(point, "vo2_l_min")
        ve = _number(point, "ve_l_min")
        ratio = _number(point, "ve_vo2")
        if not vo2 or not ve or not ratio:
            continue
        reconstructed = ve / ratio
        diffs.append(abs(reconstructed - vo2) / vo2)
    if diffs and mean(diffs) > 0.05:
        return [{
            "code": "ventilatory_vo2_consistency",
            "message": (
                "Controle coherence: V'E/(V'E/V'O2) differe de V'O2 XML "
                "de plus de 5% en moyenne. Aucun fallback metier applique."
            ),
            "mean_relative_diff": round(mean(diffs), 4),
        }]
    return []


def qualify_stage_speed(stage: dict) -> dict:
    """Qualifie les paliers non-course sans les supprimer de l'analyse."""
    speed = stage["speed_kmh"]
    if speed <= 0:
        return {
            "status": "non_running_zero_speed",
            "warning": _speed_warning(
                stage,
                "warmup_zero_speed_stage",
                "Palier d'echauffement a vitesse nulle: EC non interpretable.",
            ),
        }
    if speed < MIN_RUNNING_SPEED_KMH:
        return {
            "status": "low_speed_non_running",
            "warning": _speed_warning(
                stage,
                "warmup_low_speed_stage",
                (
                    "Palier d'echauffement a vitesse tres basse: EC calculee "
                    "si possible, mais hors allure de course."
                ),
            ),
        }
    return {"status": "running_stage"}


def _vo2_ml_min(point: dict) -> Optional[float]:
    value = _number(point, "vo2_l_min")
    return value * 1000 if value is not None else None


def _vco2_ml_min(point: dict) -> dict:
    native = _number(point, "vco2_l_min")
    if native is not None:
        source = point.get("value_sources", {}).get("vco2_l_min")
        if source == "xml":
            source = "xml_native"
        return {"value": native * 1000, "source": source or "xml_native"}
    return {"value": None, "source": None}


def _vco2_source(items: list[dict]) -> Optional[str]:
    sources = {item.get("source") for item in items if item.get("source")}
    if not sources:
        return None
    if len(sources) == 1:
        return next(iter(sources))
    return "derived_mixed"


def _number(point: dict, key: str) -> Optional[float]:
    value = point.get("values", {}).get(key)
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _first_number(*values) -> Optional[float]:
    for value in values:
        if _positive_number(value) is not None:
            return float(value)
    return None


def _positive_number(value) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and isfinite(value) and value > 0:
        return float(value)
    return None


def _finite_number(value, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f"{field} doit etre un nombre fini.")
    return float(value)


def _selection_int(value, field: str) -> int:
    number = _finite_number(value, field)
    if number != int(number):
        raise ValueError(f"{field} doit etre un entier.")
    return int(number)


def _normalise_manual_exclusions(
    exclusions: list[dict],
    start_seconds: float,
    end_seconds: float,
) -> list[dict]:
    if not isinstance(exclusions, list):
        raise ValueError("exclusions doit etre une liste.")
    normalised = []
    for exclusion in exclusions:
        if not isinstance(exclusion, dict):
            raise ValueError("exclusion EC invalide.")
        start = _finite_number(exclusion.get("start_seconds"), "exclusion.start_seconds")
        end = _finite_number(exclusion.get("end_seconds"), "exclusion.end_seconds")
        bounded_start = max(start_seconds, min(start, end, end_seconds))
        bounded_end = min(end_seconds, max(start, end, start_seconds))
        if bounded_end > bounded_start:
            normalised.append({
                "start_seconds": round(bounded_start, 3),
                "end_seconds": round(bounded_end, 3),
            })
    normalised.sort(key=lambda item: item["start_seconds"])
    merged = []
    for item in normalised:
        if merged and item["start_seconds"] <= merged[-1]["end_seconds"]:
            merged[-1]["end_seconds"] = max(merged[-1]["end_seconds"], item["end_seconds"])
        else:
            merged.append(item)
    return merged


def _manual_is_excluded(t_seconds, exclusions: list[dict]) -> bool:
    return (
        isinstance(t_seconds, (int, float))
        and not isinstance(t_seconds, bool)
        and isfinite(t_seconds)
        and any(item["start_seconds"] <= t_seconds <= item["end_seconds"] for item in exclusions)
    )


def _points_between(points: list[dict], start_seconds: float, end_seconds: float) -> list[dict]:
    return [
        point for point in points
        if (
            isinstance(point.get("t_seconds"), (int, float))
            and not isinstance(point.get("t_seconds"), bool)
            and start_seconds <= point["t_seconds"] <= end_seconds
        )
    ]


def _average_metric(points: list[dict], key: str) -> Optional[float]:
    values = [_number(point, key) for point in points]
    values = [value for value in values if value is not None]
    return mean(values) if values else None


def _round_optional(value: Optional[float], digits: int) -> Optional[float]:
    return round(value, digits) if value is not None else None


def _manual_warning(stage_index: int, code: str) -> dict:
    message = "Economie de course manuelle indisponible ou partielle."
    if code == "manual_exclusions_no_usable_vo2_vco2":
        message = (
            "Economie de course manuelle indisponible: exclusions sans point "
            "VO2/VCO2 utilisable."
        )
    return {
        "code": code,
        "message": message,
        "stage_index": stage_index,
    }


def _stage_duration_seconds(stage: dict) -> float:
    start = stage.get("start_seconds")
    end = stage.get("end_seconds")
    if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
        return 0
    return max(0, end - start)


def _stage_warning(stage: dict, code: str) -> dict:
    return {
        "code": code,
        "message": (
            "Economie de course indisponible pour le palier "
            f"{stage['stage_index']} ({stage['speed_kmh']} km/h)."
        ),
        "stage_index": stage["stage_index"],
    }


def _speed_warning(stage: dict, code: str, message: str) -> dict:
    return {
        "code": code,
        "message": message,
        "stage_index": stage["stage_index"],
        "speed_kmh": stage["speed_kmh"],
    }
