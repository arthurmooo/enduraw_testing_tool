"""
Transformation XML/profil vers le JSON attendu par Valentin.

Le module assemble les donnees saisies localement et les mesures MetaSoft. Les
graphes peuvent venir du parser historique (`measurements`) ou du parser
normalise (`metasoft_analysis.points`). Les seuils restent issus du profil
coach pour eviter tout fallback silencieux depuis des marqueurs non valides.
"""
from datetime import datetime
from math import isfinite
from typing import Dict, List, Any, Optional

from core.models import (
    TestResult, Seuil, VO2Max, VMA, PatientInfo,
    GraphCurve, Graph, ZoneSeuil
)
from core.metasoft_analysis import build_metasoft_analysis
from config import GRAPH_COLORS, GRAPH_INTERVAL_SECONDS


class DataTransformer:
    """Assemble le profil local et les mesures XML dans le JSON d'export."""
    
    def transform(
        self,
        xml_data: Dict[str, Any],
        manual_input: Dict[str, Any],
        manual_running_economy: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Transforme un XML parse et un profil saisi vers le payload final."""
        # Identite export: le XML garde le nom de test si le profil est incomplet.
        filename_data = xml_data.get('filename_data', {})
        patient_data = xml_data.get('patient_data', {})
        
        last_name = patient_data.get('Nom', filename_data.get('last_name', ''))
        first_name = patient_data.get('Prénom', filename_data.get('first_name', ''))
        athlete_name = f"{last_name} {first_name}".strip()
        
        result = TestResult()
        result.user_id = manual_input.get('email', '')
        result.athlete_name = athlete_name
        metasoft_analysis = self._metasoft_analysis_for_export(xml_data, manual_input)
        result.test_date = (
            filename_data.get('date')
            or metasoft_analysis.get('test', {}).get('date', '')
            or self._test_date_from_metadata(xml_data.get('test_metadata', {}))
        )
        result.test_type = "VO2max"
        
        consentements = manual_input.get('consentements', {})
        result.consentements = {
            'risques': consentements.get('risques', False),
            'donnees': consentements.get('donnees', False),
            'anonyme': consentements.get('anonyme', False)
        }
        
        # Seuils: valeurs coach, avec poids MetaSoft prioritaire pour convertir la VO2 XML.
        result.seuils = self._build_seuils(
            xml_data.get('summary_data', {}),
            manual_input,
            metasoft_analysis,
        )
        
        result.protocole = self._build_protocole(xml_data, manual_input)
        
        result.test_lactate = self._build_test_lactate(manual_input)
        result.observations_lactate = manual_input.get('observations_lactate', '')
        
        result.patient_info = self._build_patient_info(xml_data, manual_input)
        
        result.conseils_entrainements = manual_input.get('conseils_entrainements', '')
        
        # Source graphe prioritaire: points normalises MetaSoft, units natives.
        # Fallback: ancienne structure `measurements` pour les exports existants.
        metasoft_points = metasoft_analysis.get('points', [])
        if metasoft_points:
            result.graphiques = self._build_graphiques_from_metasoft_points(
                metasoft_points,
                result.seuils
            )
        else:
            result.graphiques = self._build_graphiques(
                xml_data.get('measurements', []),
                result.seuils
            )
        if manual_running_economy and manual_running_economy.get("rows"):
            # Source sidecar EC; Valentin filtre `enabled: false`, sans statut legacy = actif.
            enabled_by_stage = {
                item.get("stage_index"): item.get("enabled")
                for item in manual_running_economy.get("stage_selections") or []
                if isinstance(item, dict)
            }
            rows = [
                row for row in manual_running_economy["rows"]
                if enabled_by_stage.get(row.get("stage_index"), True) is not False
            ]
            if rows:
                result.running_economy_manual = {
                    **manual_running_economy,
                    "rows": rows,
                }
        
        # Logos and partners (placeholders)
        result.logos = {
            "logo_gauche": "assets/logos/logo1.png",
            "logo_droit": "assets/logos/logo1.png"
        }
        result.partenaires = {
            "titre": "Nos Partenaires",
            "logos": []
        }
        
        return result.to_dict()

    def _metasoft_analysis_for_export(
        self,
        xml_data: Dict[str, Any],
        manual_input: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Recalcule l'analyse si le XML n'a pas de masse mais le profil oui."""
        metasoft_analysis = xml_data.get('metasoft_analysis', {})
        metasoft_parsed = xml_data.get('metasoft_parsed')
        if not metasoft_parsed:
            return metasoft_analysis

        xml_mass = self._safe_float(
            metasoft_parsed.get('athlete', {}).get('weight_kg')
        )
        manual_mass = self._safe_float(
            manual_input.get('body_composition', {}).get('current_weight')
        )
        if xml_mass is None and manual_mass is not None and manual_mass > 0:
            # Fallback source: profil local matche au XML, uniquement si masse XML absente.
            metasoft_analysis = build_metasoft_analysis(
                metasoft_parsed,
                manual_mass_kg=manual_mass,
            )
            xml_data['metasoft_analysis'] = metasoft_analysis
        return metasoft_analysis

    def _test_date_from_metadata(self, test_metadata: Dict[str, Any]) -> str:
        """Extrait YYYY-MM-DD depuis `Heure de debut` MetaSoft si parsable."""
        for key, value in test_metadata.items():
            normalized = key.lower().replace("é", "e").replace("è", "e")
            if "debut" not in normalized and "start" not in normalized:
                continue
            parsed = self._parse_ddmmyyyy_date(value)
            if parsed:
                return parsed
        return ''

    def _parse_ddmmyyyy_date(self, value: Any) -> str:
        """Convertit `DD/MM/YYYY ...` sans inventer de date si le format diverge."""
        if not value:
            return ''
        date_token = str(value).strip().split()[0]
        try:
            return datetime.strptime(date_token, "%d/%m/%Y").strftime("%Y-%m-%d")
        except ValueError:
            return ''
    
    def _build_seuils(
        self,
        summary_data: Dict[str, Any],
        manual_input: Dict[str, Any],
        metasoft_analysis: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Construit les seuils depuis le profil, sans reconstruire de marqueur XML."""
        seuils = {}
        
        stress_results = manual_input.get('stress_test_results', {})
        thresholds = stress_results.get('thresholds', {})
        sv1_data = thresholds.get('sv1', {})
        sv2_data = thresholds.get('sv2', {})
        
        # Source: champs valides par le coach dans le formulaire local.
        vma_value = stress_results.get('vma')
        fc_max_value = self._round_bpm(stress_results.get('max_hr'))
        vo2max_value = stress_results.get('measured_vo2max')
        
        sv1 = Seuil()
        sv1.fc = self._round_bpm(sv1_data.get('hr_bpm'))
        sv1.allure = sv1_data.get('pace_km_h')
        sv1.vo2 = sv1_data.get('vo2_ml_kg_min')
        
        if sv1.allure and vma_value:
            sv1.pourcentage_vma = int((sv1.allure / vma_value) * 100)
        
        # Unites: FC bpm, vitesse km/h, VO2 ml/kg/min; pourcentages entiers.
        sv1_dict = sv1.to_dict()
        if sv1.fc and fc_max_value:
            sv1_dict['pourcentage_fc_max'] = int((sv1.fc / fc_max_value) * 100)
        if sv1.vo2 and vo2max_value:
            sv1_dict['pourcentage_vo2max'] = int((sv1.vo2 / vo2max_value) * 100)
        seuils['SV1'] = sv1_dict
        
        sv2 = Seuil()
        sv2.fc = self._round_bpm(sv2_data.get('hr_bpm'))
        sv2.allure = sv2_data.get('pace_km_h')
        sv2.vo2 = sv2_data.get('vo2_ml_kg_min')
        
        if sv2.allure and vma_value:
            sv2.pourcentage_vma = int((sv2.allure / vma_value) * 100)
        
        # Meme contrat que SV1: pas de fallback depuis les courbes brutes.
        sv2_dict = sv2.to_dict()
        if sv2.fc and fc_max_value:
            sv2_dict['pourcentage_fc_max'] = int((sv2.fc / fc_max_value) * 100)
        if sv2.vo2 and vo2max_value:
            sv2_dict['pourcentage_vo2max'] = int((sv2.vo2 / vo2max_value) * 100)
        seuils['SV2'] = sv2_dict
        
        vo2max = VO2Max()
        vo2max.valeur = vo2max_value
        vo2max.fc_max = fc_max_value
        vo2max_dict = vo2max.to_dict()
        
        # Source VO2: test XML/MetaSoft en ml/kg/min; poids XML kg prioritaire,
        # poids profil kg seulement si MetaSoft n'en fournit pas d'exploitable.
        xml_weight = self._positive_float(
            (metasoft_analysis or {}).get('athlete', {}).get('weight_kg')
        )
        profile_weight = self._positive_float(
            manual_input.get('body_composition', {}).get('current_weight')
        )
        weight = xml_weight or profile_weight
        if vo2max_value and weight is not None:
            vo2max_dict['vo2_peak_l_min'] = round(vo2max_value * weight / 1000, 2)
        
        seuils['VO2_max'] = vo2max_dict
        
        vma = VMA()
        vma.valeur = vma_value
        seuils['VMA'] = vma.to_dict()
        
        return seuils
    
    def _build_protocole(
        self,
        xml_data: Dict[str, Any],
        manual_input: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Construit le protocole depuis la saisie coach uniquement."""
        first_speed = manual_input.get('stress_test_results', {}).get(
            'first_stage_speed'
        )
        description = manual_input.get('protocol_description', '')
        
        return {
            "vitesse_depart_test": first_speed,
            "description": description
        }
    
    def _build_test_lactate(self, manual_input: Dict[str, Any]) -> Dict[str, Any]:
        """Construit le bloc lactate depuis la saisie locale."""
        lactate_profile = manual_input.get('stress_test_results', {}).get('lactate_profile', [])
        
        mesures = []
        for entry in lactate_profile:
            if entry.get('speed') is not None and entry.get('lactate_mmol_l') is not None:
                mesures.append({
                    "vitesse": entry['speed'],
                    "lactate": entry['lactate_mmol_l']
                })
        
        return {
            "actif": len(mesures) > 0,
            "mesures": mesures
        }
    
    def _build_patient_info(
        self,
        xml_data: Dict[str, Any],
        manual_input: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Construit les infos patient; le profil prime sur le XML."""
        identity = manual_input.get('identity', {})
        body_comp = manual_input.get('body_composition', {})
        prof_life = manual_input.get('professional_life', {})
        equipment = manual_input.get('equipment_and_tracking', {})
        history = manual_input.get('history_and_goals', {})
        stress = manual_input.get('stress_test_results', {})
        
        patient_info = PatientInfo()
        
        xml_athlete = (
            xml_data.get('metasoft_analysis', {}).get('athlete', {})
            or xml_data.get('metasoft_parsed', {}).get('athlete', {})
        )

        # Identity: le profil manuel prime; le XML sert seulement de fallback export.
        patient_info.nom = identity.get('last_name') or xml_athlete.get('last_name', '')
        patient_info.prenom = identity.get('first_name') or xml_athlete.get('first_name', '')
        patient_info.date_naissance = identity.get('date_of_birth', '')
        patient_info.age = identity.get('age')
        patient_info.sport_base = identity.get('sport_practiced', '')
        patient_info.specialty = identity.get('specialty', '')
        patient_info.has_coach = identity.get('has_coach', False)
        
        # Le poids XML est un fallback export, sans ecraser le profil local.
        patient_info.taille_cm = body_comp.get('height_cm')
        patient_info.poids_actuel = body_comp.get('current_weight') or xml_athlete.get('weight_kg')
        patient_info.poids_debut = body_comp.get('weight_before_test')
        patient_info.poids_final = body_comp.get('weight_after_test')
        
        # Professional
        patient_info.metier = prof_life.get('job_title', '')
        patient_info.heures_travail = prof_life.get('working_hours_per_week')
        
        # Equipment & Tracking
        patient_info.marque_montre = equipment.get('watch_brand', '')
        patient_info.vo2_montre = equipment.get('watch_estimated_vo2')
        patient_info.fc_repos = self._round_bpm(equipment.get('min_hr_before'))
        patient_info.fcmax_ever = self._round_bpm(equipment.get('max_hr_ever'))
        patient_info.volume_cap = self._parse_volume(equipment.get('average_weekly_volume', ''))
        
        # Watch predictions
        predictions = equipment.get('watch_race_predictions', {})
        patient_info.prediction_5k = predictions.get('5k', '')
        patient_info.prediction_10k = predictions.get('10k', '')
        patient_info.prediction_semi = predictions.get('half_marathon', '')
        patient_info.prediction_marathon = predictions.get('marathon', '')
        
        # History & Goals
        patient_info.records_officiels = history.get('official_records', '')
        patient_info.trail_runner = history.get('trail_runner', False)
        patient_info.utmb_index = history.get('utmb_index')
        patient_info.objectifs = history.get('upcoming_goals', '')
        
        # Session context
        patient_info.seance_veille = manual_input.get('seance_veille', '')
        patient_info.observations = manual_input.get('observations', '')
        
        # Last stage speed
        patient_info.last_stage_speed = stress.get('last_stage_speed')
        
        # RSI
        rsi_data = manual_input.get('rsi', {})
        patient_info.rsi_avant = rsi_data.get('avant')
        patient_info.rsi_apres = rsi_data.get('apres')
        
        # CMJ Avant
        cmj_data = manual_input.get('cmj', {})
        cmj_avant = cmj_data.get('avant', {})
        patient_info.cmj_avant_hauteur_cm = cmj_avant.get('hauteur_cm')
        patient_info.cmj_avant_force_max_kfg_kg = cmj_avant.get('force_max_kfg_kg')
        patient_info.cmj_avant_puissance_max_w_kg = cmj_avant.get('puissance_max_w_kg')
        
        # CMJ Après
        cmj_apres = cmj_data.get('apres', {})
        patient_info.cmj_apres_hauteur_cm = cmj_apres.get('hauteur_cm')
        patient_info.cmj_apres_force_max_kfg_kg = cmj_apres.get('force_max_kfg_kg')
        patient_info.cmj_apres_puissance_max_w_kg = cmj_apres.get('puissance_max_w_kg')
        
        # Notes privées
        patient_info.notes_privees = manual_input.get('notes_privees', '')
        
        # Altitude de vie
        patient_info.altitude_vie_m = manual_input.get('altitude_vie_m')
        
        # SpO2
        spo2_data = manual_input.get('spo2', {})
        patient_info.spo2_avant = spo2_data.get('avant')
        patient_info.spo2_apres = spo2_data.get('apres')
        
        # Lactatémie au repos
        patient_info.lactatemie_repos = manual_input.get('lactatemie_repos')
        
        return patient_info.to_dict()
    
    def _build_graphiques(
        self,
        measurements: List[Dict[str, Any]],
        seuils: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Construit les graphes depuis les mesures historiques."""
        if not measurements:
            return {}
        
        # Aggregate measurements by interval
        aggregated = self._aggregate_by_interval(measurements, GRAPH_INTERVAL_SECONDS)
        
        # Extract time values
        time_values = [m['t_seconds'] for m in aggregated if 't_seconds' in m]
        
        # Graph 1: FC, V'O2, V'CO2
        graph1 = Graph(titre="Heart Rate, V'O2 and V'CO2 Evolution")
        
        # FC curve
        fc_values = [self._round_bpm(m.get('FC')) for m in aggregated]
        if any(v is not None for v in fc_values):
            graph1.courbes.append(GraphCurve(
                nom="FC (bpm)",
                couleur=GRAPH_COLORS["FC"],
                temps_secondes=time_values,
                valeurs=fc_values
            ))
        
        # V'O2 curve
        vo2_values = [m.get("V'O2") for m in aggregated]
        if any(v is not None for v in vo2_values):
            graph1.courbes.append(GraphCurve(
                nom="V'O2 (L/min)",
                couleur=GRAPH_COLORS["V'O2"],
                temps_secondes=time_values,
                valeurs=vo2_values
            ))
        
        # V'CO2 curve (if available - need to parse from XML)
        # Note: This might need adjustment based on actual XML column names
        
        # Graph 2: V'E, BF, RER
        graph2 = Graph(titre="V'E, RER and Breathing Frequency Evolution")
        
        # V'E curve
        ve_values = [m.get("V'E") for m in aggregated]
        if any(v is not None for v in ve_values):
            graph2.courbes.append(GraphCurve(
                nom="V'E (L/min)",
                couleur=GRAPH_COLORS["V'E"],
                temps_secondes=time_values,
                valeurs=ve_values
            ))
        
        # BF curve
        bf_values = [m.get("BF") for m in aggregated]
        if any(v is not None for v in bf_values):
            graph2.courbes.append(GraphCurve(
                nom="BF (/min)",
                couleur=GRAPH_COLORS["BF"],
                temps_secondes=time_values,
                valeurs=bf_values
            ))
        
        # RER curve
        rer_values = [m.get("RER") for m in aggregated]
        if any(v is not None for v in rer_values):
            graph2.courbes.append(GraphCurve(
                nom="RER",
                couleur=GRAPH_COLORS["RER"],
                dash="dot",
                temps_secondes=time_values,
                valeurs=rer_values
            ))
        
        # Build zones_seuils
        zones = self._build_zones_seuils(aggregated, seuils)
        
        result = {
            "graphique_1": graph1.to_dict(),
            "graphique_2": graph2.to_dict(),
            "zones_seuils": [z.to_dict() for z in zones]
        }
        
        return result

    def _build_graphiques_from_metasoft_points(
        self,
        points: List[Dict[str, Any]],
        seuils: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Construit les graphes stricts depuis les points MetaSoft normalises.

        Source: mesures XML natives dans `point.values`. Unite: FC bpm, VO2 et
        VE en L/min, BF en cycles/min, RER sans unite. Transformation: moyenne
        par intervalle pour conserver un JSON leger; aucun lissage n'est exporte.
        """
        aggregated = self._aggregate_metasoft_points(points, GRAPH_INTERVAL_SECONDS)
        if not aggregated:
            return {}

        time_values = [m['t_seconds'] for m in aggregated if 't_seconds' in m]
        graph1 = Graph(titre="FC et V'O2")
        graph2 = Graph(titre="V'E, BF et RER")

        fc_values = [self._round_bpm(m.get('fc_bpm')) for m in aggregated]
        if any(v is not None for v in fc_values):
            graph1.courbes.append(GraphCurve(
                nom="FC (bpm)",
                couleur=GRAPH_COLORS["FC"],
                temps_secondes=time_values,
                valeurs=fc_values
            ))

        vo2_values = [m.get('vo2_l_min') for m in aggregated]
        if any(v is not None for v in vo2_values):
            graph1.courbes.append(GraphCurve(
                nom="V'O2 (L/min)",
                couleur=GRAPH_COLORS["V'O2"],
                temps_secondes=time_values,
                valeurs=vo2_values
            ))

        ve_values = [m.get('ve_l_min') for m in aggregated]
        if any(v is not None for v in ve_values):
            graph2.courbes.append(GraphCurve(
                nom="V'E (L/min)",
                couleur=GRAPH_COLORS["V'E"],
                temps_secondes=time_values,
                valeurs=ve_values
            ))

        bf_values = [m.get('bf_per_min') for m in aggregated]
        if any(v is not None for v in bf_values):
            graph2.courbes.append(GraphCurve(
                nom="BF (/min)",
                couleur=GRAPH_COLORS["BF"],
                temps_secondes=time_values,
                valeurs=bf_values
            ))

        rer_values = [m.get('rer') for m in aggregated]
        if any(v is not None for v in rer_values):
            graph2.courbes.append(GraphCurve(
                nom="RER",
                couleur=GRAPH_COLORS["RER"],
                dash="dot",
                temps_secondes=time_values,
                valeurs=rer_values
            ))

        return {
            "graphique_1": graph1.to_dict(),
            "graphique_2": graph2.to_dict(),
            "zones_seuils": [z.to_dict() for z in self._build_zones_seuils(aggregated, seuils)]
        }

    def _aggregate_metasoft_points(
        self,
        points: List[Dict[str, Any]],
        interval_sec: int,
    ) -> List[Dict[str, Any]]:
        """Moyenne par fenetre temporelle les valeurs XML normalisees numeriques."""
        buckets = {}
        for point in points:
            t_seconds = point.get('t_seconds')
            if not isinstance(t_seconds, (int, float)):
                continue
            bucket = int(t_seconds // interval_sec) * interval_sec + interval_sec
            buckets.setdefault(bucket, []).append(point)

        aggregated = []
        for bucket in sorted(buckets):
            row = {'t_seconds': bucket}
            keys = set().union(*(point.get('values', {}).keys() for point in buckets[bucket]))
            for key in keys:
                values = [
                    point.get('values', {}).get(key)
                    for point in buckets[bucket]
                    if isinstance(point.get('values', {}).get(key), (int, float))
                ]
                if values:
                    row[key] = round(sum(values) / len(values), 2)
            aggregated.append(row)
        return aggregated
    
    def _aggregate_by_interval(
        self,
        measurements: List[Dict],
        interval_sec: int = 15,
    ) -> List[Dict]:
        """Moyenne les mesures historiques par fenetre temporelle."""
        if not measurements:
            return []
        
        aggregated = []
        current_interval = 0
        current_values = {}
        count = 0
        
        for m in measurements:
            t = m.get('t_seconds', 0)
            interval = int(t // interval_sec) * interval_sec + interval_sec
            
            if interval != current_interval:
                # Save previous interval if we have data
                if count > 0:
                    avg_values = {'t_seconds': current_interval}
                    for key, values in current_values.items():
                        if values:
                            valid_values = [v for v in values if v is not None]
                            if valid_values:
                                avg_values[key] = round(sum(valid_values) / len(valid_values), 2)
                    aggregated.append(avg_values)
                
                # Start new interval
                current_interval = interval
                current_values = {}
                count = 0
            
            # Accumulate values
            for key, value in m.items():
                if key not in ['t', 't_seconds', 'Phase', 'Marqueur']:
                    if key not in current_values:
                        current_values[key] = []
                    current_values[key].append(value)
            count += 1
        
        # Don't forget last interval
        if count > 0:
            avg_values = {'t_seconds': current_interval}
            for key, values in current_values.items():
                if values:
                    valid_values = [v for v in values if v is not None]
                    if valid_values:
                        avg_values[key] = round(sum(valid_values) / len(valid_values), 2)
            aggregated.append(avg_values)
        
        return aggregated
    
    def _build_zones_seuils(
        self,
        aggregated: List[Dict],
        seuils: Dict[str, Any],
    ) -> List[ZoneSeuil]:
        """Construit les zones seuils depuis FC bpm, ancien ou nouveau format."""
        zones = []
        
        # SV1 zone
        sv1 = seuils.get('SV1', {})
        if sv1.get('fc'):
            fc_target = sv1['fc']
            zone = self._find_zone_by_fc(aggregated, fc_target, 'SV1', 'orange')
            if zone:
                zones.append(zone)
        
        # SV2 zone
        sv2 = seuils.get('SV2', {})
        if sv2.get('fc'):
            fc_target = sv2['fc']
            zone = self._find_zone_by_fc(aggregated, fc_target, 'SV2', 'purple')
            if zone:
                zones.append(zone)
        
        # Zone VO2max: FC bpm, compatible format historique et normalise.
        vo2max = seuils.get('VO2_max', {})
        if vo2max.get('fc_max'):
            fc_max = vo2max['fc_max']
            for m in aggregated:
                fc = m.get('FC') or m.get('fc_bpm')
                if fc and fc >= fc_max * 0.98:
                    zones.append(ZoneSeuil(
                        nom="VO2_max",
                        couleur="red",
                        fc=fc_max,
                        temps_sec=m['t_seconds'],
                        label=f"VO2Max\nFC={fc_max}"
                    ))
                    break
        
        return zones
    
    def _find_zone_by_fc(
        self,
        aggregated: List[Dict],
        fc_target: int,
        name: str,
        color: str,
    ) -> Optional[ZoneSeuil]:
        """Trouve la plage ou la FC moyenne est dans la tolerance du seuil."""
        tolerance = 0.02
        fc_min = int(fc_target * (1 - tolerance))
        fc_max = int(fc_target * (1 + tolerance))
        
        matching_times = []
        for m in aggregated:
            fc = m.get('FC') or m.get('fc_bpm')
            if fc and fc_min <= fc <= fc_max:
                matching_times.append(m['t_seconds'])
        
        if matching_times:
            return ZoneSeuil(
                nom=name,
                couleur=color,
                fc_min=fc_min,
                fc_max=fc_max,
                temps_debut_sec=min(matching_times),
                temps_fin_sec=max(matching_times),
                label=f"{name}\n[{fc_min}-{fc_max}] bpm"
            )
        return None
    
    def _safe_float(self, value: Any) -> Optional[float]:
        """Safely convert to float"""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value).replace(',', '.'))
        except (ValueError, TypeError):
            return None

    def _positive_float(self, value: Any) -> Optional[float]:
        """Retourne un nombre strictement positif; bool et NaN restent invalides."""
        if isinstance(value, bool):
            return None
        number = self._safe_float(value)
        if number is None or not isfinite(number) or number <= 0:
            return None
        return number

    def _round_bpm(self, value: Any) -> Optional[int]:
        """Arrondit uniquement les valeurs exportees en bpm, sans toucher aux sources."""
        if isinstance(value, bool):
            return None
        number = self._safe_float(value)
        if number is None or not isfinite(number):
            return None
        return int(number + 0.5)
    
    def _safe_int(self, value: Any) -> Optional[int]:
        """Safely convert to int"""
        if value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        try:
            return int(float(str(value).replace(',', '.')))
        except (ValueError, TypeError):
            return None
    
    def _parse_volume(self, volume_str: str) -> Optional[float]:
        """Parse volume string to number"""
        if not volume_str:
            return None
        try:
            # Remove units and convert
            clean = volume_str.replace('km', '').replace('h', '').strip()
            return float(clean.replace(',', '.'))
        except ValueError:
            return None
