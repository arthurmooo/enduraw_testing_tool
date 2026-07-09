"""Helpers purs pour les graphes MetaSoft de l'app locale.

Ce module ne dessine rien et ne modifie jamais l'analyse recue: il prepare les
series que la future fenetre Tk/matplotlib affichera. Source: points normalises
`analysis["points"]` et EC deja calculee dans `analysis["computed"]`. Unites:
celles des exports MetaSoft, sauf l'EC deja exprimee en `J/kg/m`. Transformation:
lissage temporel centre strictement visuel, jamais utilise pour les marqueurs,
le profil ou le JSON exporte.
"""


MARKER_CONFIGS = {
    "SV1": {"label": "SV1", "color": "#00d48a"},
    "SV2": {"label": "SV2", "color": "#ff8a00"},
    "VO2_max": {"label": "VO2max", "color": "#ff405d"},
    "VMA": {"label": "VMA", "color": "#18b8ff"},
}


def _series(key, label, unit, color, axis="y", smoothable=True):
    return {
        "key": key,
        "label": label,
        "unit": unit,
        "color": color,
        "axis": axis,
        "smoothable": smoothable and key != "speed_kmh",
    }


GRAPH_CONFIGS = (
    {
        "id": "ve_vo2_peto2_time",
        "title": "V'E, V'E/V'O2, PETO2",
        "kind": "time",
        "source": "points",
        "x_axis": {"key": "t_seconds", "label": "Temps", "unit": "s"},
        "series": (
            _series("ve_l_min", "V'E", "L/min", "#10a8ff"),
            _series("ve_vo2", "V'E/V'O2", "sans unite", "#16e0c2", "y2"),
            _series("peto2_mmhg", "PETO2", "mmHg", "#ff8a00", "y2"),
        ),
    },
    {
        "id": "ve_vco2_petco2_time",
        "title": "V'E, V'E/V'CO2, PETCO2",
        "kind": "time",
        "source": "points",
        "x_axis": {"key": "t_seconds", "label": "Temps", "unit": "s"},
        "series": (
            _series("ve_l_min", "V'E", "L/min", "#10a8ff"),
            _series("ve_vco2", "V'E/V'CO2", "sans unite", "#16e0c2", "y2"),
            _series("petco2_mmhg", "PETCO2", "mmHg", "#ff6b00", "y2"),
        ),
    },
    {
        "id": "ve_time",
        "title": "V'E",
        "kind": "time",
        "source": "points",
        "x_axis": {"key": "t_seconds", "label": "Temps", "unit": "s"},
        "series": (_series("ve_l_min", "V'E", "L/min", "#10a8ff"),),
    },
    {
        "id": "hr_vo2_fc_time",
        "title": "HR, V'O2/HR",
        "kind": "time",
        "source": "points",
        "x_axis": {"key": "t_seconds", "label": "Temps", "unit": "s"},
        "series": (
            _series("fc_bpm", "HR", "bpm", "#ff5b22"),
            _series("vo2_fc_ml", "V'O2/HR", "ml", "#10a8ff", "y2"),
        ),
    },
    {
        "id": "vo2_vco2_time",
        "title": "V'O2, V'CO2",
        "kind": "time",
        "source": "points",
        "x_axis": {"key": "t_seconds", "label": "Temps", "unit": "s"},
        "series": (
            _series("vo2_l_min", "V'O2", "L/min", "#10a8ff"),
            _series("vco2_l_min", "V'CO2", "L/min", "#16d18d"),
        ),
    },
    {
        "id": "de_time",
        "title": "DE / CHOx / FATOx / PROx",
        "kind": "time",
        "source": "points",
        "x_axis": {"key": "t_seconds", "label": "Temps", "unit": "s"},
        "series": (
            _series("de_kcal_h", "DE", "kcal/h", "#f8fafc"),
            _series("decho_kcal_h", "CHOx", "kcal/h", "#ff8a00"),
            _series("defat_kcal_h", "FATOx", "kcal/h", "#16d18d"),
            _series("depro_kcal_h", "PROx", "kcal/h", "#a855f7"),
        ),
    },
    {
        "id": "ve_vco2_scatter",
        "title": "V'E(V'CO2)",
        "kind": "scatter",
        "source": "points",
        "x_axis": {"key": "vco2_l_min", "label": "V'CO2", "unit": "L/min"},
        "series": (_series("ve_l_min", "V'E", "L/min", "#10a8ff", "y", False),),
    },
    {
        "id": "vco2_hr_scatter",
        "title": "V'CO2, HR",
        "kind": "scatter",
        "source": "points",
        "x_axis": {"key": "vo2_l_min", "label": "V'O2", "unit": "L/min"},
        "series": (
            _series("vco2_l_min", "V'CO2", "L/min", "#16d18d", "y", False),
            _series("fc_bpm", "HR", "bpm", "#ff5b22", "y2", False),
        ),
    },
    {
        "id": "ve_ratios_time",
        "title": "V'E/V'O2, V'E/V'CO2",
        "kind": "time",
        "source": "points",
        "x_axis": {"key": "t_seconds", "label": "Temps", "unit": "s"},
        "series": (
            _series("ve_vo2", "V'E/V'O2", "sans unite", "#10a8ff"),
            _series("ve_vco2", "V'E/V'CO2", "sans unite", "#ff6b00"),
        ),
    },
    {
        "id": "vt_ve_scatter",
        "title": "VT(V'E)",
        "kind": "scatter",
        "source": "points",
        "x_axis": {"key": "ve_l_min", "label": "V'E", "unit": "L/min"},
        "series": (_series("vt_l", "VT", "L", "#a855f7", "y", False),),
    },
    {
        "id": "rer_time",
        "title": "RER",
        "kind": "time",
        "source": "points",
        "x_axis": {"key": "t_seconds", "label": "Temps", "unit": "s"},
        "series": (_series("rer", "RER", "sans unite", "#16e0c2"),),
    },
    {
        "id": "pet_time",
        "title": "PETO2, PETCO2",
        "kind": "time",
        "source": "points",
        "x_axis": {"key": "t_seconds", "label": "Temps", "unit": "s"},
        "series": (
            _series("peto2_mmhg", "PETO2", "mmHg", "#10a8ff"),
            _series("petco2_mmhg", "PETCO2", "mmHg", "#ff6b00"),
        ),
    },
    {
        "id": "running_economy",
        "title": "Economie de course",
        "kind": "bar",
        "source": "running_economy",
        "x_axis": {"key": "stage_index", "label": "Palier"},
        "series": (
            _series("value_j_kg_m", "EC (J/kg/m)", "J/kg/m", "#16e0c2", "y", False),
        ),
    },
)

GRAPH_CONFIGS_BY_ID = {config["id"]: config for config in GRAPH_CONFIGS}


def smooth_series_by_time(times, values, window_seconds):
    """Lisse une serie par fenetre temporelle centree, sans muter les entrees.

    `times` est en secondes. `values` garde les valeurs natives de la serie.
    `None` et les valeurs non numeriques sont ignorees dans la moyenne; si la
    fenetre ne contient aucune valeur numerique, le point lisse vaut `None`.
    """
    if len(times) != len(values):
        raise ValueError("times et values doivent avoir la meme longueur")
    if window_seconds <= 0:
        return list(values)

    raw_values = [_number_or_none(value) for value in values]
    samples = [
        (index, time_value, raw_values[index])
        for index, time_value in enumerate(_number_or_none(time) for time in times)
        if time_value is not None
    ]
    if not samples:
        return list(values)

    # Les points MetaSoft arrivent deja tries; le fallback garde le helper pur.
    if any(samples[index][1] > samples[index + 1][1] for index in range(len(samples) - 1)):
        samples = sorted(samples, key=lambda sample: sample[1])

    half_window = window_seconds / 2
    left = 0
    right = 0
    total = 0.0
    count = 0
    by_index = {}

    for original_index, center_time, _value in samples:
        while right < len(samples) and samples[right][1] <= center_time + half_window:
            value = samples[right][2]
            if value is not None:
                total += value
                count += 1
            right += 1
        while left < len(samples) and samples[left][1] < center_time - half_window:
            value = samples[left][2]
            if value is not None:
                total -= value
                count -= 1
            left += 1
        by_index[original_index] = total / count if count else None

    return [by_index.get(index, raw_values[index]) for index in range(len(values))]


def get_point_series_availability(points, graph_config):
    """Retourne les series presentes/absentes dans des points MetaSoft normalises."""
    config = _resolve_graph_config(graph_config)
    available_keys = set()
    for point in points or []:
        x_key = config.get("x_axis", {}).get("key")
        if x_key == "t_seconds" and _number_or_none(point.get("t_seconds")) is not None:
            available_keys.add("t_seconds")
        for key, value in point.get("values", {}).items():
            if _number_or_none(value) is not None:
                available_keys.add(key)

    available = []
    missing = []
    x_key = config.get("x_axis", {}).get("key")
    x_available = x_key == "t_seconds" or x_key in available_keys
    for series_config in config["series"]:
        target = available if x_available and series_config["key"] in available_keys else missing
        target.append(series_config)
    return {"available": available, "missing": missing}


def build_graph_render_data(analysis, graph_config, smooth_window_seconds=0):
    """Prepare les donnees de rendu brutes et lissees sans modifier `analysis`."""
    config = _resolve_graph_config(graph_config)
    if config.get("source") == "running_economy":
        return _build_running_economy_render_data(analysis, config)
    return _build_point_render_data(analysis, config, smooth_window_seconds)


def click_x_to_time_seconds(x_value, times):
    """Convertit une coordonnee x matplotlib en temps clique borne aux donnees."""
    x_seconds = _number_or_none(x_value)
    valid_times = _valid_times(times)
    if x_seconds is None or not valid_times:
        return None
    return min(max(x_seconds, valid_times[0]), valid_times[-1])


def clamp_time_range(start_seconds, end_seconds, times):
    """Borne un range de zoom/selection aux temps disponibles, ordre inclus."""
    start = click_x_to_time_seconds(start_seconds, times)
    end = click_x_to_time_seconds(end_seconds, times)
    if start is None or end is None:
        return None
    return (min(start, end), max(start, end))


def _build_point_render_data(analysis, config, smooth_window_seconds):
    points = [
        point for point in analysis.get("points", [])
        if _point_x_value(point, config) is not None
    ]
    x_values = [_point_x_value(point, config) for point in points]
    availability = get_point_series_availability(points, config)
    render_series = []

    for series_config in config["series"]:
        raw_values = [
            _number_or_none(point.get("values", {}).get(series_config["key"]))
            for point in points
        ]
        should_smooth = (
            config.get("kind") == "time"
            and series_config["smoothable"]
            and smooth_window_seconds > 0
        )
        render_values = (
            smooth_series_by_time(x_values, raw_values, smooth_window_seconds)
            if should_smooth else list(raw_values)
        )
        render_series.append({
            **series_config,
            "raw_values": raw_values,
            "render_values": render_values,
            "smoothed": should_smooth,
        })

    return {
        "id": config["id"],
        "title": config["title"],
        "source": config["source"],
        "kind": config.get("kind", "time"),
        "x_axis": config["x_axis"],
        "x_values": x_values,
        "series": render_series,
        "missing_series": availability["missing"],
    }


def _build_running_economy_render_data(analysis, config):
    economy = analysis.get("computed", {}).get("running_economy", []) or []
    rows = [
        row for row in economy
        if _number_or_none(row.get("stage_index")) is not None
    ]
    x_values = [row["stage_index"] for row in rows]
    render_series = []
    missing = []

    for series_config in config["series"]:
        raw_values = [_number_or_none(row.get(series_config["key"])) for row in rows]
        if not any(value is not None for value in raw_values):
            missing.append(series_config)
        render_series.append({
            **series_config,
            "raw_values": raw_values,
            "render_values": list(raw_values),
            "smoothed": False,
        })

    return {
        "id": config["id"],
        "title": config["title"],
        "source": config["source"],
        "kind": config.get("kind", "bar"),
        "x_axis": config["x_axis"],
        "x_values": x_values,
        "series": render_series,
        "missing_series": missing,
        "stage_speeds_kmh": [row.get("speed_kmh") for row in rows],
    }


def _resolve_graph_config(graph_config):
    if isinstance(graph_config, str):
        return GRAPH_CONFIGS_BY_ID[graph_config]
    return graph_config


def _point_x_value(point, config):
    key = config.get("x_axis", {}).get("key")
    if key == "t_seconds":
        return _number_or_none(point.get("t_seconds"))
    return _number_or_none(point.get("values", {}).get(key))


def _valid_times(times):
    values = sorted(
        time_value for time_value in (_number_or_none(time) for time in times)
        if time_value is not None
    )
    return values


def _number_or_none(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None
