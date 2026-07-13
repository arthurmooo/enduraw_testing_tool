"""Résumé de profil des résultats reportés depuis l'analyse MetaSoft.

Le module ne recalcule aucune mesure. Il formate uniquement les lactates lus
dans le profil et l'économie de course lue dans le sidecar du match. Les unités
restent celles des sources officielles : mmol/L, km/h, L/min et J/kg/m.
"""
from math import isfinite
from typing import Any, Dict


LACTATE_TYPE_LABELS = {
    "rest_before": "Repos initial",
    "post_warmup": "Après échauffement",
    "stage": "Palier",
    "recovery": "Récupération",
    "rest_after": "Repos final",
}


def build_profile_metasoft_summary(
    profile: Dict[str, Any],
    economy_state: Dict[str, Any],
    matched: bool,
) -> Dict[str, Dict[str, Any]]:
    """Construit les textes affichés dans le profil, sans modifier les sources."""
    return {
        "lactate": _lactate_summary(profile),
        "running_economy": _running_economy_summary(economy_state, matched),
    }


def _lactate_summary(profile: Dict[str, Any]) -> Dict[str, Any]:
    stress = profile.get("stress_test_results", {}) or {}
    measurements = stress.get("lactate_profile", []) or []
    thresholds = stress.get("lactate_thresholds", {}) or {}
    if not measurements:
        return {
            "status": "Non renseigné",
            "tone": "muted",
            "lines": ["Aucune prise de lactate reportée."],
        }

    thresholds_by_index = {}
    for name, threshold in thresholds.items():
        if not isinstance(threshold, dict):
            continue
        index = threshold.get("measurement_index")
        if isinstance(index, int):
            thresholds_by_index.setdefault(index, []).append(str(name).upper())

    lines = []
    included = 0
    excluded = 0
    incomplete = 0
    for index, measurement in enumerate(measurements):
        if not isinstance(measurement, dict):
            incomplete += 1
            continue
        enabled = measurement.get("enabled") is not False
        included += int(enabled)
        excluded += int(not enabled)
        if enabled and (
            _number(measurement.get("speed")) is None
            or _number(measurement.get("lactate_mmol_l")) is None
        ):
            incomplete += 1

        label = _lactate_label(measurement)
        values = []
        speed = _format_number(measurement.get("speed"))
        lactate = _format_number(measurement.get("lactate_mmol_l"))
        if speed != "—":
            values.append(f"{speed} km/h")
        if lactate != "—":
            values.append(f"{lactate} mmol/L")
        delay = _format_number(measurement.get("delay_minutes"))
        if delay != "—":
            values.append(f"à {delay} min")
        values.extend(thresholds_by_index.get(index, []))
        details = " · ".join(values) if values else "Valeur non renseignée"
        state = "Incluse" if enabled else "Écartée"
        lines.append(f"[{state}] {label} — {details}")

    status = f"{included} incluse(s) · {excluded} écartée(s)"
    if incomplete:
        status += f" · {incomplete} incomplète(s)"
    return {
        "status": status,
        "tone": "warning" if incomplete else "success",
        "lines": lines,
    }


def _running_economy_summary(
    economy_state: Dict[str, Any],
    matched: bool,
) -> Dict[str, Any]:
    if not matched:
        return {
            "status": "Aucun XML associé",
            "tone": "muted",
            "lines": ["Associez le profil à un XML pour calculer l'EC."],
        }

    status = economy_state.get("status")
    if status == "missing":
        return {
            "status": "Non renseignée",
            "tone": "muted",
            "lines": ["Aucune économie de course reportée."],
        }
    if status in {"stale", "corrupt"}:
        label = "À recalculer" if status == "stale" else "Données invalides"
        return {
            "status": label,
            "tone": "danger",
            "lines": [
                "Ouvrez l'analyse MetaSoft et reportez de nouveau l'économie de course."
            ],
        }

    data = economy_state.get("data") if status == "ok" else None
    if not isinstance(data, dict):
        return {
            "status": "Données indisponibles",
            "tone": "danger",
            "lines": ["Le résumé EC ne peut pas être affiché."],
        }

    enabled_by_stage = {
        item.get("stage_index"): item.get("enabled")
        for item in data.get("stage_selections", [])
        if isinstance(item, dict)
    }
    rows = [row for row in data.get("rows", []) if isinstance(row, dict)]
    included = sum(
        enabled_by_stage.get(row.get("stage_index"), True) is not False
        for row in rows
    )
    excluded = len(rows) - included
    lines = []
    for row in rows:
        enabled = enabled_by_stage.get(row.get("stage_index"), True) is not False
        state = "Incluse" if enabled else "Écartée"
        source = row.get("sources", {}).get("selection")
        prefix = "Zone" if source == "manual_free_zone" else "Palier"
        stage = row.get("stage_index", "—")
        speed = _format_number(row.get("speed_kmh"))
        start = _format_time(row.get("start_seconds"))
        end = _format_time(row.get("end_seconds"))
        ec = _format_number(row.get("ec_j_kg_m"), digits=3)
        percent = _format_number(row.get("percent_vo2max"), digits=1)
        points = row.get("point_count", "—")
        exclusions = len(row.get("exclusions", []) or [])
        lines.append(
            f"[{state}] {prefix} {stage} — {speed} km/h · {start}–{end} · "
            f"EC {ec} J/kg/m"
        )
        lines.append(
            f"VO2 {_format_number(row.get('vo2_l_min'))} L/min · "
            f"VCO2 {_format_number(row.get('vco2_l_min'))} L/min · "
            f"{percent} %VO2max · {points} pts · {exclusions} exclusion(s)"
        )

    rest = data.get("rest_baseline")
    if isinstance(rest, dict):
        lines.append(
            f"Repos — {_format_time(rest.get('start_seconds'))}–"
            f"{_format_time(rest.get('end_seconds'))} · "
            f"{rest.get('point_count', '—')} pts · "
            f"{len(rest.get('exclusions', []) or [])} exclusion(s)"
        )
    if not lines:
        lines.append("Aucun palier EC calculé.")

    return {
        "status": f"{included} inclus · {excluded} écarté(s)",
        "tone": "success" if included else "warning",
        "lines": lines,
    }


def _lactate_label(measurement: Dict[str, Any]) -> str:
    if str(measurement.get("label") or "").strip():
        return str(measurement["label"]).strip()
    kind = measurement.get("type")
    label = LACTATE_TYPE_LABELS.get(kind, "Mesure")
    if kind == "stage" and measurement.get("stage_index") is not None:
        return f"{label} {measurement['stage_index']}"
    return label


def _number(value: Any):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if isfinite(number) else None


def _format_number(value: Any, digits: int = 2) -> str:
    number = _number(value)
    if number is None:
        return "—"
    text = f"{number:.{digits}f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


def _format_time(value: Any) -> str:
    seconds = _number(value)
    if seconds is None or seconds < 0:
        return "—"
    rounded = int(round(seconds))
    hours, remainder = divmod(rounded, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"
