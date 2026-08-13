export interface ReadingLine {
  id: string;
  seriesKey: string;
  seriesLabel: string;
  x0: number;
  x1: number;
  y0: number;
  y1: number;
  xUnit?: string;
  yUnit?: string;
  timeAxis: boolean;
  color?: string;
  sourceYRange?: [number, number];
}

export interface SharedReadingLine extends ReadingLine {
  sourceGraphId: string;
}

export interface ReadingLineMetrics {
  deltaX: number;
  deltaY: number;
  slope: number | null;
  slopeUnit: string;
}

export function plotCoordinatesFromClient(
  clientX: number,
  clientY: number,
  bounds: { left: number; right: number; top: number; bottom: number },
  margin: { l: number; r: number; t: number; b: number },
  xRange: [number, number],
  yRange: [number, number],
): { x: number; y: number } | null {
  const left = bounds.left + margin.l;
  const right = bounds.right - margin.r;
  const top = bounds.top + margin.t;
  const bottom = bounds.bottom - margin.b;
  if (right <= left || bottom <= top || clientX < left || clientX > right || clientY < top || clientY > bottom) {
    return null;
  }
  return {
    x: xRange[0] + ((clientX - left) / (right - left)) * (xRange[1] - xRange[0]),
    y: yRange[1] - ((clientY - top) / (bottom - top)) * (yRange[1] - yRange[0]),
  };
}

export function readingLineMetrics(line: ReadingLine): ReadingLineMetrics {
  const deltaX = line.x1 - line.x0;
  const deltaY = line.y1 - line.y0;
  const slope = deltaX === 0 ? null : deltaY / (line.timeAxis ? deltaX / 60 : deltaX);
  return {
    deltaX,
    deltaY,
    slope,
    slopeUnit: line.timeAxis
      ? `${line.yUnit || "unite"}/min`
      : `${line.yUnit || "unite"}/${line.xUnit || "unite X"}`,
  };
}

export function readingLineAnnotation(line: ReadingLine): string {
  const metrics = readingLineMetrics(line);
  const slope = metrics.slope === null ? "pente verticale" : `${signed(metrics.slope)} ${metrics.slopeUnit}`;
  return `${line.seriesLabel} · Δ ${signed(metrics.deltaY)} ${line.yUnit || ""} · ${slope}`.trim();
}

export function updateReadingLinesFromRelayout(
  lines: ReadingLine[],
  event: Readonly<Record<string, unknown>>,
  shapeStartIndex: number,
): ReadingLine[] {
  const next = lines.map((line) => ({ ...line }));
  let changed = false;
  const shapes = event.shapes;
  if (Array.isArray(shapes)) {
    shapes.slice(shapeStartIndex, shapeStartIndex + next.length).forEach((shape, index) => {
      if (!shape || typeof shape !== "object" || !next[index]) return;
      changed = applyShape(next[index], shape as Record<string, unknown>) || changed;
    });
  }
  for (const [key, value] of Object.entries(event)) {
    const match = /^shapes\[(\d+)]\.(x0|x1|y0|y1)$/.exec(key);
    if (!match) continue;
    const line = next[Number(match[1]) - shapeStartIndex];
    if (!line || typeof value !== "number" || !Number.isFinite(value)) continue;
    line[match[2] as "x0" | "x1" | "y0" | "y1"] = value;
    changed = true;
  }
  return changed ? next : lines;
}

export function sharedReadingLineShapes(lines: SharedReadingLine[]): Array<Record<string, unknown>> {
  return lines.flatMap((line) => {
    const color = line.color || "#f8e36a";
    const range = line.sourceYRange;
    if (!range || range[1] <= range[0]) return [];
    const toPaper = (value: number) => Math.min(1, Math.max(0, (value - range[0]) / (range[1] - range[0])));
    return [{
      type: "line",
      xref: "x",
      yref: "paper",
      x0: line.x0,
      x1: line.x1,
      y0: toPaper(line.y0),
      y1: toPaper(line.y1),
      line: { color, width: 2.2, dash: "dash" },
      editable: false,
    }];
  });
}

function applyShape(line: ReadingLine, shape: Record<string, unknown>): boolean {
  let changed = false;
  for (const key of ["x0", "x1", "y0", "y1"] as const) {
    const value = shape[key];
    if (typeof value !== "number" || !Number.isFinite(value) || line[key] === value) continue;
    line[key] = value;
    changed = true;
  }
  return changed;
}

function signed(value: number): string {
  const rendered = Math.abs(value).toLocaleString("fr-FR", { maximumFractionDigits: 2 });
  return `${value > 0 ? "+" : value < 0 ? "−" : ""}${rendered}`;
}
