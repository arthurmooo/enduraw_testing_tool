"""Parsing XML MetaSoft pour l'app locale Enduraw Testing Tool.

Le module lit les exports Spreadsheet XML MetaSoft en local. Il expose deux
contrats pour rester compatible avec l'app existante:
- les champs historiques (`filename_data`, `patient_data`, `measurements`) que
  l'export Valentin consomme deja;
- un payload normalise `metasoft_parsed`, source des graphes interactifs et des
  calculs MetaSoft. Les valeurs absentes restent absentes: ce parser ne
  reconstruit aucune metrique physiologique.
"""
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from config import (
        SECTION_ADMIN_DATA,
        SECTION_BIO_DATA,
        SECTION_MEASUREMENT_DATA,
        SECTION_PATIENT_DATA,
        SECTION_SUMMARY_TABLE,
        SECTION_TEST_DATA,
    )
except ImportError:  # pragma: no cover - chemin utile si le module est lance seul
    from src.config import (
        SECTION_ADMIN_DATA,
        SECTION_BIO_DATA,
        SECTION_MEASUREMENT_DATA,
        SECTION_PATIENT_DATA,
        SECTION_SUMMARY_TABLE,
        SECTION_TEST_DATA,
    )


SS_NS = "urn:schemas-microsoft-com:office:spreadsheet"
SS_INDEX = f"{{{SS_NS}}}Index"

METRIC_LABELS = {
    "V'O2": "vo2_l_min",
    "V'O2/kg": "vo2_ml_kg_min",
    "V'CO2": "vco2_l_min",
    "FC": "fc_bpm",
    "V'E": "ve_l_min",
    "VT": "vt_l",
    "BF": "bf_per_min",
    "RER": "rer",
    "v": "speed_kmh",
    "PetO2": "peto2_mmhg",
    "PetCO2": "petco2_mmhg",
    "DE": "de_kcal_h",
    "DECHO": "decho_kcal_h",
    "DEFAT": "defat_kcal_h",
    "DEPRO": "depro_kcal_h",
    "V'E/V'O2": "ve_vo2",
    "V'E/V'CO2": "ve_vco2",
}

SECTION_BOUNDARIES = (
    SECTION_ADMIN_DATA,
    SECTION_PATIENT_DATA,
    SECTION_BIO_DATA,
    SECTION_TEST_DATA,
    SECTION_SUMMARY_TABLE,
    SECTION_MEASUREMENT_DATA,
    "Valeur de pente",
)


class TCPXmlParser:
    """Parser MetaSoft conservant l'API historique de l'app locale."""

    NAMESPACES = {
        "ss": SS_NS,
        "o": "urn:schemas-microsoft-com:office:office",
        "x": "urn:schemas-microsoft-com:office:excel",
        "html": "http://www.w3.org/TR/REC-html40",
    }

    def __init__(self):
        self.filepath = None
        self.tree = None
        self.root = None

    def parse_file(self, filepath: str) -> Dict[str, Any]:
        """Parse un XML MetaSoft depuis disque sans ecriture ni appel reseau.

        Source: fichier XML local. Unite: les unites restent celles declarees
        dans l'export MetaSoft. Transformation: parsing Spreadsheet, conversion
        numerique et calculs MetaSoft locaux; aucun fallback metier silencieux.
        """
        self.filepath = filepath
        with open(filepath, "rb") as xml_file:
            content = xml_file.read()

        self.tree = ET.ElementTree(ET.fromstring(content))
        self.root = self.tree.getroot()
        rows = parse_spreadsheet_rows(self.root)

        patient_data = self._parse_patient_data(rows)
        bio_data = self._parse_bio_data(rows)
        test_metadata = self._parse_test_metadata(rows)
        summary_data = self._parse_summary_table(rows)
        measurements = self._parse_measurement_data(rows)
        filename = os.path.basename(filepath)
        metasoft_parsed = parse_metasoft_xml_root(self.root, filename, len(content))

        try:
            from core.metasoft_analysis import build_metasoft_analysis
        except ImportError:  # pragma: no cover - chemin utile hors app package
            from src.core.metasoft_analysis import build_metasoft_analysis

        return {
            "filename_data": self._parse_filename(filename),
            "patient_data": patient_data,
            "bio_data": bio_data,
            "test_metadata": test_metadata,
            "summary_data": summary_data,
            "measurements": measurements,
            "metasoft_parsed": metasoft_parsed,
            "metasoft_analysis": build_metasoft_analysis(metasoft_parsed),
        }

    def _parse_filename(self, filename: str) -> Dict[str, str]:
        """Extrait nom compose et date depuis `TCP__NOM_Prenom_YYYY...xml`."""
        metadata = parse_filename_metadata(filename)
        athlete = metadata["athlete"]
        test = metadata["test"]
        return {
            "last_name": athlete.get("last_name", ""),
            "first_name": athlete.get("first_name", ""),
            "date": test.get("date", ""),
            "time": test.get("time", ""),
            "datetime": test.get("datetime", ""),
        }

    def _get_row_cells(self, row) -> List[str]:
        """Lit une ligne Spreadsheet en respectant `ss:Index` pour cellules vides."""
        cells = []
        for cell in row.findall(f"{{{SS_NS}}}Cell"):
            index = cell.attrib.get(SS_INDEX)
            if index:
                target = max(int(index) - 1, 0)
                while len(cells) < target:
                    cells.append("")
            data = cell.find(f"{{{SS_NS}}}Data")
            cells.append((data.text or "").strip() if data is not None else "")
        return cells

    def _find_section_start(self, rows: List[List[str]], section_name: str) -> int:
        for i, row in enumerate(rows):
            if row and section_name in row[0]:
                return i
        return -1

    def _parse_key_value_pairs(
        self,
        rows: List[List[str]],
        start_idx: int,
        end_section: Optional[str] = None,
    ) -> Dict[str, str]:
        result = {}
        i = start_idx + 1
        while i < len(rows):
            cells = rows[i]
            if cells and end_section and end_section in cells[0]:
                break
            if cells and any(section in cells[0] for section in SECTION_BOUNDARIES):
                break
            if not cells or all(c == "" for c in cells):
                if i + 1 < len(rows):
                    next_cells = rows[i + 1]
                    if next_cells and any(
                        "Données" in c or "Tableau" in c or "Valeur" in c
                        for c in next_cells
                        if c
                    ):
                        break
                i += 1
                continue
            if len(cells) >= 2 and cells[0]:
                result[cells[0]] = cells[2] if len(cells) > 2 else cells[1]
            i += 1
        return result

    def _parse_patient_data(self, rows: List[List[str]]) -> Dict[str, str]:
        idx = self._find_section_start(rows, SECTION_ADMIN_DATA)
        if idx == -1:
            idx = self._find_section_start(rows, SECTION_PATIENT_DATA)
        return {} if idx == -1 else self._parse_key_value_pairs(rows, idx)

    def _parse_bio_data(self, rows: List[List[str]]) -> Dict[str, str]:
        idx = self._find_section_start(rows, SECTION_BIO_DATA)
        return {} if idx == -1 else self._parse_key_value_pairs(rows, idx)

    def _parse_test_metadata(self, rows: List[List[str]]) -> Dict[str, str]:
        idx = self._find_section_start(rows, SECTION_TEST_DATA)
        return {} if idx == -1 else self._parse_key_value_pairs(rows, idx)

    def _parse_summary_table(self, rows: List[List[str]]) -> Dict[str, Dict[str, Any]]:
        idx = self._find_section_start(rows, SECTION_SUMMARY_TABLE)
        if idx == -1:
            return {}

        result = {}
        headers = []
        i = idx + 1
        while i < len(rows):
            cells = rows[i]
            if cells and "Variable" in cells[0]:
                headers = cells
                i += 1
                break
            i += 1

        while i < len(rows):
            cells = rows[i]
            if not cells or all(c == "" for c in cells):
                if i + 1 < len(rows):
                    next_cells = rows[i + 1]
                    if not next_cells or all(c == "" for c in next_cells):
                        break
                i += 1
                continue
            if cells and any(
                "Valeur de pente" in c or SECTION_MEASUREMENT_DATA in c
                for c in cells
                if c
            ):
                break
            if len(cells) >= 2 and cells[0]:
                result[cells[0]] = {
                    header: _convert_value(cells[j])
                    for j, header in enumerate(headers)
                    if j < len(cells)
                }
            i += 1
        return result

    def _parse_measurement_data(self, rows: List[List[str]]) -> List[Dict[str, Any]]:
        """Retourne les mesures historiques avec labels MetaSoft natifs."""
        headers, _units, start_index = find_measurement_header(rows)
        if not headers:
            return []

        measurements = []
        for row in rows[start_index:]:
            if not row or not _looks_like_time(row[0]):
                if measurements:
                    break
                continue
            row_data = {}
            for j, header in enumerate(headers):
                if not header:
                    continue
                value = row[j] if j < len(row) else ""
                if header == "t":
                    row_data["t_seconds"] = _time_to_seconds(value)
                    row_data["t"] = value
                else:
                    row_data[header] = _convert_value(value)
            measurements.append(row_data)
        return measurements

    def _convert_value(self, value: str) -> Any:
        return _convert_value(value)

    def _time_to_seconds(self, time_str: str) -> Optional[float]:
        return _time_to_seconds(time_str)


def parse_xml_file(filepath: str) -> Dict[str, Any]:
    """Parse un XML MetaSoft depuis disque avec le contrat historique."""
    return TCPXmlParser().parse_file(filepath)


def parse_metasoft_xml_bytes(content: bytes, filename: str) -> dict:
    """Retourne un payload normalise depuis un XML MetaSoft.

    Source: cellules Spreadsheet XML. Les valeurs numeriques restent dans les
    unites XML natives, sauf `t_seconds` converti en secondes pour l'axe temps.
    """
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise ValueError(f"XML MetaSoft invalide: {exc}") from exc

    return parse_metasoft_xml_root(root, filename, len(content))


def parse_metasoft_xml_root(root: ET.Element, filename: str, size_bytes: int = 0) -> dict:
    """Retourne le payload normalise depuis une racine XML deja chargee."""
    warnings = []
    rows = parse_spreadsheet_rows(root)
    if not rows:
        raise ValueError("Aucune ligne Spreadsheet exploitable dans le XML.")

    headers, units, start_index = find_measurement_header(rows)
    if not headers:
        raise ValueError("En-tete de mesures MetaSoft introuvable.")

    metrics = _build_metric_specs(headers, units)
    points = parse_measurement_points(headers, rows[start_index:], metrics)
    if not points:
        warnings.append({
            "code": "no_measurement_points",
            "message": "Aucun point de mesure MetaSoft exploitable.",
        })

    metadata = parse_filename_metadata(filename)
    patient = parse_weight_or_patient_metadata(rows)
    metadata["athlete"].update({
        key: value for key, value in patient.items()
        if key in {"first_name", "last_name", "athlete_name", "weight_kg"}
        and value not in (None, "")
    })

    for key in ("vo2_l_min", "rer", "speed_kmh"):
        if key not in metrics:
            warnings.append({
                "code": f"missing_{key}",
                "message": f"Mesure absente du XML: {key}.",
            })

    return {
        "file": {"filename": filename, "size_bytes": size_bytes},
        "athlete": metadata["athlete"],
        "test": metadata["test"],
        "metrics": metrics,
        "points": points,
        "warnings": warnings,
    }


def parse_spreadsheet_rows(root: ET.Element) -> List[List[str]]:
    """Lit les lignes Spreadsheet en respectant les trous `ss:Index`."""
    rows = []
    for row in root.findall(f".//{{{SS_NS}}}Row"):
        cells = []
        for cell in row.findall(f"{{{SS_NS}}}Cell"):
            index = cell.attrib.get(SS_INDEX)
            if index:
                target = max(int(index) - 1, 0)
                while len(cells) < target:
                    cells.append("")
            data = cell.find(f"{{{SS_NS}}}Data")
            cells.append((data.text or "").strip() if data is not None else "")
        if cells:
            rows.append(cells)
    return rows


def find_measurement_header(rows: List[List[str]]) -> Tuple[List[str], List[str], int]:
    """Trouve l'en-tete `t / Phase / ...` puis sa ligne d'unites."""
    for index, row in enumerate(rows):
        if row and row[0] == "t" and "Phase" in row:
            units = rows[index + 1] if index + 1 < len(rows) else []
            return row, units, index + 2
    return [], [], 0


def parse_measurement_points(
    headers: List[str],
    measurement_rows: List[List[str]],
    metrics: dict,
) -> List[dict]:
    """Convertit les lignes MetaSoft en points canoniques pour les graphes."""
    points = []
    for row in measurement_rows:
        if not row or not _looks_like_time(row[0]):
            if points:
                break
            continue

        raw = {}
        values = {}
        for pos, header in enumerate(headers):
            if not header:
                continue
            cell = row[pos] if pos < len(row) else ""
            value = _convert_value(cell)
            raw[header] = value
            metric_key = METRIC_LABELS.get(header)
            if metric_key and metric_key in metrics:
                values[metric_key] = value

        points.append({
            "index": len(points),
            "t": str(raw.get("t") or row[0]),
            "t_seconds": _time_to_seconds(str(raw.get("t") or row[0])),
            "phase": raw.get("Phase") or None,
            "marker": raw.get("Marqueur") or None,
            "values": values,
            "raw": raw,
        })
    return points


def parse_filename_metadata(filename: str) -> dict:
    """Extrait date et nom, y compris pour les noms composes avec espaces."""
    match = re.match(
        r"^TCP__(?P<name>.+)_(?P<date>\d{4}\.\d{2}\.\d{2})"
        r"_(?P<time>\d{2}\.\d{2}\.\d{2})_?\.xml$",
        Path(filename).name,
    )
    athlete = {"first_name": "", "last_name": "", "athlete_name": ""}
    test = {"date": "", "time": "", "datetime": "", "type": "VO2max"}
    if not match:
        return {"athlete": athlete, "test": test}

    name_parts = match.group("name").split("_")
    first_name = name_parts[-1] if name_parts else ""
    last_name = " ".join(name_parts[:-1])
    date = match.group("date").replace(".", "-")
    time_value = match.group("time").replace(".", ":")
    athlete.update({
        "first_name": first_name,
        "last_name": last_name,
        "athlete_name": f"{last_name} {first_name}".strip(),
    })
    test.update({
        "date": date,
        "time": time_value,
        "datetime": f"{date}T{time_value}",
    })
    return {"athlete": athlete, "test": test}


def parse_weight_or_patient_metadata(rows: List[List[str]]) -> dict:
    """Extrait poids et identite sans ecraser les champs manuels."""
    patient = {}
    for row in rows:
        key = row[0].strip() if row else ""
        value = _first_value(row[1:])
        if not value:
            continue
        if key in {"Nom", "Nom de famille"}:
            patient["last_name"] = str(value)
        elif key in {"Prenom", "Prénom"}:
            patient["first_name"] = str(value)
        elif "poids" in key.lower():
            patient["weight_kg"] = _first_number(row[1:])

    first = patient.get("first_name", "")
    last = patient.get("last_name", "")
    if first or last:
        patient["athlete_name"] = f"{last} {first}".strip()
    return patient


def get_available_tests(folder_path: str) -> List[Dict[str, str]]:
    """Liste les XML TCP disponibles avec les metadonnees de nom/date."""
    tests = []
    parser = TCPXmlParser()
    for filename in os.listdir(folder_path):
        if filename.startswith("TCP__") and filename.endswith(".xml"):
            info = parser._parse_filename(filename)
            info["filepath"] = os.path.join(folder_path, filename)
            info["filename"] = filename
            tests.append(info)
    tests.sort(key=lambda x: x.get("datetime", ""), reverse=True)
    return tests


def _build_metric_specs(headers: List[str], units: List[str]) -> dict:
    metrics = {}
    for pos, source_label in enumerate(headers):
        key = METRIC_LABELS.get(source_label)
        if not key:
            continue
        metrics[key] = {
            "key": key,
            "source_label": source_label,
            "unit": units[pos] if pos < len(units) and units[pos] else None,
            "source": "xml",
            "transform": "native",
        }
    return metrics


def _convert_value(value: str):
    if value in ("", "-"):
        return None
    cleaned = str(value).replace(",", ".").replace(" ", "")
    try:
        number = float(cleaned)
    except ValueError:
        return value
    return int(number) if number.is_integer() else number


def _time_to_seconds(time_value: str) -> Optional[float]:
    try:
        parts = str(time_value).replace(",", ".").split(":")
        if len(parts) != 3:
            return None
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    except (TypeError, ValueError):
        return None


def _looks_like_time(value: str) -> bool:
    return bool(re.match(r"^\d+:\d{2}:\d{2}", str(value)))


def _first_value(values: List[str]):
    for value in values:
        converted = _convert_value(value)
        if converted not in (None, ""):
            return converted
    return None


def _first_number(values: List[str]):
    for value in values:
        converted = _convert_value(value)
        if isinstance(converted, (int, float)):
            return converted
        if isinstance(converted, str):
            match = re.search(r"-?\d+(?:[,.]\d+)?", converted)
            if match:
                return float(match.group(0).replace(",", "."))
    return None
