"""Fenetre locale de lecture des analyses MetaSoft.

Source: profil et XML d'une association de session locale. Le XML est parse
une seule fois via `TCPXmlParser`; si la masse manque dans le XML, l'analyse
est recalculee avec le poids du profil local. Les graphes affichent les series
normalisees et l'EC deja calculee, avec lissage strictement visuel: aucune
valeur lissee n'est reportee au profil ou a l'export JSON.
"""
import unicodedata
from copy import deepcopy
from datetime import datetime
from tkinter import messagebox

import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

try:
    from config import APP_VERSION
    from core.data_transformer import DataTransformer
    from core.metasoft_analysis import build_metasoft_analysis
    from core.metasoft_audit_export import (
        build_metasoft_audit_export,
        metasoft_audit_filename,
    )
    from core.metasoft_markers import (
        apply_metasoft_stress_patch,
        build_metasoft_marker,
        metasoft_marker_to_stress_patch,
    )
    from ui.metasoft_graphs import (
        GRAPH_CONFIGS,
        MARKER_CONFIGS,
        build_graph_render_data,
        clamp_time_range,
        click_x_to_time_seconds,
    )
    from utils.xml_parser import TCPXmlParser
except ImportError:  # pragma: no cover - utile pour imports depuis la racine du repo
    from src.config import APP_VERSION
    from src.core.data_transformer import DataTransformer
    from src.core.metasoft_analysis import build_metasoft_analysis
    from src.core.metasoft_audit_export import (
        build_metasoft_audit_export,
        metasoft_audit_filename,
    )
    from src.core.metasoft_markers import (
        apply_metasoft_stress_patch,
        build_metasoft_marker,
        metasoft_marker_to_stress_patch,
    )
    from src.ui.metasoft_graphs import (
        GRAPH_CONFIGS,
        MARKER_CONFIGS,
        build_graph_render_data,
        clamp_time_range,
        click_x_to_time_seconds,
    )
    from src.utils.xml_parser import TCPXmlParser


SMOOTH_OPTIONS_SECONDS = (0, 15, 30, 60, 120, 240)
MARKER_UI_LABELS = ("SV1", "SV2", "VO2max", "VMA")
DEFAULT_MARKER_WINDOW_SECONDS = 240

PHASE_COLORS = {
    "Repos": "#334155",
    "Echauffement": "#0f766e",
    "Exercice": "#7c2d12",
    "Retablissement": "#3730a3",
}


class MetaSoftAnalysisWindow(ctk.CTkToplevel):
    """Fenetre d'analyse MetaSoft pour une association profil/XML locale."""

    def __init__(self, master, session_manager, match_info):
        super().__init__(master)
        self.session_manager = session_manager
        self.match_info = match_info
        self.profile_name = match_info.get("profile_name", "")
        self.xml_filename = match_info.get("xml_filename", "")
        self.parser = TCPXmlParser()

        self.profile = {}
        self.xml_data = {}
        self.analysis = {}
        self.smooth_seconds = 0
        self.active_graph_id = GRAPH_CONFIGS[0]["id"]
        self.graph_buttons = {}
        self.canvas = None
        self.toolbar = None
        self.figure = None
        self.home_limits = []
        self.markers = {}
        self.last_click_time = None

        self.title(f"MetaSoft - {self.profile_name} / {self.xml_filename}")
        self.geometry("1280x820")
        self.minsize(1040, 680)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        self._build_shell()
        self.after(50, self._load_match)

    def _build_shell(self):
        self.header = ctk.CTkFrame(self)
        self.header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        self.header.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(
            self.header,
            text="Chargement MetaSoft...",
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w",
        )
        self.title_label.grid(row=0, column=0, padx=10, pady=(8, 2), sticky="ew")

        self.meta_label = ctk.CTkLabel(self.header, text="", anchor="w", text_color="gray")
        self.meta_label.grid(row=1, column=0, padx=10, pady=(0, 8), sticky="ew")

        self.warning_label = ctk.CTkLabel(
            self,
            text="",
            anchor="w",
            justify="left",
            text_color="#f59e0b",
        )
        self.warning_label.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 5))

        toolbar = ctk.CTkFrame(self)
        toolbar.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
        toolbar.grid_columnconfigure(4, weight=1)

        ctk.CTkLabel(toolbar, text="Lissage visuel").grid(row=0, column=0, padx=(10, 6))
        self.smooth_slider = ctk.CTkSlider(
            toolbar,
            from_=0,
            to=len(SMOOTH_OPTIONS_SECONDS) - 1,
            number_of_steps=len(SMOOTH_OPTIONS_SECONDS) - 1,
            width=220,
            command=self._on_smooth_slider,
        )
        self.smooth_slider.grid(row=0, column=1, padx=6, pady=10)
        self.smooth_slider.set(0)
        self.smooth_label = ctk.CTkLabel(toolbar, text="0 s", width=52)
        self.smooth_label.grid(row=0, column=2, padx=6)

        self.reset_button = ctk.CTkButton(
            toolbar,
            text="Reset zoom",
            width=110,
            command=self._reset_zoom,
        )
        self.reset_button.grid(row=0, column=3, padx=8)

        self.markers_button = ctk.CTkButton(
            toolbar,
            text="Effacer marqueurs",
            width=135,
            state="disabled",
            command=self._clear_markers,
        )
        self.markers_button.grid(row=0, column=5, padx=4)
        self.report_button = ctk.CTkButton(
            toolbar,
            text="Reporter",
            width=110,
            state="disabled",
            command=self._report_markers_to_profile,
        )
        self.report_button.grid(row=0, column=6, padx=4)
        self.export_button = ctk.CTkButton(
            toolbar,
            text="Exporter JSON + audit",
            width=160,
            state="disabled",
            command=self._export_json_and_audit,
        )
        self.export_button.grid(row=0, column=7, padx=(4, 10))

        body = ctk.CTkFrame(self)
        body.grid(row=3, column=0, sticky="nsew", padx=10, pady=(5, 10))
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self.graph_list = ctk.CTkScrollableFrame(body, width=220)
        self.graph_list.grid(row=0, column=0, sticky="nsw", padx=(8, 6), pady=8)
        self.graph_list.grid_columnconfigure(0, weight=1)

        graph_panel = ctk.CTkFrame(body)
        graph_panel.grid(row=0, column=1, sticky="nsew", padx=6, pady=8)
        graph_panel.grid_columnconfigure(0, weight=1)
        graph_panel.grid_rowconfigure(0, weight=1)
        self.graph_panel = graph_panel

        self.canvas_frame = ctk.CTkFrame(graph_panel)
        self.canvas_frame.grid(row=0, column=0, sticky="nsew", padx=8, pady=(8, 4))
        self.canvas_frame.grid_columnconfigure(0, weight=1)
        self.canvas_frame.grid_rowconfigure(0, weight=1)

        self.matplotlib_toolbar_frame = ctk.CTkFrame(graph_panel)
        self.matplotlib_toolbar_frame.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 4))

        graph_actions = ctk.CTkFrame(graph_panel, fg_color="transparent")
        graph_actions.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 8))
        graph_actions.grid_columnconfigure(0, weight=1)
        self.missing_label = ctk.CTkLabel(
            graph_actions,
            text="",
            anchor="w",
            justify="left",
            text_color="#f59e0b",
        )
        self.missing_label.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(
            graph_actions,
            text="Plein ecran",
            width=120,
            command=self._open_fullscreen,
        ).grid(row=0, column=1, padx=(8, 0))

        side = ctk.CTkFrame(body, width=280)
        side.grid(row=0, column=2, sticky="nse", padx=(6, 8), pady=8)
        side.grid_propagate(False)
        side.grid_columnconfigure(0, weight=1)
        side.grid_rowconfigure(2, weight=1)
        side.grid_rowconfigure(4, weight=1)
        ctk.CTkLabel(
            side,
            text="Marqueurs",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))

        marker_controls = ctk.CTkFrame(side)
        marker_controls.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))
        marker_controls.grid_columnconfigure(1, weight=1)
        self.marker_name_var = ctk.StringVar(value="SV1")
        self.marker_mode_var = ctk.StringVar(value="Point")
        ctk.CTkOptionMenu(
            marker_controls,
            values=list(MARKER_UI_LABELS),
            variable=self.marker_name_var,
            width=95,
        ).grid(row=0, column=0, padx=(6, 4), pady=(8, 4), sticky="w")
        ctk.CTkOptionMenu(
            marker_controls,
            values=["Point", "Fenetre"],
            variable=self.marker_mode_var,
            width=95,
        ).grid(row=0, column=1, padx=4, pady=(8, 4), sticky="ew")

        ctk.CTkLabel(marker_controls, text="Duree").grid(row=1, column=0, padx=6, sticky="w")
        self.marker_duration_entry = ctk.CTkEntry(marker_controls, width=95)
        self.marker_duration_entry.grid(row=1, column=1, padx=4, pady=3, sticky="ew")
        self.marker_duration_entry.insert(0, _format_time_seconds(DEFAULT_MARKER_WINDOW_SECONDS))

        ctk.CTkLabel(marker_controls, text="Debut").grid(row=2, column=0, padx=6, sticky="w")
        self.marker_start_entry = ctk.CTkEntry(marker_controls, width=95)
        self.marker_start_entry.grid(row=2, column=1, padx=4, pady=3, sticky="ew")
        ctk.CTkLabel(marker_controls, text="Fin").grid(row=3, column=0, padx=6, sticky="w")
        self.marker_end_entry = ctk.CTkEntry(marker_controls, width=95)
        self.marker_end_entry.grid(row=3, column=1, padx=4, pady=3, sticky="ew")

        ctk.CTkButton(
            marker_controls,
            text="Recalculer",
            command=self._recompute_marker_from_fields,
        ).grid(row=4, column=0, padx=6, pady=(6, 8), sticky="ew")
        ctk.CTkButton(
            marker_controls,
            text="Supprimer",
            fg_color="#9f1239",
            hover_color="#881337",
            command=self._delete_selected_marker,
        ).grid(row=4, column=1, padx=4, pady=(6, 8), sticky="ew")

        self.marker_text = ctk.CTkTextbox(side, wrap="none", height=180)
        self.marker_text.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))

        ctk.CTkLabel(
            side,
            text="Warnings et sources",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        ).grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 4))
        self.info_text = ctk.CTkTextbox(side, wrap="word")
        self.info_text.grid(row=4, column=0, sticky="nsew", padx=10, pady=(0, 10))

        for index, config in enumerate(GRAPH_CONFIGS):
            button = ctk.CTkButton(
                self.graph_list,
                text=f"{index + 1}. {config['title']}",
                anchor="w",
                command=lambda graph_id=config["id"]: self._select_graph(graph_id),
            )
            button.grid(row=index, column=0, sticky="ew", padx=6, pady=3)
            self.graph_buttons[config["id"]] = button
        self._sync_graph_buttons()

    def _load_match(self):
        try:
            self.profile = self.session_manager.get_profile(self.profile_name)
            if not self.profile:
                raise ValueError("Profil introuvable")

            xml_path = self.session_manager.get_xml_path(self.xml_filename)
            if not xml_path:
                raise ValueError("XML introuvable")

            self.xml_data = self.parser.parse_file(xml_path)
            parsed = self.xml_data.get("metasoft_parsed", {})
            analysis = self.xml_data.get("metasoft_analysis", {})
            profile_mass = _profile_mass_kg(self.profile)
            # Source masse: XML prioritaire; le profil local ne sert que si le
            # XML ne donne aucun poids exploitable.
            if _positive_number(parsed.get("athlete", {}).get("weight_kg")) is None:
                if profile_mass is not None:
                    analysis = build_metasoft_analysis(parsed, profile_mass)
                    self.xml_data["metasoft_analysis"] = analysis
            self.analysis = analysis
        except Exception as exc:
            self.title_label.configure(text="Analyse MetaSoft impossible")
            self.meta_label.configure(text=str(exc))
            return

        self._render_header()
        self._render_info_text()
        self._render_marker_table()
        self._draw_active_graph()
        self.markers_button.configure(state="normal")
        self.report_button.configure(state="normal")
        self.export_button.configure(state="normal")

    def _render_header(self):
        athlete = self.analysis.get("athlete", {})
        test = self.analysis.get("test", {})
        points = self.analysis.get("points", [])
        xml_name = _identity_name(athlete) or self.xml_filename
        profile_name = _profile_name(self.profile) or self.profile_name
        date_test = test.get("datetime") or test.get("date") or "date inconnue"
        warnings = self._warnings()

        self.title_label.configure(text=f"MetaSoft - {xml_name}")
        self.meta_label.configure(
            text=(
                f"Profil: {profile_name}  |  XML: {self.xml_filename}  |  "
                f"Test: {date_test}  |  Points: {len(points)}  |  "
                f"Warnings: {len(warnings)}"
            )
        )

        mismatch = _identity_mismatch_warning(athlete, self.profile)
        if mismatch:
            self.warning_label.configure(
                text=(
                    "Alerte identite non bloquante - "
                    f"XML: {mismatch['xml']} / Profil: {mismatch['profile']}"
                )
            )
        elif warnings:
            self.warning_label.configure(text=warnings[0].get("message", "Warning MetaSoft"))
        else:
            self.warning_label.configure(text="")

    def _render_info_text(self):
        lines = []
        mismatch = _identity_mismatch_warning(self.analysis.get("athlete", {}), self.profile)
        if mismatch:
            lines.append("Identite")
            lines.append(f"- XML: {mismatch['xml']}")
            lines.append(f"- Profil: {mismatch['profile']}")
            lines.append("- Non bloquant")
            lines.append("")

        lines.append("Donnees")
        lines.append("- Points MetaSoft normalises: " + str(len(self.analysis.get("points", []))))
        lines.append("- Lissage: visuel uniquement, export/profil inchanges")
        lines.append("")

        warnings = self._warnings()
        lines.append("Warnings")
        if warnings:
            for warning in warnings:
                message = warning.get("message") or warning.get("code") or str(warning)
                lines.append(f"- {message}")
        else:
            lines.append("- Aucun")

        self.info_text.configure(state="normal")
        self.info_text.delete("1.0", "end")
        self.info_text.insert("1.0", "\n".join(lines))
        self.info_text.configure(state="disabled")

    def _warnings(self):
        return list(self.analysis.get("warnings", []) or [])

    def _on_smooth_slider(self, value):
        index = int(round(float(value)))
        index = max(0, min(index, len(SMOOTH_OPTIONS_SECONDS) - 1))
        self.smooth_seconds = SMOOTH_OPTIONS_SECONDS[index]
        self.smooth_slider.set(index)
        self.smooth_label.configure(text=f"{self.smooth_seconds} s")
        if self.analysis:
            self._draw_active_graph()

    def _select_graph(self, graph_id):
        self.active_graph_id = graph_id
        self._sync_graph_buttons()
        if self.analysis:
            self._draw_active_graph()

    def _sync_graph_buttons(self):
        for graph_id, button in self.graph_buttons.items():
            active = graph_id == self.active_graph_id
            button.configure(fg_color="#1f6aa5" if active else ("gray75", "gray25"))

    def _draw_active_graph(self):
        config = next(item for item in GRAPH_CONFIGS if item["id"] == self.active_graph_id)
        self._clear_canvas()
        self.figure = Figure(figsize=(8.8, 5.8), dpi=100)
        render = draw_metasoft_graph(
            self.figure,
            self.analysis,
            config,
            self.smooth_seconds,
            self.markers,
        )

        self.canvas = FigureCanvasTkAgg(self.figure, master=self.canvas_frame)
        self.canvas.draw()
        self.canvas.mpl_connect("button_press_event", self._on_canvas_click)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        self.toolbar = NavigationToolbar2Tk(
            self.canvas,
            self.matplotlib_toolbar_frame,
            pack_toolbar=False,
        )
        self.toolbar.update()
        self.toolbar.grid(row=0, column=0, sticky="w")
        self.home_limits = _capture_limits(self.figure)
        self._render_missing_series(render)

    def _clear_canvas(self):
        if self.toolbar is not None:
            self.toolbar.destroy()
            self.toolbar = None
        if self.canvas is not None:
            self.canvas.get_tk_widget().destroy()
            self.canvas = None
        self.home_limits = []

    def _render_missing_series(self, render):
        missing = [series["label"] for series in render.get("missing_series", [])]
        text = (
            "Absent XML: " + ", ".join(missing)
            if missing else "Toutes les series du graphe sont disponibles."
        )
        self.missing_label.configure(text=text)

    def _on_canvas_click(self, event):
        if getattr(event, "dblclick", False):
            self._reset_zoom()
            return
        if getattr(event, "button", None) != 1 or event.xdata is None or event.inaxes is None:
            return
        if _toolbar_is_active(self.toolbar):
            return
        config = next(item for item in GRAPH_CONFIGS if item["id"] == self.active_graph_id)
        if config.get("source") != "points" or config.get("kind") != "time":
            self.missing_label.configure(text="Marqueurs: choisir un graphe avec axe temps.")
            return
        time_seconds = click_x_to_time_seconds(event.xdata, self._point_times())
        if time_seconds is None:
            return
        self.last_click_time = time_seconds
        self._place_marker_from_time(time_seconds)

    def _reset_zoom(self):
        if not self.figure or not self.home_limits:
            return
        for axis, x_limits, y_limits in self.home_limits:
            axis.set_xlim(x_limits)
            axis.set_ylim(y_limits)
        if self.canvas:
            self.canvas.draw_idle()

    def _open_fullscreen(self):
        if not self.analysis:
            return
        config = next(item for item in GRAPH_CONFIGS if item["id"] == self.active_graph_id)
        MetaSoftGraphWindow(self, self.analysis, config, self.smooth_seconds, self.markers)

    def _selected_marker_name(self):
        return _marker_name_from_label(self.marker_name_var.get())

    def _point_times(self):
        return [point.get("t_seconds") for point in self.analysis.get("points", [])]

    def _place_marker_from_time(self, time_seconds):
        name = self._selected_marker_name()
        points = self.analysis.get("points", [])
        if self.marker_mode_var.get() == "Fenetre":
            duration = (
                _parse_time_seconds(self.marker_duration_entry.get())
                or DEFAULT_MARKER_WINDOW_SECONDS
            )
            window = clamp_time_range(
                time_seconds - duration / 2,
                time_seconds + duration / 2,
                self._point_times(),
            )
            if window is None:
                return
            start, end = window
            marker = build_metasoft_marker(
                points,
                name,
                window_start_seconds=start,
                window_end_seconds=end,
            )
            self._set_entry(self.marker_start_entry, _format_time_seconds(start))
            self._set_entry(self.marker_end_entry, _format_time_seconds(end))
        else:
            marker = build_metasoft_marker(points, name, t_seconds=time_seconds)
            self._set_entry(self.marker_start_entry, _format_time_seconds(time_seconds))
            self._set_entry(self.marker_end_entry, _format_time_seconds(time_seconds))
        self.markers[name] = marker
        self._render_marker_table()
        self._draw_active_graph()

    def _recompute_marker_from_fields(self):
        name = self._selected_marker_name()
        points = self.analysis.get("points", [])
        if self.marker_mode_var.get() == "Fenetre":
            start = _parse_time_seconds(self.marker_start_entry.get())
            end = _parse_time_seconds(self.marker_end_entry.get())
            window = clamp_time_range(start, end, self._point_times())
            if window is None:
                messagebox.showwarning("Marqueur", "Debut/fin invalides.", parent=self)
                return
            start, end = window
            marker = build_metasoft_marker(
                points,
                name,
                window_start_seconds=start,
                window_end_seconds=end,
            )
            self._set_entry(self.marker_start_entry, _format_time_seconds(start))
            self._set_entry(self.marker_end_entry, _format_time_seconds(end))
        else:
            time_seconds = _parse_time_seconds(self.marker_start_entry.get())
            if time_seconds is None:
                time_seconds = self.last_click_time
            time_seconds = click_x_to_time_seconds(time_seconds, self._point_times())
            if time_seconds is None:
                messagebox.showwarning("Marqueur", "Temps invalide.", parent=self)
                return
            marker = build_metasoft_marker(points, name, t_seconds=time_seconds)
            self._set_entry(self.marker_start_entry, _format_time_seconds(time_seconds))
            self._set_entry(self.marker_end_entry, _format_time_seconds(time_seconds))
        self.markers[name] = marker
        self._render_marker_table()
        self._draw_active_graph()

    def _delete_selected_marker(self):
        self.markers.pop(self._selected_marker_name(), None)
        self._render_marker_table()
        self._draw_active_graph()

    def _clear_markers(self):
        self.markers.clear()
        self._render_marker_table()
        self._draw_active_graph()

    def _render_marker_table(self):
        lines = [
            "Marqueur | Mode | Temps | n | FC | VO2/kg | VO2 L/min | Vitesse | Warnings"
        ]
        if not self.markers:
            lines.append("Aucun marqueur. Clic gauche sur un graphe temporel pour poser.")
        for name in ("SV1", "SV2", "VO2_max", "VMA"):
            marker = self.markers.get(name)
            if not marker:
                continue
            values = marker.get("values", {})
            lines.append(
                " | ".join([
                    _marker_label(name),
                    _marker_mode_label(marker),
                    _marker_time_label(marker),
                    str(_marker_point_count(marker)),
                    _format_number(values.get("fc_bpm")),
                    _format_number(values.get("vo2_ml_kg_min")),
                    _format_number(values.get("vo2_l_min")),
                    _format_number(values.get("speed_kmh")),
                    _marker_warning_label(marker),
                ])
            )
        self.marker_text.configure(state="normal")
        self.marker_text.delete("1.0", "end")
        self.marker_text.insert("1.0", "\n".join(lines))
        self.marker_text.configure(state="disabled")

    def _report_markers_to_profile(self):
        patch_results = [
            metasoft_marker_to_stress_patch(marker)
            for marker in self.markers.values()
        ]
        patch_result = _merge_patch_results(patch_results)
        if patch_result.get("status") != "ok":
            warnings = patch_result.get("warnings", [])
            message = warnings[0].get("message") if warnings else "Aucun marqueur reportable."
            messagebox.showwarning("Report profil", message, parent=self)
            return

        conflicts = _patch_conflicts(self.profile, patch_result)
        if conflicts:
            details = "\n".join(
                f"- {item['path']}: {item['old']} -> {item['new']}"
                for item in conflicts
            )
            if not messagebox.askyesno(
                "Confirmer le report",
                "Ces champs sont deja remplis avec une valeur differente:\n\n"
                f"{details}\n\nEcraser ces valeurs ?",
                parent=self,
            ):
                return

        updated_profile = apply_metasoft_stress_patch(self.profile, patch_result)
        new_profile_name = self.session_manager.update_profile(self.profile_name, updated_profile)
        if not new_profile_name:
            messagebox.showerror("Report profil", "Sauvegarde profil impossible.", parent=self)
            return
        self.profile_name = new_profile_name
        self.match_info["profile_name"] = new_profile_name
        self.profile = updated_profile
        if hasattr(self.master, "refresh"):
            self.master.refresh()
        messagebox.showinfo("Report profil", "Profil sauvegarde.", parent=self)

    def _export_json_and_audit(self):
        try:
            profile = self.session_manager.get_profile(self.profile_name) or self.profile
            if not profile.get("email"):
                messagebox.showwarning(
                    "Attention",
                    "L'email est requis dans le profil",
                    parent=self,
                )
                return

            output = DataTransformer().transform(self.xml_data, profile)
            output_filename = self._output_filename(profile)
            output_path = self.session_manager.save_output(output_filename, output)

            audit_filename = metasoft_audit_filename(output_filename)
            generated_at = datetime.now().isoformat(timespec="seconds")
            sidecar = build_metasoft_audit_export(
                self.analysis,
                profile=profile,
                markers=self.markers,
                json_filename=output_filename,
                audit_filename=audit_filename,
                profile_filename=self.profile_name,
                generated_at=generated_at,
                app_version=APP_VERSION,
                ui_warnings=[],
            )
            audit_path = self.session_manager.save_output(audit_filename, sidecar)

            self.session_manager.mark_as_exported(self.profile_name)
            if hasattr(self.master, "refresh"):
                self.master.refresh()
            messagebox.showinfo(
                "Export MetaSoft",
                f"JSON:\n{output_path}\n\nAudit:\n{audit_path}",
                parent=self,
            )
        except Exception as exc:
            messagebox.showerror("Export MetaSoft", f"Erreur lors de l'export: {exc}", parent=self)

    def _output_filename(self, profile):
        identity = profile.get("identity", {})
        name = f"{identity.get('last_name', 'Unknown')}_{identity.get('first_name', '')}"
        name = name.strip("_") or "Unknown"
        session = getattr(self.session_manager, "current_session", None)
        date = getattr(session, "date", "") or datetime.now().strftime("%Y-%m-%d")
        return f"{name}_{date}.json"

    def _set_entry(self, entry, value):
        entry.delete(0, "end")
        entry.insert(0, value)

    def destroy(self):
        self._clear_canvas()
        super().destroy()


class MetaSoftGraphWindow(ctk.CTkToplevel):
    """Toplevel dedie a un graphe MetaSoft agrandi."""

    def __init__(self, master, analysis, graph_config, smooth_seconds, markers=None):
        super().__init__(master)
        self.analysis = analysis
        self.graph_config = graph_config
        self.smooth_seconds = smooth_seconds
        self.markers = markers or {}
        self.canvas = None
        self.toolbar = None
        self.home_limits = []

        self.title(f"MetaSoft - {graph_config['title']}")
        self.geometry("1120x760")
        self.minsize(900, 620)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.canvas_frame = ctk.CTkFrame(self)
        self.canvas_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 4))
        self.canvas_frame.grid_columnconfigure(0, weight=1)
        self.canvas_frame.grid_rowconfigure(0, weight=1)

        controls = ctk.CTkFrame(self)
        controls.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        controls.grid_columnconfigure(1, weight=1)
        self.toolbar_frame = ctk.CTkFrame(controls, fg_color="transparent")
        self.toolbar_frame.grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            controls,
            text="Reset zoom",
            width=110,
            command=self._reset_zoom,
        ).grid(row=0, column=2, padx=8, pady=6)

        self._draw()

    def _draw(self):
        figure = Figure(figsize=(10, 6.4), dpi=100)
        draw_metasoft_graph(
            figure,
            self.analysis,
            self.graph_config,
            self.smooth_seconds,
            self.markers,
        )
        self.canvas = FigureCanvasTkAgg(figure, master=self.canvas_frame)
        self.canvas.draw()
        self.canvas.mpl_connect("button_press_event", self._on_canvas_click)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.toolbar_frame, pack_toolbar=False)
        self.toolbar.update()
        self.toolbar.grid(row=0, column=0, sticky="w")
        self.home_limits = _capture_limits(figure)

    def _on_canvas_click(self, event):
        if getattr(event, "dblclick", False):
            self._reset_zoom()

    def _reset_zoom(self):
        for axis, x_limits, y_limits in self.home_limits:
            axis.set_xlim(x_limits)
            axis.set_ylim(y_limits)
        if self.canvas:
            self.canvas.draw_idle()

    def destroy(self):
        if self.toolbar is not None:
            self.toolbar.destroy()
        if self.canvas is not None:
            self.canvas.get_tk_widget().destroy()
        super().destroy()


def draw_metasoft_graph(figure, analysis, graph_config, smooth_seconds=0, markers=None):
    """Dessine un graphe MetaSoft matplotlib et retourne les donnees de rendu."""
    render = build_graph_render_data(analysis, graph_config, smooth_seconds)
    figure.clear()
    axis = figure.add_subplot(111)
    _style_axis(axis)

    if render["source"] == "running_economy":
        _draw_running_economy(axis, render)
    else:
        _draw_point_graph(axis, analysis, render)
        if render.get("kind") == "time":
            _draw_marker_overlays(axis, markers or {})

    _draw_missing_text(axis, render)
    title = render["title"]
    if smooth_seconds and render["source"] == "points" and render.get("kind") == "time":
        title = f"{title} - lissage {smooth_seconds} s"
    axis.set_title(title, color=_text_color(), fontsize=13, fontweight="bold")
    figure.tight_layout(pad=1.8)
    return render


def _draw_point_graph(axis, analysis, render):
    if render.get("kind") == "time":
        _draw_phase_background(axis, analysis)
    y2_axis = None
    plotted = []

    for series in render["series"]:
        values = series["render_values"]
        if not any(value is not None for value in values):
            continue
        target_axis = axis
        if series.get("axis") == "y2":
            if y2_axis is None:
                y2_axis = axis.twinx()
                _style_axis(y2_axis)
            target_axis = y2_axis
        if render.get("kind") == "scatter":
            artist = target_axis.scatter(
                render["x_values"],
                values,
                color=series["color"],
                s=16,
                alpha=0.8,
                label=series["label"],
            )
        else:
            artist = target_axis.plot(
                render["x_values"],
                values,
                color=series["color"],
                linewidth=1.7,
                label=series["label"],
                drawstyle="steps-post" if series["key"] == "speed_kmh" else "default",
            )[0]
        plotted.append(artist)

    if render.get("kind") == "time" and not any(
        series["key"] == "speed_kmh" for series in render["series"]
    ):
        _draw_speed_step(axis, analysis)
    axis.set_xlabel(_axis_title(render["x_axis"]), color=_text_color())
    axis.set_ylabel(_axis_label(render["series"], "y"), color=_text_color())
    if y2_axis:
        y2_axis.set_ylabel(_axis_label(render["series"], "y2"), color=_text_color())
    if not plotted:
        axis.text(
            0.5,
            0.5,
            "Aucune serie disponible pour ce graphe",
            transform=axis.transAxes,
            ha="center",
            va="center",
            color=_text_color(),
        )
    _legend(axis)


def _draw_running_economy(axis, render):
    values = render["series"][0]["render_values"] if render["series"] else []
    has_values = any(value is not None for value in values)
    if has_values:
        axis.bar(
            render["x_values"],
            [value if value is not None else 0 for value in values],
            color="#16e0c2",
            alpha=0.8,
            label="EC (J/kg/m)",
        )
        for x_value, speed in zip(render["x_values"], render.get("stage_speeds_kmh", [])):
            if speed is not None:
                axis.text(x_value, 0.02, f"{speed:g} km/h", transform=axis.get_xaxis_transform(),
                          ha="center", va="bottom", fontsize=8, color=_text_color())
    else:
        axis.text(
            0.5,
            0.5,
            "EC indisponible: masse/repos/VO2/VCO2 ou vitesse manquants",
            transform=axis.transAxes,
            ha="center",
            va="center",
            color=_text_color(),
        )
    axis.set_xlabel("Palier", color=_text_color())
    axis.set_ylabel("EC (J/kg/m)", color=_text_color())
    _legend(axis)


def _draw_phase_background(axis, analysis):
    for phase in analysis.get("phases", []) or []:
        start = _number(phase.get("start_seconds"))
        end = _number(phase.get("end_seconds"))
        if start is None or end is None or end <= start:
            continue
        color = PHASE_COLORS.get(phase.get("phase"), "#475569")
        axis.axvspan(start, end, color=color, alpha=0.12, zorder=0)
        axis.text(
            (start + end) / 2,
            0.98,
            phase.get("phase", ""),
            transform=axis.get_xaxis_transform(),
            ha="center",
            va="top",
            fontsize=8,
            color=_text_color(),
            alpha=0.8,
        )


def _draw_speed_step(axis, analysis):
    points = analysis.get("points", []) or []
    times = []
    speeds = []
    for point in points:
        time_value = _number(point.get("t_seconds"))
        speed = _number(point.get("values", {}).get("speed_kmh"))
        if time_value is not None and speed is not None:
            times.append(time_value)
            speeds.append(speed)
    if not times:
        return
    low = min(speeds)
    high = max(speeds)
    if high == low:
        y_values = [0.1 for _speed in speeds]
    else:
        y_values = [0.04 + ((speed - low) / (high - low) * 0.14) for speed in speeds]
    axis.step(
        times,
        y_values,
        where="post",
        transform=axis.get_xaxis_transform(),
        color="#94a3b8",
        linewidth=1.0,
        alpha=0.75,
        label="vitesse (repere)",
        zorder=1,
    )


def _draw_missing_text(axis, render):
    missing = [series["label"] for series in render.get("missing_series", [])]
    if not missing:
        return
    axis.text(
        0.01,
        0.02,
        "Absent XML: " + ", ".join(missing),
        transform=axis.transAxes,
        ha="left",
        va="bottom",
        fontsize=8,
        color="#f59e0b",
    )


def _draw_marker_overlays(axis, markers):
    for name, marker in markers.items():
        if marker.get("status") != "ok":
            continue
        color = MARKER_CONFIGS.get(name, {}).get("color", "#facc15")
        label = _marker_label(name)
        if marker.get("mode") == "range":
            start = _number(marker.get("window_start_seconds"))
            end = _number(marker.get("window_end_seconds"))
            if start is None or end is None:
                continue
            axis.axvspan(start, end, color=color, alpha=0.16, zorder=2)
            x_label = (start + end) / 2
        else:
            x_label = _number(marker.get("selection_time_seconds"))
            if x_label is None:
                continue
            axis.axvline(x_label, color=color, linewidth=1.4, alpha=0.9, zorder=3)
        axis.text(
            x_label,
            0.92,
            label,
            transform=axis.get_xaxis_transform(),
            ha="center",
            va="top",
            fontsize=8,
            color=color,
            fontweight="bold",
            zorder=4,
        )


def _legend(axis):
    handles = []
    labels = []
    for target in axis.figure.axes:
        axis_handles, axis_labels = target.get_legend_handles_labels()
        handles.extend(axis_handles)
        labels.extend(axis_labels)
    if handles:
        axis.legend(handles, labels, loc="upper left", fontsize=8, framealpha=0.25)


def _style_axis(axis):
    bg = "#1f2937" if ctk.get_appearance_mode() == "Dark" else "#f8fafc"
    grid = "#475569" if ctk.get_appearance_mode() == "Dark" else "#cbd5e1"
    axis.figure.patch.set_facecolor(bg)
    axis.set_facecolor(bg)
    axis.tick_params(colors=_text_color(), labelsize=8)
    axis.grid(True, alpha=0.25, color=grid)
    for spine in axis.spines.values():
        spine.set_color(grid)


def _axis_label(series_configs, axis_name):
    labels = [series["unit"] for series in series_configs if series.get("axis") == axis_name]
    labels = [label for label in labels if label]
    return " / ".join(dict.fromkeys(labels)) if labels else ""


def _axis_title(axis_config):
    unit = axis_config.get("unit")
    return f"{axis_config['label']} ({unit})" if unit else axis_config["label"]


def _capture_limits(figure):
    return [(axis, axis.get_xlim(), axis.get_ylim()) for axis in figure.axes]


def _toolbar_is_active(toolbar):
    mode = str(getattr(toolbar, "mode", "") or "")
    return bool(mode and mode not in ("None", "_Mode.NONE"))


def _text_color():
    return "white" if ctk.get_appearance_mode() == "Dark" else "#0f172a"


def _identity_mismatch_warning(xml_athlete, profile):
    xml_name = _identity_name(xml_athlete)
    profile_name = _profile_name(profile)
    if not xml_name or not profile_name:
        return None
    if _clean_identity(xml_name) == _clean_identity(profile_name):
        return None
    return {"xml": xml_name, "profile": profile_name}


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
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", ".").strip())
        except ValueError:
            return None
    return None


def _marker_name_from_label(label):
    return "VO2_max" if str(label).strip() == "VO2max" else str(label).strip()


def _marker_label(name):
    return MARKER_CONFIGS.get(name, {}).get("label", name)


def _marker_mode_label(marker):
    return "Fenetre" if marker.get("mode") == "range" else "Point"


def _marker_time_label(marker):
    if marker.get("mode") == "range":
        return (
            f"{_format_time_seconds(marker.get('window_start_seconds'))}-"
            f"{_format_time_seconds(marker.get('window_end_seconds'))}"
        )
    selected = _format_time_seconds(marker.get("selection_time_seconds"))
    source = _format_time_seconds(marker.get("source_point_t_seconds"))
    return f"{selected} -> {source}"


def _marker_point_count(marker):
    if marker.get("mode") == "range":
        return marker.get("point_count", 0)
    return 1 if marker.get("status") == "ok" else 0


def _marker_warning_label(marker):
    warnings = marker.get("warnings", [])
    if not warnings:
        return "-"
    return "; ".join(warning.get("message") or warning.get("code", "") for warning in warnings)


def _format_number(value):
    number = _number(value)
    if number is None:
        return "-"
    return f"{number:.3f}".rstrip("0").rstrip(".")


def _format_time_seconds(value):
    number = _number(value)
    if number is None:
        return ""
    total = round(max(float(number), 0), 3)
    whole_seconds = int(total)
    decimals = total - whole_seconds
    hours, remainder = divmod(whole_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if decimals:
        second_text = f"{seconds + decimals:06.3f}".rstrip("0").rstrip(".")
    else:
        second_text = f"{seconds:02d}"
    return f"{hours}:{minutes:02d}:{second_text}"


def _parse_time_seconds(value):
    text = str(value or "").strip()
    if not text:
        return None
    if ":" not in text:
        number = _number(text)
        return number if number is not None and number >= 0 else None
    parts = text.split(":")
    if len(parts) == 2:
        parts = ["0", *parts]
    if len(parts) != 3:
        return None
    try:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2].replace(",", "."))
    except ValueError:
        return None
    total = hours * 3600 + minutes * 60 + seconds
    return total if hours >= 0 and minutes >= 0 and seconds >= 0 else None


def _merge_patch_results(patch_results):
    merged = {"status": "ok", "patch": {"stress_test_results": {}}, "warnings": []}
    for result in patch_results:
        if result.get("status") != "ok":
            merged["status"] = "blocked"
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
    for path, new_value in _flatten_patch_values(patch_result.get("patch", {})):
        old_value = _read_path(profile, path)
        if _empty_value(old_value) or _same_value(old_value, new_value):
            continue
        conflicts.append({
            "path": ".".join(path),
            "old": old_value,
            "new": new_value,
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
