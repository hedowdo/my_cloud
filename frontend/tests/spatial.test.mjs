import assert from 'node:assert/strict';
import test from 'node:test';
import { fit, logicalDelta, CANVAS_ZOOM } from '../src/api/spatial.ts';
test('camera stays at 65% for empty, sparse and distant placements and all viewport sizes', () => {
  for (const points of [
    [],
    [{ x: 240, y: 0 }],
    [
      { x: -1000, y: 500 },
      { x: 900, y: -300 },
    ],
    [{ x: 1e6, y: -1e6 }],
  ]) {
    for (const [width, height] of [
      [1600, 900],
      [820, 1180],
      [380, 420],
    ]) {
      const c = fit(points, width, height);
      assert.equal(c.zoom, 0.65);
      assert.ok(Number.isFinite(c.x) && Number.isFinite(c.y));
      const xs = [0, ...points.map((p) => p.x)],
        ys = [0, ...points.map((p) => p.y)];
      assert.equal(
        ((Math.min(...xs) + Math.max(...xs)) / 2) * c.zoom + c.x,
        width / 2,
      );
      assert.equal(
        ((Math.min(...ys) + Math.max(...ys)) / 2) * c.zoom + c.y,
        (height - 60) / 2,
      );
    }
  }
});
test('drag at fixed scale preserves exact screen-to-shared-coordinate conversion', () => {
  assert.deepEqual(logicalDelta({ x: 65, y: -26 }, CANVAS_ZOOM), {
    x: 100,
    y: -40,
  });
});
