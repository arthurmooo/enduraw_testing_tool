"""Serveur HTTP local MetaSoft pour l'UI navigateur.

Le serveur expose uniquement la session locale deja chargee par l'app Tkinter.
Source: profils/XML/matches via `SessionManager`. Transformations officielles:
parser MetaSoft, analyse Python, marqueurs Python et report profil.
Aucun endpoint ne lit de valeur preview React comme source officielle, et aucune
ecriture BDD n'existe dans ce module.
"""
import json
import mimetypes
import secrets
import threading
import unicodedata
import gc
from contextlib import contextmanager
from copy import deepcopy
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, HTTPServer
from math import isfinite
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from core.metasoft_analysis import build_metasoft_analysis
from core.metasoft_markers import (
    apply_metasoft_stress_patch,
    build_metasoft_marker,
    metasoft_marker_to_stress_patch,
)
from utils.xml_parser import TCPXmlParser


VALID_MARKERS = {"SV1", "SV2", "VO2_max", "VMA"}
_PROCESS_TOKEN = secrets.token_urlsafe(32)


class LocalMetaSoftServer:
    """Petit serveur local reusable pour une session MetaSoft active."""

    _instance = None
    _lock = threading.Lock()

    def __init__(self, session_manager, host="127.0.0.1"):
        self.session_manager = session_manager
        self.host = host
        self.token = _PROCESS_TOKEN
        self.httpd = None
        self.thread = None
        self._profile_update_lock = threading.Lock()
        self._profile_updates = []
        self._match_context_cache = {}

    @classmethod
    def ensure_started(cls, session_manager):
        """Demarre le serveur une seule fois et remplace la session active."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(session_manager)
            elif cls._instance.session_manager is not session_manager:
                cls._instance.session_manager = session_manager
                cls._instance._clear_match_context_cache()
            if not cls._instance.is_running():
                cls._instance.start()
            return cls._instance

    @classmethod
    def consume_profile_updates(cls, session_manager=None):
        """Retourne les profils modifies par l'API locale depuis le dernier appel."""
        instance = cls._instance
        if not instance:
            return []
        if session_manager is not None and instance.session_manager is not session_manager:
            return []
        return instance.consume_pending_profile_updates()

    def start(self):
        """Lance un serveur local mono-thread sur un port ephemere."""
        self.httpd = HTTPServer((self.host, 0), _MetaSoftHandler)
        self.httpd.local_api = self
        self.thread = threading.Thread(
            target=self.httpd.serve_forever,
            name="enduraw-metasoft-local-api",
            daemon=True,
        )
        self.thread.start()
        return self

    def stop(self):
        """Arrete le serveur, utile pour les tests locaux."""
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
        if self.thread:
            self.thread.join(timeout=2)
        self.httpd = None
        self.thread = None

    def is_running(self):
        return bool(self.httpd and self.thread and self.thread.is_alive())

    @property
    def port(self):
        if not self.httpd:
            return None
        return self.httpd.server_address[1]

    def url_for_match(self, match_info):
        match_id = _match_id(
            match_info.get("profile_name", ""),
            match_info.get("xml_filename", ""),
        )
        return f"http://{self.host}:{self.port}/metasoft?match_id={match_id}&token={self.token}"

    def _record_profile_update(self, profile_name):
        with self._profile_update_lock:
            if profile_name not in self._profile_updates:
                self._profile_updates.append(profile_name)

    def _clear_match_context_cache(self):
        self._match_context_cache.clear()

    def consume_pending_profile_updates(self):
        """Consomme les profils modifies en attente pour une UI locale."""
        with self._profile_update_lock:
            updates = list(self._profile_updates)
            self._profile_updates.clear()
            return updates

    def route_get(self, path):
        if path == "/api/health":
            return {
                "ok": True,
                "app": "enduraw_testing_tool",
                "mode": "local",
                "api_version": 1,
            }
        if path == "/api/session":
            return self._session_payload()
        if path == "/api/matches":
            return {"ok": True, "matches": self._matches_payload()}

        parts = _path_parts(path)
        if len(parts) == 4 and parts[:2] == ["api", "matches"] and parts[3] == "analysis":
            return self._analysis_payload(parts[2])
        return _error("match_not_found", "Route API locale inconnue.", status=404)

    def route_post(self, path, payload):
        parts = _path_parts(path)
        if len(parts) != 5 or parts[:2] != ["api", "matches"]:
            return _error("match_not_found", "Route API locale inconnue.", status=404)

        match_id = parts[2]
        suffix = parts[3:]
        if suffix == ["markers", "officialize"]:
            return self._officialize_payload(match_id, payload)
        if suffix == ["profile", "report-preview"]:
            return self._report_preview_payload(match_id, payload)
        if suffix == ["profile", "report"]:
            return self._report_payload(match_id, payload)
        return _error("match_not_found", "Route API locale inconnue.", status=404)

    def static_dist(self):
        return Path(__file__).resolve().parents[2] / "local_ui" / "dist"

    def _session_payload(self):
        session = getattr(self.session_manager, "current_session", None)
        if not session:
            return _error("session_not_loaded", "Aucune session locale chargee.", status=409)
        return {
            "ok": True,
            "session": {
                "name": session.name,
                "date": session.date,
                "location": session.location,
            },
        }

    def _matches_payload(self):
        return [
            {
                "match_id": _match_id(match.profile_name, match.xml_filename),
                "profile_name": match.profile_name,
                "xml_filename": match.xml_filename,
                "exported": bool(match.exported),
            }
            for match in getattr(self.session_manager, "matches", [])
        ]

    def _analysis_payload(self, match_id):
        context = self._match_context(match_id)
        if not context["ok"]:
            return context
        warnings = _identity_warnings(context["analysis"].get("athlete", {}), context["profile"])
        return {
            "ok": True,
            "match": context["match"],
            "profile": _public_profile(context["profile"]),
            "analysis": _ui_analysis_payload(context["analysis"]),
            "warnings": warnings,
            "source_of_truth": {
                "metrics": "python.metasoft_analysis",
                "markers": "python.metasoft_markers",
                "export": "tkinter.export_button_json_valentin",
                "smoothing": "react_visual_only",
            },
        }

    def _officialize_payload(self, match_id, payload):
        context = self._match_context(match_id)
        if not context["ok"]:
            return context
        markers_result = self._officialize(context, payload)
        if not markers_result["ok"]:
            return markers_result
        return {
            "ok": True,
            "markers": markers_result["markers"],
            "source": "python.build_metasoft_marker",
            "warnings": _marker_warnings(markers_result["markers"]),
        }

    def _report_preview_payload(self, match_id, payload):
        context = self._match_context(match_id)
        if not context["ok"]:
            return context
        patch_result = self._patch_from_payload(context, payload)
        if not patch_result["ok"]:
            return patch_result
        conflicts = _patch_conflicts(context["profile"], patch_result["patch_result"])
        return {
            "ok": True,
            "status": "conflict" if conflicts else "ready",
            "patch": {} if conflicts else patch_result["patch_result"]["patch"],
            "conflicts": conflicts,
            "confirmed_markers": patch_result["markers"],
            "warnings": patch_result["warnings"],
        }

    def _report_payload(self, match_id, payload):
        context = self._match_context(match_id)
        if not context["ok"]:
            return context
        patch_result = self._patch_from_payload(context, payload)
        if not patch_result["ok"]:
            return patch_result

        conflicts = _patch_conflicts(context["profile"], patch_result["patch_result"])
        if conflicts and payload.get("conflict_policy") != "overwrite":
            return _error(
                "profile_conflict",
                "Conflits profil: confirmation overwrite requise.",
                status=409,
                details={"conflicts": conflicts},
            )

        patch = patch_result["patch_result"].get("patch", {})
        updated_paths = [".".join(path) for path, _value in _flatten_patch_values(patch)]
        profile = context["profile"]
        if updated_paths:
            profile = apply_metasoft_stress_patch(profile, patch_result["patch_result"])
            profile_name = self.session_manager.update_profile(context["match"]["profile_name"], profile)
            if not profile_name:
                return _error("profile_not_found", "Sauvegarde profil impossible.", status=404)
            self._record_profile_update(profile_name)
        else:
            profile_name = context["match"]["profile_name"]

        return {
            "ok": True,
            "profile_name": profile_name,
            "updated_paths": updated_paths,
            "confirmed_markers": patch_result["markers"],
            "warnings": patch_result["warnings"],
        }

    def _patch_from_payload(self, context, payload):
        markers_result = self._officialize(context, payload)
        if not markers_result["ok"]:
            return markers_result

        patch_results = [
            metasoft_marker_to_stress_patch(marker)
            for marker in markers_result["markers"].values()
        ]
        patch_result = _merge_patch_results(patch_results)
        if markers_result["markers"] and patch_result.get("status") != "ok":
            return _error(
                "marker_blocked",
                "Aucun marqueur MetaSoft reportable.",
                status=422,
                details={"markers": markers_result["markers"]},
            )
        updated_paths = [
            ".".join(path)
            for path, _value in _flatten_patch_values(patch_result.get("patch", {}))
        ]
        return {
            "ok": True,
            "markers": markers_result["markers"],
            "patch_result": patch_result,
            "updated_paths": updated_paths,
            "warnings": markers_result["warnings"] + patch_result.get("warnings", []),
        }

    def _officialize(self, context, payload):
        selections = payload.get("marker_selections", [])
        if not isinstance(selections, list):
            return _error(
                "invalid_marker_selection",
                "marker_selections doit etre une liste.",
                status=400,
            )

        markers = {}
        for selection in selections:
            marker = _marker_from_selection(context["analysis"].get("points", []), selection)
            if not marker["ok"]:
                return marker
            markers[marker["marker"]["name"]] = marker["marker"]
        return {"ok": True, "markers": markers, "warnings": _marker_warnings(markers)}

    def _match_context(self, match_id):
        session = getattr(self.session_manager, "current_session", None)
        if not session:
            return _error("session_not_loaded", "Aucune session locale chargee.", status=409)

        match = self._find_match(match_id)
        if not match:
            return _error("match_not_found", "Association profil/XML introuvable.", status=404)

        profile = self.session_manager.get_profile(match.profile_name)
        if not profile:
            return _error("profile_not_found", "Profil local introuvable.", status=404)

        xml_path = self.session_manager.get_xml_path(match.xml_filename)
        if not xml_path:
            return _error("xml_not_found", "XML local introuvable.", status=404)

        xml_file = Path(xml_path)
        try:
            xml_stat = xml_file.stat()
        except OSError as exc:
            return _error(
                "xml_not_found",
                f"XML local inaccessible: {exc}",
                status=404,
            )

        profile_mass = _profile_mass_kg(profile)
        cache_key = (
            id(session),
            getattr(session, "name", None),
            match_id,
            str(xml_file.resolve()),
            xml_stat.st_mtime_ns,
            xml_stat.st_size,
            profile_mass,
        )
        cached = self._match_context_cache.get(cache_key)
        if cached:
            xml_data = cached["xml_data"]
            analysis = cached["analysis"]
        else:
            try:
                xml_data = TCPXmlParser().parse_file(str(xml_file))
            except Exception as exc:
                return _error(
                    "xml_parse_failed",
                    f"Parsing XML MetaSoft impossible: {exc}",
                    status=422,
                )

            parsed = xml_data.get("metasoft_parsed", {})
            analysis = xml_data.get("metasoft_analysis", {})
            if _positive_number(parsed.get("athlete", {}).get("weight_kg")) is None:
                if profile_mass is not None:
                    # Source masse: profil local matche, seulement si le XML n'a
                    # aucun poids exploitable. Unite: kg.
                    analysis = build_metasoft_analysis(parsed, manual_mass_kg=profile_mass)
                    xml_data["metasoft_analysis"] = analysis
            # Cache memoire uniquement: cle fichier + session + masse fallback,
            # jamais de disque, pour ne pas masquer un XML modifie.
            self._match_context_cache = {cache_key: {"xml_data": xml_data, "analysis": analysis}}

        return {
            "ok": True,
            "match": {
                "match_id": _match_id(match.profile_name, match.xml_filename),
                "profile_name": match.profile_name,
                "xml_filename": match.xml_filename,
            },
            "profile": profile,
            "xml_data": xml_data,
            "analysis": analysis,
        }

    def _find_match(self, match_id):
        for match in getattr(self.session_manager, "matches", []):
            if _match_id(match.profile_name, match.xml_filename) == match_id:
                return match
        return None


class _MetaSoftHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        with _no_gc_in_server_thread():
            parsed = urlparse(self.path)
            if parsed.path.startswith("/api/"):
                if not self._valid_token():
                    self._send_json(_error("invalid_token", "Token local invalide.", status=403))
                    return
                self._send_json(self.server.local_api.route_get(parsed.path))
                return
            if parsed.path == "/metasoft":
                self._send_metasoft_page(parsed)
                return
            self._send_static(parsed.path)

    def do_POST(self):
        with _no_gc_in_server_thread():
            parsed = urlparse(self.path)
            if not parsed.path.startswith("/api/"):
                self._send_json(_error("match_not_found", "Route locale inconnue.", status=404))
                return
            if not self._valid_token():
                self._send_json(_error("invalid_token", "Token local invalide.", status=403))
                return

            payload = self._read_json()
            if not payload["ok"]:
                self._send_json(payload)
                return
            self._send_json(self.server.local_api.route_post(parsed.path, payload["data"]))

    def log_message(self, _format, *_args):
        return

    def _valid_token(self):
        return self.headers.get("X-Enduraw-Local-Token") == self.server.local_api.token

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length == 0:
            return {"ok": True, "data": {}}
        try:
            data = self.rfile.read(length).decode("utf-8")
            return {"ok": True, "data": json.loads(data)}
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return _error(
                "invalid_marker_selection",
                f"JSON de requete invalide: {exc}",
                status=400,
            )

    def _send_json(self, payload):
        status = payload.pop("_status", 200)
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _send_metasoft_page(self, parsed):
        token = parse_qs(parsed.query).get("token", [""])[0]
        if token != self.server.local_api.token:
            self._send_json(_error("invalid_token", "Token local invalide.", status=403))
            return

        dist = self.server.local_api.static_dist()
        index = dist / "index.html"
        if index.exists():
            self._send_file(index)
            return

        query = parse_qs(parsed.query)
        match_id = query.get("match_id", [""])[0]
        html = _placeholder_html(match_id, token).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)

    def _send_static(self, path):
        dist = self.server.local_api.static_dist()
        if not dist.exists():
            self._send_json(_error("match_not_found", "UI locale non construite.", status=404))
            return
        target = (dist / unquote(path).lstrip("/")).resolve()
        if dist.resolve() not in target.parents and target != dist.resolve():
            self._send_json(_error("match_not_found", "Chemin statique invalide.", status=404))
            return
        if target.is_dir():
            target = target / "index.html"
        self._send_file(target)

    def _send_file(self, path):
        if not path.exists() or not path.is_file():
            self._send_json(_error("match_not_found", "Fichier statique introuvable.", status=404))
            return
        content = path.read_bytes()
        self.send_response(200)
        self.send_header(
            "Content-Type",
            mimetypes.guess_type(str(path))[0] or "application/octet-stream",
        )
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def _match_id(profile_name, xml_filename):
    """ID local stable sans exposer de chemin disque."""
    raw = f"{Path(str(profile_name)).name}\0{Path(str(xml_filename)).name}"
    return sha256(raw.encode("utf-8")).hexdigest()[:12]


@contextmanager
def _no_gc_in_server_thread():
    """Evite de finaliser des objets Tk depuis le thread HTTP local.

    Tk/Tcl doit rester pilote par le main thread. Les gros payloads MetaSoft
    peuvent declencher le GC Python dans le thread HTTP; si un widget Tk mort
    est finalise a ce moment-la, macOS peut segfault dans libtcl. Le refcount
    Python continue de liberer les objets ordinaires; seul le GC cyclique est
    suspendu pendant la requete locale.
    """
    was_enabled = gc.isenabled()
    if was_enabled:
        gc.disable()
    try:
        yield
    finally:
        if was_enabled:
            gc.enable()


def _path_parts(path):
    return [unquote(part) for part in path.strip("/").split("/") if part]


def _marker_from_selection(points, selection):
    if not isinstance(selection, dict):
        return _error("invalid_marker_selection", "Selection marqueur invalide.", status=400)

    name = _normalise_marker_name(selection.get("name"))
    mode = selection.get("mode")
    if name not in VALID_MARKERS or mode not in {"point", "range"}:
        return _error("invalid_marker_selection", "Nom ou mode marqueur invalide.", status=400)

    if mode == "point":
        t_seconds = _number(selection.get("t_seconds"))
        if t_seconds is None:
            return _error("invalid_marker_selection", "Temps point manquant.", status=400)
        marker = build_metasoft_marker(points, name, t_seconds=t_seconds)
    else:
        start = _number(selection.get("window_start_seconds"))
        end = _number(selection.get("window_end_seconds"))
        if start is None or end is None:
            return _error("invalid_marker_selection", "Fenetre marqueur incomplete.", status=400)
        marker = build_metasoft_marker(
            points,
            name,
            window_start_seconds=start,
            window_end_seconds=end,
        )
    if marker.get("status") != "ok":
        return _error(
            "marker_blocked",
            "Marqueur MetaSoft bloque: selection officielle refusee.",
            status=422,
            details={"marker": marker},
        )
    return {"ok": True, "marker": marker}


def _merge_patch_results(patch_results):
    merged = {"status": "ok", "patch": {"stress_test_results": {}}, "warnings": []}
    for result in patch_results:
        if result.get("status") != "ok":
            merged["warnings"].extend(result.get("warnings", []))
            continue
        _deep_merge(
            merged["patch"]["stress_test_results"],
            result.get("patch", {}).get("stress_test_results", {}),
        )
        merged["warnings"].extend(result.get("warnings", []))
    if not merged["patch"]["stress_test_results"]:
        merged["status"] = "blocked"
    return merged


def _deep_merge(target, source):
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_merge(target[key], value)
        else:
            target[key] = deepcopy(value)


def _patch_conflicts(profile, patch_result):
    conflicts = []
    for path, incoming in _flatten_patch_values(patch_result.get("patch", {})):
        current = _read_path(profile, path)
        if _empty_value(current) or _same_value(current, incoming):
            continue
        conflicts.append({
            "path": ".".join(path),
            "current": current,
            "incoming": incoming,
        })
    return conflicts


def _flatten_patch_values(data, prefix=()):
    for key, value in data.items():
        path = (*prefix, key)
        if isinstance(value, dict):
            yield from _flatten_patch_values(value, path)
        else:
            yield path, value


def _read_path(data, path):
    current = data
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def _empty_value(value):
    return value is None or value == "" or value == {}


def _same_value(left, right):
    left_number = _number(left)
    right_number = _number(right)
    if left_number is not None and right_number is not None:
        return abs(left_number - right_number) < 1e-9
    return left == right


def _public_profile(profile):
    return {
        "identity": deepcopy(profile.get("identity", {})),
        "body_composition": deepcopy(profile.get("body_composition", {})),
        "stress_test_results": deepcopy(profile.get("stress_test_results", {})),
    }


def _ui_analysis_payload(analysis):
    """Retourne l'analyse React sans colonnes brutes point-par-point.

    Source complete: `context["analysis"]`, conservee en memoire pour les
    marqueurs Python, l'export JSON et le sidecar audit. Le payload UI ne retire
    que `raw` et `value_sources`, inutiles au rendu React actuel.
    """
    ui_analysis = dict(analysis)
    ui_analysis["points"] = [
        {
            key: value
            for key, value in point.items()
            if key not in {"raw", "value_sources"}
        }
        for point in analysis.get("points", [])
    ]
    return ui_analysis


def _identity_warnings(xml_athlete, profile):
    xml_name = _identity_name(xml_athlete)
    profile_name = _profile_name(profile)
    if not xml_name or not profile_name:
        return []
    if _clean_identity(xml_name) == _clean_identity(profile_name):
        return []
    return [{
        "code": "identity_mismatch",
        "message": "Identite XML differente du profil local; export non bloque.",
        "blocking": False,
        "xml_athlete_name": xml_name,
        "profile_athlete_name": profile_name,
    }]


def _identity_name(identity):
    return (
        identity.get("athlete_name")
        or f"{identity.get('last_name', '')} {identity.get('first_name', '')}".strip()
    )


def _profile_name(profile):
    return _identity_name(profile.get("identity", {}) or {})


def _clean_identity(value):
    normalized = unicodedata.normalize("NFKD", str(value).strip().lower())
    ascii_value = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(ascii_value.split())


def _profile_mass_kg(profile):
    return _positive_number((profile.get("body_composition", {}) or {}).get("current_weight"))


def _positive_number(value):
    number = _number(value)
    return number if number is not None and number > 0 else None


def _number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if isfinite(number) else None
    if isinstance(value, str):
        try:
            number = float(value.replace(",", ".").strip())
            return number if isfinite(number) else None
        except ValueError:
            return None
    return None


def _normalise_marker_name(name):
    normalized = str(name or "").strip().replace(" ", "_").replace("-", "_")
    if normalized.lower() == "vo2max":
        return "VO2_max"
    for marker_name in VALID_MARKERS:
        if marker_name.lower() == normalized.lower():
            return marker_name
    return normalized


def _marker_warnings(markers):
    warnings = []
    for name, marker in markers.items():
        for warning in marker.get("warnings", []):
            copied = deepcopy(warning)
            copied.setdefault("marker", name)
            warnings.append(copied)
    return warnings


def _placeholder_html(match_id, token):
    # Placeholder volontaire: Lot 1 verifie l'ouverture locale avant React.
    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Enduraw MetaSoft local</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 32px; color: #132018; }}
    code {{ background: #edf2ef; padding: 2px 5px; border-radius: 4px; }}
    button {{ padding: 8px 12px; }}
    pre {{ white-space: pre-wrap; background: #f6f8f7; padding: 12px; }}
  </style>
</head>
<body>
  <h1>MetaSoft local</h1>
  <p>Placeholder Lot 1. Match: <code>{match_id}</code></p>
  <button id="health">Tester /api/health</button>
  <pre id="result"></pre>
  <script>
    window.ENDURAW_LOCAL_BOOTSTRAP = {{ matchId: {json.dumps(match_id)}, token: {json.dumps(token)} }};
    document.getElementById("health").onclick = async () => {{
      const response = await fetch("/api/health", {{
        headers: {{ "X-Enduraw-Local-Token": window.ENDURAW_LOCAL_BOOTSTRAP.token }}
      }});
      document.getElementById("result").textContent =
        JSON.stringify(await response.json(), null, 2);
    }};
  </script>
</body>
</html>"""


def _error(code, message, status=400, details=None, extra=None):
    payload = {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "blocking": True,
            "details": details or {},
        },
        "warnings": [],
        "_status": status,
    }
    if extra:
        payload.update(extra)
    return payload
