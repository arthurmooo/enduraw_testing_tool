"""
TCP Data Processor - Session-Based Main Application
Tab-based UI with Sessions, Profiles, and XML Matching
"""
import os
import subprocess
import sys
import customtkinter as ctk
from datetime import datetime
from hashlib import sha256
from tkinter import filedialog, messagebox
from typing import Dict, List, Any, Optional
from pathlib import Path

from utils.xml_parser import TCPXmlParser
from core.data_transformer import DataTransformer
from core.metasoft_identity import metasoft_identity_check
from core.metasoft_markers import metasoft_unproven_profile_markers
from core.metasoft_audit_export import (
    build_metasoft_audit_export,
    metasoft_audit_filename,
)
from utils.json_exporter import JsonExporter
from core.session_manager import SessionManager, metasoft_profile_has_lactates
from core.mongo_service import MongoService
from core.protocol_store import ProtocolStore
from core.app_paths import (
    ensure_user_data_dirs,
    resource_root as resolve_resource_root,
    user_data_root,
)
from ui.app_tabs import SessionListItem, ProfileListItem, XmlListItem, MatchListItem
from config import APP_NAME, APP_VERSION, SIDEBAR_COLORS, SIDEBAR_WIDTH

# Import TabbedInputForm (3 tabs: Profil/Perso, Mesures Test, Analyse)
from ui.tabbed_form import TabbedInputForm

# Set appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


def _open_local_folder(path: Path) -> None:
    """Ouvre un dossier local avec le gestionnaire natif, sans shell."""
    path = Path(path)
    if sys.platform.startswith("win"):
        os.startfile(str(path))
        return
    command = "open" if sys.platform == "darwin" else "xdg-open"
    subprocess.Popen([command, str(path)])


def _open_metasoft_match(session_manager: SessionManager, match_info: Dict[str, Any]) -> None:
    """Ouvre l'analyse React locale du match dans le navigateur par défaut."""
    import webbrowser

    from local_api.metasoft_server import LocalMetaSoftServer

    try:
        server = LocalMetaSoftServer.ensure_started(session_manager)
        url = server.url_for_match(match_info)
        if not webbrowser.open(url):
            messagebox.showinfo("Analyse MetaSoft", f"URL locale:\n{url}")
    except Exception as error:
        messagebox.showerror("Analyse MetaSoft", f"Ouverture impossible:\n{error}")


def _save_metasoft_audit_sidecar(
    session_manager: SessionManager,
    xml_data: Dict[str, Any],
    profile_data: Dict[str, Any],
    output_filename: str,
    profile_filename: str,
    markers: Optional[Dict[str, Any]] = None,
    manual_running_economy: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Sauve le sidecar MetaSoft avec les marqueurs canoniques prouves.

    Source: analyse MetaSoft deja parse/recalculee par `DataTransformer` et EC
    manuelle validee pour le match. Transformation: export audit pur, sans
    points bruts decimes ni warnings UI.
    Fallback: aucun sidecar si le XML historique n'expose pas d'analyse MetaSoft.
    """
    analysis = xml_data.get("metasoft_analysis")
    if not analysis:
        return None

    audit_filename = metasoft_audit_filename(output_filename)
    sidecar = build_metasoft_audit_export(
        analysis,
        profile=profile_data,
        markers=markers or {},
        manual_running_economy=manual_running_economy,
        json_filename=output_filename,
        audit_filename=audit_filename,
        profile_filename=profile_filename,
        generated_at=datetime.now().isoformat(timespec="seconds"),
        app_version=APP_VERSION,
    )
    return session_manager.save_output(audit_filename, sidecar)


def _validated_metasoft_export_markers(
    session_manager: SessionManager,
    match,
    xml_data: Dict[str, Any],
    profile_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Bloque l'export si identite ou provenance MetaSoft n'est pas prouvee."""
    analysis = xml_data.get("metasoft_analysis")
    if not isinstance(analysis, dict):
        # Le garde-fou ne change pas le contrat des anciens flux non MetaSoft.
        return {}
    identity = metasoft_identity_check(analysis.get("athlete", {}), profile_data)
    if not identity["ok"]:
        raise ValueError(
            f"{identity['code']}: {identity['message']} "
            f"(XML={identity['xml_athlete_name']!r}, profil={identity['profile_athlete_name']!r})"
        )

    provenance = session_manager.validate_metasoft_report(match, profile_data)
    profile_markers = metasoft_unproven_profile_markers(profile_data, {})
    profile_has_lactates = metasoft_profile_has_lactates(profile_data)
    if not provenance["valid"]:
        # Un report invalide explicite reste bloquant meme si le profil ne porte
        # aucun seuil; `missing` reste compatible avec un profil historiquement vide.
        if profile_has_lactates and not profile_markers:
            raise ValueError(
                "lactate_provenance_stale: lactates MetaSoft absents ou perimes "
                f"({provenance['reason']})."
            )
        if profile_markers or match.metasoft_report is not None:
            raise ValueError(
                "marker_provenance_stale: provenance MetaSoft absente ou perimee "
                f"({provenance['reason']})."
            )
        return {}

    unproven = metasoft_unproven_profile_markers(
        profile_data,
        provenance["markers"],
    )
    if unproven:
        raise ValueError(
            "marker_provenance_incomplete: champs profil sans marqueur MetaSoft "
            f"prouve ({', '.join(unproven)})."
        )
    return provenance["markers"]


def _validated_manual_running_economy(session_manager, match, match_id):
    """Retourne l'EC exportable ou bloque explicitement stale/corrupt."""
    state = session_manager.manual_running_economy_state(match_id, match)
    if state["status"] == "missing":
        return None
    if state["status"] != "ok":
        raise ValueError(
            f"manual_running_economy_{state['status']}: {state.get('reason', '')}"
        )
    return state["data"]


def _match_id(profile_name: str, xml_filename: str) -> str:
    raw = f"{Path(str(profile_name)).name}\0{Path(str(xml_filename)).name}"
    return sha256(raw.encode("utf-8")).hexdigest()[:12]


class SessionTab(ctk.CTkFrame):
    """Tab for managing sessions"""
    
    def __init__(self, master, session_manager: SessionManager, on_session_loaded=None, **kwargs):
        super().__init__(master, **kwargs)
        self.session_manager = session_manager
        self.on_session_loaded = on_session_loaded
        self.session_items: List[SessionListItem] = []
        self.selected_item: Optional[SessionListItem] = None
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        self._create_ui()
        self._refresh_sessions()
    
    def _create_ui(self):
        # Header with buttons
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        header.grid_columnconfigure(1, weight=1)
        
        title = ctk.CTkLabel(header, text="Sessions", font=ctk.CTkFont(size=18, weight="bold"))
        title.grid(row=0, column=0, sticky="w")
        
        btn_frame = ctk.CTkFrame(header, fg_color="transparent")
        btn_frame.grid(row=0, column=2)
        
        self.new_btn = ctk.CTkButton(btn_frame, text="+ Nouvelle Session", command=self._new_session)
        self.new_btn.grid(row=0, column=0, padx=5)
        
        self.open_btn = ctk.CTkButton(btn_frame, text="Ouvrir", command=self._open_session, state="disabled")
        self.open_btn.grid(row=0, column=1, padx=5)

        self.folder_btn = ctk.CTkButton(
            btn_frame,
            text="Ouvrir dossier",
            command=self._open_data_folder,
        )
        self.folder_btn.grid(row=0, column=2, padx=5)
        
        self.delete_btn = ctk.CTkButton(btn_frame, text="Supprimer", fg_color="#c0392b", 
                                        hover_color="#a93226", command=self._delete_session, state="disabled")
        self.delete_btn.grid(row=0, column=3, padx=5)
        
        # Session list
        self.session_list = ctk.CTkScrollableFrame(self)
        self.session_list.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.session_list.grid_columnconfigure(0, weight=1)
        
        # Current session info
        self.info_frame = ctk.CTkFrame(self)
        self.info_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
        
        self.session_label = ctk.CTkLabel(self.info_frame, text="Aucune session active",
                                          font=ctk.CTkFont(size=14, weight="bold"))
        self.session_label.grid(row=0, column=0, padx=15, pady=10)
    
    def _refresh_sessions(self):
        for item in self.session_items:
            item.destroy()
        self.session_items.clear()
        self.selected_item = None
        
        sessions = self.session_manager.list_sessions()
        for session_info in sessions:
            item = SessionListItem(self.session_list, session_info, on_select=self._on_select)
            item.grid(sticky="ew", pady=2)
            self.session_items.append(item)
        
        self._update_buttons()
        self._update_current_session_info()
    
    def _on_select(self, item: SessionListItem):
        if self.selected_item:
            self.selected_item.set_selected(False)
        self.selected_item = item
        item.set_selected(True)
        self._update_buttons()
    
    def _update_buttons(self):
        state = "normal" if self.selected_item else "disabled"
        self.open_btn.configure(state=state)
        self.delete_btn.configure(state=state)
    
    def _update_current_session_info(self):
        if self.session_manager.current_session:
            s = self.session_manager.current_session
            self.session_label.configure(text=f"Session active: {s.name} ({s.location})")
        else:
            self.session_label.configure(text="Aucune session active")
    
    def _new_session(self):
        dialog = NewSessionDialog(self)
        self.wait_window(dialog)
        
        if dialog.result:
            try:
                self.session_manager.create_session(
                    date=dialog.result['date'],
                    location=dialog.result['location'],
                    description=dialog.result.get('description', '')
                )
                self._refresh_sessions()
                if self.on_session_loaded:
                    self.on_session_loaded()
                messagebox.showinfo("Succès", "Session créée avec succès!")
            except Exception as e:
                messagebox.showerror("Erreur", f"Erreur lors de la création: {e}")
    
    def _open_session(self):
        if not self.selected_item:
            return
        try:
            path = self.selected_item.session_info.get('path', '')
            self.session_manager.load_session(path)
            self._update_current_session_info()
            if self.on_session_loaded:
                self.on_session_loaded()
            messagebox.showinfo("Succès", "Session chargée!")
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur: {e}")

    def _open_data_folder(self):
        try:
            _open_local_folder(self.session_manager.base_path)
        except Exception as error:
            messagebox.showerror(
                "Dossier de données",
                f"Ouverture impossible:\n{error}",
            )
    
    def _delete_session(self):
        if not self.selected_item:
            return
        if not messagebox.askyesno("Confirmer", "Supprimer cette session et tout son contenu?"):
            return
        try:
            path = self.selected_item.session_info.get('path', '')
            self.session_manager.delete_session(path)
            self._refresh_sessions()
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur: {e}")


class NewSessionDialog(ctk.CTkToplevel):
    """Dialog for creating a new session"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.result = None
        
        self.title("Nouvelle Session")
        self.geometry("400x250")
        self.transient(parent)
        self.grab_set()
        
        # Form
        ctk.CTkLabel(self, text="Date (YYYY-MM-DD):").grid(row=0, column=0, padx=20, pady=10, sticky="w")
        self.date_entry = ctk.CTkEntry(self, width=200)
        self.date_entry.grid(row=0, column=1, padx=20, pady=10)
        
        from datetime import datetime
        self.date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
        
        ctk.CTkLabel(self, text="Lieu:").grid(row=1, column=0, padx=20, pady=10, sticky="w")
        self.location_entry = ctk.CTkEntry(self, width=200)
        self.location_entry.grid(row=1, column=1, padx=20, pady=10)
        
        ctk.CTkLabel(self, text="Description:").grid(row=2, column=0, padx=20, pady=10, sticky="w")
        self.desc_entry = ctk.CTkEntry(self, width=200)
        self.desc_entry.grid(row=2, column=1, padx=20, pady=10)
        
        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=3, column=0, columnspan=2, pady=20)
        
        ctk.CTkButton(btn_frame, text="Créer", command=self._create).grid(row=0, column=0, padx=10)
        ctk.CTkButton(btn_frame, text="Annuler", fg_color="gray", command=self.destroy).grid(row=0, column=1, padx=10)
    
    def _create(self):
        date = self.date_entry.get().strip()
        location = self.location_entry.get().strip()
        
        if not date or not location:
            messagebox.showwarning("Attention", "Date et lieu sont requis")
            return
        
        self.result = {
            'date': date,
            'location': location,
            'description': self.desc_entry.get().strip()
        }
        self.destroy()


class ProfileTab(ctk.CTkFrame):
    """Tab for managing profiles"""
    
    def __init__(self, master, session_manager: SessionManager, mongo_service: Optional[MongoService] = None, protocol_store: Optional[ProtocolStore] = None, **kwargs):
        super().__init__(master, **kwargs)
        self.session_manager = session_manager
        self.mongo_service = mongo_service
        self.protocol_store = protocol_store
        self.profile_items: List[ProfileListItem] = []
        self.selected_item: Optional[ProfileListItem] = None
        self.current_filename: Optional[str] = None
        
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self._create_ui()
    
    def _create_ui(self):
        # Left panel - profile list
        left_panel = ctk.CTkFrame(self, width=280)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)
        left_panel.grid_rowconfigure(1, weight=1)
        left_panel.grid_propagate(False)
        
        # Header
        header = ctk.CTkFrame(left_panel, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        
        ctk.CTkLabel(header, text="Profils", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0)
        
        self.new_btn = ctk.CTkButton(header, text="+", width=30, command=self._new_profile)
        self.new_btn.grid(row=0, column=1, padx=5)
        
        self.delete_btn = ctk.CTkButton(header, text="Suppr.", width=50, fg_color="#c0392b",
                                        hover_color="#a93226", command=self._delete_profile, state="disabled")
        self.delete_btn.grid(row=0, column=2)
        
        # List
        self.profile_list = ctk.CTkScrollableFrame(left_panel)
        self.profile_list.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.profile_list.grid_columnconfigure(0, weight=1)
        
        # Right panel - form
        right_panel = ctk.CTkFrame(self)
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
        right_panel.grid_columnconfigure(0, weight=1)
        right_panel.grid_rowconfigure(1, weight=1)
        
        # Form header
        form_header = ctk.CTkFrame(right_panel, fg_color="transparent")
        form_header.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        form_header.grid_columnconfigure(0, weight=1)
        
        self.form_title = ctk.CTkLabel(form_header, text="Sélectionnez un profil",
                                       font=ctk.CTkFont(size=16, weight="bold"))
        self.form_title.grid(row=0, column=0, sticky="w")
        
        self.analysis_btn = ctk.CTkButton(
            form_header,
            text="Ouvrir l'analyse MetaSoft",
            command=self._open_metasoft_analysis,
            state="disabled",
            fg_color="#167d5b",
            hover_color="#12694d",
        )
        self.analysis_btn.grid(row=0, column=1, padx=(0, 8))

        self.save_btn = ctk.CTkButton(
            form_header,
            text="Sauvegarder",
            command=self._save_profile,
            state="disabled",
        )
        self.save_btn.grid(row=0, column=2)
        
        # Form (tabbed: Profil/Perso, Mesures Test, Analyse)
        self.form = TabbedInputForm(right_panel, on_db_lookup=self._on_db_lookup, protocol_store=self.protocol_store)
        self.form.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
    
    def refresh(self):
        """Refresh profile list"""
        for item in self.profile_items:
            item.destroy()
        self.profile_items.clear()
        self.selected_item = None
        self.current_filename = None
        
        if not self.session_manager.current_session:
            self.form.clear()
            self.form_title.configure(text="Aucune session active")
            self._update_buttons()
            return
        
        profiles = self.session_manager.list_profiles()
        for profile_info in profiles:
            # Check if matched
            match = self.session_manager.get_match_for_profile(profile_info['filename'])
            item = ProfileListItem(self.profile_list, profile_info, on_select=self._on_select)
            item.set_matched(match is not None)
            item.grid(sticky="ew", pady=2)
            self.profile_items.append(item)
        
        self.form.clear()
        self.form_title.configure(text="Sélectionnez un profil")
        self._update_buttons()
    
    def _on_select(self, item: ProfileListItem):
        # Deselect previous item (only if widget still exists)
        if self.selected_item:
            try:
                if self.selected_item.winfo_exists():
                    self.selected_item.set_selected(False)
            except Exception:
                pass  # Widget was destroyed, ignore
        
        self.selected_item = item
        self.current_filename = item.profile_info.get('filename')
        
        # Check if clicked item still exists
        try:
            if not item.winfo_exists():
                return
            item.set_selected(True)
        except Exception:
            return
        
        # Load profile data
        data = self.session_manager.get_profile(self.current_filename)
        if data:
            self.form.set_data(data)
            self._refresh_metasoft_context(data)
            # Safely get name (handle None values)
            identity = data.get('identity') or {}
            last_name = (identity.get('last_name') or '').strip()
            first_name = (identity.get('first_name') or '').strip()
            name = f"{last_name} {first_name}".strip()
            self.form_title.configure(text=name or "Nouveau profil")
        else:
            self.form.clear()
            self.form_title.configure(text="Profil non trouvé")
        
        self._update_buttons()
    
    def _update_buttons(self):
        state = "normal" if self.selected_item else "disabled"
        self.save_btn.configure(state=state)
        self.delete_btn.configure(state=state)
        match = (
            self.session_manager.get_match_for_profile(self.current_filename)
            if self.current_filename
            else None
        )
        self.analysis_btn.configure(state="normal" if match else "disabled")

    def _refresh_metasoft_context(self, profile: Dict[str, Any]) -> None:
        """Relit l'EC liée au match; les lactates restent lus dans le profil."""
        match = self.session_manager.get_match_for_profile(self.current_filename)
        economy_state = {"status": "missing", "data": None, "reason": None}
        if match:
            match_id = _match_id(match.profile_name, match.xml_filename)
            economy_state = self.session_manager.manual_running_economy_state(
                match_id,
                match,
            )
        self.form.set_metasoft_context(profile, economy_state, matched=match is not None)

    def _open_metasoft_analysis(self) -> None:
        if not self.current_filename:
            return
        match = self.session_manager.get_match_for_profile(self.current_filename)
        if match:
            _open_metasoft_match(self.session_manager, match.to_dict())
    
    def _new_profile(self):
        if not self.session_manager.current_session:
            messagebox.showwarning("Attention", "Veuillez d'abord ouvrir une session")
            return
        
        # Save current first
        if self.current_filename:
            self._save_profile(silent=True)
        
        from core.profile_template import get_empty_profile
        empty = get_empty_profile()
        
        try:
            filename = self.session_manager.add_profile(empty)
            self.refresh()
            
            # Select the new profile
            for item in self.profile_items:
                if item.profile_info.get('filename') == filename:
                    self._on_select(item)
                    break
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur: {e}")
    
    def _save_profile(self, silent=False):
        if not self.current_filename:
            return
        
        # Validate data before saving
        is_valid, msg = self.form.validate_all()
        if not is_valid:
            if not silent:
                messagebox.showerror("Erreur de Validation", msg)
            return

        # Check if file still exists (might have been deleted)
        profile_exists = self.session_manager.get_profile(self.current_filename) is not None
        if not profile_exists:
            if not silent:
                messagebox.showwarning("Attention", "Ce profil n'existe plus. Rafraîchissement...")
            self.current_filename = None
            self.refresh()
            return
        
        data = self.form.get_data()
        try:
            # update_profile now returns new filename (may be renamed)
            new_filename = self.session_manager.update_profile(self.current_filename, data)
            if new_filename:
                # Update current filename if it was renamed
                self.current_filename = new_filename
                self._refresh_metasoft_context(data)
                
                if not silent:
                    self.save_btn.configure(text="Sauvegardé")
                    self.after(1500, lambda: self.save_btn.configure(text="Sauvegarder"))
                    
                    # Update the form title with the new name
                    identity = data.get('identity') or {}
                    last_name = (identity.get('last_name') or '').strip()
                    first_name = (identity.get('first_name') or '').strip()
                    name = f"{last_name} {first_name}".strip()
                    self.form_title.configure(text=name or "Nouveau profil")
                    
                    # Only refresh the profile list on explicit save (not silent)
                    # to avoid destroying widgets during click handlers
                    self._refresh_profile_list()
            elif not silent:
                messagebox.showerror("Erreur", "Impossible de sauvegarder le profil")
        except Exception as e:
            if not silent:
                messagebox.showerror("Erreur", f"Erreur: {e}")
    
    def _refresh_profile_list(self):
        """Refresh profile list while keeping current selection"""
        saved_filename = self.current_filename
        
        # Clear and rebuild list
        for item in self.profile_items:
            item.destroy()
        self.profile_items.clear()
        
        if not self.session_manager.current_session:
            return
        
        profiles = self.session_manager.list_profiles()
        for profile_info in profiles:
            match = self.session_manager.get_match_for_profile(profile_info['filename'])
            item = ProfileListItem(self.profile_list, profile_info, on_select=self._on_select)
            item.set_matched(match is not None)
            item.grid(sticky="ew", pady=2)
            self.profile_items.append(item)
            
            # Re-select the previously selected item
            if profile_info.get('filename') == saved_filename:
                self.selected_item = item
                item.set_selected(True)

    def reload_profile_from_disk(self, filename: str):
        """Reload a profile changed by the local React analysis window."""
        if not filename:
            return

        if self.current_filename == filename:
            data = self.session_manager.get_profile(filename)
            if data:
                self.form.set_data(data)
                self._refresh_metasoft_context(data)
                identity = data.get('identity') or {}
                last_name = (identity.get('last_name') or '').strip()
                first_name = (identity.get('first_name') or '').strip()
                name = f"{last_name} {first_name}".strip()
                self.form_title.configure(text=name or "Nouveau profil")

        self._refresh_profile_list()
    
    def _delete_profile(self):
        if not self.current_filename:
            return
        if not messagebox.askyesno("Confirmer", "Supprimer ce profil?"):
            return
        
        self.session_manager.delete_profile(self.current_filename)
        self.current_filename = None
        self.refresh()

    # ------------------------------------------------------------------ #
    #  DB Lookup                                                          #
    # ------------------------------------------------------------------ #
    def _on_db_lookup(self, email: str):
        """
        Called when user clicks the DB lookup button in the form.
        Searches MongoDB for the user and merges data into empty fields.
        """
        if not self.mongo_service or not self.mongo_service.is_connected:
            self.form.set_db_status("Non connecte a la DB", color="red")
            return

        self.form.set_db_status("Recherche en cours...", color="gray")
        self.update_idletasks()  # Force UI refresh

        user = self.mongo_service.find_user_by_email(email)
        if user:
            # Convert DB doc to profile format
            db_profile = MongoService.db_user_to_profile(user)
            filled = self.form.merge_db_data(db_profile)
            username = user.get("username", email)
            self.form.set_db_status(
                f"Trouve : {username} - {filled} champ(s) pre-rempli(s)",
                color="green"
            )
        else:
            self.form.set_db_status(
                "Aucun compte trouve - un profil sera cree a l'export",
                color="orange"
            )


class XmlMatchTab(ctk.CTkFrame):
    """Tab for matching XMLs with profiles"""
    
    def __init__(self, master, session_manager: SessionManager, mongo_service: Optional[MongoService] = None, **kwargs):
        super().__init__(master, **kwargs)
        self.session_manager = session_manager
        self.mongo_service = mongo_service
        self.parser = TCPXmlParser()
        self.transformer = DataTransformer()
        self.exporter = JsonExporter()
        
        self.xml_items: List[XmlListItem] = []
        self.profile_items: List[ProfileListItem] = []
        self.match_items: List[MatchListItem] = []
        
        self.selected_xml: Optional[XmlListItem] = None
        self.selected_profile: Optional[ProfileListItem] = None
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        self._create_ui()
    
    def _create_ui(self):
        # === LEFT: XMLs ===
        xml_panel = ctk.CTkFrame(self)
        xml_panel.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=5, pady=10)
        xml_panel.grid_rowconfigure(1, weight=1)
        xml_panel.grid_columnconfigure(0, weight=1)
        
        # XML header
        xml_header = ctk.CTkFrame(xml_panel, fg_color="transparent")
        xml_header.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        
        ctk.CTkLabel(xml_header, text="Fichiers XML", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0)
        ctk.CTkButton(xml_header, text="Importer", width=80, command=self._import_xmls).grid(row=0, column=1, padx=5)
        
        self.xml_list = ctk.CTkScrollableFrame(xml_panel)
        self.xml_list.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.xml_list.grid_columnconfigure(0, weight=1)
        
        # === CENTER: Actions ===
        center_panel = ctk.CTkFrame(self, fg_color="transparent")
        center_panel.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=5, pady=10)
        center_panel.grid_rowconfigure(0, weight=1)
        
        action_frame = ctk.CTkFrame(center_panel)
        action_frame.place(relx=0.5, rely=0.3, anchor="center")
        
        self.match_btn = ctk.CTkButton(action_frame, text="Matcher", width=120, height=40,
                                       font=ctk.CTkFont(size=14), command=self._create_match, state="disabled")
        self.match_btn.grid(row=0, column=0, pady=10)
        
        ctk.CTkLabel(action_frame, text="Sélectionnez un XML\net un profil", 
                    text_color="gray", justify="center").grid(row=1, column=0)
        
        # === RIGHT: Profiles ===
        profile_panel = ctk.CTkFrame(self)
        profile_panel.grid(row=0, column=2, rowspan=2, sticky="nsew", padx=5, pady=10)
        profile_panel.grid_rowconfigure(1, weight=1)
        profile_panel.grid_columnconfigure(0, weight=1)
        
        # Profile header
        profile_header = ctk.CTkFrame(profile_panel, fg_color="transparent")
        profile_header.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        
        ctk.CTkLabel(profile_header, text="Profils", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0)
        ctk.CTkButton(profile_header, text="Refresh", width=60, command=self.refresh).grid(row=0, column=1, padx=5)
        
        self.profile_list = ctk.CTkScrollableFrame(profile_panel)
        self.profile_list.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.profile_list.grid_columnconfigure(0, weight=1)
        
        # === BOTTOM: Matches ===
        match_panel = ctk.CTkFrame(self)
        match_panel.grid(row=2, column=0, columnspan=3, sticky="nsew", padx=5, pady=5)
        match_panel.grid_columnconfigure(0, weight=1)
        match_panel.grid_rowconfigure(1, weight=1)
        
        match_header = ctk.CTkFrame(match_panel, fg_color="transparent")
        match_header.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        match_header.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(match_header, text="Associations", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, padx=5, sticky="w")
        
        self.export_all_btn = ctk.CTkButton(
            match_header, text="Exporter tout", width=140,
            fg_color="#2fa572", hover_color="#1e8c5e",
            command=self._export_all_matches
        )
        self.export_all_btn.grid(row=0, column=1, padx=5)
        ctk.CTkButton(
            match_header,
            text="Ouvrir les exports",
            width=140,
            command=self._open_output_folder,
        ).grid(row=0, column=2, padx=5)
        
        self.match_list = ctk.CTkScrollableFrame(match_panel, height=150)
        self.match_list.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.match_list.grid_columnconfigure(0, weight=1)
    
    def refresh(self):
        """Refresh all lists"""
        self._refresh_xmls()
        self._refresh_profiles()
        self._refresh_matches()

    def _open_output_folder(self):
        """Ouvre le dossier JSON de la session active."""
        output_dir = self.session_manager.get_output_dir()
        if not output_dir:
            messagebox.showwarning("Exports", "Chargez d'abord une session.")
            return
        try:
            path = Path(output_dir)
            path.mkdir(parents=True, exist_ok=True)
            _open_local_folder(path)
        except Exception as error:
            messagebox.showerror("Exports", f"Ouverture impossible:\n{error}")
    
    def _refresh_xmls(self):
        for item in self.xml_items:
            item.destroy()
        self.xml_items.clear()
        self.selected_xml = None
        
        if not self.session_manager.current_session:
            return
        
        xmls = self.session_manager.list_xmls()
        for xml_info in xmls:
            match = self.session_manager.get_match_for_xml(xml_info['filename'])
            item = XmlListItem(self.xml_list, xml_info, on_select=self._on_xml_select)
            item.set_matched(match is not None)
            item.grid(sticky="ew", pady=2)
            self.xml_items.append(item)
    
    def _refresh_profiles(self):
        for item in self.profile_items:
            item.destroy()
        self.profile_items.clear()
        self.selected_profile = None
        
        if not self.session_manager.current_session:
            return
        
        profiles = self.session_manager.list_profiles()
        for profile_info in profiles:
            match = self.session_manager.get_match_for_profile(profile_info['filename'])
            item = ProfileListItem(self.profile_list, profile_info, on_select=self._on_profile_select)
            item.set_matched(match is not None)
            item.grid(sticky="ew", pady=2)
            self.profile_items.append(item)
    
    def _refresh_matches(self):
        for item in self.match_items:
            item.destroy()
        self.match_items.clear()
        
        if not self.session_manager.current_session:
            return
        
        for match in self.session_manager.matches:
            item = MatchListItem(self.match_list, match.to_dict(),
                               on_export=self._export_match, on_remove=self._remove_match,
                               on_analyze=self._analyze_match)
            item.grid(sticky="ew", pady=2)
            self.match_items.append(item)
    
    def _on_xml_select(self, item: XmlListItem):
        if self.selected_xml:
            self.selected_xml.set_selected(False)
        self.selected_xml = item
        item.set_selected(True)
        self._update_match_button()
    
    def _on_profile_select(self, item: ProfileListItem):
        if self.selected_profile:
            self.selected_profile.set_selected(False)
        self.selected_profile = item
        item.set_selected(True)
        self._update_match_button()
    
    def _update_match_button(self):
        if self.selected_xml and self.selected_profile:
            self.match_btn.configure(state="normal")
        else:
            self.match_btn.configure(state="disabled")
    
    def _import_xmls(self):
        if not self.session_manager.current_session:
            messagebox.showwarning("Attention", "Veuillez d'abord ouvrir une session")
            return
        
        # Ask user to choose import method
        choice = messagebox.askyesnocancel(
            "Import XML",
            "Voulez-vous importer un dossier entier ?\n\nOui = Dossier\nNon = Fichiers individuels"
        )
        
        if choice is None:  # Cancel
            return
        
        files_to_import = []
        
        if choice:  # Yes = folder
            folder = filedialog.askdirectory(title="Sélectionner un dossier contenant des XMLs")
            if folder:
                from pathlib import Path
                folder_path = Path(folder)
                files_to_import = list(folder_path.glob("*.xml"))
        else:  # No = individual files
            files = filedialog.askopenfilenames(
                title="Sélectionner des fichiers XML",
                filetypes=[("XML files", "*.xml"), ("All files", "*.*")]
            )
            files_to_import = list(files) if files else []
        
        if not files_to_import:
            return
        
        imported = 0
        for filepath in files_to_import:
            try:
                self.session_manager.import_xml(str(filepath))
                imported += 1
            except Exception as e:
                print(f"Error importing {filepath}: {e}")
        
        self._refresh_xmls()
        messagebox.showinfo("Succès", f"{imported} fichier(s) importé(s)")
    
    def _create_match(self):
        if not self.selected_xml or not self.selected_profile:
            return
        
        xml_filename = self.selected_xml.xml_info.get('filename', '')
        profile_filename = self.selected_profile.profile_info.get('filename', '')
        
        self.session_manager.create_match(profile_filename, xml_filename)
        self.refresh()
    
    def _remove_match(self, match_info: Dict):
        profile_name = match_info.get('profile_name', '')
        self.session_manager.remove_match(profile_name)
        self.refresh()

    def _analyze_match(self, match_info: Dict):
        _open_metasoft_match(self.session_manager, match_info)

    def _export_match(self, match_info: Dict):
        profile_name = match_info.get('profile_name', '')
        xml_filename = match_info.get('xml_filename', '')
        
        try:
            # Get profile data
            profile_data = self.session_manager.get_profile(profile_name)
            if not profile_data:
                messagebox.showerror("Erreur", "Profil non trouvé")
                return
            
            if not profile_data.get('email'):
                messagebox.showwarning("Attention", "L'email est requis dans le profil")
                return
            
            # Parse XML
            xml_path = self.session_manager.get_xml_path(xml_filename)
            xml_data = self.parser.parse_file(xml_path)
            match = self.session_manager.get_match_for_profile(profile_name)
            if not match or match.xml_filename != xml_filename:
                raise ValueError("Association profil/XML introuvable pour l'export MetaSoft")
            markers = _validated_metasoft_export_markers(
                self.session_manager,
                match,
                xml_data,
                profile_data,
            )

            # La transformation ne commence qu'apres tous les garde-fous bloquants.
            match_id = _match_id(profile_name, xml_filename)
            manual_ec = _validated_manual_running_economy(
                self.session_manager,
                match,
                match_id,
            )
            output = self.transformer.transform(xml_data, profile_data, manual_ec)
            
            # Generate output filename
            identity = profile_data.get('identity', {})
            name = f"{identity.get('last_name', 'Unknown')}_{identity.get('first_name', '')}".strip('_')
            date = self.session_manager.current_session.date
            output_filename = f"{name}_{date}.json"
            
            # Save to session output folder
            output_path = self.session_manager.save_output(output_filename, output)
            audit_path = _save_metasoft_audit_sidecar(
                self.session_manager,
                xml_data,
                profile_data,
                output_filename,
                profile_name,
                markers,
                manual_running_economy=manual_ec,
            )
            
            # Mark as exported
            self.session_manager.mark_as_exported(profile_name)
            self._refresh_matches()
            
            message = f"JSON Valentin:\n{output_path}"
            if audit_path:
                message += f"\n\nAudit local MetaSoft:\n{audit_path}"
            messagebox.showinfo("Succès", message)
            
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors de l'export: {e}")

    def _export_all_matches(self):
        """Export all matched profiles+XML at once."""
        if not self.session_manager.current_session:
            messagebox.showwarning("Attention", "Aucune session active")
            return
        
        matches = self.session_manager.matches
        if not matches:
            messagebox.showinfo("Info", "Aucune association à exporter")
            return
        
        success = 0
        errors = []
        
        for match in matches:
            profile_name = match.profile_name
            xml_filename = match.xml_filename
            
            try:
                profile_data = self.session_manager.get_profile(profile_name)
                if not profile_data:
                    errors.append(f"{profile_name}: profil non trouvé")
                    continue
                
                if not profile_data.get('email'):
                    errors.append(f"{profile_name}: email manquant")
                    continue
                
                xml_path = self.session_manager.get_xml_path(xml_filename)
                if not xml_path:
                    errors.append(f"{xml_filename}: XML non trouvé")
                    continue
                
                xml_data = self.parser.parse_file(xml_path)
                markers = _validated_metasoft_export_markers(
                    self.session_manager,
                    match,
                    xml_data,
                    profile_data,
                )
                match_id = _match_id(profile_name, xml_filename)
                manual_ec = _validated_manual_running_economy(
                    self.session_manager,
                    match,
                    match_id,
                )
                output = self.transformer.transform(xml_data, profile_data, manual_ec)
                
                identity = profile_data.get('identity', {})
                name = f"{identity.get('last_name', 'Unknown')}_{identity.get('first_name', '')}".strip('_')
                date = self.session_manager.current_session.date
                output_filename = f"{name}_{date}.json"
                
                self.session_manager.save_output(output_filename, output)
                _save_metasoft_audit_sidecar(
                    self.session_manager,
                    xml_data,
                    profile_data,
                    output_filename,
                    profile_name,
                    markers,
                    manual_running_economy=manual_ec,
                )
                self.session_manager.mark_as_exported(profile_name)
                success += 1
                
            except Exception as e:
                errors.append(f"{profile_name}: {e}")
        
        self._refresh_matches()
        
        # Show summary
        msg = (
            f"{success}/{len(matches)} JSON Valentin exporté(s) avec succès."
            "\nAudit local MetaSoft créé quand l'analyse MetaSoft est disponible."
        )
        if errors:
            msg += "\n\nErreurs:\n" + "\n".join(f"• {e}" for e in errors)
            messagebox.showwarning("Export terminé", msg)
        else:
            output_dir = self.session_manager.get_output_dir()
            msg += f"\n\nDossier: {output_dir}"
            messagebox.showinfo("Export terminé", msg)


class TCPDataProcessorSession(ctk.CTk):
    """Main application with tabbed interface"""
    
    def __init__(
        self,
        data_root: Optional[Path] = None,
        resources: Optional[Path] = None,
    ):
        super().__init__()
        
        self.title(f"{APP_NAME} v{APP_VERSION} - Session Mode")
        self.geometry("1200x800")
        self.minsize(1000, 700)
        
        self.data_root = user_data_root() if data_root is None else Path(data_root)
        self.resources = resolve_resource_root() if resources is None else Path(resources)
        ensure_user_data_dirs(self.data_root)

        self.session_manager = SessionManager(str(self.data_root))
        self.mongo_service = MongoService(str(self.data_root))
        self.protocol_store = ProtocolStore(str(self.data_root))
        
        self._set_icon()
        self._create_ui()
        
        # Auto-connect if URI was saved previously
        if self.mongo_service.uri:
            self.after(500, self._auto_connect_mongo)
        self.after(1000, self._poll_local_profile_updates)
    
    def _set_icon(self):
        try:
            icon_path = self.resources / "icon.ico"
            if icon_path.exists():
                self.iconbitmap(str(icon_path))
        except Exception:
            pass
    
    def _create_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ================================================================
        #  SIDEBAR  (fixed width, left)
        # ================================================================
        self.sidebar = ctk.CTkFrame(
            self, width=SIDEBAR_WIDTH, corner_radius=0,
            fg_color=SIDEBAR_COLORS["bg"]
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_columnconfigure(0, weight=1)

        # App name -------------------------------------------------------
        ctk.CTkLabel(
            self.sidebar, text="ENDURAW",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).grid(row=0, column=0, padx=20, pady=(24, 4), sticky="w")

        ctk.CTkLabel(
            self.sidebar, text="Testing Tool",
            font=ctk.CTkFont(size=12), text_color="gray",
        ).grid(row=1, column=0, padx=20, pady=(0, 16), sticky="w")

        # Separator -------------------------------------------------------
        sep1 = ctk.CTkFrame(self.sidebar, height=1,
                            fg_color=SIDEBAR_COLORS["separator"])
        sep1.grid(row=2, column=0, sticky="ew", padx=16, pady=4)

        # Navigation items ------------------------------------------------
        nav_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        nav_frame.grid(row=3, column=0, sticky="ew", padx=8, pady=8)
        nav_frame.grid_columnconfigure(0, weight=1)

        self._nav_buttons: Dict[str, ctk.CTkButton] = {}
        self._pages: Dict[str, ctk.CTkFrame] = {}
        self._current_page: Optional[str] = None

        nav_items = ["Sessions", "Profils", "XML Matching"]
        for idx, name in enumerate(nav_items):
            btn = ctk.CTkButton(
                nav_frame, text=name, anchor="w",
                height=36, corner_radius=8,
                fg_color="transparent",
                text_color=SIDEBAR_COLORS["btn_text"],
                hover_color=SIDEBAR_COLORS["btn_hover"],
                font=ctk.CTkFont(size=13),
                command=lambda n=name: self._show_page(n),
            )
            btn.grid(row=idx, column=0, sticky="ew", pady=2)
            self._nav_buttons[name] = btn

        # Separator -------------------------------------------------------
        sep2 = ctk.CTkFrame(self.sidebar, height=1,
                            fg_color=SIDEBAR_COLORS["separator"])
        sep2.grid(row=4, column=0, sticky="ew", padx=16, pady=4)

        # Protocoles button ------------------------------------------------
        self.settings_btn = ctk.CTkButton(
            self.sidebar, text="Protocoles", anchor="w",
            height=36, corner_radius=8,
            fg_color="transparent",
            text_color=SIDEBAR_COLORS["btn_text"],
            hover_color=SIDEBAR_COLORS["btn_hover"],
            font=ctk.CTkFont(size=13),
            command=self._open_protocol_manager,
        )
        self.settings_btn.grid(row=5, column=0, sticky="ew", padx=8, pady=2)

        # Push remaining items to bottom -----------------------------------
        self.sidebar.grid_rowconfigure(6, weight=1)

        # Theme toggle (bottom of sidebar) ---------------------------------
        bottom_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        bottom_frame.grid(row=7, column=0, sticky="ew", padx=8, pady=(0, 16))
        bottom_frame.grid_columnconfigure(0, weight=1)

        self.theme_btn = ctk.CTkButton(
            bottom_frame, text="Light Mode", anchor="w",
            height=32, corner_radius=8,
            fg_color="transparent",
            text_color="gray",
            hover_color=SIDEBAR_COLORS["btn_hover"],
            font=ctk.CTkFont(size=12),
            command=self._toggle_theme,
        )
        self.theme_btn.grid(row=0, column=0, sticky="ew", pady=2)

        # ================================================================
        #  MAIN CONTENT  (right side)
        # ================================================================
        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.grid(row=0, column=1, sticky="nsew")
        main_container.grid_columnconfigure(0, weight=1)
        main_container.grid_rowconfigure(1, weight=1)

        # Row 0: MongoDB connection bar ------------------------------------
        self._create_mongo_bar(main_container)

        # Row 1: Content area (pages stacked, one visible at a time) -------
        self.content = ctk.CTkFrame(main_container, fg_color="transparent")
        self.content.grid(row=1, column=0, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        # Session page
        self.session_tab = SessionTab(
            self.content, self.session_manager,
            on_session_loaded=self._on_session_loaded,
        )
        self._pages["Sessions"] = self.session_tab

        # Profile page
        self.profile_tab = ProfileTab(
            self.content, self.session_manager,
            mongo_service=self.mongo_service,
            protocol_store=self.protocol_store,
        )
        self._pages["Profils"] = self.profile_tab

        # XML Match page
        self.match_tab = XmlMatchTab(
            self.content, self.session_manager,
            mongo_service=self.mongo_service,
        )
        self._pages["XML Matching"] = self.match_tab

        # Session info label (top-right, inside mongo bar or header)
        # (already part of mongo bar)

        # Show first page
        self._show_page("Sessions")

    # ------------------------------------------------------------------ #
    #  Sidebar navigation helpers                                         #
    # ------------------------------------------------------------------ #
    def _show_page(self, name: str):
        """Show the requested page and highlight its nav button."""
        if self._current_page == name:
            return
        # Hide all pages
        for page in self._pages.values():
            page.pack_forget()
        # Show selected
        self._pages[name].pack(in_=self.content, fill="both", expand=True)
        # Update button styles
        for btn_name, btn in self._nav_buttons.items():
            if btn_name == name:
                btn.configure(fg_color=SIDEBAR_COLORS["btn_active"])
            else:
                btn.configure(fg_color="transparent")
        self._current_page = name

    def _poll_local_profile_updates(self):
        """Synchronise l'ecran Profils apres report depuis l'UI React locale."""
        try:
            from local_api.metasoft_server import LocalMetaSoftServer

            for profile_name in LocalMetaSoftServer.consume_profile_updates(self.session_manager):
                self.profile_tab.reload_profile_from_disk(profile_name)
        finally:
            self.after(1000, self._poll_local_profile_updates)
    
    # ------------------------------------------------------------------ #
    #  MongoDB connection bar                                             #
    # ------------------------------------------------------------------ #
    def _create_mongo_bar(self, parent):
        """Create a compact connection bar for MongoDB URI."""
        bar = ctk.CTkFrame(parent, height=44, corner_radius=0,
                           fg_color=("gray90", "gray17"))
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_columnconfigure(2, weight=1)

        # Session info (left side)
        self.session_info = ctk.CTkLabel(
            bar, text="Aucune session active", text_color="gray",
            font=ctk.CTkFont(size=12),
        )
        self.session_info.grid(row=0, column=0, padx=(15, 20), pady=8)

        # DB label
        db_label = ctk.CTkLabel(bar, text="MongoDB", font=ctk.CTkFont(size=12))
        db_label.grid(row=0, column=1, padx=(10, 5), pady=8)

        # URI entry
        self.mongo_uri_entry = ctk.CTkEntry(
            bar,
            placeholder_text="mongodb+srv://user:pass@cluster.mongodb.net/enduraw",
            show="\u2022", width=400,
        )
        self.mongo_uri_entry.grid(row=0, column=2, padx=5, pady=8, sticky="ew")

        # Pre-fill with saved URI
        if self.mongo_service.uri:
            self.mongo_uri_entry.insert(0, self.mongo_service.uri)

        # Toggle visibility
        self._uri_visible = False
        self.toggle_uri_btn = ctk.CTkButton(
            bar, text="Afficher", width=60, height=28,
            fg_color="transparent", hover_color=("gray80", "gray30"),
            font=ctk.CTkFont(size=11),
            command=self._toggle_uri_visibility,
        )
        self.toggle_uri_btn.grid(row=0, column=3, padx=2, pady=8)

        # Connect button
        self.mongo_connect_btn = ctk.CTkButton(
            bar, text="Connecter", width=90, height=28,
            command=self._connect_mongo,
        )
        self.mongo_connect_btn.grid(row=0, column=4, padx=5, pady=8)

        # Status indicator
        self.mongo_status_label = ctk.CTkLabel(
            bar, text="Deconnecte", text_color="gray",
            font=ctk.CTkFont(size=11),
        )
        self.mongo_status_label.grid(row=0, column=5, padx=(5, 15), pady=8)
    
    def _toggle_uri_visibility(self):
        if self._uri_visible:
            self.mongo_uri_entry.configure(show="\u2022")
            self.toggle_uri_btn.configure(text="Afficher")
            self._uri_visible = False
        else:
            self.mongo_uri_entry.configure(show="")
            self.toggle_uri_btn.configure(text="Masquer")
            self._uri_visible = True
    
    def _connect_mongo(self):
        """Connect or disconnect from MongoDB."""
        if self.mongo_service.is_connected:
            self.mongo_service.disconnect()
            self.mongo_connect_btn.configure(text="Connecter")
            self.mongo_status_label.configure(text="Deconnecte", text_color="gray")
            return
        
        uri = self.mongo_uri_entry.get().strip()
        if not uri:
            messagebox.showwarning("Attention", "Veuillez saisir l'URI MongoDB")
            return
        
        self.mongo_status_label.configure(text="Connexion...", text_color="orange")
        self.update_idletasks()
        
        try:
            self.mongo_service.connect(uri=uri)
            nb_users = len(self.mongo_service.get_all_users())
            self.mongo_connect_btn.configure(text="Deconnecter", fg_color="#c0392b", hover_color="#a93226")
            self.mongo_status_label.configure(
                text=f"Connecte ({nb_users} users)", text_color="#2fa572"
            )
        except Exception as e:
            self.mongo_status_label.configure(text="Erreur", text_color="#c0392b")
            messagebox.showerror("Erreur MongoDB", f"Connexion echouee:\n{e}")
    
    def _auto_connect_mongo(self):
        """Try to auto-connect using saved URI."""
        try:
            self.mongo_service.connect()
            nb_users = len(self.mongo_service.get_all_users())
            self.mongo_connect_btn.configure(text="Deconnecter", fg_color="#c0392b", hover_color="#a93226")
            self.mongo_status_label.configure(
                text=f"Connecte ({nb_users} users)", text_color="#2fa572"
            )
        except Exception:
            self.mongo_status_label.configure(text="Auto-connect echoue", text_color="#f0ad4e")
    
    def _on_session_loaded(self):
        """Called when a session is loaded or created"""
        if self.session_manager.current_session:
            s = self.session_manager.current_session
            self.session_info.configure(text=f"Session: {s.name}")
            
            # Switch to Profils page automatically
            self._show_page("Profils")
        else:
            self.session_info.configure(text="Aucune session active")
        
        # Refresh other tabs
        self.profile_tab.refresh()
        self.match_tab.refresh()
    
    def _toggle_theme(self):
        """Toggle between dark and light mode"""
        current = ctk.get_appearance_mode()
        if current == "Dark":
            ctk.set_appearance_mode("light")
            self.theme_btn.configure(text="Dark Mode")
        else:
            ctk.set_appearance_mode("dark")
            self.theme_btn.configure(text="Light Mode")
    
    # ------------------------------------------------------------------ #
    #  Protocol management dialog                                         #
    # ------------------------------------------------------------------ #
    def _open_protocol_manager(self):
        """Open the protocol management dialog."""
        dialog = ProtocolManagerDialog(self, self.protocol_store)
        self.wait_window(dialog)
        # After dialog closes, refresh the dropdown in the form
        self.profile_tab.form.refresh_protocol_list()


class ProtocolManagerDialog(ctk.CTkToplevel):
    """Dialog to manage saved test protocols (add / edit / delete)."""

    def __init__(self, parent, protocol_store: ProtocolStore):
        super().__init__(parent)
        self.protocol_store = protocol_store
        self.title("Gestion des Protocoles")
        self.geometry("650x500")
        self.minsize(500, 400)
        self.transient(parent)
        self.grab_set()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._create_ui()
        self._refresh_list()

    def _create_ui(self):
        # ---- Header ----
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 5))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header, text="Protocoles de Test",
                     font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, sticky="w")

        btn_frame = ctk.CTkFrame(header, fg_color="transparent")
        btn_frame.grid(row=0, column=1, sticky="e")
        ctk.CTkButton(btn_frame, text="+ Ajouter", width=90, command=self._add_protocol).grid(row=0, column=0, padx=5)

        # ---- Main area (split: list left, detail right) ----
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=1, column=0, sticky="nsew", padx=15, pady=5)
        main.grid_columnconfigure(0, weight=1)
        main.grid_columnconfigure(1, weight=2)
        main.grid_rowconfigure(0, weight=1)

        # ---- Left: protocol list ----
        left = ctk.CTkFrame(main)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        left.grid_rowconfigure(0, weight=1)
        left.grid_columnconfigure(0, weight=1)

        self.proto_listbox = ctk.CTkScrollableFrame(left)
        self.proto_listbox.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.proto_listbox.grid_columnconfigure(0, weight=1)

        # ---- Right: detail / editor ----
        right = ctk.CTkFrame(main)
        right.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(right, text="Nom du protocole", anchor="w").grid(
            row=0, column=0, padx=10, pady=(10, 2), sticky="w")
        self.name_entry = ctk.CTkEntry(right, placeholder_text="ex: Paliers 1 km/h Course")
        self.name_entry.grid(row=1, column=0, padx=10, pady=2, sticky="ew")

        ctk.CTkLabel(right, text="Description", anchor="w").grid(
            row=2, column=0, padx=10, pady=(10, 2), sticky="nw")
        self.desc_text = ctk.CTkTextbox(right, height=200)
        self.desc_text.grid(row=3, column=0, padx=10, pady=2, sticky="nsew")
        right.grid_rowconfigure(3, weight=1)

        action_bar = ctk.CTkFrame(right, fg_color="transparent")
        action_bar.grid(row=4, column=0, padx=10, pady=10, sticky="ew")
        action_bar.grid_columnconfigure(0, weight=1)

        self.save_btn = ctk.CTkButton(action_bar, text="Sauvegarder", command=self._save_current, state="disabled")
        self.save_btn.grid(row=0, column=0, padx=5, sticky="e")

        self.delete_btn = ctk.CTkButton(action_bar, text="Supprimer", fg_color="#c0392b",
                                        hover_color="#a93226", command=self._delete_current, state="disabled")
        self.delete_btn.grid(row=0, column=1, padx=5)

        self._selected_name: Optional[str] = None

    # ------------------------------------------------------------------ #
    #  List management                                                    #
    # ------------------------------------------------------------------ #
    def _refresh_list(self):
        """Rebuild the protocol list buttons."""
        for w in self.proto_listbox.winfo_children():
            w.destroy()

        for name in self.protocol_store.list_names():
            btn = ctk.CTkButton(
                self.proto_listbox, text=name, anchor="w",
                fg_color="transparent", hover_color=("gray80", "gray30"),
                text_color=("gray10", "gray90"),
                command=lambda n=name: self._select_protocol(n)
            )
            btn.grid(sticky="ew", pady=1)

    def _select_protocol(self, name: str):
        """Load a protocol into the editor."""
        self._selected_name = name
        self.name_entry.delete(0, "end")
        self.name_entry.insert(0, name)
        self.desc_text.delete("1.0", "end")
        self.desc_text.insert("1.0", self.protocol_store.get_description(name))
        self.save_btn.configure(state="normal")
        self.delete_btn.configure(state="normal")

    def _add_protocol(self):
        """Clear editor for a new protocol."""
        self._selected_name = None
        self.name_entry.delete(0, "end")
        self.desc_text.delete("1.0", "end")
        self.name_entry.focus()
        self.save_btn.configure(state="normal")
        self.delete_btn.configure(state="disabled")

    def _save_current(self):
        """Save (create or update) the current protocol."""
        name = self.name_entry.get().strip()
        description = self.desc_text.get("1.0", "end-1c").strip()

        if not name:
            messagebox.showwarning("Attention", "Le nom du protocole est requis", parent=self)
            return

        if self._selected_name and self._selected_name != name:
            # Rename
            if not self.protocol_store.rename(self._selected_name, name):
                messagebox.showwarning("Attention", f"Le nom « {name} » existe déjà", parent=self)
                return
            self.protocol_store.update(name, description)
        elif self._selected_name:
            # Update existing
            self.protocol_store.update(name, description)
        else:
            # New protocol
            if not self.protocol_store.add(name, description):
                messagebox.showwarning("Attention", f"Le nom « {name} » existe déjà", parent=self)
                return

        self._selected_name = name
        self._refresh_list()
        messagebox.showinfo("Sauvegardé", f"Protocole « {name} » enregistré", parent=self)

    def _delete_current(self):
        if not self._selected_name:
            return
        if not messagebox.askyesno("Confirmer", f"Supprimer le protocole « {self._selected_name} » ?", parent=self):
            return
        self.protocol_store.delete(self._selected_name)
        self._selected_name = None
        self.name_entry.delete(0, "end")
        self.desc_text.delete("1.0", "end")
        self.save_btn.configure(state="disabled")
        self.delete_btn.configure(state="disabled")
        self._refresh_list()


def main():
    """Entry point"""
    app = TCPDataProcessorSession()
    app.mainloop()


if __name__ == "__main__":
    main()
