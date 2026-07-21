import { useCallback, useEffect, useRef, type ReactNode } from "react";
import { Minus, Plus, RotateCcw, X } from "lucide-react";

export type ChartScaleMode = "common" | "series";

export interface ChartSeriesOption {
  key: string;
  label: string;
  color: string;
}

export interface ChartPopoverPosition {
  left: number;
  top: number;
  opensBelow: boolean;
}

export function useChartClickArbitration(delayMs = 320) {
  const timerRef = useRef<number | null>(null);
  const blockedUntilRef = useRef(0);
  const cancel = useCallback(() => {
    if (timerRef.current === null) return;
    window.clearTimeout(timerRef.current);
    timerRef.current = null;
  }, []);
  const block = useCallback((durationMs = 450) => {
    cancel();
    blockedUntilRef.current = window.performance.now() + durationMs;
  }, [cancel]);
  const schedule = useCallback((callback: () => void) => {
    cancel();
    timerRef.current = window.setTimeout(() => {
      timerRef.current = null;
      callback();
    }, delayMs);
  }, [cancel, delayMs]);
  const isBlocked = useCallback(
    () => window.performance.now() < blockedUntilRef.current,
    [],
  );
  useEffect(() => cancel, [cancel]);
  return { block, cancel, isBlocked, schedule };
}

export function ChartActionPopover({
  position,
  eyebrow,
  title,
  ariaLabel,
  onClose,
  children,
}: {
  position: ChartPopoverPosition;
  eyebrow: string;
  title: string;
  ariaLabel: string;
  onClose: () => void;
  children: ReactNode;
}) {
  return (
    <div
      className={`marker-popover marker-action-menu${position.opensBelow ? " marker-popover-below" : ""}`}
      style={{ left: position.left, top: position.top }}
      role="dialog"
      aria-label={ariaLabel}
      onClick={(event) => event.stopPropagation()}
      onContextMenu={(event) => event.preventDefault()}
      onMouseDown={(event) => event.stopPropagation()}
      onMouseUp={(event) => event.stopPropagation()}
    >
      <div className="popover-head">
        <div>
          <p>{eyebrow}</p>
          <strong>{title}</strong>
        </div>
        <button type="button" onClick={onClose} aria-label="Fermer">
          <X size={16} />
        </button>
      </div>
      {children}
    </div>
  );
}

export function ChartScaleControls({
  series,
  mode,
  selectedSeriesKey,
  onModeChange,
  onSelectedSeriesChange,
  onZoomIn,
  onZoomOut,
  onAuto,
  onResetZoom,
  showResetZoom,
  showScaleButtons = true,
}: {
  series: ChartSeriesOption[];
  mode: ChartScaleMode;
  selectedSeriesKey: string;
  onModeChange: (mode: ChartScaleMode) => void;
  onSelectedSeriesChange: (key: string) => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onAuto: () => void;
  onResetZoom: () => void;
  showResetZoom: boolean;
  showScaleButtons?: boolean;
}) {
  return (
    <div
      className="scale-controls"
      aria-label={showScaleButtons ? "Regler l'echelle verticale" : "Reinitialiser le zoom horizontal"}
    >
      {showScaleButtons && series.length > 1 && (
        <button
          type="button"
          onClick={() => onModeChange(mode === "common" ? "series" : "common")}
          title="Basculer entre une echelle commune et une echelle par courbe"
        >
          {mode === "series" ? "Par courbe" : "Commune"}
        </button>
      )}
      {showScaleButtons && mode === "series" && series.length > 1 && (
        <select
          aria-label="Courbe dont l'echelle est affichee et ajustee"
          value={selectedSeriesKey}
          onChange={(event) => onSelectedSeriesChange(event.target.value)}
        >
          {series.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}
        </select>
      )}
      {showScaleButtons && (
        <>
          <button type="button" onClick={onZoomOut} title="Elargir l'echelle verticale" aria-label="Elargir l'echelle verticale">
            <Minus size={14} />
          </button>
          <button type="button" onClick={onAuto} title="Echelle automatique sur la zone visible">Auto</button>
          <button type="button" onClick={onZoomIn} title="Resserrer l'echelle verticale" aria-label="Resserrer l'echelle verticale">
            <Plus size={14} />
          </button>
        </>
      )}
      {showResetZoom && (
        <button type="button" className="zoom-reset-button" onClick={onResetZoom} title="Reinitialiser le zoom horizontal">
          <RotateCcw size={13} /> Reinitialiser
        </button>
      )}
    </div>
  );
}

export function ChartSeriesToggles<TSeries extends ChartSeriesOption>({
  series,
  hiddenSeries,
  onToggle,
}: {
  series: TSeries[];
  hiddenSeries: Set<string>;
  onToggle: (series: TSeries) => void;
}) {
  return (
    <div className="series-toggles">
      {series.map((item) => (
        <button
          key={item.key}
          type="button"
          onClick={() => onToggle(item)}
          className={hiddenSeries.has(item.key) ? "series-toggle muted" : "series-toggle"}
          aria-pressed={!hiddenSeries.has(item.key)}
        >
          <span style={{ backgroundColor: item.color }} />
          {item.label}
        </button>
      ))}
    </div>
  );
}

export function ChartPlacementPopover<TMode extends string>({
  position,
  title,
  valueLabel,
  modes,
  activeMode,
  onModeChange,
  help,
  onClose,
  children,
}: {
  position: ChartPopoverPosition;
  title: string;
  valueLabel: string;
  modes: Array<{ value: TMode; label: string }>;
  activeMode: TMode;
  onModeChange: (mode: TMode) => void;
  help?: string;
  onClose: () => void;
  children: ReactNode;
}) {
  return (
    <div
      className={position.opensBelow ? "marker-popover marker-popover-below" : "marker-popover"}
      style={{ left: position.left, top: position.top }}
      role="dialog"
      onClick={(event) => event.stopPropagation()}
      onContextMenu={(event) => event.stopPropagation()}
      onMouseDown={(event) => event.stopPropagation()}
      onMouseMove={(event) => event.stopPropagation()}
      onMouseUp={(event) => event.stopPropagation()}
    >
      <div className="popover-head">
        <div>
          <p>{title}</p>
          <span>{valueLabel}</span>
        </div>
        <button type="button" onClick={onClose} aria-label="Fermer">
          <X size={16} />
        </button>
      </div>
      <div className={`segmented segmented-${modes.length}`}>
        {modes.map((mode) => (
          <button
            key={mode.value}
            type="button"
            onClick={() => onModeChange(mode.value)}
            className={activeMode === mode.value ? "active" : ""}
            aria-pressed={activeMode === mode.value}
          >
            {mode.label}
          </button>
        ))}
      </div>
      {help && <p className="popover-help">{help}</p>}
      {children}
    </div>
  );
}

export function chartPopoverPosition(
  clientX: number,
  clientY: number,
  height = 252,
  width = 336,
): ChartPopoverPosition {
  const renderedWidth = Math.min(width, Math.max(1, window.innerWidth - 24));
  const opensBelow = clientY < height + 16;
  return {
    left: Math.min(
      Math.max(clientX, renderedWidth / 2 + 12),
      window.innerWidth - renderedWidth / 2 - 12,
    ),
    top: opensBelow ? clientY + 10 : clientY - 10,
    opensBelow,
  };
}
