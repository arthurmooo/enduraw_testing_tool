"""
Tab-based UI components for TCP Data Processor
"""
import os
import customtkinter as ctk
from tkinter import filedialog, messagebox
from typing import Dict, List, Any, Optional
from pathlib import Path


class SessionListItem(ctk.CTkFrame):
    """Individual session item in the list"""
    
    def __init__(self, master, session_info: Dict, on_select=None, **kwargs):
        super().__init__(master, **kwargs)
        self.session_info = session_info
        self.on_select = on_select
        self.is_selected = False
        
        self.configure(fg_color="transparent", corner_radius=5)
        self.grid_columnconfigure(0, weight=1)
        
        # Name label
        name = session_info.get('name', 'Unknown')
        self.name_label = ctk.CTkLabel(
            self, text=name, font=ctk.CTkFont(weight="bold"), anchor="w"
        )
        self.name_label.grid(row=0, column=0, padx=10, pady=2, sticky="w")
        
        # Info label
        date = session_info.get('date', '')
        location = session_info.get('location', '')
        self.info_label = ctk.CTkLabel(
            self, text=f"{date} - {location}",
            font=ctk.CTkFont(size=11), text_color="gray", anchor="w"
        )
        self.info_label.grid(row=1, column=0, padx=10, pady=0, sticky="w")
        
        # Bind click
        self.bind("<Button-1>", self._on_click)
        self.name_label.bind("<Button-1>", self._on_click)
        self.info_label.bind("<Button-1>", self._on_click)
    
    def _on_click(self, event):
        if self.on_select:
            self.on_select(self)
    
    def set_selected(self, selected: bool):
        self.is_selected = selected
        self.configure(fg_color=("gray85", "gray25") if selected else "transparent")


class ProfileListItem(ctk.CTkFrame):
    """Individual profile item in the list"""
    
    def __init__(self, master, profile_info: Dict, on_select=None, **kwargs):
        super().__init__(master, **kwargs)
        self.profile_info = profile_info
        self.on_select = on_select
        self.is_selected = False
        self.is_matched = False
        
        self.configure(fg_color="transparent", corner_radius=5)
        self.grid_columnconfigure(0, weight=1)
        
        # Name
        name = f"{profile_info.get('last_name', '')} {profile_info.get('first_name', '')}"
        self.name_label = ctk.CTkLabel(
            self, text=name.strip() or "Sans nom",
            font=ctk.CTkFont(weight="bold"), anchor="w"
        )
        self.name_label.grid(row=0, column=0, padx=10, pady=2, sticky="w")
        
        # Email
        email = profile_info.get('email', '')
        self.email_label = ctk.CTkLabel(
            self, text=email or "Pas d'email",
            font=ctk.CTkFont(size=11), text_color="gray", anchor="w"
        )
        self.email_label.grid(row=1, column=0, padx=10, pady=0, sticky="w")
        
        # Status indicator
        self.status_label = ctk.CTkLabel(
            self, text="○", font=ctk.CTkFont(size=12), text_color="gray"
        )
        self.status_label.grid(row=0, column=1, rowspan=2, padx=10)
        
        # Bind click
        self.bind("<Button-1>", self._on_click)
        self.name_label.bind("<Button-1>", self._on_click)
        self.email_label.bind("<Button-1>", self._on_click)
    
    def _on_click(self, event):
        if self.on_select:
            self.on_select(self)
    
    def set_selected(self, selected: bool):
        self.is_selected = selected
        self.configure(fg_color=("gray85", "gray25") if selected else "transparent")
    
    def set_matched(self, matched: bool):
        self.is_matched = matched
        if matched:
            self.status_label.configure(text="●", text_color="green")
        else:
            self.status_label.configure(text="○", text_color="gray")


class XmlListItem(ctk.CTkFrame):
    """Individual XML item in the list"""
    
    def __init__(self, master, xml_info: Dict, on_select=None, **kwargs):
        super().__init__(master, **kwargs)
        self.xml_info = xml_info
        self.on_select = on_select
        self.is_selected = False
        self.is_matched = False
        
        self.configure(fg_color="transparent", corner_radius=5)
        self.grid_columnconfigure(0, weight=1)
        
        # Filename
        filename = xml_info.get('filename', 'Unknown')
        self.name_label = ctk.CTkLabel(
            self, text=filename[:40] + "..." if len(filename) > 40 else filename,
            font=ctk.CTkFont(weight="bold"), anchor="w"
        )
        self.name_label.grid(row=0, column=0, padx=10, pady=2, sticky="w")
        
        # Name from filename
        name = f"{xml_info.get('last_name', '')} {xml_info.get('first_name', '')}"
        self.info_label = ctk.CTkLabel(
            self, text=name.strip() or "Nom inconnu",
            font=ctk.CTkFont(size=11), text_color="gray", anchor="w"
        )
        self.info_label.grid(row=1, column=0, padx=10, pady=0, sticky="w")
        
        # Status
        self.status_label = ctk.CTkLabel(
            self, text="○", font=ctk.CTkFont(size=12), text_color="gray"
        )
        self.status_label.grid(row=0, column=1, rowspan=2, padx=10)
        
        # Bind
        self.bind("<Button-1>", self._on_click)
        self.name_label.bind("<Button-1>", self._on_click)
        self.info_label.bind("<Button-1>", self._on_click)
    
    def _on_click(self, event):
        if self.on_select:
            self.on_select(self)
    
    def set_selected(self, selected: bool):
        self.is_selected = selected
        self.configure(fg_color=("gray85", "gray25") if selected else "transparent")
    
    def set_matched(self, matched: bool):
        self.is_matched = matched
        if matched:
            self.status_label.configure(text="●", text_color="green")
        else:
            self.status_label.configure(text="○", text_color="gray")


class MatchListItem(ctk.CTkFrame):
    """Item showing a profile-XML match"""
    
    def __init__(
        self,
        master,
        match_info: Dict,
        on_export=None,
        on_remove=None,
        on_analyze=None,
        **kwargs,
    ):
        super().__init__(master, **kwargs)
        self.match_info = match_info
        
        self.configure(fg_color=("gray90", "gray20"), corner_radius=5)
        self.grid_columnconfigure(0, weight=1)
        
        # Profile name
        profile = match_info.get('profile_name', '')
        self.profile_label = ctk.CTkLabel(
            self, text=f"{profile}",
            font=ctk.CTkFont(weight="bold"), anchor="w"
        )
        self.profile_label.grid(row=0, column=0, padx=10, pady=2, sticky="w")
        
        # XML name
        xml = match_info.get('xml_filename', '')
        self.xml_label = ctk.CTkLabel(
            self, text=f"{xml[:30]}..." if len(xml) > 30 else xml,
            font=ctk.CTkFont(size=11), text_color="gray", anchor="w"
        )
        self.xml_label.grid(row=1, column=0, padx=10, pady=0, sticky="w")
        
        # Buttons frame
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=0, column=1, rowspan=2, padx=5, pady=5)

        # Analyze button
        self.analyze_btn = ctk.CTkButton(
            btn_frame, text="Analyser",
            width=85, height=28,
            command=lambda: on_analyze(match_info) if on_analyze else None
        )
        self.analyze_btn.grid(row=0, column=0, padx=2)
        
        # Export button
        exported = match_info.get('exported', False)
        self.export_btn = ctk.CTkButton(
            btn_frame, text="Exporte" if exported else "Exporter",
            width=80, height=28,
            fg_color="#2fa572" if exported else None,
            command=lambda: on_export(match_info) if on_export else None
        )
        self.export_btn.grid(row=0, column=1, padx=2)
        
        # Remove button
        self.remove_btn = ctk.CTkButton(
            btn_frame, text="X", width=30, height=28,
            fg_color="#c0392b", hover_color="#a93226",
            command=lambda: on_remove(match_info) if on_remove else None
        )
        self.remove_btn.grid(row=0, column=2, padx=2)
