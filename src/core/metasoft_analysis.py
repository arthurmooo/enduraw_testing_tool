"""Calculs MetaSoft locaux pour l'app de testing.

Le module enrichit le parser XML sans persistance: phases, paliers
d'echauffement, depense energetique native et economie de course. Les unites
sont explicites: `V'O2` XML en L/min devient ml/min pour l'EC, la vitesse
`km/h` devient `m/min`, et le resultat d'EC est en `J/kg/m`. Aucune valeur
absente n'est reconstruite depuis une equation de confort.
"""
from statistics import mean
from typing import Optional


MIN_STABLE_SPEED_STAGE_SECONDS = 60
MIN_RUNNING_SPEED_KMH = 6.0


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
    # Formule Notion: VO2/VCO2 en ml/min, vitesse en m/min, masse en kg.
    value = (
        ((0.00055 * (vco2 - rest_baseline["vco2_ml_min"]))
        + (0.004471 * (vo2 - rest_baseline["vo2_ml_min"])))
        * 4184
        / (mass_kg * result["speed_m_min"])
    )
    result.update({
        "value_j_kg_m": round(value, 3),
        "vo2_ml_min": round(vo2, 3),
        "vco2_ml_min": round(vco2, 3),
        "mass_kg": mass_kg,
        "vco2_source": _vco2_source(vco2_valid),
    })
    return result


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
        return {"value": native * 1000, "source": "xml_native"}
    vo2 = _number(point, "vo2_l_min")
    rer = _number(point, "rer")
    if vo2 is not None and rer is not None:
        return {"value": vo2 * rer * 1000, "source": "derived_vo2_x_rer"}
    return {"value": None, "source": None}


def _vco2_source(items: list[dict]) -> Optional[str]:
    sources = {item.get("source") for item in items if item.get("source")}
    if "xml_native" in sources:
        return "xml_native"
    if "derived_vo2_x_rer" in sources:
        return "derived_vo2_x_rer"
    return None


def _number(point: dict, key: str) -> Optional[float]:
    value = point.get("values", {}).get(key)
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _first_number(*values) -> Optional[float]:
    for value in values:
        if isinstance(value, (int, float)) and value > 0:
            return float(value)
    return None


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
