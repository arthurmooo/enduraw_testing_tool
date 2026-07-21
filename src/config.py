"""
Configuration constants for Enduraw Testing Tool
"""

# Application metadata
APP_NAME = "Enduraw Testing Tool"
APP_VERSION = "1.1.3"

# File patterns
XML_FILENAME_PATTERN = r"TCP__([A-Z]+)_([A-Za-z]+)_(\d{4})\.(\d{2})\.(\d{2})_(\d{2})\.(\d{2})\.(\d{2})_\.xml"

# XML section headers (French)
SECTION_PATIENT_DATA = "Données du patient"
SECTION_ADMIN_DATA = "Données administratives"
SECTION_BIO_DATA = "Données de base Biologiques et Médicales"
SECTION_TEST_DATA = "Données test"
SECTION_SUMMARY_TABLE = "Tableau Résumé"
SECTION_MEASUREMENT_DATA = "Measurement Data"

# Summary table column headers
SUMMARY_COLUMNS = [
    "Variable", "Unité", "Repos", "Pédalage à Vide", "Echauffement",
    "VT1", "AT % Pred", "AT % Max", "VT2", "RCP % Pred", "RCP % Max",
    "Pic de V'O2", "Pic V'O2 % Pred", "Prédit", "Valeurs Maximales Absolues"
]

# Measurement data columns
MEASUREMENT_COLUMNS = [
    "t", "Phase", "Marqueur", "V'O2", "V'O2/kg", "V'O2/FC", "FC",
    "TT", "V'E/V'O2", "V'E/V'CO2", "RER", "V'E", "VT", "BF"
]

# Graph colors
GRAPH_COLORS = {
    "FC": "rgb(255, 0, 0)",
    "V'O2": "rgb(0, 0, 255)",
    "V'CO2": "rgb(0, 200, 0)",
    "V'E": "rgb(255, 140, 0)",
    "BF": "rgb(30, 144, 255)",
    "RER": "rgb(220, 20, 60)"
}

# Default aggregation interval for graphs (seconds)
GRAPH_INTERVAL_SECONDS = 15

# UI Colors (CustomTkinter theme)
UI_COLORS = {
    "primary": "#1f538d",
    "secondary": "#14375e",
    "success": "#2fa572",
    "warning": "#f0ad4e",
    "danger": "#d9534f",
    "background": "#2b2b2b",
    "surface": "#333333",
}

# Sidebar navigation colors (light, dark)
SIDEBAR_COLORS = {
    "bg":          ("#f5f5f7", "#1c1c1e"),
    "btn_active":  ("#e8e8ec", "#38383a"),
    "btn_hover":   ("#dcdce0", "#2c2c2e"),
    "btn_text":    ("#1d1d1f", "#f5f5f7"),
    "separator":   ("#d2d2d7", "#3a3a3c"),
    "accent":      "#0071e3",
}

# Navbar width
SIDEBAR_WIDTH = 220
