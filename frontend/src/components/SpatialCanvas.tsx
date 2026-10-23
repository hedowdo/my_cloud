import { useEffect, useRef, useState, type PointerEvent } from 'react';
import { api, ApiError, type Session } from '../api/identity';
import { symbol, type Item } from '../api/files';
import {
  clamp,
  fit,
  logicalDelta,
  CANVAS_ZOOM,
  type Camera,
  type Point,
  type Position,
} from '../api/spatial';
import './spatial.css';

type Drag = {
  id: string | null;
  pointer: number;
  start: Point;
  original: Point;
  camera: Camera;
  moved: boolean;
};
export function SpatialCanvas({
  items,
  parent,
  session,
  selected,
  onSelect,
  onOpen,
  onUpload,
  onExpired,
  onTrash,
  onShowTrash,
}: {
  items: Item[];
  parent: string;
  session: Session;
  selected: string | undefined;
  onSelect: (
    item: Item | null,
    source?: 'pointer' | 'keyboard' | 'touch',
  ) => void;
  onOpen: (item: Item) => void;
  onUpload: () => void;
  onExpired: () => void;
  onTrash: (item: Item) => Promise<void>;
  onShowTrash: () => void;
}) {
  const viewport = useRef<HTMLDivElement>(null);
  const trashTarget = useRef<HTMLButtonElement>(null);
  const [overTrash, setOverTrash] = useState(false);
  const [issue, setIssue] = useState('');
  function reportIssue(value: string) {
    setIssue(value);
    setMessage(value);
  }
  function hitsTrash(x: number, y: number) {
    const box = trashTarget.current?.getBoundingClientRect();
    return (
      !!box &&
      x >= box.left &&
      x <= box.right &&
      y >= box.top &&
      y <= box.bottom
    );
  }
  const [positions, setPositions] = useState<Record<string, Position>>({});
  const positionsRef = useRef(positions);
  const [camera, setCamera] = useState<Camera>({
    x: 0,
    y: 0,
    zoom: CANVAS_ZOOM,
  });
  const cameraRef = useRef(camera);
  const [hovered, setHovered] = useState<string | null>(null);
  const [dragging, setDragging] = useState<string | null>(null);
  const drag = useRef<Drag | null>(null);
  const skipClick = useRef(false);
  const saving = useRef(false);
  const fitted = useRef(false);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState('Arranging your space…');
  const [conflict, setConflict] = useState<{
    id: string;
    point: Point;
    revision: number;
  } | null>(null);
  const keys = items
    .map((item) => item.id)
    .sort()
    .join(',');
  const sessionRef = useRef(session);
  useEffect(() => {
    sessionRef.current = session;
  }, [session]);
  const activeParent = useRef(parent);
  useEffect(() => {
    activeParent.current = parent;
    return () => {
      activeParent.current = '';
    };
  }, [parent]);
  function applyPositions(rows: Position[]) {
    const next = Object.fromEntries(rows.map((p) => [p.item_id, p]));
    positionsRef.current = next;
    setPositions(next);
  }
  function moveCamera(next: Camera) {
    const box = viewport.current;
    const bound =
      1_000_000 * next.zoom +
      Math.max(box?.clientWidth ?? 0, box?.clientHeight ?? 0);
    const bounded = {
      ...next,
      zoom: CANVAS_ZOOM,
      x: clamp(next.x, -bound, bound),
      y: clamp(next.y, -bound, bound),
    };
    cameraRef.current = bounded;
    setCamera(bounded);
  }
  function fitAll() {
    const box = viewport.current;
    if (box)
      moveCamera(
        fit(
          Object.values(positionsRef.current),
          box.clientWidth,
          box.clientHeight,
        ),
      );
  }
  useEffect(() => {
    let active = true;
    fitted.current = false;
    async function initialize() {
      const ids = keys ? keys.split(',') : [],
        rows: Position[] = [];
      for (let start = 0; start < ids.length; start += 250) {
        if (!active) return rows;
        rows.push(
          ...(await api<Position[]>(
            `/folders/${parent}/positions/initialize`,
            'POST',
            { item_ids: ids.slice(start, start + 250) },
            sessionRef.current,
          )),
        );
      }
      return rows;
    }
    initialize()
      .then((rows) => {
        if (!active) return;
        applyPositions(rows);
        setMessage('');
        setIssue('');
        const box = viewport.current;
        if (box) moveCamera(fit(rows, box.clientWidth, box.clientHeight));
        fitted.current = true;
      })
      .catch((error) => {
        if (!active) return;
        if (error instanceof ApiError && error.status === 401) onExpired();
        else
          reportIssue(
            'Could not load placement. Switch to list view or refresh to retry.',
          );
      });
    const timer = window.setInterval(() => {
      if (drag.current || saving.current || !active || !fitted.current) return;
      void api<Position[]>(`/folders/${parent}/positions`)
        .then((rows) => {
          if (active && !drag.current && !saving.current) {
            const ids = new Set(keys.split(','));
            applyPositions(rows.filter((p) => ids.has(p.item_id)));
          }
        })
        .catch((error) => {
          if (active && error instanceof ApiError && error.status === 401)
            onExpired();
          else if (active)
            reportIssue(
              'Placement refresh unavailable. Your files remain available in list view.',
            );
        });
    }, 5000);
    return () => {
      active = false;
      window.clearInterval(timer);
      drag.current = null;
    };
  }, [keys, parent, onExpired]);
  useEffect(() => {
    const box = viewport.current;
    if (!box) return;
    let previous = { width: box.clientWidth, height: box.clientHeight };
    const observer = new ResizeObserver(() => {
      const width = box.clientWidth,
        height = box.clientHeight;
      if (!drag.current) {
        const next = {
          ...cameraRef.current,
          x: cameraRef.current.x + (width - previous.width) / 2,
          y: cameraRef.current.y + (height - previous.height) / 2,
        };
        moveCamera(next);
      }
      previous = { width, height };
    });
    observer.observe(box);
    return () => observer.disconnect();
  }, []);
  async function persist(id: string, point: Point, revision: number) {
    if (saving.current) return;
    saving.current = true;
    setPending(true);
    setMessage('Saving placement…');
    setIssue('');
    const folder = parent;
    try {
      const row = await api<Position>(
        `/items/${id}/position`,
        'PATCH',
        {
          parent_id: folder,
          expected_revision: revision,
          expected_item_revision: items.find((item) => item.id === id)
            ?.revision,
          x: point.x,
          y: point.y,
        },
        session,
      );
      if (activeParent.current !== folder) return;
      const next = { ...positionsRef.current, [id]: row };
      positionsRef.current = next;
      setPositions(next);
      setConflict(null);
      setMessage('Placement saved for your circle.');
    } catch (error) {
      if (activeParent.current !== folder) return;
      if (error instanceof ApiError && error.status === 401) onExpired();
      try {
        const rows = await api<Position[]>(`/folders/${folder}/positions`);
        if (activeParent.current !== folder) return;
        const ids = new Set(keys.split(','));
        applyPositions(rows.filter((p) => ids.has(p.item_id)));
        const latest = await api<Item>(`/items/${id}`);
        if (
          latest.parent_id !== folder ||
          latest.revision !== items.find((item) => item.id === id)?.revision
        ) {
          setConflict(null);
          reportIssue(
            'This file changed. Refresh the file list before moving it again.',
          );
          return;
        }
        const row = rows.find((p) => p.item_id === id);
        setConflict(row ? { id, point, revision: row.revision } : null);
        reportIssue(
          row
            ? 'Placement changed or could not be saved. Review the current position; retry only if you still want your move.'
            : 'This item is unavailable or moved folders. Refresh the file list.',
        );
      } catch {
        reportIssue(
          'Could not save or refresh placement. Refresh before trying again.',
        );
      }
    } finally {
      saving.current = false;
      setPending(false);
    }
  }
  function start(event: PointerEvent, id: string | null) {
    if (event.button !== 0 || saving.current || conflict) return;
    if (!id && (event.target as HTMLElement).closest('button')) return;
    const point = id ? positionsRef.current[id] : cameraRef.current;
    if (!point) return;
    event.stopPropagation();
    event.currentTarget.setPointerCapture(event.pointerId);
    drag.current = {
      id,
      pointer: event.pointerId,
      start: { x: event.clientX, y: event.clientY },
      original: { ...point },
      camera: { ...cameraRef.current },
      moved: false,
    };
    if (id) setDragging(id);
  }
  function pointerMove(event: PointerEvent) {
    const current = drag.current;
    if (!current || current.pointer !== event.pointerId) return;
    const delta = {
      x: event.clientX - current.start.x,
      y: event.clientY - current.start.y,
    };
    if (Math.hypot(delta.x, delta.y) < 5 && !current.moved) return;
    current.moved = true;
    if (current.id) {
      setOverTrash(hitsTrash(event.clientX, event.clientY));
      const logical = logicalDelta(delta, current.camera.zoom);
      const original = positionsRef.current[current.id];
      const next = {
        ...positionsRef.current,
        [current.id]: {
          ...original,
          x: clamp(current.original.x + logical.x, -1e6, 1e6),
          y: clamp(current.original.y + logical.y, -1e6, 1e6),
        },
      };
      positionsRef.current = next;
      setPositions(next);
    } else
      moveCamera({
        ...current.camera,
        x: current.original.x + delta.x,
        y: current.original.y + delta.y,
      });
  }
  function end(event: PointerEvent, cancel = false) {
    const current = drag.current;
    if (!current || current.pointer !== event.pointerId) return;
    drag.current = null;
    setDragging(null);
    setOverTrash(false);
    if (event.currentTarget.hasPointerCapture(event.pointerId))
      event.currentTarget.releasePointerCapture(event.pointerId);
    skipClick.current = current.moved;
    if (current.id && current.moved) {
      const row = positionsRef.current[current.id];
      if (cancel || hitsTrash(event.clientX, event.clientY)) {
        const next = {
          ...positionsRef.current,
          [current.id]: { ...row, ...current.original },
        };
        positionsRef.current = next;
        setPositions(next);
        if (!cancel) {
          const item = items.find((item) => item.id === current.id);
          if (item) {
            saving.current = true;
            setPending(true);
            setIssue('');
            void onTrash(item)
              .catch((error) => {
                if (activeParent.current === parent)
                  reportIssue(
                    error instanceof Error
                      ? error.message
                      : 'Could not move item to the Recycle Bin.',
                  );
              })
              .finally(() => {
                saving.current = false;
                setPending(false);
              });
          }
        }
      } else void persist(current.id, row, row.revision);
    } else if (cancel) moveCamera(current.camera);
  }
  return (
    <section
      className={`spatial-shell ${items.length > 100 ? 'spatial-dense' : ''} ${dragging ? 'spatial-dragging' : ''}`}
      aria-label="Shared spatial dashboard"
    >
      <div className="spatial-tools" aria-label="Canvas controls">
        <details className="spatial-more">
          <summary aria-label="More canvas controls">⋯</summary>
          <div className="spatial-more-content">
            <button className="secondary" onClick={fitAll}>
              Recenter
            </button>
            {(['left', 'right', 'up', 'down'] as const).map((direction) => (
              <button
                className="secondary"
                key={direction}
                aria-label={`Pan ${direction}`}
                onClick={() =>
                  moveCamera({
                    ...cameraRef.current,
                    x:
                      cameraRef.current.x +
                      (direction === 'left'
                        ? 80
                        : direction === 'right'
                          ? -80
                          : 0),
                    y:
                      cameraRef.current.y +
                      (direction === 'up'
                        ? 80
                        : direction === 'down'
                          ? -80
                          : 0),
                  })
                }
              >
                {{ left: '←', right: '→', up: '↑', down: '↓' }[direction]}
              </button>
            ))}
            <p>
              Drag empty space to pan. Focus a node and use arrow keys to move
              it.
            </p>
          </div>
        </details>
      </div>
      <p className="spatial-guidance visually-hidden" id="spatial-help">
        Drag nodes to arrange. Drag empty space to pan. Focus a node and use
        arrow keys to move it; Enter selects, then Open in details. Double click
        opens. Drag to the bottom-left Recycle Bin to discard; items can be
        restored.
      </p>
      <div
        className="spatial-viewport"
        ref={viewport}
        onPointerDown={(e) => start(e, null)}
        onPointerMove={pointerMove}
        onPointerUp={(e) => end(e)}
        onPointerCancel={(e) => end(e, true)}
        onClick={(e) => {
          if (skipClick.current) {
            skipClick.current = false;
            return;
          }
          if (!(e.target as HTMLElement).closest('button')) onSelect(null);
        }}
      >
        <div
          className="spatial-world"
          style={{
            transform: `translate(${camera.x}px,${camera.y}px) scale(${camera.zoom})`,
          }}
        >
          <svg className="spatial-lines" aria-hidden="true" overflow="visible">
            <path
              d={items
                .map((item) => {
                  const p = positions[item.id];
                  return p ? `M0 0 L${p.x} ${p.y}` : '';
                })
                .join(' ')}
              vectorEffect="non-scaling-stroke"
            />
            <path
              className="active"
              d={[...new Set([selected, hovered])]
                .map((id) => {
                  const p = id ? positions[id] : undefined;
                  return p ? `M0 0 L${p.x} ${p.y}` : '';
                })
                .join(' ')}
              vectorEffect="non-scaling-stroke"
            />
          </svg>
          <div
            className="spatial-core"
            aria-hidden="true"
            style={{ transform: `scale(${1 / camera.zoom})` }}
          >
            <span />
            <span />
            <span />
            <i />
          </div>
          {items.map((item, index) => {
            const p = positions[item.id];
            return (
              p && (
                <button
                  key={item.id}
                  className={`spatial-node ${selected === item.id ? 'selected' : ''} ${index < 40 ? 'animated' : ''}`}
                  style={{
                    left: p.x,
                    top: p.y,
                    // Keep the icon, focus ring and filename readable at every camera scale.
                    transform: `scale(${1 / camera.zoom})`,
                    animationDelay: `-${index * 0.73}s`,
                  }}
                  aria-label={`Select ${item.name}`}
                  aria-pressed={selected === item.id}
                  aria-describedby="spatial-help"
                  aria-disabled={pending}
                  data-item-id={item.id}
                  onPointerEnter={() => setHovered(item.id)}
                  onPointerLeave={() => setHovered(null)}
                  onFocus={(event) => {
                    setHovered(item.id);
                    const box = viewport.current;
                    if (box && event.currentTarget.matches(':focus-visible')) {
                      const c = cameraRef.current,
                        x = p.x * c.zoom + c.x,
                        y = p.y * c.zoom + c.y;
                      if (
                        x < 60 ||
                        x > box.clientWidth - 60 ||
                        y < 60 ||
                        y > box.clientHeight - 60
                      ) {
                        const zoom = CANVAS_ZOOM;
                        moveCamera({
                          zoom,
                          x: box.clientWidth / 2 - p.x * zoom,
                          y: box.clientHeight / 2 - p.y * zoom,
                        });
                      }
                    }
                  }}
                  onBlur={() => setHovered(null)}
                  onPointerDown={(e) => start(e, item.id)}
                  onPointerMove={pointerMove}
                  onPointerUp={(e) => end(e)}
                  onPointerCancel={(e) => end(e, true)}
                  onClick={(e) => {
                    e.stopPropagation();
                    if (skipClick.current) {
                      skipClick.current = false;
                      return;
                    }
                    onSelect(
                      item,
                      e.detail === 0
                        ? 'keyboard'
                        : (e.nativeEvent as globalThis.PointerEvent)
                              .pointerType === 'touch'
                          ? 'touch'
                          : 'pointer',
                    );
                  }}
                  onDoubleClick={() => {
                    if (!skipClick.current) {
                      onSelect(null);
                      onOpen(item);
                    }
                  }}
                  onKeyDown={(e) => {
                    const d: Record<string, Point> = {
                      ArrowLeft: { x: -20, y: 0 },
                      ArrowRight: { x: 20, y: 0 },
                      ArrowUp: { x: 0, y: -20 },
                      ArrowDown: { x: 0, y: 20 },
                    };
                    if (d[e.key]) {
                      e.preventDefault();
                      if (saving.current || conflict) return;
                      const step = e.shiftKey ? 5 : 1;
                      void persist(
                        item.id,
                        {
                          x: clamp(p.x + d[e.key].x * step, -1e6, 1e6),
                          y: clamp(p.y + d[e.key].y * step, -1e6, 1e6),
                        },
                        p.revision,
                      );
                    }
                  }}
                >
                  <span className="spatial-orb" aria-hidden="true">
                    {item.has_icon ? (
                      <img
                        src={`/api/items/${item.id}/icon?v=${item.revision}`}
                        alt=""
                      />
                    ) : (
                      symbol(item)
                    )}
                  </span>
                  <span className="spatial-name">{item.name}</span>
                </button>
              )
            );
          })}
        </div>
        {!items.length && (
          <div className="spatial-empty">
            <h2>A little room for everything.</h2>
            <p>Your circle’s files, connected in one calm space.</p>
            <button onClick={onUpload}>Upload your first file</button>
          </div>
        )}
      </div>
      <button
        ref={trashTarget}
        className={`canvas-trash secondary ${overTrash ? 'drop-active' : ''}`}
        aria-label="Open Recycle Bin"
        title="Recycle Bin — drag items here"
        disabled={pending}
        onClick={onShowTrash}
      >
        <svg
          viewBox="0 0 24 24"
          width="25"
          height="25"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7" />
        </svg>
      </button>
      {issue && (
        <div className="spatial-issue" role="alert">
          {issue}
          <button
            className="secondary"
            aria-label="Dismiss canvas error"
            onClick={() => setIssue('')}
          >
            ×
          </button>
        </div>
      )}
      <div className="spatial-status visually-hidden" role="status">
        {message}
      </div>
      {conflict && (
        <div className="spatial-conflict">
          <p>
            Your intended placement is waiting. Other file actions are
            unchanged.
          </p>
          <button
            disabled={pending}
            onClick={() =>
              void persist(conflict.id, conflict.point, conflict.revision)
            }
          >
            Retry my placement
          </button>{' '}
          <button
            className="secondary"
            disabled={pending}
            onClick={() => {
              setConflict(null);
              setMessage('Kept the shared position.');
              setIssue('');
            }}
          >
            Keep shared position
          </button>
        </div>
      )}
      {items.length >= 500 && (
        <p className="spatial-limit">
          Canvas shows the first 500 matching items. Switch to list view to
          browse every page.
        </p>
      )}
    </section>
  );
}
