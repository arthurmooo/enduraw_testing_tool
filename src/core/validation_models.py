"""
Pydantic models for data validation.
Handles robust validation for dates, times, emails, and numeric ranges.
"""
from typing import Optional, Dict, Any, List, Union
from pydantic import BaseModel, Field, field_validator, EmailStr, model_validator
from datetime import datetime
import re

# --- Custom Validators ---

def validate_date_format(v: Optional[str]) -> Optional[str]:
    """Validates date format (DD/MM/YYYY or YYYY-MM-DD)"""
    if not v:
        return None
    
    # Try DD/MM/YYYY
    try:
        datetime.strptime(v, "%d/%m/%Y")
        return v
    except ValueError:
        pass
        
    # Try YYYY-MM-DD
    try:
        datetime.strptime(v, "%Y-%m-%d")
        return v
    except ValueError:
        pass
    
    raise ValueError("Format de date invalide. Utilisez JJ/MM/AAAA ou AAAA-MM-JJ")

def validate_time_duration(v: Optional[str]) -> Optional[str]:
    """Validates time format HH:MM:SS (can be > 24h)"""
    if not v:
        return None
    
    # Check format HH:MM:SS
    pattern = r"^\d+:[0-5]\d:[0-5]\d$"
    if not re.match(pattern, v):
        raise ValueError("Format d'heure invalide. Utilisez HH:MM:SS")
    
    return v

# --- Sub-models ---

class ConsentData(BaseModel):
    risques: bool = False
    donnees: bool = False
    anonyme: bool = False
    image: bool = False

class IdentityData(BaseModel):
    last_name: Optional[str] = None
    first_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    age: Optional[int] = Field(None, ge=0, le=120)
    sport_practiced: Optional[str] = None
    specialty: Optional[str] = None
    has_coach: bool = False
    
    @field_validator('last_name', 'first_name')
    @classmethod
    def validate_names(cls, v):
        if v and not re.match(r"^[a-zA-ZÀ-ÿ\s-]+$", v):
            raise ValueError("Le nom ne doit contenir que des lettres")
        return v.title() if v else v

    @field_validator('date_of_birth')
    @classmethod
    def validate_dob(cls, v):
        return validate_date_format(v)

class BodyComposition(BaseModel):
    height_cm: Optional[float] = Field(None, gt=0, lt=300)
    current_weight: Optional[float] = Field(None, gt=0, lt=300)
    weight_before_test: Optional[float] = Field(None, gt=0, lt=300)
    weight_after_test: Optional[float] = Field(None, gt=0, lt=300)

class ProfessionalLife(BaseModel):
    job_title: Optional[str] = None
    working_hours_per_week: Optional[float] = Field(None, ge=0, le=168)

class RacePredictions(BaseModel):
    prediction_5k: Optional[str] = Field(None, alias="5k")
    prediction_10k: Optional[str] = Field(None, alias="10k")
    prediction_half: Optional[str] = Field(None, alias="half_marathon")
    prediction_marathon: Optional[str] = Field(None, alias="marathon")
    
    @field_validator('*')
    @classmethod
    def validate_times(cls, v):
        return validate_time_duration(v)

class EquipmentTracking(BaseModel):
    watch_brand: Optional[str] = None
    watch_estimated_vo2: Optional[float] = Field(None, gt=0, lt=100)
    min_hr_before: Optional[int] = Field(None, gt=20, lt=200)
    max_hr_ever: Optional[int] = Field(None, gt=100, lt=250)
    average_weekly_volume: Optional[str] = None # Can be string like "50km" or "5h"
    watch_race_predictions: RacePredictions = Field(default_factory=RacePredictions)

class PersonalRecords(BaseModel):
    record_5k: Optional[str] = Field(None, alias="5k")
    record_10k: Optional[str] = Field(None, alias="10k")
    record_half: Optional[str] = Field(None, alias="half_marathon")
    record_marathon: Optional[str] = Field(None, alias="marathon")
    
    @field_validator('*')
    @classmethod
    def validate_times(cls, v):
        return validate_time_duration(v)

class HistoryGoals(BaseModel):
    personal_records: PersonalRecords = Field(default_factory=PersonalRecords)
    utmb_index: Optional[float] = Field(None, ge=0, le=1000)
    upcoming_goals: Optional[str] = None

class ThresholdData(BaseModel):
    hr_bpm: Optional[int] = Field(None, gt=30, lt=230)
    pace_km_h: Optional[float] = Field(None, gt=0, lt=30)
    vo2_ml_kg_min: Optional[float] = Field(None, gt=0, lt=100)

class Thresholds(BaseModel):
    sv1: ThresholdData = Field(default_factory=ThresholdData)
    sv2: ThresholdData = Field(default_factory=ThresholdData)

class LactatePoint(BaseModel):
    speed: float
    lactate_mmol_l: float

class StressTestResults(BaseModel):
    thresholds: Thresholds = Field(default_factory=Thresholds)
    measured_vo2max: Optional[float] = Field(None, gt=0, lt=100)
    max_hr: Optional[int] = Field(None, gt=50, lt=240)
    vma: Optional[float] = Field(None, gt=0, lt=30)
    first_stage_speed: Optional[float] = Field(None, gt=0)
    last_stage_speed: Optional[float] = Field(None, gt=0)
    lactate_profile: List[LactatePoint] = Field(default_factory=list)
    lactate_thresholds: Dict[str, Any] = Field(default_factory=dict)

class RSI(BaseModel):
    avant: Optional[float] = None
    apres: Optional[float] = None

class CMJMeasure(BaseModel):
    hauteur_cm: Optional[float] = None
    force_max_kfg_kg: Optional[float] = None
    puissance_max_w_kg: Optional[float] = None

class CMJ(BaseModel):
    avant: CMJMeasure = Field(default_factory=CMJMeasure)
    apres: CMJMeasure = Field(default_factory=CMJMeasure)

class SpO2(BaseModel):
    avant: Optional[float] = Field(None, ge=50, le=100)
    apres: Optional[float] = Field(None, ge=50, le=100)

# --- Main Model ---

class ProfileFormModel(BaseModel):
    """Main validation model for the Profile Form"""
    
    email: EmailStr
    consentements: ConsentData = Field(default_factory=ConsentData)
    identity: IdentityData = Field(default_factory=IdentityData)
    body_composition: BodyComposition = Field(default_factory=BodyComposition)
    professional_life: ProfessionalLife = Field(default_factory=ProfessionalLife)
    equipment_and_tracking: EquipmentTracking = Field(default_factory=EquipmentTracking)
    history_and_goals: HistoryGoals = Field(default_factory=HistoryGoals)
    
    seance_veille: Optional[str] = None
    observations: Optional[str] = None
    protocol_description: Optional[str] = None
    
    stress_test_results: StressTestResults = Field(default_factory=StressTestResults)
    
    conseils_entrainements: Optional[str] = None
    rsi: RSI = Field(default_factory=RSI)
    cmj: CMJ = Field(default_factory=CMJ)
    notes_privees: Optional[str] = None
    altitude_vie_m: Optional[float] = None
    spo2: SpO2 = Field(default_factory=SpO2)
    lactatemie_repos: Optional[float] = None

    @field_validator('email')
    @classmethod
    def lower_email(cls, v):
        return v.lower()
