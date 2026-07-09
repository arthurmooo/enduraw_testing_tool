# Plan corrections EC manuelle MetaSoft

## Decisions approuvees

- Source officielle: Python, via `core.metasoft_analysis`.
- React conserve une preview live uniquement pour l'UX; les valeurs calculees par React ne sont jamais persistees.
- Payload sauvegarde: selections incluses (`stage_index`, `start_seconds`, `end_seconds`,
  `exclusions`) et metadata UI locale `stage_selections` pour memoriser les paliers ecartes.
- Sidecar local: persistance par match avec fingerprint session/profil/XML, sans chemin disque.
- Masse EC manuelle: poids XML MetaSoft `analysis["athlete"]["weight_kg"]` uniquement.
- VO2max EC manuelle: `profile.stress_test_results.measured_vo2max` uniquement.
- Report profil: `/profile/report` accepte les selections EC et persiste le sidecar seulement
  apres succes du patch profil, avec le fingerprint profil final.
- Export final: inclure `running_economy_manual.rows` seulement si le sidecar est canonical,
  compatible fingerprint et contient au moins une row incluse.
- VCO2: provenance unique si une source, `derived_mixed` si plusieurs sources derivees/natives coexistent.

## Implementation

1. Extraire la formule EC existante dans un helper Python partage par EC auto et EC manuelle.
2. Ajouter `build_manual_running_economy(analysis, selections, profile_vo2max_ml_kg_min=None)`.
3. Valider les bornes, le palier, les valeurs finies et normaliser/clamp les exclusions.
4. Exclure les artefacts du calcul officiel sans interpolation ni reconstruction.
5. Recalculer en Python les moyennes VO2/VCO2/DE sur la population unique VO2+VCO2 exploitable,
   EC `J/kg/m`, `%VO2max` et warnings.
6. Adapter l'endpoint local pour ignorer les champs calcules React, clearer sur `selections: []`
   sans metadata, et persister le payload Python canonical.
7. Fingerprinter le sidecar avec session, profil et XML; ignorer les sidecars stale ou legacy.
8. Adapter l'export Tk pour lire uniquement un sidecar compatible fingerprint.
9. Adapter React pour envoyer les selections EC dans `/profile/report` sans sauvegarde prealable.
10. Couvrir les cas critiques par tests unitaires/API/build UI.
