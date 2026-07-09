import { MARKER_COLORS } from "../lib/graphConfig";
import { formatNumber, MARKER_NAMES, secondsToClock } from "../lib/markerUtils";
import type { ConfirmedMarkers, DraftMarkers, MetaSoftMarkerName } from "../types/metasoft";

export function MarkerPanel({
  draftMarkers,
  confirmedMarkers,
  dirtyMarkers,
  profileVo2maxMlKgMin,
}: {
  draftMarkers: DraftMarkers;
  confirmedMarkers: ConfirmedMarkers;
  dirtyMarkers: Set<MetaSoftMarkerName>;
  profileVo2maxMlKgMin: number | null;
}) {
  const displayedVo2maxMlKgMin = currentVo2maxMlKgMin(
    draftMarkers,
    confirmedMarkers,
    dirtyMarkers,
    profileVo2maxMlKgMin,
  );

  return (
    <section className="panel marker-panel">
      <div className="panel-title-row">
        <h2>Marqueurs</h2>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Nom</th>
              <th>Mode</th>
              <th>Temps</th>
              <th>Fenetre</th>
              <th>FC</th>
              <th>VO2 (L/min)</th>
              <th>VO2/kg</th>
              <th>%VO2max</th>
              <th>Vitesse</th>
              <th>Statut</th>
            </tr>
          </thead>
          <tbody>
            {MARKER_NAMES.map((name) => {
              const draft = draftMarkers[name];
              const confirmed = confirmedMarkers[name];
              const dirty = dirtyMarkers.has(name);
              const official = confirmed && !dirty ? confirmed : null;
              const row = official ?? draft;
              return (
                <tr key={name}>
                  <td>
                    <span className="marker-name" style={{ color: MARKER_COLORS[name] }}>
                      {name === "VO2_max" ? "VO2max" : name}
                    </span>
                  </td>
                  <td>{draft.mode === "point" ? "Ligne" : "Range"}</td>
                  <td>{secondsToClock(row.t_seconds)}</td>
                  <td>
                    {row.window_start_seconds === null || row.window_end_seconds === null
                      ? "-"
                      : `${secondsToClock(row.window_start_seconds)} - ${secondsToClock(row.window_end_seconds)}`}
                  </td>
                  <td>{formatNumber(row.values.fc_bpm, 0)}</td>
                  <td>{formatNumber(row.values.vo2_l_min, 2)}</td>
                  <td>{formatNumber(row.values.vo2_ml_kg_min, 1)}</td>
                  <td>{formatNumber(percentVo2Max(row.values.vo2_ml_kg_min, displayedVo2maxMlKgMin), 1)}</td>
                  <td>{formatNumber(row.values.speed_kmh, 1)}</td>
                  <td>
                    {dirty ? (
                      <span className="status-warn">needsSave</span>
                    ) : official ? (
                      <span className="status-ok">Python</span>
                    ) : (
                      <span className="status-muted">preview</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="panel-note">
        Reporter au profil officialise les marqueurs via Python. Un drag/click repasse le marqueur en needsSave.
      </p>
    </section>
  );
}

function currentVo2maxMlKgMin(
  draftMarkers: DraftMarkers,
  confirmedMarkers: ConfirmedMarkers,
  dirtyMarkers: Set<MetaSoftMarkerName>,
  profileVo2maxMlKgMin: number | null,
): number | null {
  const marker = dirtyMarkers.has("VO2_max")
    ? draftMarkers.VO2_max
    : confirmedMarkers.VO2_max ?? draftMarkers.VO2_max;
  return marker.values.vo2_ml_kg_min ?? profileVo2maxMlKgMin;
}

function percentVo2Max(vo2: number | null | undefined, vo2Max: number | null | undefined): number | null {
  if (
    typeof vo2 !== "number"
    || typeof vo2Max !== "number"
    || !Number.isFinite(vo2)
    || !Number.isFinite(vo2Max)
    || vo2Max <= 0
  ) {
    return null;
  }
  return (vo2 / vo2Max) * 100;
}
