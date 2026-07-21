"""
Tabbed Input Form - 3 onglets pour la saisie profil
  1. Profil / Perso : informations personnelles de l'athlète
  2. Mesures Test : données collectées pendant le test
  3. Analyse : synthèse des résultats + conseils / commentaires métier
"""
import customtkinter as ctk
from typing import Dict, List, Any, Optional
from pydantic import ValidationError
from core.validation_models import ProfileFormModel
from core.protocol_store import ProtocolStore
from ui.profile_metasoft_summary import build_profile_metasoft_summary

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


class TabbedInputForm(ctk.CTkFrame):
    """Form with 3 tabs: Profil/Perso, Mesures Test, Analyse"""

    def __init__(self, master, on_db_lookup=None, protocol_store: Optional[ProtocolStore] = None, **kwargs):
        super().__init__(master, **kwargs)

        self.on_db_lookup = on_db_lookup  # callback(email: str)
        self.protocol_store = protocol_store
        self.entries: Dict[str, Dict] = {}
        self.lactate_entries: List[Dict] = []
        self.lactate_thresholds: Dict[str, Any] = {}
        self.summary_labels: Dict[str, ctk.CTkLabel] = {}
        self.metasoft_summary_widgets: Dict[str, Dict[str, ctk.CTkLabel]] = {}

        self._init_field_mapping()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Tab view ---
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=0, column=0, sticky="nsew")

        self.tabview.add("Profil / Perso")
        self.tabview.add("Mesures Test")
        self.tabview.add("Analyse")

        # Build each tab
        self._create_profil_tab()
        self._create_mesures_tab()
        self._create_analyse_tab()

        # Refresh summary when switching to Analyse tab
        self.tabview.configure(command=self._on_tab_changed)

    # ------------------------------------------------------------------ #
    #  Field mapping  (flat key -> Pydantic model path)
    # ------------------------------------------------------------------ #
    def _init_field_mapping(self):
        self.field_mapping = {
            'email': ('email',),

            # Consent
            'consent_risques': ('consentements', 'risques'),
            'consent_donnees': ('consentements', 'donnees'),
            'consent_anonyme': ('consentements', 'anonyme'),
            'consent_image': ('consentements', 'image'),

            # Identity
            'last_name': ('identity', 'last_name'),
            'first_name': ('identity', 'first_name'),
            'date_of_birth': ('identity', 'date_of_birth'),
            'age': ('identity', 'age'),
            'sport_practiced': ('identity', 'sport_practiced'),
            'specialty': ('identity', 'specialty'),
            'has_coach': ('identity', 'has_coach'),

            # Body
            'height_cm': ('body_composition', 'height_cm'),
            'current_weight': ('body_composition', 'current_weight'),
            'weight_before_test': ('body_composition', 'weight_before_test'),
            'weight_after_test': ('body_composition', 'weight_after_test'),
            'altitude_vie': ('altitude_vie_m',),

            # SpO2
            'spo2_avant': ('spo2', 'avant'),
            'spo2_apres': ('spo2', 'apres'),
            'lactatemie_repos': ('lactatemie_repos',),

            # Job
            'job_title': ('professional_life', 'job_title'),
            'working_hours_per_week': ('professional_life', 'working_hours_per_week'),

            # Equipment
            'watch_brand': ('equipment_and_tracking', 'watch_brand'),
            'watch_estimated_vo2': ('equipment_and_tracking', 'watch_estimated_vo2'),
            'min_hr_before': ('equipment_and_tracking', 'min_hr_before'),
            'max_hr_ever': ('equipment_and_tracking', 'max_hr_ever'),
            'average_weekly_volume': ('equipment_and_tracking', 'average_weekly_volume'),

            # Predictions
            'prediction_5k': ('equipment_and_tracking', 'watch_race_predictions', '5k'),
            'prediction_10k': ('equipment_and_tracking', 'watch_race_predictions', '10k'),
            'prediction_half': ('equipment_and_tracking', 'watch_race_predictions', 'half_marathon'),
            'prediction_marathon': ('equipment_and_tracking', 'watch_race_predictions', 'marathon'),

            # Records
            'record_5k': ('history_and_goals', 'personal_records', '5k'),
            'record_10k': ('history_and_goals', 'personal_records', '10k'),
            'record_half': ('history_and_goals', 'personal_records', 'half_marathon'),
            'record_marathon': ('history_and_goals', 'personal_records', 'marathon'),
            'utmb_index': ('history_and_goals', 'utmb_index'),
            'upcoming_goals': ('history_and_goals', 'upcoming_goals'),

            # Context
            'seance_veille': ('seance_veille',),
            'observations': ('observations',),
            'protocol_description': ('protocol_description',),

            # Results
            'measured_vo2max': ('stress_test_results', 'measured_vo2max'),
            'max_hr': ('stress_test_results', 'max_hr'),
            'vma': ('stress_test_results', 'vma'),
            'first_stage_speed': ('stress_test_results', 'first_stage_speed'),
            'last_stage_speed': ('stress_test_results', 'last_stage_speed'),

            # SV1
            'sv1_hr': ('stress_test_results', 'thresholds', 'sv1', 'hr_bpm'),
            'sv1_speed': ('stress_test_results', 'thresholds', 'sv1', 'pace_km_h'),
            'sv1_vo2': ('stress_test_results', 'thresholds', 'sv1', 'vo2_ml_kg_min'),

            # SV2
            'sv2_hr': ('stress_test_results', 'thresholds', 'sv2', 'hr_bpm'),
            'sv2_speed': ('stress_test_results', 'thresholds', 'sv2', 'pace_km_h'),
            'sv2_vo2': ('stress_test_results', 'thresholds', 'sv2', 'vo2_ml_kg_min'),

            # RSI / CMJ
            'rsi_avant': ('rsi', 'avant'),
            'rsi_apres': ('rsi', 'apres'),
            'cmj_avant_hauteur': ('cmj', 'avant', 'hauteur_cm'),
            'cmj_avant_force': ('cmj', 'avant', 'force_max_kfg_kg'),
            'cmj_avant_puissance': ('cmj', 'avant', 'puissance_max_w_kg'),
            'cmj_apres_hauteur': ('cmj', 'apres', 'hauteur_cm'),
            'cmj_apres_force': ('cmj', 'apres', 'force_max_kfg_kg'),
            'cmj_apres_puissance': ('cmj', 'apres', 'puissance_max_w_kg'),

            # Others
            'conseils_entrainements': ('conseils_entrainements',),
            'notes_privees': ('notes_privees',),
        }

    # ================================================================== #
    #  TAB 1 – PROFIL / PERSO                                            #
    # ================================================================== #
    def _create_profil_tab(self):
        tab = self.tabview.tab("Profil / Perso")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(tab)
        scroll.pack(fill="both", expand=True)
        scroll.grid_columnconfigure(0, weight=1)
        scroll.grid_columnconfigure(1, weight=1)

        # ---------- LEFT COLUMN ----------
        left = ctk.CTkFrame(scroll, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left.grid_columnconfigure(1, weight=1)
        r = 0

        # Consentement
        r = self._add_section(left, "Consentement", r)
        r = self._add_consent_checkbox(
            left, "consent_risques",
            "Je reconnais avoir été informé(e) des risques inhérents à la réalisation d'un test d'effort maximal. "
            "J'accepte de participer en toute connaissance de cause et décharge Enduraw de toute responsabilité "
            "en cas d'incident lié à mon état de santé non signalé préalablement.", r)
        r = self._add_consent_checkbox(
            left, "consent_donnees",
            "Je consens à la collecte et à la sauvegarde de mes données personnelles et de mes résultats de test "
            "par Enduraw, conformément au RGPD.", r)
        r = self._add_consent_checkbox(
            left, "consent_anonyme",
            "Je consens à l'utilisation future de mes données de test, de manière anonymisée, "
            "à des fins statistiques, de recherche ou d'amélioration des services Enduraw.", r)
        r = self._add_consent_checkbox(
            left, "consent_image",
            "Je consens à l'utilisation par Enduraw de l'image de ma personne (photos ou vidéos) "
            "prise lors du test, sur tous supports de communication.", r)

        # Identification
        r = self._add_section(left, "Identification", r)
        r = self._add_email_field_with_lookup(left, r)
        r = self._add_field(left, "last_name", "Nom", r)
        r = self._add_field(left, "first_name", "Prénom", r)
        r = self._add_field(left, "date_of_birth", "Date de naissance", r)
        r = self._add_field(left, "age", "Âge", r, field_type="number")
        r = self._add_field(left, "sport_practiced", "Sport pratiqué", r)
        r = self._add_field(left, "specialty", "Spécialité", r)
        r = self._add_checkbox(left, "has_coach", "A un coach", r)

        # Données Corporelles (seulement taille / poids actuel / altitude)
        r = self._add_section(left, "Données Corporelles", r)
        r = self._add_field(left, "height_cm", "Taille (cm)", r, field_type="number")
        r = self._add_field(left, "current_weight", "Poids actuel (kg)", r, field_type="number")
        r = self._add_field(left, "altitude_vie", "Altitude de vie (m)", r, field_type="number")

        # Vie professionnelle
        r = self._add_section(left, "Vie Professionnelle", r)
        r = self._add_field(left, "job_title", "Métier", r)
        r = self._add_field(left, "working_hours_per_week", "Heures/semaine", r, field_type="number")

        # ---------- RIGHT COLUMN ----------
        right = ctk.CTkFrame(scroll, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        right.grid_columnconfigure(1, weight=1)
        r2 = 0

        # Équipement
        r2 = self._add_section(right, "Équipement & Suivi", r2)
        r2 = self._add_field(right, "watch_brand", "Marque de montre", r2)
        r2 = self._add_field(right, "watch_estimated_vo2", "VO2 montre", r2, field_type="number")
        r2 = self._add_field(right, "min_hr_before", "FC repos (bpm)", r2, field_type="number")
        r2 = self._add_field(right, "max_hr_ever", "FC max connue", r2, field_type="number")
        r2 = self._add_field(right, "average_weekly_volume", "Volume hebdo", r2)
        r2 = self._add_subsection(right, "Prédictions montre (HH:MM:SS)", r2)
        r2 = self._add_time_field(right, "prediction_5k", "5K", r2)
        r2 = self._add_time_field(right, "prediction_10k", "10K", r2)
        r2 = self._add_time_field(right, "prediction_half", "Semi", r2)
        r2 = self._add_time_field(right, "prediction_marathon", "Marathon", r2)

        # Historique & Objectifs
        r2 = self._add_section(right, "Historique & Objectifs", r2)
        r2 = self._add_subsection(right, "Records personnels (HH:MM:SS)", r2)
        r2 = self._add_time_field(right, "record_5k", "5K", r2)
        r2 = self._add_time_field(right, "record_10k", "10K", r2)
        r2 = self._add_time_field(right, "record_half", "Semi", r2)
        r2 = self._add_time_field(right, "record_marathon", "Marathon", r2)
        r2 = self._add_field(right, "utmb_index", "Index UTMB", r2, field_type="number")
        r2 = self._add_textfield(right, "upcoming_goals", "Objectifs à venir", r2)

    # ================================================================== #
    #  TAB 2 – MESURES TEST                                               #
    # ================================================================== #
    def _create_mesures_tab(self):
        tab = self.tabview.tab("Mesures Test")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(tab)
        scroll.pack(fill="both", expand=True)
        scroll.grid_columnconfigure(0, weight=1)
        scroll.grid_columnconfigure(1, weight=1)

        # ---------- LEFT COLUMN ----------
        left = ctk.CTkFrame(scroll, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left.grid_columnconfigure(1, weight=1)
        r = 0

        # Contexte Séance
        r = self._add_section(left, "Contexte Séance", r)
        r = self._add_field(left, "seance_veille", "Séance de la veille", r)
        r = self._add_textfield(left, "observations", "Observations", r)

        # Protocole
        r = self._add_section(left, "Protocole", r)
        r = self._add_protocol_selector(left, r)
        r = self._add_field(left, "first_stage_speed", "Vitesse 1er palier (km/h)", r, field_type="number")
        r = self._add_field(left, "last_stage_speed", "Vitesse dernier palier (km/h)", r, field_type="number")

        # Données corporelles du jour du test
        r = self._add_section(left, "Pesée du Test", r)
        r = self._add_field(left, "weight_before_test", "Poids avant test (kg)", r, field_type="number")
        r = self._add_field(left, "weight_after_test", "Poids après test (kg)", r, field_type="number")

        # SpO2 & Lactatémie repos
        r = self._add_section(left, "Mesures Pré-Test", r)
        r = self._add_subsection(left, "SpO2 (%)", r)
        r = self._add_field(left, "spo2_avant", "Avant test", r, field_type="number")
        r = self._add_field(left, "spo2_apres", "Après test", r, field_type="number")
        r = self._add_field(left, "lactatemie_repos", "Lactatémie repos (mmol/L)", r, field_type="number")

        # ---------- RIGHT COLUMN ----------
        right = ctk.CTkFrame(scroll, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        right.grid_columnconfigure(1, weight=1)
        r2 = 0

        # Résultats du Test
        r2 = self._add_section(right, "Résultats du Test", r2)
        r2 = self._add_field(right, "measured_vo2max", "VO2max mesuré (ml/min/kg)", r2, field_type="number")
        r2 = self._add_field(right, "max_hr", "FC max atteinte (bpm)", r2, field_type="number")
        r2 = self._add_field(right, "vma", "VMA (km/h)", r2, field_type="number")

        # RSI
        r2 = self._add_subsection(right, "RSI", r2)
        r2 = self._add_rsi(right, r2)

        # CMJ
        r2 = self._add_subsection(right, "CMJ", r2)
        r2 = self._add_cmj(right, r2)

        # Seuils ventilatoires
        r2 = self._add_section(right, "Seuils Ventilatoires", r2)
        r2 = self._add_thresholds(right, r2)

        # Lactate
        r2 = self._add_section(right, "Mesures Lactate", r2)
        r2 = self._add_lactate(right, r2)

    # ================================================================== #
    #  TAB 3 – ANALYSE                                                    #
    # ================================================================== #
    def _create_analyse_tab(self):
        tab = self.tabview.tab("Analyse")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(tab)
        scroll.pack(fill="both", expand=True)
        scroll.grid_columnconfigure(0, weight=1)
        scroll.grid_columnconfigure(1, weight=1)

        # ---------- LEFT: SYNTHÈSE (read-only) ----------
        left = ctk.CTkFrame(scroll, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left.grid_columnconfigure(1, weight=1)
        r = 0

        r = self._add_section(left, "Synthèse des Résultats", r)

        # Summary cards
        summary_frame = ctk.CTkFrame(left, corner_radius=8)
        summary_frame.grid(row=r, column=0, columnspan=2, sticky="ew", pady=5)
        summary_frame.grid_columnconfigure(1, weight=1)

        summary_fields = [
            ("sum_vo2max", "VO2max (ml/min/kg)"),
            ("sum_vo2_peak", "VO2 pic (L/min)"),
            ("sum_vma", "VMA (km/h)"),
            ("sum_fcmax", "FC max (bpm)"),
        ]
        for i, (key, label) in enumerate(summary_fields):
            ctk.CTkLabel(summary_frame, text=label, anchor="w",
                         font=ctk.CTkFont(size=12)).grid(row=i, column=0, padx=10, pady=4, sticky="w")
            lbl = ctk.CTkLabel(summary_frame, text="—", anchor="e",
                               font=ctk.CTkFont(size=13, weight="bold"))
            lbl.grid(row=i, column=1, padx=10, pady=4, sticky="e")
            self.summary_labels[key] = lbl
        r += 1

        # SV1 card
        sv1_card = ctk.CTkFrame(left, corner_radius=8)
        sv1_card.grid(row=r, column=0, columnspan=2, sticky="ew", pady=5)
        sv1_card.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(sv1_card, text="SV1", font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#e67e22").grid(
            row=0, column=0, columnspan=2, padx=10, pady=(8, 2))
        for i, (key, label) in enumerate([
            ("sum_sv1_hr", "FC (bpm)"),
            ("sum_sv1_hr_pct", "% FC max"),
            ("sum_sv1_speed", "Vitesse (km/h)"),
            ("sum_sv1_speed_pct", "% VMA"),
            ("sum_sv1_vo2", "VO2 (ml/kg/min)"),
            ("sum_sv1_vo2_pct", "% VO2max"),
        ]):
            ctk.CTkLabel(sv1_card, text=label, anchor="w").grid(row=i + 1, column=0, padx=10, pady=2, sticky="w")
            lbl = ctk.CTkLabel(sv1_card, text="—", anchor="e", font=ctk.CTkFont(weight="bold"))
            lbl.grid(row=i + 1, column=1, padx=10, pady=2, sticky="e")
            self.summary_labels[key] = lbl
        ctk.CTkLabel(sv1_card, text="").grid(row=7, pady=3)
        r += 1

        # SV2 card
        sv2_card = ctk.CTkFrame(left, corner_radius=8)
        sv2_card.grid(row=r, column=0, columnspan=2, sticky="ew", pady=5)
        sv2_card.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(sv2_card, text="SV2", font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#e74c3c").grid(
            row=0, column=0, columnspan=2, padx=10, pady=(8, 2))
        for i, (key, label) in enumerate([
            ("sum_sv2_hr", "FC (bpm)"),
            ("sum_sv2_hr_pct", "% FC max"),
            ("sum_sv2_speed", "Vitesse (km/h)"),
            ("sum_sv2_speed_pct", "% VMA"),
            ("sum_sv2_vo2", "VO2 (ml/kg/min)"),
            ("sum_sv2_vo2_pct", "% VO2max"),
        ]):
            ctk.CTkLabel(sv2_card, text=label, anchor="w").grid(row=i + 1, column=0, padx=10, pady=2, sticky="w")
            lbl = ctk.CTkLabel(sv2_card, text="—", anchor="e", font=ctk.CTkFont(weight="bold"))
            lbl.grid(row=i + 1, column=1, padx=10, pady=2, sticky="e")
            self.summary_labels[key] = lbl
        ctk.CTkLabel(sv2_card, text="").grid(row=7, pady=3)
        r += 1

        # Athlete info summary
        r = self._add_section(left, "Athlète", r)
        athlete_card = ctk.CTkFrame(left, corner_radius=8)
        athlete_card.grid(row=r, column=0, columnspan=2, sticky="ew", pady=5)
        athlete_card.grid_columnconfigure(1, weight=1)
        for i, (key, label) in enumerate([
            ("sum_name", "Nom"),
            ("sum_sport", "Sport"),
            ("sum_weight", "Poids (kg)"),
        ]):
            ctk.CTkLabel(athlete_card, text=label, anchor="w").grid(row=i, column=0, padx=10, pady=3, sticky="w")
            lbl = ctk.CTkLabel(athlete_card, text="—", anchor="e", font=ctk.CTkFont(weight="bold"))
            lbl.grid(row=i, column=1, padx=10, pady=3, sticky="e")
            self.summary_labels[key] = lbl
        ctk.CTkLabel(athlete_card, text="").grid(row=3, pady=2)
        r += 1

        # ---------- Lactate graph ----------
        r = self._add_section(left, "Graphique Lactate", r)
        self.lactate_graph_frame = ctk.CTkFrame(left, corner_radius=8, height=300)
        self.lactate_graph_frame.grid(row=r, column=0, columnspan=2, sticky="ew", pady=5)
        self.lactate_graph_frame.grid_columnconfigure(0, weight=1)
        self.lactate_canvas = None  # will hold FigureCanvasTkAgg
        r += 1

        # ---------- RIGHT: CHAMPS ANALYSE ----------
        right = ctk.CTkFrame(scroll, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        right.grid_columnconfigure(1, weight=1)
        r2 = 0

        r2 = self._add_section(right, "Résultats MetaSoft reportés", r2)
        r2 = self._add_metasoft_summary(right, r2)

        r2 = self._add_section(right, "Conseils d'Entraînement", r2)
        r2 = self._add_textfield(right, "conseils_entrainements", "Recommandations de séances", r2, height=200)

        r2 = self._add_section(right, "Notes Privées", r2)
        r2 = self._add_textfield(right, "notes_privees", "Notes internes (non visibles en front)", r2, height=150)

    # ------------------------------------------------------------------ #
    #  Summary refresh                                                    #
    # ------------------------------------------------------------------ #
    def _on_tab_changed(self, tab_name=None):
        """Called when active tab changes"""
        if self.tabview.get() == "Analyse":
            self._update_summary()

    def _update_summary(self):
        """Refresh read-only summary labels from current entries"""
        def _val(key):
            if key not in self.entries:
                return "—"
            w = self.entries[key]['widget']
            t = self.entries[key]['type']
            if t == 'textbox':
                v = w.get("1.0", "end-1c").strip()
            elif t == 'checkbox':
                return str(bool(w.get()))
            else:
                v = w.get().strip()
            return v if v else "—"

        mapping = {
            "sum_vo2max": "measured_vo2max",
            "sum_vma": "vma",
            "sum_fcmax": "max_hr",
            "sum_sv1_hr": "sv1_hr",
            "sum_sv1_speed": "sv1_speed",
            "sum_sv1_vo2": "sv1_vo2",
            "sum_sv2_hr": "sv2_hr",
            "sum_sv2_speed": "sv2_speed",
            "sum_sv2_vo2": "sv2_vo2",
            "sum_weight": "current_weight",
            "sum_sport": "sport_practiced",
        }
        for sum_key, entry_key in mapping.items():
            if sum_key in self.summary_labels:
                self.summary_labels[sum_key].configure(text=_val(entry_key))

        # ---------- Computed percentages ----------
        def _num(key):
            v = _val(key)
            if v == "—":
                return None
            try:
                return float(str(v).replace(",", "."))
            except (ValueError, TypeError):
                return None

        vo2max = _num("measured_vo2max")
        vma = _num("vma")
        fcmax = _num("max_hr")
        weight = _num("current_weight")

        # VO2 peak (L/min) = vo2max (ml/min/kg) * weight (kg) / 1000
        if vo2max is not None and weight is not None and weight > 0:
            vo2_peak = round(vo2max * weight / 1000, 2)
            self.summary_labels.get("sum_vo2_peak", ctk.CTkLabel(self)).configure(text=str(vo2_peak))
        else:
            if "sum_vo2_peak" in self.summary_labels:
                self.summary_labels["sum_vo2_peak"].configure(text="—")

        # SV1 percentages
        sv1_hr = _num("sv1_hr")
        sv1_speed = _num("sv1_speed")
        sv1_vo2 = _num("sv1_vo2")
        if sv1_hr is not None and fcmax is not None and fcmax > 0:
            self.summary_labels.get("sum_sv1_hr_pct", ctk.CTkLabel(self)).configure(
                text=f"{round(sv1_hr / fcmax * 100)}%")
        else:
            if "sum_sv1_hr_pct" in self.summary_labels:
                self.summary_labels["sum_sv1_hr_pct"].configure(text="—")
        if sv1_speed is not None and vma is not None and vma > 0:
            self.summary_labels.get("sum_sv1_speed_pct", ctk.CTkLabel(self)).configure(
                text=f"{round(sv1_speed / vma * 100)}%")
        else:
            if "sum_sv1_speed_pct" in self.summary_labels:
                self.summary_labels["sum_sv1_speed_pct"].configure(text="—")
        if sv1_vo2 is not None and vo2max is not None and vo2max > 0:
            self.summary_labels.get("sum_sv1_vo2_pct", ctk.CTkLabel(self)).configure(
                text=f"{round(sv1_vo2 / vo2max * 100)}%")
        else:
            if "sum_sv1_vo2_pct" in self.summary_labels:
                self.summary_labels["sum_sv1_vo2_pct"].configure(text="—")

        # SV2 percentages
        sv2_hr = _num("sv2_hr")
        sv2_speed = _num("sv2_speed")
        sv2_vo2 = _num("sv2_vo2")
        if sv2_hr is not None and fcmax is not None and fcmax > 0:
            self.summary_labels.get("sum_sv2_hr_pct", ctk.CTkLabel(self)).configure(
                text=f"{round(sv2_hr / fcmax * 100)}%")
        else:
            if "sum_sv2_hr_pct" in self.summary_labels:
                self.summary_labels["sum_sv2_hr_pct"].configure(text="—")
        if sv2_speed is not None and vma is not None and vma > 0:
            self.summary_labels.get("sum_sv2_speed_pct", ctk.CTkLabel(self)).configure(
                text=f"{round(sv2_speed / vma * 100)}%")
        else:
            if "sum_sv2_speed_pct" in self.summary_labels:
                self.summary_labels["sum_sv2_speed_pct"].configure(text="—")
        if sv2_vo2 is not None and vo2max is not None and vo2max > 0:
            self.summary_labels.get("sum_sv2_vo2_pct", ctk.CTkLabel(self)).configure(
                text=f"{round(sv2_vo2 / vo2max * 100)}%")
        else:
            if "sum_sv2_vo2_pct" in self.summary_labels:
                self.summary_labels["sum_sv2_vo2_pct"].configure(text="—")

        # Name composite
        ln = _val("last_name")
        fn = _val("first_name")
        name = f"{ln} {fn}".replace("—", "").strip()
        if "sum_name" in self.summary_labels:
            self.summary_labels["sum_name"].configure(text=name or "—")

        # ---------- Lactate graph ----------
        self._update_lactate_graph()

    def _update_lactate_graph(self):
        """Render or update the lactate vs speed graph from lactate entries."""
        # Clear previous canvas
        if self.lactate_canvas is not None:
            self.lactate_canvas.get_tk_widget().destroy()
            self.lactate_canvas = None

        # Gather data from lactate entries
        data = self._get_lactate_data()
        if len(data) < 2:
            # Not enough points — show placeholder
            placeholder = ctk.CTkLabel(
                self.lactate_graph_frame, text="Ajoutez au moins 2 mesures de lactate\npour afficher le graphique",
                text_color="gray", font=ctk.CTkFont(size=12))
            placeholder.grid(row=0, column=0, padx=20, pady=40)
            # Store reference to destroy later
            self._lactate_placeholder = placeholder
            return

        # Remove placeholder if present
        if hasattr(self, '_lactate_placeholder') and self._lactate_placeholder is not None:
            try:
                self._lactate_placeholder.destroy()
            except Exception:
                pass
            self._lactate_placeholder = None

        # Sort by speed
        data.sort(key=lambda d: d['speed'])
        speeds = [d['speed'] for d in data]
        lactates = [d['lactate_mmol_l'] for d in data]

        # Detect dark/light theme
        is_dark = ctk.get_appearance_mode() == "Dark"
        bg_color = "#2b2b2b" if is_dark else "#f0f0f0"
        text_color = "white" if is_dark else "black"
        grid_color = "#444444" if is_dark else "#cccccc"

        fig, ax = plt.subplots(figsize=(5, 2.8), dpi=100)
        fig.patch.set_facecolor(bg_color)
        ax.set_facecolor(bg_color)

        ax.plot(speeds, lactates, 'o-', color='#e74c3c', linewidth=2, markersize=6, label='Lactate')
        ax.set_xlabel("Vitesse (km/h)", color=text_color, fontsize=9)
        ax.set_ylabel("Lactate (mmol/L)", color=text_color, fontsize=9)
        ax.set_title("Profil Lactate", color=text_color, fontsize=11, fontweight='bold')
        ax.tick_params(colors=text_color, labelsize=8)
        ax.grid(True, alpha=0.3, color=grid_color)
        for spine in ax.spines.values():
            spine.set_color(grid_color)
        ax.legend(fontsize=8, facecolor=bg_color, edgecolor=grid_color, labelcolor=text_color)

        fig.tight_layout(pad=1.5)

        canvas = FigureCanvasTkAgg(fig, master=self.lactate_graph_frame)
        canvas.draw()
        canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        self.lactate_canvas = canvas
        plt.close(fig)

    # ================================================================== #
    #  Helper methods – create widgets                                    #
    # ================================================================== #
    def _add_email_field_with_lookup(self, frame, row: int) -> int:
        """Email field with a DB lookup button next to it."""
        lbl = ctk.CTkLabel(frame, text="Email (ID utilisateur) *", anchor="w")
        lbl.grid(row=row, column=0, padx=(0, 5), pady=2, sticky="w")

        email_frame = ctk.CTkFrame(frame, fg_color="transparent")
        email_frame.grid(row=row, column=1, pady=2, sticky="ew")
        email_frame.grid_columnconfigure(0, weight=1)

        entry = ctk.CTkEntry(email_frame, width=150)
        entry.grid(row=0, column=0, sticky="ew")
        self.entries["email"] = {'widget': entry, 'type': 'text'}
        entry.bind('<FocusOut>', lambda e: self._on_focus_out("email"))

        self.db_lookup_btn = ctk.CTkButton(
            email_frame, text="Rechercher", width=80, height=28,
            font=ctk.CTkFont(size=11),
            command=self._trigger_db_lookup,
        )
        self.db_lookup_btn.grid(row=0, column=1, padx=(5, 0))

        # Status label (shows result feedback)
        self.db_status_label = ctk.CTkLabel(
            frame, text="", font=ctk.CTkFont(size=11), text_color="gray"
        )
        self.db_status_label.grid(row=row + 1, column=0, columnspan=2, sticky="w", padx=5)

        return row + 2

    def _trigger_db_lookup(self):
        """Called when user clicks the DB lookup button."""
        email = self.entries.get("email", {}).get("widget")
        if email:
            email_val = email.get().strip()
            if email_val and self.on_db_lookup:
                self.on_db_lookup(email_val)
            elif not email_val:
                self.set_db_status("Saisissez un email d'abord", color="orange")

    def set_db_status(self, text: str, color: str = "gray"):
        """Update the status label under the email field."""
        if hasattr(self, "db_status_label"):
            self.db_status_label.configure(text=text, text_color=color)

    def _add_section(self, frame, title: str, row: int) -> int:
        lbl = ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(size=14, weight="bold"))
        lbl.grid(row=row, column=0, columnspan=2, pady=(15, 5), sticky="w")
        return row + 1

    def _add_subsection(self, frame, title: str, row: int) -> int:
        lbl = ctk.CTkLabel(frame, text=f"  {title}",
                           font=ctk.CTkFont(size=12, slant="italic"), text_color="gray")
        lbl.grid(row=row, column=0, columnspan=2, pady=(8, 2), sticky="w")
        return row + 1

    def _add_metasoft_summary(self, frame, row: int) -> int:
        """Ajoute les résumés liés aux sources officielles profil et sidecar EC."""
        container = ctk.CTkFrame(frame, fg_color="transparent")
        container.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 5))
        container.grid_columnconfigure(0, weight=1)

        for index, (key, title) in enumerate((
            ("lactate", "Lactates et seuils lactiques"),
            ("running_economy", "Économie de course"),
        )):
            block = ctk.CTkFrame(container, corner_radius=8)
            block.grid(row=index, column=0, sticky="ew", pady=4)
            block.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                block,
                text=title,
                anchor="w",
                font=ctk.CTkFont(size=13, weight="bold"),
            ).grid(row=0, column=0, padx=10, pady=(9, 3), sticky="w")
            status = ctk.CTkLabel(
                block,
                text="Non renseigné",
                corner_radius=6,
                fg_color="#48515f",
                text_color="#f2f5f7",
                font=ctk.CTkFont(size=11, weight="bold"),
            )
            status.grid(row=0, column=1, padx=10, pady=(9, 3), sticky="e")
            details = ctk.CTkLabel(
                block,
                text="Aucune donnée reportée.",
                anchor="w",
                justify="left",
                wraplength=520,
                text_color=("#475569", "#a8b1bd"),
            )
            details.grid(
                row=1,
                column=0,
                columnspan=2,
                padx=10,
                pady=(4, 10),
                sticky="ew",
            )
            self.metasoft_summary_widgets[key] = {
                "status": status,
                "details": details,
            }
        return row + 1

    def _add_field(self, frame, key: str, label: str, row: int, field_type: str = "text") -> int:
        lbl = ctk.CTkLabel(frame, text=label, anchor="w")
        lbl.grid(row=row, column=0, padx=(0, 5), pady=2, sticky="w")
        entry = ctk.CTkEntry(frame, width=150)
        entry.grid(row=row, column=1, pady=2, sticky="ew")
        self.entries[key] = {'widget': entry, 'type': field_type}
        entry.bind('<FocusOut>', lambda e, k=key: self._on_focus_out(k))
        return row + 1

    def _add_time_field(self, frame, key: str, label: str, row: int) -> int:
        lbl = ctk.CTkLabel(frame, text=label, anchor="w")
        lbl.grid(row=row, column=0, padx=(0, 5), pady=2, sticky="w")
        entry = ctk.CTkEntry(frame, width=100, placeholder_text="HH:MM:SS")
        entry.grid(row=row, column=1, pady=2, sticky="w")

        def on_focus_out(e):
            self._format_time_entry(entry)
            self._on_focus_out(key)

        entry.bind('<FocusOut>', on_focus_out)
        entry.bind('<Return>', lambda e, ent=entry: self._format_time_entry(ent))
        self.entries[key] = {'widget': entry, 'type': 'time'}
        return row + 1

    def _add_checkbox(self, frame, key: str, label: str, row: int) -> int:
        cb = ctk.CTkCheckBox(frame, text=label)
        cb.grid(row=row, column=0, columnspan=2, pady=5, sticky="w")
        self.entries[key] = {'widget': cb, 'type': 'checkbox'}
        return row + 1

    def _add_consent_checkbox(self, frame, key: str, label: str, row: int) -> int:
        cf = ctk.CTkFrame(frame, fg_color="transparent")
        cf.grid(row=row, column=0, columnspan=2, sticky="ew", pady=5)
        cf.grid_columnconfigure(1, weight=1)
        cb = ctk.CTkCheckBox(cf, text="", width=20)
        cb.grid(row=0, column=0, padx=(0, 10), sticky="nw")
        lw = ctk.CTkLabel(cf, text=label, wraplength=350, justify="left", anchor="w")
        lw.grid(row=0, column=1, sticky="w")
        self.entries[key] = {'widget': cb, 'type': 'checkbox'}
        return row + 1

    def _add_textfield(self, frame, key: str, label: str, row: int, height: int = 80) -> int:
        lbl = ctk.CTkLabel(frame, text=label, anchor="w")
        lbl.grid(row=row, column=0, columnspan=2, pady=(5, 2), sticky="w")
        tb = ctk.CTkTextbox(frame, height=height)
        tb.grid(row=row + 1, column=0, columnspan=2, pady=2, sticky="ew")
        self.entries[key] = {'widget': tb, 'type': 'textbox'}
        tb.bind('<FocusOut>', lambda e, k=key: self._on_focus_out(k))
        return row + 2

    # ---------- Protocol selector (dropdown + textbox) ----------
    def _add_protocol_selector(self, frame, row: int) -> int:
        """Add a protocol dropdown + description textbox combo."""
        # Dropdown row
        selector_frame = ctk.CTkFrame(frame, fg_color="transparent")
        selector_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(5, 2))
        selector_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(selector_frame, text="Protocole enregistré", anchor="w").grid(
            row=0, column=0, padx=(0, 8), sticky="w")

        protocol_names = self.protocol_store.list_names() if self.protocol_store else []
        values = ["— Aucun —"] + protocol_names

        self.protocol_combo = ctk.CTkComboBox(
            selector_frame, values=values,
            command=self._on_protocol_selected,
            state="readonly" if protocol_names else "disabled"
        )
        self.protocol_combo.set("— Aucun —")
        self.protocol_combo.grid(row=0, column=1, sticky="ew")
        row += 1

        # Description textbox (editable — user can still type freely)
        lbl = ctk.CTkLabel(frame, text="Description du test", anchor="w")
        lbl.grid(row=row, column=0, columnspan=2, pady=(5, 2), sticky="w")
        row += 1

        tb = ctk.CTkTextbox(frame, height=80)
        tb.grid(row=row, column=0, columnspan=2, pady=2, sticky="ew")
        self.entries['protocol_description'] = {'widget': tb, 'type': 'textbox'}
        tb.bind('<FocusOut>', lambda e: self._on_focus_out('protocol_description'))
        row += 1

        return row

    def _on_protocol_selected(self, choice: str):
        """When user picks a protocol from the dropdown, fill the description."""
        if choice == "— Aucun —" or not self.protocol_store:
            return
        description = self.protocol_store.get_description(choice)
        if description:
            tb = self.entries['protocol_description']['widget']
            tb.delete("1.0", "end")
            tb.insert("1.0", description)

    def refresh_protocol_list(self):
        """Refresh the protocol dropdown values (called after protocol manager closes)."""
        if not self.protocol_store:
            return
        protocol_names = self.protocol_store.list_names()
        values = ["— Aucun —"] + protocol_names
        self.protocol_combo.configure(
            values=values,
            state="readonly" if protocol_names else "disabled"
        )

    # ---------- Thresholds ----------
    def _add_thresholds(self, frame, row: int) -> int:
        tf = ctk.CTkFrame(frame, fg_color="transparent")
        tf.grid(row=row, column=0, columnspan=2, sticky="ew", pady=5)
        tf.grid_columnconfigure(0, weight=1)
        tf.grid_columnconfigure(1, weight=1)

        for col, prefix, title in [(0, "sv1", "SV1"), (1, "sv2", "SV2")]:
            card = ctk.CTkFrame(tf, corner_radius=8)
            card.grid(row=0, column=col, padx=5, sticky="nsew")
            ctk.CTkLabel(card, text=title, font=ctk.CTkFont(weight="bold")).grid(
                row=0, column=0, columnspan=2, pady=5)
            for i, (suffix, lbl) in enumerate([("_hr", "FC"), ("_speed", "Vitesse (km/h)"), ("_vo2", "VO2")]):
                k = f"{prefix}{suffix}"
                ctk.CTkLabel(card, text=lbl).grid(row=i + 1, column=0, padx=5, pady=2, sticky="w")
                e = ctk.CTkEntry(card, width=70)
                e.grid(row=i + 1, column=1, padx=5, pady=2)
                self.entries[k] = {'widget': e, 'type': 'number'}
                e.bind('<FocusOut>', lambda ev, key=k: self._on_focus_out(key))
            ctk.CTkLabel(card, text="").grid(row=4, pady=3)
        return row + 1

    # ---------- RSI ----------
    def _add_rsi(self, frame, row: int) -> int:
        rf = ctk.CTkFrame(frame, fg_color="transparent")
        rf.grid(row=row, column=0, columnspan=2, sticky="ew", pady=5)
        rf.grid_columnconfigure(0, weight=1)
        rf.grid_columnconfigure(1, weight=1)

        for col, suffix, title in [(0, "avant", "Avant"), (1, "apres", "Après")]:
            card = ctk.CTkFrame(rf, corner_radius=8)
            card.grid(row=0, column=col, padx=5, sticky="nsew")
            ctk.CTkLabel(card, text=title, font=ctk.CTkFont(weight="bold")).grid(
                row=0, column=0, columnspan=2, pady=5)
            k = f"rsi_{suffix}"
            ctk.CTkLabel(card, text="RSI").grid(row=1, column=0, padx=5, pady=2, sticky="w")
            e = ctk.CTkEntry(card, width=70)
            e.grid(row=1, column=1, padx=5, pady=2)
            self.entries[k] = {'widget': e, 'type': 'number'}
            e.bind('<FocusOut>', lambda ev, key=k: self._on_focus_out(key))
            ctk.CTkLabel(card, text="").grid(row=2, pady=3)
        return row + 1

    # ---------- CMJ ----------
    def _add_cmj(self, frame, row: int) -> int:
        cf = ctk.CTkFrame(frame, fg_color="transparent")
        cf.grid(row=row, column=0, columnspan=2, sticky="ew", pady=5)
        cf.grid_columnconfigure(0, weight=1)
        cf.grid_columnconfigure(1, weight=1)

        for col, suffix, title in [(0, "avant", "Avant Test"), (1, "apres", "Après Test")]:
            card = ctk.CTkFrame(cf, corner_radius=8)
            card.grid(row=0, column=col, padx=5, sticky="nsew")
            ctk.CTkLabel(card, text=title, font=ctk.CTkFont(weight="bold")).grid(
                row=0, column=0, columnspan=2, pady=5)
            for i, (field, lbl) in enumerate([
                ("hauteur", "Hauteur (cm)"),
                ("force", "Force max (kgf/kg)"),
                ("puissance", "Puissance max (W/kg)"),
            ]):
                k = f"cmj_{suffix}_{field}"
                ctk.CTkLabel(card, text=lbl).grid(row=i + 1, column=0, padx=5, pady=2, sticky="w")
                e = ctk.CTkEntry(card, width=70)
                e.grid(row=i + 1, column=1, padx=5, pady=2)
                self.entries[k] = {'widget': e, 'type': 'number'}
                e.bind('<FocusOut>', lambda ev, key=k: self._on_focus_out(key))
            ctk.CTkLabel(card, text="").grid(row=4, pady=3)
        return row + 1

    # ---------- Lactate ----------
    def _add_lactate(self, frame, row: int) -> int:
        self.lactate_frame = ctk.CTkFrame(frame, fg_color="transparent")
        self.lactate_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=5)
        add_btn = ctk.CTkButton(self.lactate_frame, text="+ Ajouter mesure", width=130,
                                command=self._add_lactate_entry)
        add_btn.grid(row=0, column=0, pady=3, sticky="w")
        return row + 1

    def _add_lactate_entry(self):
        self.lactate_thresholds = {}
        row = len(self.lactate_entries) + 1
        ef = ctk.CTkFrame(self.lactate_frame, fg_color="transparent")
        ef.grid(row=row, column=0, columnspan=3, sticky="ew", pady=2)
        ef.grid_columnconfigure(1, weight=1)
        ef.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(ef, text="Vitesse (km/h):", width=100).grid(row=0, column=0, padx=(0, 5))
        se = ctk.CTkEntry(ef, width=80)
        se.grid(row=0, column=1, padx=5)

        ctk.CTkLabel(ef, text="Lactate (mmol/L):", width=110).grid(row=0, column=2, padx=(15, 5))
        le = ctk.CTkEntry(ef, width=80)
        le.grid(row=0, column=3, padx=5)

        rb = ctk.CTkButton(ef, text="x", width=30, fg_color="#c0392b", hover_color="#922b21",
                           command=lambda: self._remove_lactate_entry(ef))
        rb.grid(row=0, column=4, padx=5)

        self.lactate_entries.append({'frame': ef, 'speed': se, 'lactate': le})

    def _remove_lactate_entry(self, frame):
        for i, entry in enumerate(self.lactate_entries):
            if entry['frame'] == frame:
                frame.destroy()
                self.lactate_entries.pop(i)
                self.lactate_thresholds = {}
                break

    def _get_lactate_data(self) -> List[Dict]:
        measurements = []
        for entry in self.lactate_entries:
            try:
                sv = entry['speed'].get().replace(',', '.')
                lv = entry['lactate'].get().replace(',', '.')
                if (sv and lv) or entry.get('enabled') is False:
                    measurement = {
                        'speed': float(sv) if sv else None,
                        'lactate_mmol_l': float(lv) if lv else None,
                    }
                    for key in (
                        'type', 'order', 'enabled', 'source', 'label',
                        'stage_index', 'phase', 'time_seconds', 'delay_minutes',
                    ):
                        if entry.get(key) is not None:
                            measurement[key] = entry[key]
                    measurements.append(measurement)
            except ValueError:
                pass
        return measurements

    def _set_lactate_data(self, measurements: List[Dict]):
        for entry in self.lactate_entries[:]:
            entry['frame'].destroy()
        self.lactate_entries.clear()
        for m in measurements:
            self._add_lactate_entry()
            idx = len(self.lactate_entries) - 1
            if m.get('speed') is not None:
                self.lactate_entries[idx]['speed'].insert(0, str(m['speed']))
            if m.get('lactate_mmol_l') is not None:
                self.lactate_entries[idx]['lactate'].insert(0, str(m['lactate_mmol_l']))
            for key in (
                'type', 'order', 'enabled', 'source', 'label',
                'stage_index', 'phase', 'time_seconds', 'delay_minutes',
            ):
                if m.get(key) is not None:
                    self.lactate_entries[idx][key] = m[key]

    def _clear_lactate(self):
        for entry in self.lactate_entries[:]:
            entry['frame'].destroy()
        self.lactate_entries.clear()
        self.lactate_thresholds = {}

    # ------------------------------------------------------------------ #
    #  Time formatting                                                    #
    # ------------------------------------------------------------------ #
    def _format_time_entry(self, entry):
        value = entry.get().strip()
        if not value:
            return
        clean = value.replace(':', '').replace(' ', '')
        if clean.isdigit():
            clean = clean.zfill(6)
            if len(clean) >= 6:
                formatted = f"{clean[:2]}:{clean[2:4]}:{clean[4:6]}"
                entry.delete(0, 'end')
                entry.insert(0, formatted)

    # ================================================================== #
    #  Data I/O  (same interface as InputForm)                            #
    # ================================================================== #
    def get_data(self) -> Dict[str, Any]:
        data = {}
        for key, entry_info in self.entries.items():
            widget = entry_info['widget']
            field_type = entry_info['type']

            if field_type == 'textbox':
                value = widget.get("1.0", "end-1c")
            elif field_type == 'checkbox':
                value = widget.get()
            else:
                value = widget.get()

            if field_type == 'number' and value:
                try:
                    value = float(str(value).replace(',', '.'))
                    if value == int(value):
                        value = int(value)
                except ValueError:
                    value = None
            elif field_type == 'checkbox':
                value = bool(value)
            elif not value:
                value = None

            data[key] = value

        return self._structure_data(data, self._get_lactate_data())

    def set_data(self, data: Dict[str, Any]):
        flat = {}
        flat['email'] = data.get('email', '')

        # Consentements
        consent = data.get('consentements', {})
        flat['consent_risques'] = consent.get('risques', False)
        flat['consent_donnees'] = consent.get('donnees', False)
        flat['consent_anonyme'] = consent.get('anonyme', False)
        flat['consent_image'] = consent.get('image', False)

        identity = data.get('identity', {})
        flat['last_name'] = identity.get('last_name', '')
        flat['first_name'] = identity.get('first_name', '')
        flat['date_of_birth'] = identity.get('date_of_birth', '')
        flat['age'] = identity.get('age', '')
        flat['sport_practiced'] = identity.get('sport_practiced', '')
        flat['specialty'] = identity.get('specialty', '')
        flat['has_coach'] = identity.get('has_coach', False)

        body = data.get('body_composition', {})
        flat['height_cm'] = body.get('height_cm', '')
        flat['current_weight'] = body.get('current_weight', '')
        flat['weight_before_test'] = body.get('weight_before_test', '')
        flat['weight_after_test'] = body.get('weight_after_test', '')

        prof = data.get('professional_life', {})
        flat['job_title'] = prof.get('job_title', '')
        flat['working_hours_per_week'] = prof.get('working_hours_per_week', '')

        equip = data.get('equipment_and_tracking', {})
        flat['watch_brand'] = equip.get('watch_brand', '')
        flat['watch_estimated_vo2'] = equip.get('watch_estimated_vo2', '')
        flat['min_hr_before'] = equip.get('min_hr_before', '')
        flat['max_hr_ever'] = equip.get('max_hr_ever', '')
        flat['average_weekly_volume'] = equip.get('average_weekly_volume', '')

        preds = equip.get('watch_race_predictions', {})
        flat['prediction_5k'] = preds.get('5k', '')
        flat['prediction_10k'] = preds.get('10k', '')
        flat['prediction_half'] = preds.get('half_marathon', '')
        flat['prediction_marathon'] = preds.get('marathon', '')

        hist = data.get('history_and_goals', {})
        recs = hist.get('personal_records', {})
        flat['record_5k'] = recs.get('5k', '')
        flat['record_10k'] = recs.get('10k', '')
        flat['record_half'] = recs.get('half_marathon', '')
        flat['record_marathon'] = recs.get('marathon', '')
        flat['utmb_index'] = hist.get('utmb_index', '')
        flat['upcoming_goals'] = hist.get('upcoming_goals', '')

        flat['seance_veille'] = data.get('seance_veille', '')
        flat['observations'] = data.get('observations', '')
        flat['protocol_description'] = data.get('protocol_description', '')

        stress = data.get('stress_test_results', {})
        thresholds = stress.get('thresholds', {})
        sv1 = thresholds.get('sv1', {})
        sv2 = thresholds.get('sv2', {})
        flat['sv1_hr'] = sv1.get('hr_bpm', '')
        flat['sv1_speed'] = sv1.get('pace_km_h', '')
        flat['sv1_vo2'] = sv1.get('vo2_ml_kg_min', '')
        flat['sv2_hr'] = sv2.get('hr_bpm', '')
        flat['sv2_speed'] = sv2.get('pace_km_h', '')
        flat['sv2_vo2'] = sv2.get('vo2_ml_kg_min', '')
        flat['measured_vo2max'] = stress.get('measured_vo2max', '')
        flat['max_hr'] = stress.get('max_hr', '')
        flat['vma'] = stress.get('vma', '')
        flat['first_stage_speed'] = stress.get('first_stage_speed', '')
        flat['last_stage_speed'] = stress.get('last_stage_speed', '')

        flat['conseils_entrainements'] = data.get('conseils_entrainements', '')

        rsi = data.get('rsi', {})
        flat['rsi_avant'] = rsi.get('avant', '')
        flat['rsi_apres'] = rsi.get('apres', '')

        cmj = data.get('cmj', {})
        cmja = cmj.get('avant', {})
        flat['cmj_avant_hauteur'] = cmja.get('hauteur_cm', '')
        flat['cmj_avant_force'] = cmja.get('force_max_kfg_kg', '')
        flat['cmj_avant_puissance'] = cmja.get('puissance_max_w_kg', '')
        cmjp = cmj.get('apres', {})
        flat['cmj_apres_hauteur'] = cmjp.get('hauteur_cm', '')
        flat['cmj_apres_force'] = cmjp.get('force_max_kfg_kg', '')
        flat['cmj_apres_puissance'] = cmjp.get('puissance_max_w_kg', '')

        flat['notes_privees'] = data.get('notes_privees', '')
        flat['altitude_vie'] = data.get('altitude_vie_m', '')

        spo2 = data.get('spo2', {})
        flat['spo2_avant'] = spo2.get('avant', '')
        flat['spo2_apres'] = spo2.get('apres', '')
        flat['lactatemie_repos'] = data.get('lactatemie_repos', '')

        # Apply to widgets
        for key, value in flat.items():
            if key in self.entries:
                ei = self.entries[key]
                w = ei['widget']
                if ei['type'] == 'textbox':
                    w.delete("1.0", "end")
                    if value:
                        w.insert("1.0", str(value))
                elif ei['type'] == 'checkbox':
                    if value:
                        w.select()
                    else:
                        w.deselect()
                else:
                    w.delete(0, "end")
                    if value is not None and value != '':
                        w.insert(0, str(value))

        # Lactate
        lactate_data = data.get('stress_test_results', {}).get('lactate_profile', [])
        self._set_lactate_data(lactate_data)
        self.lactate_thresholds = dict(
            data.get('stress_test_results', {}).get('lactate_thresholds', {})
        )

        # Refresh summary if on Analyse tab
        self._update_summary()

    def set_metasoft_context(
        self,
        profile: Dict[str, Any],
        economy_state: Dict[str, Any],
        matched: bool,
    ) -> None:
        """Affiche les résultats reportés sans recalculer ni modifier leurs sources."""
        summary = build_profile_metasoft_summary(profile, economy_state, matched)
        tone_colors = {
            "success": "#167d5b",
            "warning": "#946817",
            "danger": "#a3434b",
            "muted": "#48515f",
        }
        for key, content in summary.items():
            widgets = self.metasoft_summary_widgets.get(key)
            if not widgets:
                continue
            widgets["status"].configure(
                text=content["status"],
                fg_color=tone_colors.get(content["tone"], tone_colors["muted"]),
            )
            widgets["details"].configure(text="\n".join(content["lines"]))

    def clear(self):
        for ei in self.entries.values():
            w = ei['widget']
            if ei['type'] == 'textbox':
                w.delete("1.0", "end")
            elif ei['type'] == 'checkbox':
                w.deselect()
            else:
                w.delete(0, "end")
        self._clear_lactate()
        # Reset summary
        for lbl in self.summary_labels.values():
            lbl.configure(text="—")
        self.set_metasoft_context({}, {"status": "missing"}, matched=False)
        # Reset DB status
        self.set_db_status("")

    def merge_db_data(self, db_profile: Dict[str, Any]):
        """
        Merge data from a DB user profile into the form.
        Only fills fields that are currently EMPTY, preserving user input.
        Uses set_data's flatten logic but skips non-empty widgets.
        """
        # Temporarily get current data to determine what's empty
        # Then set only empty fields from db_profile via set_data path
        flat = self._flatten_profile(db_profile)

        filled = 0
        for key, value in flat.items():
            if key not in self.entries:
                continue
            if value is None or value == '' or value is False:
                continue

            ei = self.entries[key]
            w = ei['widget']

            # Check if widget is currently empty
            if ei['type'] == 'textbox':
                current = w.get("1.0", "end-1c").strip()
            elif ei['type'] == 'checkbox':
                current = w.get()
            else:
                current = w.get().strip()

            if current:  # already has data -> skip
                continue

            # Fill with DB value
            if ei['type'] == 'textbox':
                w.insert("1.0", str(value))
            elif ei['type'] == 'checkbox':
                if value:
                    w.select()
            else:
                w.insert(0, str(value))

            filled += 1

        self._update_summary()
        return filled

    def _flatten_profile(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Flatten a profile dict to flat key->value for widget mapping."""
        flat = {}
        flat['email'] = data.get('email', '')

        consent = data.get('consentements', {})
        flat['consent_risques'] = consent.get('risques', False)
        flat['consent_donnees'] = consent.get('donnees', False)
        flat['consent_anonyme'] = consent.get('anonyme', False)
        flat['consent_image'] = consent.get('image', False)

        identity = data.get('identity', {})
        flat['last_name'] = identity.get('last_name', '')
        flat['first_name'] = identity.get('first_name', '')
        flat['date_of_birth'] = identity.get('date_of_birth', '')
        flat['age'] = identity.get('age', '')
        flat['sport_practiced'] = identity.get('sport_practiced', '')
        flat['specialty'] = identity.get('specialty', '')
        flat['has_coach'] = identity.get('has_coach', False)

        body = data.get('body_composition', {})
        flat['height_cm'] = body.get('height_cm', '')
        flat['current_weight'] = body.get('current_weight', '')
        flat['weight_before_test'] = body.get('weight_before_test', '')
        flat['weight_after_test'] = body.get('weight_after_test', '')

        prof = data.get('professional_life', {})
        flat['job_title'] = prof.get('job_title', '')
        flat['working_hours_per_week'] = prof.get('working_hours_per_week', '')

        equip = data.get('equipment_and_tracking', {})
        flat['watch_brand'] = equip.get('watch_brand', '')
        flat['watch_estimated_vo2'] = equip.get('watch_estimated_vo2', '')
        flat['min_hr_before'] = equip.get('min_hr_before', '')
        flat['max_hr_ever'] = equip.get('max_hr_ever', '')
        flat['average_weekly_volume'] = equip.get('average_weekly_volume', '')

        preds = equip.get('watch_race_predictions', {})
        flat['prediction_5k'] = preds.get('5k', '')
        flat['prediction_10k'] = preds.get('10k', '')
        flat['prediction_half'] = preds.get('half_marathon', '')
        flat['prediction_marathon'] = preds.get('marathon', '')

        hist = data.get('history_and_goals', {})
        recs = hist.get('personal_records', {})
        flat['record_5k'] = recs.get('5k', '')
        flat['record_10k'] = recs.get('10k', '')
        flat['record_half'] = recs.get('half_marathon', '')
        flat['record_marathon'] = recs.get('marathon', '')
        flat['utmb_index'] = hist.get('utmb_index', '')
        flat['upcoming_goals'] = hist.get('upcoming_goals', '')

        flat['altitude_vie'] = data.get('altitude_vie_m', '')

        spo2 = data.get('spo2', {})
        flat['spo2_avant'] = spo2.get('avant', '')
        flat['spo2_apres'] = spo2.get('apres', '')
        flat['lactatemie_repos'] = data.get('lactatemie_repos', '')

        return flat

    # ================================================================== #
    #  Validation                                                         #
    # ================================================================== #
    def validate_all(self) -> tuple:
        data = self.get_data()
        try:
            ProfileFormModel(**data)
            self._reset_all_borders()
            return True, "Données valides"
        except ValidationError as e:
            self._handle_validation_errors(e)
            return False, "Le formulaire contient des erreurs"

    def _reset_all_borders(self):
        for entry in self.entries.values():
            if hasattr(entry['widget'], 'configure'):
                try:
                    entry['widget'].configure(border_color=("gray70", "gray30"))
                except Exception:
                    pass

    def _handle_validation_errors(self, error: ValidationError):
        self._reset_all_borders()
        for err in error.errors():
            loc = err['loc']
            for key, path in self.field_mapping.items():
                if path == loc:
                    self._mark_invalid(key, err['msg'])
                    break

    def _mark_invalid(self, key, msg):
        if key in self.entries:
            widget = self.entries[key]['widget']
            if hasattr(widget, 'configure'):
                try:
                    widget.configure(border_color="red")
                except Exception:
                    pass

    def _on_focus_out(self, key):
        data = self.get_data()
        try:
            ProfileFormModel(**data)
            if key in self.entries:
                self.entries[key]['widget'].configure(border_color=("gray70", "gray30"))
        except ValidationError as e:
            is_valid = True
            target_path = self.field_mapping.get(key)
            if target_path:
                for err in e.errors():
                    if err['loc'] == target_path:
                        self._mark_invalid(key, err['msg'])
                        is_valid = False
                        break
            if is_valid and key in self.entries:
                self.entries[key]['widget'].configure(border_color=("gray70", "gray30"))

    # ------------------------------------------------------------------ #
    #  Data structuring  (flat -> nested dict)                            #
    # ------------------------------------------------------------------ #
    def _structure_data(self, flat_data: Dict, lactate_data: List[Dict]) -> Dict[str, Any]:
        has_coach = flat_data.get('has_coach', False)
        if isinstance(has_coach, str):
            has_coach = has_coach.lower() in ('oui', 'yes', 'true', '1')

        return {
            'email': flat_data.get('email', ''),
            'consentements': {
                'risques': flat_data.get('consent_risques', False),
                'donnees': flat_data.get('consent_donnees', False),
                'anonyme': flat_data.get('consent_anonyme', False),
                'image': flat_data.get('consent_image', False),
            },
            'identity': {
                'last_name': flat_data.get('last_name', ''),
                'first_name': flat_data.get('first_name', ''),
                'date_of_birth': flat_data.get('date_of_birth', ''),
                'age': flat_data.get('age'),
                'sport_practiced': flat_data.get('sport_practiced', ''),
                'specialty': flat_data.get('specialty', ''),
                'has_coach': has_coach,
            },
            'body_composition': {
                'height_cm': flat_data.get('height_cm'),
                'current_weight': flat_data.get('current_weight'),
                'weight_before_test': flat_data.get('weight_before_test'),
                'weight_after_test': flat_data.get('weight_after_test'),
            },
            'professional_life': {
                'job_title': flat_data.get('job_title', ''),
                'working_hours_per_week': flat_data.get('working_hours_per_week'),
            },
            'equipment_and_tracking': {
                'watch_brand': flat_data.get('watch_brand', ''),
                'watch_estimated_vo2': flat_data.get('watch_estimated_vo2'),
                'min_hr_before': flat_data.get('min_hr_before'),
                'max_hr_ever': flat_data.get('max_hr_ever'),
                'average_weekly_volume': flat_data.get('average_weekly_volume', ''),
                'watch_race_predictions': {
                    '5k': flat_data.get('prediction_5k', ''),
                    '10k': flat_data.get('prediction_10k', ''),
                    'half_marathon': flat_data.get('prediction_half', ''),
                    'marathon': flat_data.get('prediction_marathon', ''),
                },
            },
            'history_and_goals': {
                'personal_records': {
                    '5k': flat_data.get('record_5k', ''),
                    '10k': flat_data.get('record_10k', ''),
                    'half_marathon': flat_data.get('record_half', ''),
                    'marathon': flat_data.get('record_marathon', ''),
                },
                'utmb_index': flat_data.get('utmb_index'),
                'upcoming_goals': flat_data.get('upcoming_goals', ''),
            },
            'seance_veille': flat_data.get('seance_veille', ''),
            'observations': flat_data.get('observations', ''),
            'protocol_description': flat_data.get('protocol_description', ''),
            'stress_test_results': {
                'thresholds': {
                    'sv1': {
                        'hr_bpm': flat_data.get('sv1_hr'),
                        'pace_km_h': flat_data.get('sv1_speed'),
                        'vo2_ml_kg_min': flat_data.get('sv1_vo2'),
                    },
                    'sv2': {
                        'hr_bpm': flat_data.get('sv2_hr'),
                        'pace_km_h': flat_data.get('sv2_speed'),
                        'vo2_ml_kg_min': flat_data.get('sv2_vo2'),
                    },
                },
                'measured_vo2max': flat_data.get('measured_vo2max'),
                'max_hr': flat_data.get('max_hr'),
                'vma': flat_data.get('vma'),
                'first_stage_speed': flat_data.get('first_stage_speed'),
                'last_stage_speed': flat_data.get('last_stage_speed'),
                'lactate_profile': lactate_data,
                'lactate_thresholds': self._resolved_lactate_thresholds(lactate_data),
            },
            'conseils_entrainements': flat_data.get('conseils_entrainements', ''),
            'rsi': {
                'avant': flat_data.get('rsi_avant'),
                'apres': flat_data.get('rsi_apres'),
            },
            'cmj': {
                'avant': {
                    'hauteur_cm': flat_data.get('cmj_avant_hauteur'),
                    'force_max_kfg_kg': flat_data.get('cmj_avant_force'),
                    'puissance_max_w_kg': flat_data.get('cmj_avant_puissance'),
                },
                'apres': {
                    'hauteur_cm': flat_data.get('cmj_apres_hauteur'),
                    'force_max_kfg_kg': flat_data.get('cmj_apres_force'),
                    'puissance_max_w_kg': flat_data.get('cmj_apres_puissance'),
                },
            },
            'notes_privees': flat_data.get('notes_privees', ''),
            'altitude_vie_m': flat_data.get('altitude_vie'),
            'spo2': {
                'avant': flat_data.get('spo2_avant'),
                'apres': flat_data.get('spo2_apres'),
            },
            'lactatemie_repos': flat_data.get('lactatemie_repos'),
        }

    def _resolved_lactate_thresholds(self, measurements: List[Dict]) -> Dict[str, Any]:
        """Resynchronise les seuils React si une valeur lactate a ete editee ici."""
        resolved = {}
        for name, threshold in self.lactate_thresholds.items():
            if not isinstance(threshold, dict):
                continue
            index = threshold.get('measurement_index')
            if not isinstance(index, int):
                # Les seuils React continus sont independants d'un prelevement;
                # une sauvegarde Tk doit les conserver sans leur inventer d'index.
                if threshold.get('mode') in {'point', 'range'}:
                    resolved[name] = dict(threshold)
                continue
            if not 0 <= index < len(measurements):
                continue
            resolved[name] = {
                'measurement_index': index,
                **measurements[index],
            }
        return resolved
