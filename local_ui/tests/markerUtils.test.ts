import assert from "node:assert/strict";
import test from "node:test";
import { detectFcMaxProposal } from "../src/lib/markerUtils.ts";
import type { MetaSoftPoint } from "../src/types/metasoft.ts";

function point(tSeconds: number, phase: string, fcBpm: number): MetaSoftPoint {
  return {
    index: tSeconds,
    t_seconds: tSeconds,
    phase,
    marker: null,
    values: { fc_bpm: fcBpm },
    value_sources: {},
  } as MetaSoftPoint;
}

test("propose le pic FC natif de la phase exercice et qualifie un pic isole", () => {
  const proposal = detectFcMaxProposal([
    point(0, "Repos", 210),
    point(100, "Exercice", 170),
    point(101, "Exercice", 171),
    point(102, "Exercice", 190),
    point(103, "Exercice", 172),
    point(104, "Exercice", 173),
  ]);

  assert.deepEqual(proposal, {
    t_seconds: 102,
    raw_peak_bpm: 190,
    average_5s_bpm: 175.2,
    isolated: true,
  });
});

test("reste sans proposition lorsque la FC native est absente", () => {
  assert.equal(detectFcMaxProposal([]), null);
});
