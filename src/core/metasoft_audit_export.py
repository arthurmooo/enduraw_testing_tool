"""Export audit MetaSoft local sans toucher au JSON Valentin.

Le module assemble un sidecar pur depuis les donnees deja calculees: metadata
XML/profil, marqueurs officiels, economie de course, sources, unites et
warnings. Il ne recalcule pas l'EC, ne lit/ecrit aucun fichier et n'exporte
aucune donnee lissee. Les points bruts ne sont inclus que sur demande, decimes,
pour un controle visuel leger.
"""
import unicodedata
from copy import deepcopy
from pathlib import Path


RUNNING_ECONOMY_FORMULA = (
    "((0.00055 * (VCO2 - VCO2repos)) + "
    "(0.004471 * (VO2 - VO2repos))) * 4184 / (masse * vitesse)"
)


def metasoft_audit_filename(json_filename_or_stem: str) -> str:
    """Retourne le nom sidecar `<stem>.metasoft_audit.json`.

    Source: nom du JSON principal local. Transformation: seul le stem est
    conserve, sans dossier, pour laisser l'appelant choisir le repertoire
    d'ecriture.
    """
    stem = Path(str(json_filename_or_stem)).stem
    return f"{stem}.metasoft_audit.json"


def build_metasoft_audit_export(
    analysis: dict,
    profile: dict | None = None,
    markers=None,
    json_filename: str = "",
    audit_filename: str | None = None,
    profile_filename: str = "",
    generated_at: str | None = None,
    app_version: str = "",
    export_warnings: list[dict] | None = None,
    ui_warnings: list[dict] | None = None,
    include_audit_points: bool = False,
    audit_point_step: int = 30,
) -> dict:
    """Construit le sidecar auditable MetaSoft.

    `analysis` vient de `build_metasoft_analysis`: EC en J/kg/m, baseline repos
    et metriques XML natives. `markers` vient de `build_metasoft_marker`: temps
    en secondes, valeurs officielles brutes ou moyenne brute de fenetre. Les
    points lisses et agregats graphiques ne sont jamais lus ni exposes.
    """
    profile = profile or {}
    markers = _normalise_markers(markers)
    audit_name = audit_filename or metasoft_audit_filename(json_filename)
    identity_warning = _identity_mismatch_warning(analysis.get("athlete", {}), profile)

    warnings = {
        "analysis": deepcopy(analysis.get("warnings", [])),
        "markers": _marker_warnings(markers),
        "profile": [identity_warning] if identity_warning else [],
        "export": list(export_warnings or []),
        "ui": list(ui_warnings or []),
    }

    sidecar = {
        "export": {
            "generated_at": generated_at,
            "app_version": app_version,
            "json_filename": json_filename,
            "audit_filename": audit_name,
        },
        "xml": {
            "file": deepcopy(analysis.get("file", {})),
            "athlete": deepcopy(analysis.get("athlete", {})),
            "test": deepcopy(analysis.get("test", {})),
        },
        "profile": {
            "filename": profile_filename,
            "identity": _profile_identity(profile),
            "identity_mismatch_warning": identity_warning,
        },
        "metrics": deepcopy(analysis.get("metrics", {})),
        "markers": markers,
        "running_economy": {
            "formula": RUNNING_ECONOMY_FORMULA,
            "units": {
                "value": "J/kg/m",
                "vo2": "ml/min",
                "vco2": "ml/min",
                "mass": "kg",
                "speed": "m/min",
            },
            "sources": {
                "vo2": "V'O2 XML, L/min -> ml/min",
                "vco2": "V'CO2 XML si present, sinon VO2 * RER",
                "rest": "phase XML Repos",
                "mass": "poids XML, sinon profil local",
                "speed": "v XML, km/h -> m/min",
            },
            "rest_baseline": deepcopy(
                analysis.get("computed", {}).get("rest_baseline")
            ),
            "stages": deepcopy(
                analysis.get("computed", {}).get("running_economy", [])
            ),
        },
        "warnings": warnings,
    }

    if include_audit_points:
        sidecar["audit_points"] = _decimated_audit_points(
            analysis.get("points", []),
            audit_point_step,
        )

    return sidecar


def _normalise_markers(markers) -> dict:
    """Copie les marqueurs UI et ajoute leur provenance officielle."""
    if not markers:
        return {}
    items = markers.items() if isinstance(markers, dict) else (
        (marker.get("name"), marker) for marker in markers
    )
    result = {}
    for key, marker in items:
        if not isinstance(marker, dict):
            continue
        name = str(key or marker.get("name") or "").strip()
        if not name:
            continue
        copied = deepcopy(marker)
        copied["official_source"] = "build_metasoft_marker"
        result[name] = copied
    return result


def _marker_warnings(markers: dict) -> list[dict]:
    warnings = []
    for name, marker in markers.items():
        for warning in marker.get("warnings", []):
            copied = deepcopy(warning)
            copied.setdefault("marker", name)
            warnings.append(copied)
    return warnings


def _profile_identity(profile: dict) -> dict:
    identity = profile.get("identity", {})
    first_name = identity.get("first_name", "")
    last_name = identity.get("last_name", "")
    return {
        "first_name": first_name,
        "last_name": last_name,
        "athlete_name": f"{last_name} {first_name}".strip(),
    }


def _identity_mismatch_warning(xml_athlete: dict, profile: dict) -> dict | None:
    profile_identity = _profile_identity(profile)
    xml_name = _identity_name(xml_athlete)
    profile_name = _identity_name(profile_identity)
    if (
        not xml_name
        or not profile_name
        or _clean_name(xml_name) == _clean_name(profile_name)
    ):
        return None
    return {
        "code": "identity_mismatch",
        "message": "Identite XML differente du profil local; export non bloque.",
        "xml_athlete_name": xml_name,
        "profile_athlete_name": profile_name,
        "blocking": False,
    }


def _identity_name(identity: dict) -> str:
    return (
        identity.get("athlete_name")
        or f"{identity.get('last_name', '')} {identity.get('first_name', '')}".strip()
    )


def _clean_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value).strip().lower())
    ascii_value = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return " ".join(ascii_value.split())


def _decimated_audit_points(points: list[dict], step: int) -> list[dict]:
    # ponytail: decimation fixe; budget en octets si le XML devient trop lourd.
    step = max(int(step or 1), 1)
    decimated = []
    for point in points[::step]:
        decimated.append({
            "t_seconds": point.get("t_seconds"),
            "phase": point.get("phase"),
            "marker": point.get("marker"),
            "values": deepcopy(point.get("values", {})),
        })
    return decimated
