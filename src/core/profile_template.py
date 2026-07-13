"""
Profile Template - Empty profile structure for TCP Data Processor
"""
from typing import Dict, Any, List


def get_empty_profile() -> Dict[str, Any]:
    """
    Get an empty profile template matching the expected structure.
    All fields are visible in the form (no pre/post-test modes).
    
    Returns:
        Empty profile dictionary
    """
    return {
        # User identifier
        'email': '',
        
        # Section 0: Consentements
        'consentements': {
            'risques': False,  # Décharge de responsabilité
            'donnees': False,  # Sauvegarde des données
            'anonyme': False   # Utilisation anonymisée
        },
        
        # Section 1: Identity
        'identity': {
            'last_name': '',
            'first_name': '',
            'date_of_birth': '',  # YYYY-MM-DD
            'age': None,
            'sport_practiced': '',
            'specialty': '',
            'has_coach': False
        },
        
        # Section 2: Body Composition
        'body_composition': {
            'height_cm': None,
            'current_weight': None,
            'weight_before_test': None,
            'weight_after_test': None
        },
        
        # Section 3: Professional Life
        'professional_life': {
            'job_title': '',
            'working_hours_per_week': None
        },
        
        # Section 4: Equipment & Tracking
        'equipment_and_tracking': {
            'watch_brand': '',
            'watch_estimated_vo2': None,
            'min_hr_before': None,
            'max_hr_ever': None,
            'average_weekly_volume': '',
            'watch_race_predictions': {
                '5k': '',
                '10k': '',
                'half_marathon': '',
                'marathon': ''
            }
        },
        
        # Section 5: History & Goals
        'history_and_goals': {
            'personal_records': {
                '5k': '',
                '10k': '',
                'half_marathon': '',
                'marathon': ''
            },
            'utmb_index': None,
            'upcoming_goals': ''
        },
        
        # Section 6: Session Context
        'seance_veille': '',
        'observations': '',
        
        # Section 7: Protocol
        'protocol_description': '',
        
        # Section 8: Stress Test Results
        'stress_test_results': {
            'thresholds': {
                'sv1': {
                    'hr_bpm': None,
                    'pace_km_h': None,
                    'vo2_ml_kg_min': None
                },
                'sv2': {
                    'hr_bpm': None,
                    'pace_km_h': None,
                    'vo2_ml_kg_min': None
                }
            },
            'measured_vo2max': None,
            'max_hr': None,
            'vma': None,
            'first_stage_speed': None,
            'last_stage_speed': None,
            'lactate_profile': [],
            'lactate_thresholds': {}
        },
        
        # Section 9: Training Advice
        'conseils_entrainements': '',
        
        # Section 10: RSI (Reactive Strength Index)
        'rsi': {
            'avant': None,
            'apres': None
        },
        
        # Section 11: CMJ (Counter Movement Jump)
        'cmj': {
            'avant': {
                'hauteur_cm': None,  # Performance (hauteur de saut en cm)
                'force_max_kfg_kg': None,  # Force maximale concentrique (kgf/kg)
                'puissance_max_w_kg': None  # Puissance maximale (W/kg)
            },
            'apres': {
                'hauteur_cm': None,
                'force_max_kfg_kg': None,  # Force maximale concentrique (kgf/kg)
                'puissance_max_w_kg': None
            }
        },
        
        # Section 12: Notes privées (non affichées dans le front)
        'notes_privees': '',
        
        # Section 13: Altitude de vie
        'altitude_vie_m': None,
        
        # Section 14: SpO2
        'spo2': {
            'avant': None,  # %
            'apres': None   # %
        },
        
        # Section 15: Lactatémie au repos
        'lactatemie_repos': None  # mmol/L
    }


def get_profile_sections() -> List[Dict[str, Any]]:
    """
    Get profile sections metadata for form organization.
    
    Returns:
        List of section definitions with field info
    """
    return [
        {
            'id': 'identity',
            'title': 'Identité',
            'fields': [
                ('email', 'Email (ID utilisateur)', 'text'),
                ('last_name', 'Nom', 'text'),
                ('first_name', 'Prénom', 'text'),
                ('date_of_birth', 'Date de naissance', 'text'),
                ('age', 'Âge', 'number'),
                ('sport_practiced', 'Sport pratiqué', 'text'),
                ('specialty', 'Spécialité', 'text'),
                ('has_coach', 'A un coach', 'checkbox')
            ]
        },
        {
            'id': 'body_composition',
            'title': 'Composition Corporelle',
            'fields': [
                ('height_cm', 'Taille (cm)', 'number'),
                ('current_weight', 'Poids actuel (kg)', 'number'),
                ('weight_before_test', 'Poids avant test (kg)', 'number'),
                ('weight_after_test', 'Poids après test (kg)', 'number')
            ]
        },
        {
            'id': 'professional_life',
            'title': 'Vie Professionnelle',
            'fields': [
                ('job_title', 'Métier', 'text'),
                ('working_hours_per_week', 'Heures/semaine', 'number')
            ]
        },
        {
            'id': 'equipment',
            'title': 'Équipement & Suivi',
            'fields': [
                ('watch_brand', 'Marque de montre', 'text'),
                ('watch_estimated_vo2', 'VO2 estimé (montre)', 'number'),
                ('min_hr_before', 'FC repos', 'number'),
                ('max_hr_ever', 'FC max connue', 'number'),
                ('average_weekly_volume', 'Volume hebdo moyen', 'text')
            ]
        },
        {
            'id': 'predictions',
            'title': 'Prédictions Montre',
            'fields': [
                ('prediction_5k', '5K', 'time'),
                ('prediction_10k', '10K', 'time'),
                ('prediction_half', 'Semi-marathon', 'time'),
                ('prediction_marathon', 'Marathon', 'time')
            ]
        },
        {
            'id': 'records',
            'title': 'Records Personnels',
            'fields': [
                ('record_5k', '5K', 'time'),
                ('record_10k', '10K', 'time'),
                ('record_half', 'Semi-marathon', 'time'),
                ('record_marathon', 'Marathon', 'time')
            ]
        },
        {
            'id': 'history',
            'title': 'Historique & Objectifs',
            'fields': [
                ('utmb_index', 'Index UTMB', 'number'),
                ('upcoming_goals', 'Objectifs à venir', 'textbox')
            ]
        },
        {
            'id': 'session_context',
            'title': 'Contexte de la Session',
            'fields': [
                ('seance_veille', 'Séance veille', 'text'),
                ('observations', 'Observations', 'textbox')
            ]
        },
        {
            'id': 'protocol',
            'title': 'Protocole',
            'fields': [
                ('protocol_description', 'Description du test', 'textbox')
            ]
        },
        {
            'id': 'thresholds',
            'title': 'Seuils Ventilatoires',
            'fields': [
                # SV1
                ('sv1_hr', 'SV1 - FC (bpm)', 'number'),
                ('sv1_speed', 'SV1 - Vitesse (km/h)', 'number'),
                ('sv1_vo2', 'SV1 - VO2', 'number'),
                # SV2
                ('sv2_hr', 'SV2 - FC (bpm)', 'number'),
                ('sv2_speed', 'SV2 - Vitesse (km/h)', 'number'),
                ('sv2_vo2', 'SV2 - VO2', 'number')
            ]
        },
        {
            'id': 'test_results',
            'title': 'Résultats du Test',
            'fields': [
                ('measured_vo2max', 'VO2max mesuré', 'number'),
                ('max_hr', 'FC max atteinte', 'number'),
                ('first_stage_speed', 'Vitesse 1er palier', 'number'),
                ('last_stage_speed', 'Vitesse dernier palier', 'number')
            ]
        },
        {
            'id': 'lactate',
            'title': 'Profil Lactate',
            'is_dynamic': True
        },
        {
            'id': 'advice',
            'title': 'Conseils',
            'fields': [
                ('conseils_entrainements', 'Conseils entraînement', 'textbox')
            ]
        },
        {
            'id': 'rsi',
            'title': 'RSI (Reactive Strength Index)',
            'fields': [
                ('rsi_avant', 'RSI Avant', 'number'),
                ('rsi_apres', 'RSI Après', 'number')
            ]
        },
        {
            'id': 'cmj_avant',
            'title': 'CMJ Avant Test',
            'fields': [
                ('cmj_avant_hauteur', 'Hauteur de saut (cm)', 'number'),
                ('cmj_avant_force', 'Force max concentrique (kgf/kg)', 'number'),
                ('cmj_avant_puissance', 'Puissance max (W/kg)', 'number')
            ]
        },
        {
            'id': 'cmj_apres',
            'title': 'CMJ Après Test',
            'fields': [
                ('cmj_apres_hauteur', 'Hauteur de saut (cm)', 'number'),
                ('cmj_apres_force', 'Force max concentrique (kgf/kg)', 'number'),
                ('cmj_apres_puissance', 'Puissance max (W/kg)', 'number')
            ]
        },
        {
            'id': 'physiological',
            'title': 'Données Physiologiques',
            'fields': [
                ('altitude_vie', 'Altitude de vie (m)', 'number'),
                ('spo2_avant', 'SpO2 Avant (%)', 'number'),
                ('spo2_apres', 'SpO2 Après (%)', 'number'),
                ('lactatemie_repos', 'Lactatémie au repos (mmol/L)', 'number')
            ]
        },
        {
            'id': 'notes',
            'title': 'Notes Privées',
            'fields': [
                ('notes_privees', 'Notes internes (non visibles)', 'textbox')
            ]
        }
    ]
