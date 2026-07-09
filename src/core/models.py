"""
Data models for TCP Data Processor
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import date


@dataclass
class Seuil:
    """Threshold data (SV1, SV2, VO2max)"""
    vo2: Optional[float] = None
    allure: Optional[float] = None  # km/h
    fc: Optional[int] = None  # bpm
    pourcentage_vma: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "vo2": self.vo2,
            "allure": self.allure,
            "fc": self.fc,
            "pourcentage_vma": self.pourcentage_vma
        }


@dataclass
class VO2Max:
    """VO2 Max specific data"""
    valeur: Optional[float] = None  # ml/min/kg
    fc_max: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "valeur": self.valeur,
            "fc_max": self.fc_max
        }


@dataclass
class VMA:
    """VMA (Maximal Aerobic Speed)"""
    valeur: Optional[float] = None  # km/h
    
    def to_dict(self) -> Dict[str, Any]:
        return {"valeur": self.valeur}


@dataclass
class LactateMeasure:
    """Single lactate measurement"""
    vitesse: float
    lactate: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "vitesse": self.vitesse,
            "lactate": self.lactate
        }


@dataclass
class PatientInfo:
    """Patient/athlete information - comprehensive"""
    # Identity
    nom: str = ""
    prenom: str = ""
    date_naissance: str = ""
    age: Optional[int] = None
    sport_base: str = ""
    specialty: str = ""
    has_coach: bool = False
    
    # Body composition
    taille_cm: Optional[float] = None
    poids_actuel: Optional[float] = None
    poids_debut: Optional[float] = None
    poids_final: Optional[float] = None
    
    # Professional
    metier: str = ""
    heures_travail: Optional[int] = None
    
    # Equipment & Tracking
    marque_montre: str = ""
    vo2_montre: Optional[float] = None
    fc_repos: Optional[int] = None
    fcmax_ever: Optional[int] = None
    volume_cap: Optional[float] = None
    
    # Watch predictions
    prediction_5k: str = ""
    prediction_10k: str = ""
    prediction_semi: str = ""
    prediction_marathon: str = ""
    
    # History & Goals
    records_officiels: str = ""
    trail_runner: bool = False
    utmb_index: Optional[float] = None
    objectifs: str = ""
    
    # Session context
    seance_veille: str = ""
    observations: str = ""
    
    # Protocol
    last_stage_speed: Optional[float] = None
    
    # Legacy fields
    annee_debut: Optional[int] = None
    
    # RSI (Reactive Strength Index)
    rsi_avant: Optional[float] = None
    rsi_apres: Optional[float] = None
    
    # CMJ (Counter Movement Jump) - Avant test
    cmj_avant_hauteur_cm: Optional[float] = None  # Performance (hauteur de saut en cm)
    cmj_avant_force_max_kfg_kg: Optional[float] = None  # Force maximale concentrique (kgf/kg)
    cmj_avant_puissance_max_w_kg: Optional[float] = None  # Puissance maximale (W/kg)
    
    # CMJ (Counter Movement Jump) - Après test
    cmj_apres_hauteur_cm: Optional[float] = None
    cmj_apres_force_max_kfg_kg: Optional[float] = None  # Force maximale concentrique (kgf/kg)
    cmj_apres_puissance_max_w_kg: Optional[float] = None
    
    # Notes privées (non affichées dans le front)
    notes_privees: str = ""
    
    # Altitude de vie
    altitude_vie_m: Optional[int] = None
    
    # SpO2
    spo2_avant: Optional[float] = None  # %
    spo2_apres: Optional[float] = None  # %
    
    # Lactatémie au repos
    lactatemie_repos: Optional[float] = None  # mmol/L
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            # Identity
            "nom": self.nom,
            "prenom": self.prenom,
            "date_naissance": self.date_naissance,
            "age": self.age,
            "sport_base": self.sport_base,
            "specialty": self.specialty,
            "has_coach": self.has_coach,
            
            # Body composition
            "taille_cm": self.taille_cm,
            "poids_actuel": self.poids_actuel,
            "poids_debut": self.poids_debut,
            "poids_final": self.poids_final,
            
            # Professional
            "metier": self.metier,
            "heures_travail": self.heures_travail,
            
            # Equipment
            "marque_montre": self.marque_montre,
            "vo2_montre": self.vo2_montre,
            "fc_repos": self.fc_repos,
            "fcmax_ever": self.fcmax_ever,
            "volume_cap": self.volume_cap,
            
            # Watch predictions
            "prediction_5k": self.prediction_5k,
            "prediction_10k": self.prediction_10k,
            "prediction_semi": self.prediction_semi,
            "prediction_marathon": self.prediction_marathon,
            
            # History & Goals
            "records_officiels": self.records_officiels,
            "trail_runner": self.trail_runner,
            "utmb_index": self.utmb_index,
            "objectifs": self.objectifs,
            
            # Session
            "seance_veille": self.seance_veille,
            "observations": self.observations,
            
            # Protocol
            "last_stage_speed": self.last_stage_speed,
            
            # Legacy
            "annee_debut": self.annee_debut,
            
            # RSI
            "rsi_avant": self.rsi_avant,
            "rsi_apres": self.rsi_apres,
            
            # CMJ Avant
            "cmj_avant": {
                "hauteur_cm": self.cmj_avant_hauteur_cm,
                "force_max_kfg_kg": self.cmj_avant_force_max_kfg_kg,
                "puissance_max_w_kg": self.cmj_avant_puissance_max_w_kg
            },
            
            # CMJ Après
            "cmj_apres": {
                "hauteur_cm": self.cmj_apres_hauteur_cm,
                "force_max_kfg_kg": self.cmj_apres_force_max_kfg_kg,
                "puissance_max_w_kg": self.cmj_apres_puissance_max_w_kg
            },
            
            # Notes privées
            "notes_privees": self.notes_privees,
            
            # Altitude de vie
            "altitude_vie_m": self.altitude_vie_m,
            
            # SpO2
            "spo2_avant": self.spo2_avant,
            "spo2_apres": self.spo2_apres,
            
            # Lactatémie au repos
            "lactatemie_repos": self.lactatemie_repos
        }


@dataclass
class GraphCurve:
    """Single curve data for graphs"""
    nom: str
    couleur: str
    type: str = "lines"
    temps_secondes: List[float] = field(default_factory=list)
    valeurs: List[float] = field(default_factory=list)
    dash: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "nom": self.nom,
            "couleur": self.couleur,
            "type": self.type,
            "temps_secondes": self.temps_secondes,
            "valeurs": self.valeurs
        }
        if self.dash:
            result["dash"] = self.dash
        return result


@dataclass
class Graph:
    """Graph structure with multiple curves"""
    titre: str
    courbes: List[GraphCurve] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "titre": self.titre,
            "courbes": [c.to_dict() for c in self.courbes]
        }


@dataclass
class ZoneSeuil:
    """Threshold zone for graph annotation"""
    nom: str
    couleur: str
    fc_min: Optional[int] = None
    fc_max: Optional[int] = None
    fc: Optional[int] = None
    temps_debut_sec: Optional[float] = None
    temps_fin_sec: Optional[float] = None
    temps_sec: Optional[float] = None
    label: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "nom": self.nom,
            "couleur": self.couleur,
            "label": self.label
        }
        if self.fc_min is not None:
            result["fc_min"] = self.fc_min
        if self.fc_max is not None:
            result["fc_max"] = self.fc_max
        if self.fc is not None:
            result["fc"] = self.fc
        if self.temps_debut_sec is not None:
            result["temps_debut_sec"] = self.temps_debut_sec
        if self.temps_fin_sec is not None:
            result["temps_fin_sec"] = self.temps_fin_sec
        if self.temps_sec is not None:
            result["temps_sec"] = self.temps_sec
        return result


@dataclass
class TestResult:
    """Complete test result ready for MongoDB export"""
    user_id: str = ""  # Email
    athlete_name: str = ""
    test_date: str = ""  # YYYY-MM-DD
    test_type: str = "VO2max"
    consentements: Dict[str, bool] = field(default_factory=lambda: {'risques': False, 'donnees': False, 'anonyme': False})
    seuils: Dict[str, Any] = field(default_factory=dict)
    protocole: Dict[str, Any] = field(default_factory=dict)
    test_lactate: Dict[str, Any] = field(default_factory=dict)
    observations_lactate: str = ""
    patient_info: Dict[str, Any] = field(default_factory=dict)
    conseils_entrainements: str = ""
    graphiques: Dict[str, Any] = field(default_factory=dict)
    running_economy_manual: Optional[Dict[str, Any]] = None
    logos: Dict[str, str] = field(default_factory=dict)
    partenaires: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "user_id": self.user_id,
            "athlete_name": self.athlete_name,
            "test_date": self.test_date,
            "test_type": self.test_type,
            "consentements": self.consentements,
            "seuils": self.seuils,
            "protocole": self.protocole,
            "test_lactate": self.test_lactate,
            "observations_lactate": self.observations_lactate,
            "patient_info": self.patient_info,
            "conseils_entrainements": self.conseils_entrainements,
            "graphiques": self.graphiques,
            "logos": self.logos,
            "partenaires": self.partenaires
        }
        if self.running_economy_manual:
            result["running_economy_manual"] = self.running_economy_manual
        return result
