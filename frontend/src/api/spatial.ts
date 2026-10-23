export type Point = { x: number; y: number };
export type Position = Point & { item_id: string; revision: number };
export type Camera = Point & { zoom: number };
export const CANVAS_ZOOM = 0.65;
export function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}
export function fit(points: Point[], width: number, height: number): Camera {
  const xs = [0, ...points.map((p) => p.x)];
  const ys = [0, ...points.map((p) => p.y)];
  const left = Math.min(...xs),
    right = Math.max(...xs);
  const top = Math.min(...ys),
    bottom = Math.max(...ys);
  const zoom = CANVAS_ZOOM;
  return {
    zoom,
    x: width / 2 - ((left + right) / 2) * zoom,
    y: (height - 60) / 2 - ((top + bottom) / 2) * zoom,
  };
}
export function logicalDelta(delta: Point, zoom: number): Point {
  return { x: delta.x / zoom, y: delta.y / zoom };
}
