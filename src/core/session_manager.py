"""
Session Manager - Handles sessions and profiles for TCP Data Processor
"""
import os
import json
import shutil
import uuid
import hashlib
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional


@dataclass
class Session:
    """Session metadata"""
    name: str
    date: str
    location: str
    description: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Session':
        return cls(
            name=data.get('name', ''),
            date=data.get('date', ''),
            location=data.get('location', ''),
            description=data.get('description', ''),
            created_at=data.get('created_at', datetime.now().isoformat())
        )


@dataclass
class ProfileMatch:
    """Tracks profile-XML matching"""
    profile_name: str
    xml_filename: str
    matched_at: str = field(default_factory=lambda: datetime.now().isoformat())
    exported: bool = False
    metasoft_report: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if self.metasoft_report is None:
            data.pop('metasoft_report')
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProfileMatch':
        return cls(
            profile_name=data.get('profile_name', ''),
            xml_filename=data.get('xml_filename', ''),
            matched_at=data.get('matched_at', datetime.now().isoformat()),
            exported=data.get('exported', False),
            metasoft_report=(
                deepcopy(data.get('metasoft_report'))
                if isinstance(data.get('metasoft_report'), dict)
                else None
            ),
        )


class SessionManager:
    """Manages sessions and profiles"""
    
    SESSIONS_DIR = "sessions"
    SESSION_FILE = "session.json"
    PROFILES_DIR = "profiles"
    XML_DIR = "xml"
    OUTPUT_DIR = "output"
    MATCHES_FILE = "matches.json"
    MANUAL_RUNNING_ECONOMY_FILE = "running_economy_manual.json"
    
    def __init__(self, base_path: str):
        """
        Initialize session manager.
        
        Args:
            base_path: Base folder where Sessions directory will be created
        """
        self.base_path = Path(base_path)
        self.sessions_path = self.base_path / self.SESSIONS_DIR
        self.current_session: Optional[Session] = None
        self.current_session_path: Optional[Path] = None
        self.matches: List[ProfileMatch] = []
    
    def _ensure_sessions_dir(self):
        """Ensure Sessions directory exists"""
        self.sessions_path.mkdir(parents=True, exist_ok=True)
    
    def _sanitize_name(self, name: str) -> str:
        """Sanitize string for use as folder/file name"""
        # Replace spaces and special chars
        sanitized = name.replace(' ', '_')
        # Keep only alphanumeric, underscore, hyphen
        sanitized = ''.join(c for c in sanitized if c.isalnum() or c in '_-')
        return sanitized
    
    # ==================== SESSION OPERATIONS ====================
    
    def create_session(self, date: str, location: str, description: str = "") -> Session:
        """
        Create a new session.
        
        Args:
            date: Session date (YYYY-MM-DD format)
            location: Session location
            description: Optional description
            
        Returns:
            Created Session object
        """
        self._ensure_sessions_dir()
        
        # Generate session name from date and location
        safe_location = self._sanitize_name(location)
        session_name = f"{date}_{safe_location}"
        
        # Create session folder
        session_path = self.sessions_path / session_name
        session_path.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (session_path / self.PROFILES_DIR).mkdir(exist_ok=True)
        (session_path / self.XML_DIR).mkdir(exist_ok=True)
        (session_path / self.OUTPUT_DIR).mkdir(exist_ok=True)
        
        # Create session object
        session = Session(
            name=session_name,
            date=date,
            location=location,
            description=description
        )
        
        # Save session.json
        session_file = session_path / self.SESSION_FILE
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(session.to_dict(), f, indent=2, ensure_ascii=False)
        
        # Initialize empty matches
        matches_file = session_path / self.MATCHES_FILE
        with open(matches_file, 'w', encoding='utf-8') as f:
            json.dump([], f)
        
        # Set as current session
        self.current_session = session
        self.current_session_path = session_path
        self.matches = []
        
        return session
    
    def load_session(self, session_path: str) -> Session:
        """
        Load an existing session.
        
        Args:
            session_path: Path to session folder
            
        Returns:
            Loaded Session object
        """
        path = Path(session_path)
        session_file = path / self.SESSION_FILE
        
        if not session_file.exists():
            raise FileNotFoundError(f"Session file not found: {session_file}")
        
        with open(session_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        session = Session.from_dict(data)
        
        # Set as current session
        self.current_session = session
        self.current_session_path = path
        
        # Load matches
        self._load_matches()
        
        return session
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """
        List all available sessions.
        
        Returns:
            List of session info dictionaries
        """
        self._ensure_sessions_dir()
        sessions = []
        
        for item in self.sessions_path.iterdir():
            if item.is_dir():
                session_file = item / self.SESSION_FILE
                if session_file.exists():
                    try:
                        with open(session_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        data['path'] = str(item)
                        sessions.append(data)
                    except Exception:
                        pass
        
        # Sort by date descending
        sessions.sort(key=lambda x: x.get('date', ''), reverse=True)
        return sessions
    
    def delete_session(self, session_path: str) -> bool:
        """Delete a session and all its contents"""
        path = Path(session_path)
        if path.exists() and path.is_dir():
            shutil.rmtree(path)
            if self.current_session_path == path:
                self.current_session = None
                self.current_session_path = None
                self.matches = []
            return True
        return False
    
    # ==================== PROFILE OPERATIONS ====================
    
    def add_profile(self, profile_data: Dict[str, Any]) -> str:
        """
        Add a new profile to current session.
        
        Args:
            profile_data: Profile data dictionary
            
        Returns:
            Profile filename
        """
        if not self.current_session_path:
            raise ValueError("No session loaded")
        
        # Generate filename from identity, with fallback to UUID
        identity = profile_data.get('identity', {})
        last_name = (identity.get('last_name') or '').strip()
        first_name = (identity.get('first_name') or '').strip()
        
        # Build safe name
        if last_name or first_name:
            name_parts = [p for p in [last_name, first_name] if p]
            safe_name = "forms_" + self._sanitize_name('_'.join(name_parts))
        else:
            # No name provided - use UUID
            safe_name = f"forms_nouveau_profil_{uuid.uuid4().hex[:8]}"
        
        # Ensure we have a valid name
        if not safe_name:
            safe_name = f"forms_profil_{uuid.uuid4().hex[:8]}"
        
        filename = f"{safe_name}.json"
        
        # Handle duplicates
        profiles_dir = self.current_session_path / self.PROFILES_DIR
        filepath = profiles_dir / filename
        counter = 1
        while filepath.exists():
            filename = f"{safe_name}_{counter}.json"
            filepath = profiles_dir / filename
            counter += 1
        
        # Save profile
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(profile_data, f, indent=2, ensure_ascii=False)
        
        return filename
    
    def update_profile(self, filename: str, profile_data: Dict[str, Any]) -> str:
        """
        Update an existing profile. Renames file if name changed.
        
        Args:
            filename: Profile filename
            profile_data: Updated profile data
            
        Returns:
            New filename (same if not renamed), or empty string on failure
        """
        if not self.current_session_path:
            raise ValueError("No session loaded")
        
        profiles_dir = self.current_session_path / self.PROFILES_DIR
        filepath = profiles_dir / filename
        if not filepath.exists():
            return ""
        
        # Calculate new filename based on name
        identity = profile_data.get('identity', {}) or {}
        last_name = (identity.get('last_name') or '').strip()
        first_name = (identity.get('first_name') or '').strip()
        
        if last_name or first_name:
            name_parts = [p for p in [last_name, first_name] if p]
            new_safe_name = "forms_" + self._sanitize_name('_'.join(name_parts))
        else:
            # Keep original filename if no name
            new_safe_name = filepath.stem
        
        if not new_safe_name:
            new_safe_name = filepath.stem
        
        new_filename = f"{new_safe_name}.json"
        new_filepath = profiles_dir / new_filename
        
        # Handle rename if filename changed
        if new_filename != filename:
            # Handle duplicates
            counter = 1
            while new_filepath.exists() and new_filepath != filepath:
                new_filename = f"{new_safe_name}_{counter}.json"
                new_filepath = profiles_dir / new_filename
                counter += 1
            
            # Update any matches pointing to old filename
            for match in self.matches:
                if match.profile_name == filename:
                    match.profile_name = new_filename
            self._save_matches()
            
            # Rename file
            if new_filepath != filepath:
                filepath.rename(new_filepath)
                filepath = new_filepath
        
        # Save updated data
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(profile_data, f, indent=2, ensure_ascii=False)
        
        return new_filename
    
    def get_profile(self, filename: str) -> Optional[Dict[str, Any]]:
        """
        Get a profile by filename.
        
        Args:
            filename: Profile filename
            
        Returns:
            Profile data or None
        """
        if not self.current_session_path:
            return None
        
        filepath = self.current_session_path / self.PROFILES_DIR / filename
        if not filepath.exists():
            return None
        
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

    def profile_path(self, filename: str) -> Optional[Path]:
        """Retourne le chemin profil local courant sans verifier le contenu JSON."""
        if not self.current_session_path:
            return None
        path = self.current_session_path / self.PROFILES_DIR / filename
        return path if path.exists() else None
    
    def list_profiles(self) -> List[Dict[str, Any]]:
        """
        List all profiles in current session.
        
        Returns:
            List of profile info dictionaries
        """
        if not self.current_session_path:
            return []
        
        profiles = []
        profiles_dir = self.current_session_path / self.PROFILES_DIR
        
        if not profiles_dir.exists():
            return []
        
        for item in profiles_dir.glob("*.json"):
            try:
                with open(item, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                identity = data.get('identity', {}) or {}
                profiles.append({
                    'filename': item.name,
                    'last_name': (identity.get('last_name') or ''),
                    'first_name': (identity.get('first_name') or ''),
                    'email': (data.get('email') or ''),
                    'path': str(item)
                })
            except Exception:
                pass
        
        # Sort by last name (handle None/empty safely)
        profiles.sort(key=lambda x: (x.get('last_name') or '').lower())
        return profiles
    
    def delete_profile(self, filename: str) -> bool:
        """Delete a profile"""
        if not self.current_session_path:
            return False
        
        filepath = self.current_session_path / self.PROFILES_DIR / filename
        if filepath.exists():
            filepath.unlink()
            # Remove any matches for this profile
            self.matches = [m for m in self.matches if m.profile_name != filename]
            self._save_matches()
            return True
        return False
    
    # ==================== XML OPERATIONS ====================
    
    def import_xml(self, xml_path: str) -> str:
        """
        Import an XML file to current session.
        
        Args:
            xml_path: Path to XML file
            
        Returns:
            Imported filename
        """
        if not self.current_session_path:
            raise ValueError("No session loaded")
        
        source = Path(xml_path)
        if not source.exists():
            raise FileNotFoundError(f"XML file not found: {xml_path}")
        
        dest_dir = self.current_session_path / self.XML_DIR
        dest = dest_dir / source.name
        
        # Handle duplicates
        counter = 1
        while dest.exists():
            stem = source.stem
            dest = dest_dir / f"{stem}_{counter}{source.suffix}"
            counter += 1
        
        shutil.copy2(source, dest)
        return dest.name
    
    def list_xmls(self) -> List[Dict[str, Any]]:
        """
        List all XML files in current session.
        
        Returns:
            List of XML info dictionaries
        """
        if not self.current_session_path:
            return []
        
        xmls = []
        xml_dir = self.current_session_path / self.XML_DIR
        
        if not xml_dir.exists():
            return []
        
        for item in xml_dir.glob("*.xml"):
            # Try to extract info from filename (TCP_LASTNAME_Firstname_date.xml)
            parts = item.stem.split('_')
            last_name = parts[1] if len(parts) > 1 else ''
            first_name = parts[2] if len(parts) > 2 else ''
            
            xmls.append({
                'filename': item.name,
                'last_name': last_name,
                'first_name': first_name,
                'path': str(item),
                'size': item.stat().st_size
            })
        
        return xmls
    
    def get_xml_path(self, filename: str) -> Optional[str]:
        """Get full path to an XML file"""
        if not self.current_session_path:
            return None
        
        filepath = self.current_session_path / self.XML_DIR / filename
        if filepath.exists():
            return str(filepath)
        return None

    def xml_path(self, filename: str) -> Optional[Path]:
        """Retourne le chemin XML local courant sous forme Path."""
        path = self.get_xml_path(filename)
        return Path(path) if path else None
    
    # ==================== MATCHING OPERATIONS ====================
    
    def _load_matches(self):
        """Load matches from file"""
        if not self.current_session_path:
            self.matches = []
            return
        
        matches_file = self.current_session_path / self.MATCHES_FILE
        if matches_file.exists():
            with open(matches_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.matches = [ProfileMatch.from_dict(m) for m in data]
        else:
            self.matches = []
    
    def _save_matches(self):
        """Sauvegarde matches.json par remplacement atomique dans le meme dossier."""
        if not self.current_session_path:
            return

        matches_file = self.current_session_path / self.MATCHES_FILE
        temporary_file = matches_file.with_suffix(matches_file.suffix + '.tmp')
        try:
            with open(temporary_file, 'w', encoding='utf-8') as f:
                json.dump([m.to_dict() for m in self.matches], f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporary_file, matches_file)
        finally:
            if temporary_file.exists():
                temporary_file.unlink()
    
    def create_match(self, profile_filename: str, xml_filename: str) -> ProfileMatch:
        """
        Create a match between a profile and an XML file.
        
        Args:
            profile_filename: Profile JSON filename
            xml_filename: XML filename
            
        Returns:
            Created ProfileMatch
        """
        # Remove any existing match for this profile or XML
        self.matches = [m for m in self.matches 
                       if m.profile_name != profile_filename 
                       and m.xml_filename != xml_filename]
        
        match = ProfileMatch(
            profile_name=profile_filename,
            xml_filename=xml_filename
        )
        self.matches.append(match)
        self._save_matches()
        
        return match
    
    def remove_match(self, profile_filename: str) -> bool:
        """Remove a match by profile filename"""
        initial_count = len(self.matches)
        self.matches = [m for m in self.matches if m.profile_name != profile_filename]
        
        if len(self.matches) < initial_count:
            self._save_matches()
            return True
        return False
    
    def get_match_for_profile(self, profile_filename: str) -> Optional[ProfileMatch]:
        """Get match for a profile"""
        for match in self.matches:
            if match.profile_name == profile_filename:
                return match
        return None
    
    def get_match_for_xml(self, xml_filename: str) -> Optional[ProfileMatch]:
        """Get match for an XML file"""
        for match in self.matches:
            if match.xml_filename == xml_filename:
                return match
        return None
    
    def get_unmatched_profiles(self) -> List[Dict[str, Any]]:
        """Get profiles that are not matched"""
        all_profiles = self.list_profiles()
        matched_names = {m.profile_name for m in self.matches}
        return [p for p in all_profiles if p['filename'] not in matched_names]
    
    def get_unmatched_xmls(self) -> List[Dict[str, Any]]:
        """Get XMLs that are not matched"""
        all_xmls = self.list_xmls()
        matched_names = {m.xml_filename for m in self.matches}
        return [x for x in all_xmls if x['filename'] not in matched_names]
    
    def mark_as_exported(self, profile_filename: str):
        """Mark a match as exported"""
        for match in self.matches:
            if match.profile_name == profile_filename:
                match.exported = True
                self._save_matches()
                break
    
    # ==================== OUTPUT OPERATIONS ====================
    
    def get_output_dir(self) -> Optional[str]:
        """Get output directory path"""
        if not self.current_session_path:
            return None
        return str(self.current_session_path / self.OUTPUT_DIR)
    
    def save_output(self, filename: str, data: Dict[str, Any]) -> str:
        """
        Save output JSON to session output folder.
        
        Args:
            filename: Output filename
            data: Data to save
            
        Returns:
            Full path to saved file
        """
        if not self.current_session_path:
            raise ValueError("No session loaded")
        
        output_dir = self.current_session_path / self.OUTPUT_DIR
        output_dir.mkdir(exist_ok=True)
        
        filepath = output_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return str(filepath)

    def build_match_fingerprint(self, match: ProfileMatch) -> Optional[Dict[str, Any]]:
        """Fingerprint anti-stale sans exposer de chemins disque.

        Sources: session courante, fichier profil et XML importes. Les hash
        SHA-256 protegent l'export contre un sidecar EC issu d'un ancien fichier.
        """
        if not self.current_session_path or not self.current_session:
            return None
        profile_path = self.profile_path(match.profile_name)
        xml_path = self.xml_path(match.xml_filename)
        if not profile_path or not xml_path:
            return None
        try:
            xml_size = xml_path.stat().st_size
        except OSError:
            return None
        return {
            "session": {
                "name": self.current_session.name,
                "created_at": self.current_session.created_at,
            },
            "profile": {
                "filename": match.profile_name,
                "sha256": self._file_sha256(profile_path),
            },
            "xml": {
                "filename": match.xml_filename,
                "sha256": self._file_sha256(xml_path),
                "size": xml_size,
            },
        }

    def build_metasoft_source_fingerprint(
        self,
        match: ProfileMatch,
    ) -> Optional[Dict[str, Any]]:
        """Fingerprint de source MetaSoft independant des autres champs profil.

        Le nom du fichier profil identifie l'association. Le hash XML protege
        contre un rematch ou une modification de mesures; le contenu complet du
        profil n'entre pas ici car seuls les champs marqueurs sont snapshotes.
        """
        if not self.current_session_path or not self.current_session:
            return None
        if not self.profile_path(match.profile_name):
            return None
        xml_path = self.xml_path(match.xml_filename)
        if not xml_path:
            return None
        try:
            xml_size = xml_path.stat().st_size
            xml_hash = self._file_sha256(xml_path)
        except OSError:
            return None
        return {
            "session": {
                "name": self.current_session.name,
                "created_at": self.current_session.created_at,
            },
            "profile_filename": match.profile_name,
            "xml": {
                "filename": match.xml_filename,
                "sha256": xml_hash,
                "size": xml_size,
            },
        }

    def validate_metasoft_report(
        self,
        match: ProfileMatch,
        profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Valide provenance source et snapshot des champs marqueurs profil."""
        from core.metasoft_markers import metasoft_profile_marker_snapshot

        report = match.metasoft_report
        if not isinstance(report, dict):
            return {"valid": False, "reason": "missing", "markers": {}}
        if report.get("schema_version") != 1:
            return {"valid": False, "reason": "schema", "markers": {}}
        fingerprint = self.build_metasoft_source_fingerprint(match)
        if not fingerprint:
            return {"valid": False, "reason": "source_unavailable", "markers": {}}
        if report.get("source_fingerprint") != fingerprint:
            return {"valid": False, "reason": "source_changed", "markers": {}}
        if report.get("profile_marker_snapshot") != metasoft_profile_marker_snapshot(profile):
            return {"valid": False, "reason": "profile_markers_changed", "markers": {}}
        markers = report.get("markers")
        if not isinstance(markers, dict):
            return {"valid": False, "reason": "invalid_markers", "markers": {}}
        return {"valid": True, "reason": None, "markers": deepcopy(markers)}

    def record_metasoft_report(
        self,
        match: ProfileMatch,
        profile: Dict[str, Any],
        markers: Dict[str, Any],
    ) -> None:
        """Enregistre en dernier l'etat canonique d'un report MetaSoft reussi."""
        from core.metasoft_markers import metasoft_profile_marker_snapshot

        fingerprint = self.build_metasoft_source_fingerprint(match)
        if not fingerprint:
            raise ValueError("Fingerprint source MetaSoft indisponible")
        match.metasoft_report = {
            "schema_version": 1,
            "source_fingerprint": fingerprint,
            "markers": deepcopy(markers),
            "profile_marker_snapshot": metasoft_profile_marker_snapshot(profile),
            "reported_at": datetime.now().isoformat(),
        }
        try:
            self._save_matches()
        except Exception:
            # Sans ecriture matches.json confirmee, l'export courant doit rester
            # bloque plutot que reutiliser une ancienne preuve en memoire.
            match.metasoft_report = {
                "schema_version": 1,
                "status": "record_failed",
            }
            raise

    def invalidate_metasoft_report(self, match: ProfileMatch) -> None:
        """Persiste un etat non exportable avant les ecritures d'un report."""
        previous = deepcopy(match.metasoft_report)
        match.metasoft_report = {
            "schema_version": 1,
            "status": "report_in_progress",
        }
        try:
            self._save_matches()
        except Exception:
            match.metasoft_report = previous
            raise

    def clear_manual_running_economy(self, match_id: str) -> None:
        """Supprime l'EC manuelle sauvegardee pour ce match uniquement."""
        if not self.current_session_path:
            raise ValueError("No session loaded")
        payload = self._load_manual_running_economy_payload()
        payload.pop(str(match_id), None)
        self._write_manual_running_economy_payload(payload)

    def save_manual_running_economy(
        self,
        match_id: str,
        data: Dict[str, Any],
        fingerprint: Dict[str, Any],
    ) -> None:
        """Persiste l'EC manuelle Python avec fingerprint anti-stale."""
        if not self.current_session_path:
            raise ValueError("No session loaded")
        payload = self._load_manual_running_economy_payload()
        payload[str(match_id)] = {
            "fingerprint": fingerprint,
            "data": data,
        }
        self._write_manual_running_economy_payload(payload)

    def get_manual_running_economy(
        self,
        match_id: str,
        fingerprint: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Retourne l'EC manuelle seulement si le sidecar est fingerprint-compatible."""
        item = self._load_manual_running_economy_payload().get(str(match_id))
        if not isinstance(item, dict):
            return None
        stored_fingerprint = item.get("fingerprint")
        if not stored_fingerprint or fingerprint is None:
            return None
        if stored_fingerprint != fingerprint:
            return None
        data = item.get("data")
        return data if isinstance(data, dict) else None

    def _load_manual_running_economy_payload(self) -> Dict[str, Any]:
        if not self.current_session_path:
            return {}
        path = self.current_session_path / self.MANUAL_RUNNING_ECONOMY_FILE
        if not path.exists():
            return {}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _write_manual_running_economy_payload(self, payload: Dict[str, Any]) -> None:
        path = self.current_session_path / self.MANUAL_RUNNING_ECONOMY_FILE
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    def _file_sha256(self, path: Path) -> str:
        digest = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
