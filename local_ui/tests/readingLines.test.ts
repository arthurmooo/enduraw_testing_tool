import assert from "node:assert/strict";
import test from "node:test";
import {
  readingLineMetrics,
  plotCoordinatesFromClient,
  sharedReadingLineShapes,
  updateReadingLinesFromRelayout,
  type ReadingLine,
} from "../src/lib/readingLines.ts";

const line: ReadingLine = {
  id: "line-1",
  seriesKey: "fc_bpm",
  seriesLabel: "HR",
  x0: 60,
  x1: 120,
  y0: 140,
  y1: 160,
  yUnit: "bpm",
  timeAxis: true,
};

test("calcule une pente temporelle par minute", () => {
  assert.deepEqual(readingLineMetrics(line), {
    deltaX: 60,
    deltaY: 20,
    slope: 20,
    slopeUnit: "bpm/min",
  });
});

test("rejoue le déplacement Plotly de chaque extrémité", () => {
  const updated = updateReadingLinesFromRelayout([line], {
    "shapes[4].x1": 180,
    "shapes[4].y1": 170,
  }, 4);
  assert.equal(updated[0].x1, 180);
  assert.equal(updated[0].y1, 170);
  assert.equal(line.x1, 120);
});

test("projette les memes bornes temporelles sur les autres graphes", () => {
  const shared = {
    ...line,
    sourceGraphId: "hr_vo2_fc_time",
    color: "#12ab34",
    sourceYRange: [100, 200] as [number, number],
  };
  const shapes = sharedReadingLineShapes([shared, { ...shared, id: "line-2", x0: 180, x1: 240 }]);
  assert.equal(shapes.length, 2);
  assert.equal(shapes[0].x0, 60);
  assert.equal(shapes[0].x1, 120);
  assert.equal(shapes[0].y0, 0.4);
  assert.equal(shapes[0].y1, 0.6);
  assert.equal(shapes[0].yref, "paper");
  assert.equal(shapes[0].editable, false);
  assert.equal((shapes[0].line as { color: string }).color, "#12ab34");
  assert.equal(shapes[1].x0, 180);
  assert.equal(shapes[1].x1, 240);
});

test("convertit le pointeur en coordonnees exactes du graphe", () => {
  assert.deepEqual(
    plotCoordinatesFromClient(
      150,
      100,
      { left: 0, right: 300, top: 0, bottom: 200 },
      { l: 50, r: 50, t: 20, b: 20 },
      [0, 100],
      [20, 60],
    ),
    { x: 50, y: 40 },
  );
  assert.equal(
    plotCoordinatesFromClient(10, 100, { left: 0, right: 300, top: 0, bottom: 200 }, { l: 50, r: 50, t: 20, b: 20 }, [0, 100], [20, 60]),
    null,
  );
});
