"""Validation d'identite entre le XML MetaSoft et le profil local.

La comparaison porte uniquement sur les noms declares par les deux sources.
Elle normalise casse, accents et espaces, mais ne devine jamais une identite
absente: un XML MetaSoft non verifiable reste bloquant avant report/export.
"""
import unicodedata
from typing import Any, Dict


def metasoft_identity_check(
    xml_athlete: Dict[str, Any],
    profile: Dict[str, Any],
) -> Dict[str, Any]:
    """Compare l'identite XML au profil sans fallback sur le nom de fichier."""
    xml_name = identity_name(xml_athlete)
    profile_name = identity_name((profile.get("identity", {}) or {}))
    details = {
        "blocking": True,
        "xml_athlete_name": xml_name or None,
        "profile_athlete_name": profile_name or None,
    }
    if not xml_name or not profile_name:
        return {
            "ok": False,
            "code": "identity_unverifiable",
            "message": (
                "Identite XML/profil incomplete: report et export refuses "
                "sans correspondance nominative verifiable."
            ),
            **details,
        }
    if clean_identity(xml_name) != clean_identity(profile_name):
        return {
            "ok": False,
            "code": "identity_mismatch",
            "message": "Identite XML differente du profil local: report et export refuses.",
            **details,
        }
    return {
        "ok": True,
        "code": None,
        "message": None,
        "blocking": False,
        "xml_athlete_name": xml_name,
        "profile_athlete_name": profile_name,
    }


def identity_name(identity: Dict[str, Any]) -> str:
    """Retourne le nom declare, au format nom puis prenom si necessaire."""
    return str(
        identity.get("athlete_name")
        or f"{identity.get('last_name', '')} {identity.get('first_name', '')}".strip()
    ).strip()


def clean_identity(value: Any) -> str:
    """Normalise accents, casse et espaces pour une comparaison stricte."""
    normalized = unicodedata.normalize("NFKD", str(value).strip().casefold())
    without_accents = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return " ".join(without_accents.split())
