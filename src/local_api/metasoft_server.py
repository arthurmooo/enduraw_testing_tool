"""Serveur HTTP local MetaSoft pour l'UI navigateur.

Le serveur expose uniquement la session locale deja chargee par l'app Tkinter.
Source: profils/XML/matches via `SessionManager`. Transformations officielles:
parser MetaSoft, analyse Python, marqueurs Python, EC manuelle validee UI et
report profil. Aucune ecriture BDD n'existe dans ce module.
"""
import json
import mimetypes
import secrets
import threading
import gc
from contextlib import contextmanager
from copy import deepcopy
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, HTTPServer
from math import isfinite
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from core.metasoft_analysis import build_manual_running_economy, build_metasoft_analysis
from core.metasoft_identity import metasoft_identity_check
from core.app_paths import resource_root
from core.metasoft_markers import (
    apply_metasoft_stress_patch,
    build_metasoft_marker,
    build_metasoft_marker_deletion,
    metasoft_unproven_profile_markers,
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
        if len(parts) < 4 or parts[:2] != ["api", "matches"]:
            return _error("match_not_found", "Route API locale inconnue.", status=404)

        match_id = parts[2]
        suffix = parts[3:]
        if suffix == ["markers", "officialize"]:
            return self._officialize_payload(match_id, payload)
        if suffix == ["running-economy", "manual"]:
            return self._manual_running_economy_payload(match_id, payload)
        if suffix == ["draft"]:
            return self._draft_payload(match_id, payload)
        if suffix == ["profile", "report-preview"]:
            return self._report_preview_payload(match_id, payload)
        if suffix == ["profile", "report"]:
            return self._report_payload(match_id, payload)
        return _error("match_not_found", "Route API locale inconnue.", status=404)

    def static_dist(self):
        return resource_root() / "local_ui" / "dist"

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
        identity = metasoft_identity_check(
            context["analysis"].get("athlete", {}),
            context["profile"],
        )
        warnings = [] if identity["ok"] else [_warning_from_check(identity)]
        provenance = self.session_manager.validate_metasoft_report(
            context["match_info"],
            context["profile"],
        )
        markers = provenance["markers"] if provenance["valid"] else {}
        provenance_warning = _metasoft_provenance_warning(
            provenance,
            context["match_info"],
            context["profile"],
        )
        if provenance_warning:
            warnings.append(provenance_warning)
        manual_economy_state = self.session_manager.manual_running_economy_state(
            match_id,
            context["match_info"],
        )
        if manual_economy_state["status"] in {"stale", "corrupt"}:
            warnings.append(_manual_running_economy_warning(manual_economy_state))
        draft_state = self.session_manager.metasoft_draft_state(
            match_id,
            context["match_info"],
        )
        if draft_state["status"] in {"stale", "corrupt"}:
            warnings.append({
                "code": f"metasoft_draft_{draft_state['status']}",
                "message": "Brouillon local ignore car sa source profil/XML a change.",
                "blocking": False,
            })
        confirmed_markers = {
            name: marker
            for name, marker in markers.items()
            if isinstance(marker, dict) and marker.get("action") != "delete"
        }
        deleted_markers = [
            name
            for name, marker in markers.items()
            if isinstance(marker, dict) and marker.get("action") == "delete"
        ]
        return {
            "ok": True,
            "match": context["match"],
            "profile": _public_profile(context["profile"]),
            "analysis": _ui_analysis_payload(context["analysis"]),
            "manual_running_economy": (
                manual_economy_state["data"]
                if manual_economy_state["status"] == "ok"
                else None
            ),
            "metasoft_draft": draft_state["data"] if draft_state["status"] == "ok" else None,
            "confirmed_markers": confirmed_markers,
            "deleted_markers": deleted_markers,
            "warnings": warnings,
            "source_of_truth": {
                "metrics": "python.metasoft_analysis",
                "markers": "python.metasoft_markers",
                "running_economy_manual": "python.metasoft_analysis.manual_running_economy",
                "lactate": "python.metasoft_server.validated_profile_patch",
                "export": "tkinter.export_button_json_valentin",
                "smoothing": "react_visual_only",
            },
        }

    def _draft_payload(self, match_id, payload):
        """Persiste un brouillon borne; aucun calcul ni profil officiel n'est modifie."""
        context = self._match_context(match_id)
        if not context["ok"]:
            return context
        if not isinstance(payload, dict):
            return _error("invalid_metasoft_draft", "Brouillon MetaSoft invalide.", status=400)
        if payload.get("clear") is True:
            self.session_manager.clear_metasoft_draft(match_id)
            return {"ok": True, "cleared": True}
        allowed_keys = {
            "marker_selections",
            "manual_running_economy_selections",
            "manual_running_economy_stage_selections",
            "manual_running_economy_rest_selection",
            "lactate_test",
        }
        if set(payload) - allowed_keys:
            return _error("invalid_metasoft_draft", "Champs brouillon inconnus.", status=400)
        for key in (
            "marker_selections",
            "manual_running_economy_selections",
            "manual_running_economy_stage_selections",
        ):
            value = payload.get(key, [])
            if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
                return _error("invalid_metasoft_draft", f"{key} invalide.", status=400)
        for key in ("manual_running_economy_rest_selection", "lactate_test"):
            value = payload.get(key)
            if value is not None and not isinstance(value, dict):
                return _error("invalid_metasoft_draft", f"{key} invalide.", status=400)
        if len(json.dumps(payload, ensure_ascii=False)) > 2_000_000:
            return _error("invalid_metasoft_draft", "Brouillon MetaSoft trop volumineux.", status=413)
        try:
            self.session_manager.save_metasoft_draft(
                match_id,
                context["match_info"],
                payload,
            )
        except (OSError, ValueError) as exc:
            return _error("invalid_metasoft_draft", str(exc), status=409)
        return {"ok": True, "saved": True}

    def _manual_running_economy_payload(self, match_id, payload):
        context = self._match_context(match_id)
        if not context["ok"]:
            return context
        if not isinstance(payload, dict):
            return _error(
                "invalid_running_economy_manual",
                "Payload EC manuelle invalide.",
                status=400,
            )
        selections = _manual_running_economy_selections(payload)
        if selections is None:
            return _error(
                "invalid_running_economy_manual",
                "selections doit etre une liste.",
                status=400,
            )
        stage_selections = _manual_running_economy_stage_selections(payload)
        if stage_selections is None:
            return _error(
                "invalid_running_economy_manual",
                "stage_selections doit etre une liste valide.",
                status=400,
            )
        if selections == [] and not stage_selections:
            self.session_manager.clear_manual_running_economy(match_id)
            return {"ok": True, "manual_running_economy": None}
        data = self._build_manual_running_economy(context, match_id, selections, payload)
        if not data["ok"]:
            return data
        data = data["manual_running_economy"]
        if stage_selections:
            data["stage_selections"] = stage_selections
        try:
            fingerprint = self.session_manager.build_manual_running_economy_fingerprint(
                context["match_info"],
                data,
                context["profile"],
            )
            if not fingerprint:
                return _error(
                    "match_fingerprint_unavailable",
                    "Fingerprint local EC/XML indisponible.",
                    status=409,
                )
            self.session_manager.save_manual_running_economy(match_id, data, fingerprint)
        except ValueError as exc:
            return _error(
                "manual_running_economy_corrupt",
                str(exc),
                status=409,
            )
        return {"ok": True, "manual_running_economy": data}

    def _build_manual_running_economy(self, context, match_id, selections, payload, markers=None):
        """Calcule l'EC officielle depuis l'analyse Python, sans valeurs React."""
        rest_selection = payload.get("manual_running_economy_rest_selection")
        if rest_selection is not None and not isinstance(rest_selection, dict):
            return _error(
                "invalid_running_economy_manual",
                "Selection de repos EC invalide.",
                status=400,
            )
        vo2max_result = self._manual_running_economy_vo2max(context, payload, markers)
        if not vo2max_result["ok"]:
            return vo2max_result
        try:
            data = build_manual_running_economy(
                context["analysis"],
                selections,
                profile_vo2max_ml_kg_min=vo2max_result["value"],
                vo2max_source=vo2max_result["source"],
                rest_selection=rest_selection,
            )
        except ValueError as exc:
            return _error(
                "invalid_running_economy_manual",
                str(exc),
                status=400,
            )
        data["match_id"] = match_id
        return {"ok": True, "manual_running_economy": data}

    def _manual_running_economy_vo2max(self, context, payload, markers=None):
        if "marker_selections" in payload:
            if markers is None:
                markers_result = self._officialize(context, payload)
                if not markers_result["ok"]:
                    return markers_result
                markers = markers_result["markers"]
            marker = markers.get("VO2_max")
            if marker is not None:
                value = _positive_number(marker.get("values", {}).get("vo2_ml_kg_min"))
                return {"ok": True, "value": value, "source": "metasoft_marker.vo2_max"}
        return {
            "ok": True,
            "value": _positive_number(
                context["profile"].get("stress_test_results", {}).get("measured_vo2max")
            ),
            "source": "profile.stress_test_results.measured_vo2max",
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
        identity_error = _identity_error(context)
        if identity_error:
            return identity_error
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
        identity_error = _identity_error(context)
        if identity_error:
            return identity_error
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

        manual_result = self._manual_running_economy_for_report(context, match_id, payload, patch_result)
        if not manual_result["ok"]:
            return manual_result

        previous_provenance = self.session_manager.validate_metasoft_report(
            context["match_info"],
            context["profile"],
        )
        canonical_markers = (
            deepcopy(previous_provenance["markers"])
            if previous_provenance.get("markers")
            and (
                previous_provenance["valid"]
                or str(previous_provenance.get("reason", "")).startswith(
                    "manual_running_economy_"
                )
            )
            else {}
        )
        canonical_markers.update(deepcopy(patch_result["markers"]))
        try:
            manual_state = self.session_manager.manual_running_economy_state(
                match_id,
                context["match_info"],
            )
            manual_snapshot = self.session_manager.snapshot_manual_running_economy_entry(
                match_id
            )
        except ValueError as exc:
            return _error(
                "manual_running_economy_corrupt",
                f"Report refuse: sidecar EC corrompu: {exc}",
                status=409,
            )

        updated_paths = _patch_updated_paths(context["profile"], patch_result["patch_result"])
        original_profile = deepcopy(context["profile"])
        profile = apply_metasoft_stress_patch(
            original_profile,
            patch_result["patch_result"],
        ) if updated_paths else original_profile
        profile_name = context["match"]["profile_name"]
        manual_running_economy = manual_result.get("manual_running_economy")
        if not manual_result.get("present"):
            if manual_state["status"] in {"stale", "corrupt"}:
                return _error(
                    f"manual_running_economy_{manual_state['status']}",
                    "Report refuse: EC perimee/corrompue non remplacee.",
                    status=409,
                )
            manual_running_economy = (
                manual_state["data"] if manual_state["status"] == "ok" else None
            )
        final_ec_fingerprint = None
        if manual_running_economy is not None:
            final_ec_fingerprint = self.session_manager.build_manual_running_economy_fingerprint(
                context["match_info"],
                manual_running_economy,
                profile,
            )
            if not final_ec_fingerprint:
                return _error(
                    "match_fingerprint_unavailable",
                    "Fingerprint local EC/XML indisponible.",
                    status=409,
                )

        previous_report = deepcopy(context["match_info"].metasoft_report)
        try:
            if updated_paths:
                saved_name = self.session_manager.update_profile(profile_name, profile)
                if not saved_name:
                    raise ValueError("Sauvegarde profil impossible")
                profile_name = saved_name
            if manual_result.get("present"):
                if manual_running_economy is None:
                    self.session_manager.clear_manual_running_economy(match_id)
                else:
                    self.session_manager.save_manual_running_economy(
                        match_id,
                        manual_running_economy,
                        final_ec_fingerprint,
                    )
            self.session_manager.record_metasoft_report(
                context["match_info"],
                profile,
                canonical_markers,
                manual_running_economy,
            )
            self.session_manager.clear_metasoft_draft(match_id)
        except Exception as exc:
            rollback_errors = []
            try:
                if updated_paths:
                    self.session_manager.update_profile(profile_name, original_profile)
            except Exception as rollback_exc:
                rollback_errors.append(f"profil: {rollback_exc}")
            try:
                self.session_manager.restore_manual_running_economy_entry(
                    match_id,
                    manual_snapshot,
                )
            except Exception as rollback_exc:
                rollback_errors.append(f"EC: {rollback_exc}")
            try:
                self.session_manager.restore_metasoft_report(
                    context["match_info"],
                    previous_report,
                )
            except Exception as rollback_exc:
                rollback_errors.append(f"provenance: {rollback_exc}")
            return _error(
                "metasoft_report_rollback_failed" if rollback_errors else "metasoft_report_failed",
                (
                    f"Report annule et restaure: {exc}"
                    if not rollback_errors
                    else f"Report echoue ({exc}); rollback incomplet: {', '.join(rollback_errors)}"
                ),
                status=500,
            )

        # Le profil Python affiche aussi l'EC du sidecar: un report EC seul doit
        # donc déclencher son rafraîchissement même si le JSON profil est identique.
        self._record_profile_update(profile_name)

        return {
            "ok": True,
            "profile_name": profile_name,
            "updated_paths": updated_paths,
            "confirmed_markers": patch_result["markers"],
            "manual_running_economy": manual_running_economy,
            "warnings": patch_result["warnings"],
        }

    def _manual_running_economy_for_report(self, context, match_id, payload, patch_result):
        if "manual_running_economy_selections" not in payload:
            return {"ok": True, "present": False, "manual_running_economy": None}
        selections = _manual_running_economy_selections(
            payload,
            key="manual_running_economy_selections",
        )
        stage_selections = _manual_running_economy_stage_selections(payload)
        if selections is None or stage_selections is None:
            return _error(
                "invalid_running_economy_manual",
                "Payload EC manuelle invalide.",
                status=400,
            )
        data = self._build_manual_running_economy(
            context,
            match_id,
            selections,
            payload,
            markers=patch_result["markers"],
        )
        if not data["ok"]:
            return data
        manual_running_economy = data["manual_running_economy"]
        if stage_selections:
            manual_running_economy["stage_selections"] = stage_selections
        return {
            "ok": True,
            "present": True,
            "manual_running_economy": manual_running_economy,
        }

    def _patch_from_payload(self, context, payload):
        markers_result = self._officialize(context, payload)
        if not markers_result["ok"]:
            return markers_result

        patch_results = [
            metasoft_marker_to_stress_patch(marker)
            for marker in markers_result["markers"].values()
        ]
        lactate_result = _lactate_patch(payload)
        if not lactate_result["ok"]:
            return lactate_result
        if lactate_result["present"]:
            patch_results.append(lactate_result["patch_result"])
        patch_result = _merge_patch_results(patch_results)
        if markers_result["markers"] and patch_result.get("status") != "ok":
            return _error(
                "marker_blocked",
                "Report refuse: un marqueur MetaSoft est incomplet ou non reportable.",
                status=422,
                details={
                    "markers": markers_result["markers"],
                    "warnings": patch_result.get("warnings", []),
                },
            )
        updated_paths = _patch_updated_paths(context["profile"], patch_result)
        return {
            "ok": True,
            "markers": markers_result["markers"],
            "patch_result": patch_result,
            "updated_paths": updated_paths,
            "warnings": markers_result["warnings"] + patch_result.get("warnings", []),
        }

    def _officialize(self, context, payload):
        if not isinstance(payload, dict):
            return _error(
                "invalid_marker_selection",
                "Payload marqueurs invalide.",
                status=400,
            )
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
            name = marker["marker"]["name"]
            if name in markers:
                return _error(
                    "duplicate_marker_selection",
                    f"Marqueur {name} present plusieurs fois dans le report.",
                    status=400,
                    details={"marker": name},
                )
            markers[name] = marker["marker"]
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

        if not self.session_manager.build_metasoft_source_fingerprint(match):
            return _error(
                "match_fingerprint_unavailable",
                "Fingerprint local profil/XML indisponible.",
                status=409,
            )

        return {
            "ok": True,
            "match": {
                "match_id": _match_id(match.profile_name, match.xml_filename),
                "profile_name": match.profile_name,
                "xml_filename": match.xml_filename,
            },
            "match_info": match,
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


def _manual_running_economy_selections(payload, key="selections"):
    """Extrait uniquement les champs officiels de selection EC manuelle."""
    selections = payload.get(key)
    if key == "selections" and selections is None and isinstance(payload.get("rows"), list):
        selections = payload.get("rows")
    if not isinstance(selections, list):
        return None
    result = []
    for item in selections:
        if not isinstance(item, dict):
            return None
        result.append({
            "stage_index": item.get("stage_index"),
            "start_seconds": item.get("start_seconds"),
            "end_seconds": item.get("end_seconds"),
            "exclusions": item.get("exclusions", []),
            "source": item.get("source", "detected"),
        })
    return result


def _manual_running_economy_stage_selections(payload):
    """Extrait la metadata UI locale qui memorise les paliers EC ecartes."""
    if "stage_selections" in payload:
        selections = payload.get("stage_selections")
    elif "manual_running_economy_stage_selections" in payload:
        selections = payload.get("manual_running_economy_stage_selections")
    else:
        return []
    if not isinstance(selections, list):
        return None
    result = []
    for item in selections:
        if not isinstance(item, dict):
            return None
        stage_index = _integer(item.get("stage_index"))
        enabled = item.get("enabled")
        if stage_index is None or not isinstance(enabled, bool):
            return None
        result.append({"stage_index": stage_index, "enabled": enabled})
    return result


def _lactate_patch(payload):
    """Valide le protocole lactate independant avant ecriture profil."""
    if "lactate_test" not in payload:
        return {"ok": True, "present": False}
    data = payload.get("lactate_test")
    if not isinstance(data, dict) or not isinstance(data.get("active"), bool):
        return _error("invalid_lactate_test", "Test lactate invalide.", status=400)
    if not data["active"]:
        return {
            "ok": True,
            "present": True,
            "patch_result": {
                "status": "ok",
                "patch": {"stress_test_results": {"lactate_profile": [], "lactate_thresholds": {}}},
                "delete_paths": [],
                "warnings": [],
            },
        }
    measurements = data.get("measurements")
    if not isinstance(measurements, list) or len(measurements) < 2:
        return _error("invalid_lactate_test", "Mesures lactate incompletes.", status=400)
    normalised = []
    allowed_types = {"rest_before", "post_warmup", "stage", "recovery", "rest_after"}
    for index, item in enumerate(measurements):
        if not isinstance(item, dict) or item.get("type") not in allowed_types:
            return _error("invalid_lactate_test", "Ligne lactate invalide.", status=400)
        enabled = item.get("enabled", True)
        if not isinstance(enabled, bool):
            return _error("invalid_lactate_test", "Statut de mesure lactate invalide.", status=400)
        speed = _number(item.get("speed"))
        lactate = _number(item.get("lactate_mmol_l"))
        if speed is not None and not 0 <= speed <= 40:
            return _error("invalid_lactate_test", "Vitesse ou lactate hors bornes.", status=400)
        if lactate is not None and not 0 <= lactate <= 30:
            return _error("invalid_lactate_test", "Vitesse ou lactate hors bornes.", status=400)
        if enabled and (speed is None or lactate is None):
            return _error(
                "invalid_lactate_test",
                "Chaque mesure lactate incluse doit avoir une vitesse et une valeur.",
                status=400,
            )
        if item["type"] == "stage" and speed is not None and speed <= 0:
            return _error("invalid_lactate_test", "Une vitesse de palier doit etre positive.", status=400)
        measurement = {
            "type": item["type"],
            "order": index,
            "enabled": enabled,
            "speed": round(speed, 3) if speed is not None else None,
            "lactate_mmol_l": round(lactate, 3) if lactate is not None else None,
        }
        source = item.get("source")
        if source is not None and source not in {"detected", "manual"}:
            return _error("invalid_lactate_test", "Source de mesure lactate invalide.", status=400)
        for key in ("label", "phase", "source"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                if len(value) > 120:
                    return _error("invalid_lactate_test", "Libelle de mesure lactate trop long.", status=400)
                measurement[key] = value.strip()
        stage_index = _integer(item.get("stage_index"))
        if item.get("stage_index") is not None and (stage_index is None or stage_index < 1):
            return _error("invalid_lactate_test", "Index de palier lactate invalide.", status=400)
        if stage_index is not None:
            measurement["stage_index"] = stage_index
        for key, maximum in (("time_seconds", 100_000), ("delay_minutes", 180)):
            value = _number(item.get(key))
            if value is not None:
                if not 0 <= value <= maximum:
                    return _error("invalid_lactate_test", "Temps de mesure lactate invalide.", status=400)
                measurement[key] = round(value, 3)
        normalised.append(measurement)
    if normalised[0]["type"] != "rest_before":
        return _error("invalid_lactate_test", "Le protocole doit commencer par une mesure de repos.", status=400)
    included = [item for item in normalised if item["enabled"]]
    if len(included) < 2 or not any(item["type"] == "stage" for item in included):
        return _error("invalid_lactate_test", "Au moins un palier lactate doit etre inclus.", status=400)
    thresholds = data.get("thresholds", {})
    if not isinstance(thresholds, dict):
        return _error("invalid_lactate_test", "Seuils lactate invalides.", status=400)
    resolved_thresholds = {}
    for name in ("sl1", "sl2"):
        value = thresholds.get(name)
        if value is None:
            continue
        index = _integer(value)
        if index is None or index < 0 or index >= len(normalised):
            return _error("invalid_lactate_test", f"{name.upper()} lactate invalide.", status=400)
        if normalised[index]["type"] != "stage" or not normalised[index]["enabled"]:
            return _error("invalid_lactate_test", f"{name.upper()} doit viser un palier.", status=400)
        resolved_thresholds[name] = {
            "measurement_index": index,
            **deepcopy(normalised[index]),
        }
    return {
        "ok": True,
        "present": True,
        "patch_result": {
            "status": "ok",
            "patch": {"stress_test_results": {
                "lactate_profile": normalised,
                "lactate_thresholds": resolved_thresholds,
            }},
            "delete_paths": [],
            "warnings": [],
        },
    }


def _marker_from_selection(points, selection):
    if not isinstance(selection, dict):
        return _error("invalid_marker_selection", "Selection marqueur invalide.", status=400)

    name = _normalise_marker_name(selection.get("name"))
    action = selection.get("action", "upsert")
    if name not in VALID_MARKERS or action not in {"upsert", "delete"}:
        return _error("invalid_marker_selection", "Nom ou action marqueur invalide.", status=400)
    if action == "delete":
        return {"ok": True, "marker": build_metasoft_marker_deletion(name)}

    mode = selection.get("mode")
    if mode not in {"point", "range", "previous"}:
        return _error("invalid_marker_selection", "Mode marqueur invalide.", status=400)

    if mode == "point":
        t_seconds = _number(selection.get("t_seconds"))
        if t_seconds is None:
            return _error("invalid_marker_selection", "Temps point manquant.", status=400)
        marker = build_metasoft_marker(points, name, t_seconds=t_seconds)
    elif mode == "previous":
        t_seconds = _number(selection.get("t_seconds"))
        start = _number(selection.get("window_start_seconds"))
        end = _number(selection.get("window_end_seconds", t_seconds))
        if (
            t_seconds is None
            or start is None
            or end is None
            or start < 0
            or start > t_seconds
            or end != t_seconds
        ):
            return _error("invalid_marker_selection", "Fenetre precedente incomplete.", status=400)
        # Mode precedent: l'UI garde le temps clique, l'officiel moyenne la
        # fenetre brute inclusive [t-X, t] sans lire les valeurs preview React.
        marker = build_metasoft_marker(
            points,
            name,
            window_start_seconds=start,
            window_end_seconds=t_seconds,
        )
        marker.update({
            "mode": "previous",
            "t_seconds": t_seconds,
            "selection_time_seconds": t_seconds,
        })
    else:
        start = _number(selection.get("window_start_seconds"))
        end = _number(selection.get("window_end_seconds"))
        default_time = (
            (start + end) / 2
            if start is not None and end is not None
            else None
        )
        selection_time = _number(selection.get("t_seconds", default_time))
        if (
            start is None
            or end is None
            or selection_time is None
            or selection_time < start
            or selection_time > end
        ):
            return _error("invalid_marker_selection", "Fenetre marqueur incomplete.", status=400)
        marker = build_metasoft_marker(
            points,
            name,
            window_start_seconds=start,
            window_end_seconds=end,
        )
        marker.update({
            "t_seconds": selection_time,
            "selection_time_seconds": selection_time,
        })
    if marker.get("status") != "ok":
        return _error(
            "marker_blocked",
            "Marqueur MetaSoft bloque: selection officielle refusee.",
            status=422,
            details={"marker": marker},
        )
    return {"ok": True, "marker": marker}


def _merge_patch_results(patch_results):
    merged = {
        "status": "ok",
        "patch": {"stress_test_results": {}},
        "delete_paths": [],
        "warnings": [],
    }
    for result in patch_results:
        if result.get("status") != "ok":
            merged["status"] = "blocked"
            merged["warnings"].extend(result.get("warnings", []))
            continue
        _deep_merge(
            merged["patch"]["stress_test_results"],
            result.get("patch", {}).get("stress_test_results", {}),
        )
        merged["delete_paths"].extend(deepcopy(result.get("delete_paths", [])))
        merged["warnings"].extend(result.get("warnings", []))
    if (
        patch_results
        and not merged["patch"]["stress_test_results"]
        and not merged["delete_paths"]
    ):
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
    for path in patch_result.get("delete_paths", []):
        current = _read_path(profile, path)
        if _empty_value(current):
            continue
        conflicts.append({
            "path": ".".join(path),
            "current": current,
            "incoming": None,
        })
    return conflicts


def _patch_updated_paths(profile, patch_result):
    paths = [
        ".".join(path)
        for path, _value in _flatten_patch_values(patch_result.get("patch", {}))
    ]
    paths.extend(
        ".".join(path)
        for path in patch_result.get("delete_paths", [])
        if not _empty_value(_read_path(profile, path))
    )
    return paths


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


def _identity_error(context):
    check = metasoft_identity_check(
        context["analysis"].get("athlete", {}),
        context["profile"],
    )
    if check["ok"]:
        return None
    details = {key: value for key, value in check.items() if key not in {"ok", "message"}}
    return _error(check["code"], check["message"], status=409, details=details)


def _warning_from_check(check):
    return {key: value for key, value in check.items() if key != "ok"}


def _metasoft_provenance_warning(provenance, match, profile):
    if provenance["valid"]:
        unproven = metasoft_unproven_profile_markers(profile, provenance["markers"])
        if not unproven:
            return None
        return {
            "code": "marker_provenance_incomplete",
            "message": "Valeurs marqueurs profil sans report MetaSoft prouve.",
            "blocking": True,
            "markers": unproven,
        }
    unproven = metasoft_unproven_profile_markers(profile, {})
    if provenance["reason"] == "missing" and not unproven:
        return None
    code = (
        "marker_provenance_missing"
        if provenance["reason"] == "missing"
        else "marker_provenance_stale"
    )
    return {
        "code": code,
        "message": "Provenance marqueurs MetaSoft absente ou perimee; export bloque.",
        "blocking": True,
        "reason": provenance["reason"],
        "markers": unproven,
        "profile_name": match.profile_name,
        "xml_filename": match.xml_filename,
    }


def _manual_running_economy_warning(state):
    return {
        "code": f"manual_running_economy_{state['status']}",
        "message": "EC manuelle perimee ou corrompue: nouveau report requis avant export.",
        "blocking": True,
        "reason": state.get("reason"),
    }


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


def _integer(value):
    number = _number(value)
    if number is None or number != int(number):
        return None
    return int(number)


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
