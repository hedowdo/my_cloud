import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from 'react';
import { createPortal } from 'react-dom';
import { NavigationDrawer } from './NavigationDrawer';
import { api, ApiError, type Session } from '../api/identity';
import {
  ROOT,
  bytes,
  symbol,
  transfer,
  putIcon,
  validateFile,
  type Event,
  type Item,
  type Person,
  type Storage,
} from '../api/files';
import { Administration } from './Administration';
import { DeletionQueue } from './DeletionQueue';
import { Dialog } from './Dialog';
import { Preview } from './Preview';
import { SpatialCanvas } from './SpatialCanvas';
import './file-manager.css';
import './immersive.css';

type View = 'files' | 'activity' | 'trash' | 'admin';
type Action = {
  kind: 'folder' | 'rename' | 'move' | 'trash' | 'restore' | 'delete';
  item?: Item;
};
type Collision = {
  file: File;
  target?: Item;
  resolve: (choice: string) => void;
};
const PAGE = 24;
const initialFilters = {
  q: '',
  category: 'all',
  uploader: '',
  after: '',
  before: '',
  sort: 'name',
  direction: 'asc',
  scope: 'folder',
};

function FileIcon({ item }: { item: Item }) {
  return (
    <span className={`file-symbol ${item.kind}`} aria-hidden="true">
      {item.has_icon && !item.trashed_at ? (
        <img src={`/api/items/${item.id}/icon?v=${item.revision}`} alt="" />
      ) : (
        symbol(item)
      )}
    </span>
  );
}

function Destination({
  value,
  onChange,
}: {
  value: string;
  onChange: (id: string) => void;
}) {
  const [folders, setFolders] = useState<Item[]>([]);
  const [crumbs, setCrumbs] = useState<Item[]>([]);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    Promise.all([
      api<Item[]>(
        `/browse?parent_id=${value}&category=folder&limit=10&offset=${offset}`,
      ),
      api<Item[]>(`/folders/${value}/breadcrumbs`),
    ])
      .then(([rows, path]) => {
        if (active) {
          setFolders(rows);
          setCrumbs(path);
          setError('');
        }
      })
      .catch((failure) => {
        if (active) setError(failure.message);
      });
    return () => {
      active = false;
    };
  }, [value, offset]);
  function choose(id: string) {
    setOffset(0);
    onChange(id);
  }
  return (
    <fieldset className="destination">
      <legend>Destination folder</legend>
      <nav aria-label="Destination path">
        {crumbs.map((folder) => (
          <button
            key={folder.id}
            type="button"
            className="crumb"
            onClick={() => choose(folder.id)}
          >
            {folder.id === ROOT ? 'All files' : folder.name}
          </button>
        ))}
      </nav>
      {error && (
        <p role="alert" className="error">
          {error}{' '}
          <button
            type="button"
            className="secondary"
            onClick={() => choose(ROOT)}
          >
            Use All files
          </button>
        </p>
      )}
      <p className="fine-print">
        Selected:{' '}
        {crumbs.at(-1)?.name === '/'
          ? 'All files'
          : (crumbs.at(-1)?.name ?? 'All files')}
      </p>
      <div className="folder-choices">
        {folders.map((folder) => (
          <button
            key={folder.id}
            type="button"
            className="secondary"
            onClick={() => choose(folder.id)}
          >
            ▱ {folder.name}
          </button>
        ))}
      </div>
      <div className="pager">
        <button
          className="secondary"
          type="button"
          disabled={offset === 0}
          onClick={() => setOffset(Math.max(0, offset - 10))}
        >
          Earlier folders
        </button>
        <button
          className="secondary"
          type="button"
          disabled={folders.length < 10}
          onClick={() => setOffset(offset + 10)}
        >
          More folders
        </button>
      </div>
    </fieldset>
  );
}

function ItemAction({
  action,
  parent,
  onClose,
  onSave,
  busy,
  error,
}: {
  action: Action;
  parent: string;
  onClose: () => void;
  onSave: (path: string, method: string, body: unknown) => Promise<void>;
  busy: boolean;
  error: string;
}) {
  const [name, setName] = useState(action.item?.name ?? '');
  const [destination, setDestination] = useState(
    action.kind === 'restore' ? ROOT : (action.item?.parent_id ?? parent),
  );
  const [keep, setKeep] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const item = action.item;
  const titles = {
    folder: 'New folder',
    rename: 'Rename item',
    move: 'Move item',
    trash: 'Move to Recycle Bin',
    restore: 'Restore item',
    delete: 'Permanently delete',
  };
  async function submit(event: FormEvent) {
    event.preventDefault();
    const body = {
      expected_revision: item?.revision,
      name: name.normalize('NFC'),
      collision: keep ? 'keep_both' : 'error',
    };
    if (action.kind === 'folder')
      await onSave('/folders', 'POST', {
        name: name.normalize('NFC'),
        parent_id: parent,
        collision: body.collision,
      });
    else if (action.kind === 'delete')
      await onSave(`/trash/${item!.id}`, 'DELETE', {
        expected_revision: item!.revision,
        confirm: true,
      });
    else if (action.kind === 'trash')
      await onSave(`/items/${item!.id}/trash`, 'POST', {
        expected_revision: item!.revision,
      });
    else
      await onSave(
        `/items/${item!.id}${action.kind === 'restore' ? '/restore' : ''}`,
        action.kind === 'restore' ? 'POST' : 'PATCH',
        {
          ...body,
          ...(action.kind !== 'rename' ? { parent_id: destination } : {}),
        },
      );
  }
  return (
    <Dialog title={titles[action.kind]} onClose={onClose} busy={busy}>
      <form onSubmit={(event) => void submit(event)}>
        {item && <p className="item-name">{item.name}</p>}
        {['folder', 'rename', 'move', 'restore'].includes(action.kind) && (
          <>
            <label htmlFor="item-name">
              {action.kind === 'folder' ? 'Folder name' : 'Name'}
            </label>
            <input
              id="item-name"
              data-dialog-autofocus
              required
              value={name}
              maxLength={255}
              disabled={busy}
              onChange={(event) => setName(event.target.value)}
            />
          </>
        )}
        {['move', 'restore'].includes(action.kind) && (
          <Destination value={destination} onChange={setDestination} />
        )}
        {['folder', 'rename', 'move', 'restore'].includes(action.kind) && (
          <label className="check">
            <input
              type="checkbox"
              checked={keep}
              disabled={busy}
              onChange={(event) => setKeep(event.target.checked)}
            />
            Keep both if a name already exists
          </label>
        )}
        {action.kind === 'restore' && (
          <p className="fine-print">
            Choose the destination above. Recovery copies keep their original
            bytes.
          </p>
        )}
        {action.kind === 'trash' && (
          <p>
            Everyone in your circle will see this item in the shared Recycle
            Bin. You can restore it later.
          </p>
        )}
        {action.kind === 'delete' && (
          <>
            <p>
              This permanently removes the item and everything inside it from
              the shared cloud. It cannot be restored here.
            </p>
            <label className="check">
              <input
                type="checkbox"
                checked={confirmed}
                onChange={(event) => setConfirmed(event.target.checked)}
                disabled={busy}
              />
              I understand and confirm permanent deletion.
            </label>
          </>
        )}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <div className="dialog-actions">
          <button
            type="button"
            className="secondary"
            disabled={busy}
            onClick={onClose}
          >
            Cancel
          </button>
          <button disabled={busy || (action.kind === 'delete' && !confirmed)}>
            {busy
              ? 'Saving…'
              : action.kind === 'delete'
                ? 'Delete permanently'
                : 'Confirm'}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

export function FileManager({
  session,
  onExpired,
  onTheme,
  onSignOut,
}: {
  session: Session;
  onExpired: () => void;
  onTheme: (theme: 'light' | 'dark') => void;
  onSignOut: () => void;
}) {
  const [view, setView] = useState<View>('files');
  const [parent, setParent] = useState(ROOT);
  const [items, setItems] = useState<Item[]>([]);
  const [crumbs, setCrumbs] = useState<Item[]>([]);
  const [people, setPeople] = useState<Person[]>([]);
  const [events, setEvents] = useState<Event[]>([]);
  const [storage, setStorage] = useState<Storage | null>(null);
  const [selected, setSelected] = useState<Item | null>(null);
  const [filters, setFilters] = useState(initialFilters);
  const [search, setSearch] = useState('');
  const [eventAction, setEventAction] = useState('');
  const [offset, setOffset] = useState(0);
  const [grid, setGrid] = useState(false);
  const [spatial, setSpatial] = useState(true);
  const [wide, setWide] = useState(() => window.innerWidth >= 768);
  const canvas =
    spatial && wide && view === 'files' && filters.scope === 'folder';
  useEffect(() => {
    const media = window.matchMedia('(min-width: 768px)');
    const update = () => setWide(media.matches);
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);
  const [sidebar, setSidebar] = useState(false);
  const [searchTarget, setSearchTarget] = useState<HTMLElement | null>(null);
  const [detailsPending, setDetailsPending] = useState(false);
  const selectionTimer = useRef<number | undefined>(undefined);
  const detailsTrigger = useRef<HTMLElement | null>(null);
  const detailsKeyboard = useRef(false);
  const detailsPanel = useRef<HTMLElement>(null);
  function selectSpatial(
    item: Item | null,
    source?: 'pointer' | 'keyboard' | 'touch',
  ) {
    window.clearTimeout(selectionTimer.current);
    detailsTrigger.current = document.activeElement as HTMLElement | null;
    detailsKeyboard.current = source === 'keyboard';
    setSelected(item);
    setDetailsPending(Boolean(item && source === 'pointer'));
    // Leave the desktop double-click window clear before an overlay covers the pointer.
    if (item && source === 'pointer')
      selectionTimer.current = window.setTimeout(
        () => setDetailsPending(false),
        500,
      );
  }
  function closeDetails() {
    window.clearTimeout(selectionTimer.current);
    setSelected(null);
    setDetailsPending(false);
    detailsTrigger.current?.focus({ preventScroll: true });
  }
  useEffect(() => {
    if (selected && !detailsPending && detailsKeyboard.current)
      detailsPanel.current
        ?.querySelector<HTMLButtonElement>('button')
        ?.focus({ preventScroll: true });
  }, [selected, detailsPending]);
  useEffect(() => () => window.clearTimeout(selectionTimer.current), []);
  const [version, setVersion] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  useEffect(() => {
    if (!canvas || !notice) return;
    const timer = window.setTimeout(() => setNotice(''), 5000);
    return () => window.clearTimeout(timer);
  }, [canvas, notice]);
  const [busy, setBusy] = useState(false);
  const [action, setAction] = useState<Action | null>(null);
  const [actionError, setActionError] = useState('');
  const [preview, setPreview] = useState<Item | null>(null);
  const [progress, setProgress] = useState<{
    name: string;
    percent: number;
    index: number;
    total: number;
  } | null>(null);
  const [uploadIcon, setUploadIcon] = useState<File | null>(null);
  const [collision, setCollision] = useState<Collision | null>(null);
  const [replaceConfirmed, setReplaceConfirmed] = useState(false);
  const controller = useRef<AbortController | null>(null);
  const uploadInput = useRef<HTMLInputElement>(null);
  const uploadIconInput = useRef<HTMLInputElement>(null);
  const collisionRef = useRef<Collision | null>(null);
  const loadId = useRef(0);
  const refresh = useCallback(() => {
    setError('');
    setSelected(null);
    setLoading(true);
    setVersion((value) => value + 1);
  }, []);
  const failed = useCallback(
    (failure: unknown) => {
      if (failure instanceof ApiError && failure.status === 401) onExpired();
      else
        setError(
          failure instanceof Error
            ? failure.message
            : 'Something went wrong. Please retry.',
        );
    },
    [onExpired],
  );
  useEffect(
    () => () => {
      controller.current?.abort();
      collisionRef.current?.resolve('cancel');
    },
    [],
  );
  useEffect(() => {
    let active = true;
    const current = ++loadId.current;
    const query = new URLSearchParams({
      parent_id: parent,
      limit: String(canvas ? 100 : PAGE),
      offset: String(canvas ? 0 : offset),
      ...filters,
    });
    if (!filters.uploader) query.delete('uploader');
    for (const field of ['after', 'before'] as const) {
      if (filters[field])
        query.set(
          field,
          `${filters[field]}T${field === 'before' ? '23:59:59.999' : '00:00:00'}Z`,
        );
      else query.delete(field);
    }
    async function load() {
      const [space, circle] = await Promise.all([
        api<Storage>('/storage'),
        api<Person[]>('/people'),
      ]);
      let rows: Item[] = [],
        history: Event[] = [],
        path: Item[] = [];
      if (view === 'files')
        [rows, path] = await Promise.all([
          api<Item[]>(`/browse?${query}`),
          api<Item[]>(`/folders/${parent}/breadcrumbs`),
        ]);
      if (canvas && rows.length === 100) {
        for (let start = 100; start < 500; start += 100) {
          query.set('offset', String(start));
          const more = await api<Item[]>(`/browse?${query}`);
          rows.push(...more);
          if (more.length < 100) break;
        }
      }
      if (view === 'trash')
        rows = await api<Item[]>(`/trash?limit=${PAGE}&offset=${offset}`);
      if (view === 'activity' || view === 'admin') {
        const eventsQuery = new URLSearchParams({
          limit: String(PAGE),
          offset: String(offset),
          q: filters.q,
          action: eventAction,
        });
        if (filters.uploader) eventsQuery.set('actor', filters.uploader);
        for (const key of ['after', 'before'])
          if (query.has(key)) eventsQuery.set(key, query.get(key)!);
        history = await api<Event[]>(
          `${view === 'admin' ? '/admin/activity' : '/events'}?${eventsQuery}`,
        );
      }
      if (active && current === loadId.current) {
        setStorage(space);
        setPeople(circle);
        setItems(rows);
        setCrumbs(path);
        setEvents(history);
        setLoading(false);
      }
    }
    void load().catch((failure) => {
      if (active) {
        failed(failure);
        setLoading(false);
      }
    });
    return () => {
      active = false;
    };
  }, [parent, view, offset, filters, eventAction, version, failed, canvas]);
  function navigate(next: View, folder = parent) {
    setVersion((value) => value + 1);
    if (next === 'files') {
      setSpatial(folder === ROOT);
      setGrid(false);
      setFilters(initialFilters);
      setSearch('');
    }
    setView(next);
    setParent(folder);
    setSelected(null);
    setOffset(0);
    setLoading(true);
    setNotice('');
    setError('');
  }
  function open(item: Item) {
    if (item.kind === 'folder') navigate('files', item.id);
    else setPreview(item);
  }
  function begin(next: Action) {
    setActionError('');
    setAction(next);
  }
  async function save(path: string, method: string, body: unknown) {
    setBusy(true);
    setActionError('');
    try {
      const result = await api<{ state?: string }>(path, method, body, session);
      setNotice(
        result?.state === 'pending'
          ? 'Deletion is pending. Storage remains counted until cleanup succeeds. You can retry the approved deletion in Administration.'
          : 'Changes saved.',
      );
      setAction(null);
      setSelected(null);
      refresh();
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 401) onExpired();
      else
        setActionError(
          failure instanceof Error ? failure.message : 'Unable to save.',
        );
    } finally {
      setBusy(false);
    }
  }
  function ask(file: File, target?: Item): Promise<string> {
    setReplaceConfirmed(false);
    return new Promise((resolve) => {
      const value = { file, target, resolve };
      collisionRef.current = value;
      setCollision(value);
    });
  }
  function decide(choice: string) {
    collision?.resolve(choice);
    collisionRef.current = null;
    setCollision(null);
  }
  async function uploads(list: FileList | File[]) {
    if (busy || progress) return;
    const files = Array.from(list);
    if (!files.length) return;
    if (files.length > 50) {
      setError('Choose up to 50 files at once.');
      return;
    }
    const invalid = files.map(validateFile).find(Boolean);
    if (invalid) {
      setError(invalid);
      return;
    }
    const destination = parent;
    setBusy(true);
    setError('');
    setNotice('');
    controller.current = new AbortController();
    let completed = 0;
    try {
      for (const [index, file] of files.entries()) {
        if (controller.current.signal.aborted) break;
        setProgress({
          name: file.name,
          percent: 0,
          index: index + 1,
          total: files.length,
        });
        const collisionPath = `/collisions?parent_id=${destination}&name=${encodeURIComponent(file.name.normalize('NFC'))}`;
        let target = (await api<Item | null>(collisionPath)) ?? undefined;
        let choice = target ? await ask(file, target) : 'error';
        if (choice === 'cancel') continue;
        const send = () =>
          transfer(
            file,
            {
              parent_id: destination,
              collision: choice,
              ...(choice === 'replace' && target
                ? {
                    target_id: target.id,
                    expected_revision: target.revision,
                    confirm_replace: true,
                  }
                : {}),
            },
            session,
            (percent) =>
              setProgress({
                name: file.name,
                percent,
                index: index + 1,
                total: files.length,
              }),
            controller.current!.signal,
          );
        let item: Item;
        try {
          item = await send();
        } catch (failure) {
          if (!(
            failure instanceof ApiError &&
            failure.status === 409 &&
            choice === 'error'
          ))
            throw failure;
          target = (await api<Item | null>(collisionPath)) ?? undefined;
          choice = await ask(file, target);
          if (choice === 'cancel') continue;
          item = await send();
        }
        completed++;
        if (uploadIcon) {
          try {
            await putIcon(uploadIcon, item, session);
          } catch (failure) {
            throw new Error(
              `File uploaded, but its icon was not saved. ${failure instanceof Error ? failure.message : 'Please retry the icon in details.'}`,
              { cause: failure },
            );
          }
        }
      }
      setNotice(
        `${completed} ${completed === 1 ? 'file' : 'files'} uploaded.${completed < list.length ? ' Some skipped.' : ''}`,
      );
    } catch (failure) {
      failed(failure);
    } finally {
      setBusy(false);
      setProgress(null);
      controller.current = null;
      setLoading(true);
      setVersion((value) => value + 1);
    }
  }
  async function changeIcon(file: File) {
    if (!selected) return;
    setBusy(true);
    setError('');
    try {
      setSelected(await putIcon(file, selected, session));
      setLoading(true);
      setVersion((value) => value + 1);
      setNotice('Custom icon saved.');
    } catch (failure) {
      failed(failure);
    } finally {
      setBusy(false);
    }
  }
  async function theme() {
    const next = session.user.theme === 'light' ? 'dark' : 'light';
    setBusy(true);
    try {
      await api('/users/me/preferences', 'PATCH', { theme: next }, session);
      onTheme(next);
    } catch (failure) {
      failed(failure);
    } finally {
      setBusy(false);
    }
  }
  const label =
    view === 'files'
      ? crumbs.at(-1)?.name === '/'
        ? 'All files'
        : (crumbs.at(-1)?.name ?? 'Your files')
      : view === 'trash'
        ? 'Recycle Bin'
        : view === 'admin'
          ? 'Administration'
          : 'Activity history';
  const nameOf = (id: string | null) =>
    people.find((person) => person.id === id)?.email ?? 'Your circle';
  function filter(key: keyof typeof filters, value: string) {
    setLoading(true);
    setFilters({ ...filters, [key]: value });
    setOffset(0);
  }
  const searchForm = (
    <form
      className="search-tools"
      onSubmit={(event) => {
        event.preventDefault();
        filter('q', search);
        if (canvas) setSidebar(false);
      }}
    >
      <label className="visually-hidden" htmlFor="file-search">
        Search by name
      </label>
      <div className="search-line">
        <input
          id="file-search"
          type="search"
          maxLength={255}
          placeholder={
            view === 'files'
              ? 'Find something in your space…'
              : 'Search activity by item name…'
          }
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
        <button className="secondary">Search</button>
        {view === 'files' && wide && filters.scope === 'folder' && (
          <button
            type="button"
            className="secondary spatial-toggle"
            aria-pressed={canvas}
            onClick={() => {
              setSpatial(!spatial);
              if (canvas) setGrid(false);
              setOffset(0);
              setSelected(null);
            }}
          >
            {canvas ? 'List view' : 'Spatial view'}
          </button>
        )}
        {view === 'files' && (
          <button
            type="button"
            className="secondary"
            onClick={() => {
              setSpatial(false);
              setGrid(!grid);
              setOffset(0);
            }}
            aria-label={grid ? 'Switch to list view' : 'Switch to grid view'}
          >
            {grid ? '☰' : '▦'}
          </button>
        )}
      </div>
      <details className="filter-panel">
        <summary>Filters & sorting</summary>
        <div className="filter-fields">
          {view === 'files' ? (
            <>
              <label>
                Type
                <select
                  value={filters.category}
                  onChange={(event) => filter('category', event.target.value)}
                >
                  {[
                    'all',
                    'folder',
                    'image',
                    'pdf',
                    'video',
                    'document',
                    'archive',
                    'other',
                  ].map((value) => (
                    <option key={value} value={value}>
                      {value === 'all'
                        ? 'All types'
                        : value[0].toUpperCase() + value.slice(1)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Search scope
                <select
                  value={filters.scope}
                  onChange={(event) => filter('scope', event.target.value)}
                >
                  <option value="folder">This folder</option>
                  <option value="all">All folders</option>
                </select>
              </label>
            </>
          ) : (
            <label>
              Action
              <select
                value={eventAction}
                onChange={(event) => {
                  setEventAction(event.target.value);
                  setOffset(0);
                  setLoading(true);
                }}
              >
                <option value="">All actions</option>
                {[
                  'upload',
                  'download',
                  'rename',
                  'move',
                  'folder_create',
                  'replace',
                  'trash',
                  'restore',
                  'permanent_delete',
                  'icon_update',
                  ...(view === 'admin'
                    ? [
                        'login',
                        'logout',
                        'invitation_create',
                        'user_deactivate',
                      ]
                    : []),
                ].map((value) => (
                  <option key={value}>{value}</option>
                ))}
              </select>
            </label>
          )}
          <label>
            {view === 'files' ? 'Uploaded by' : 'Actor'}
            <select
              value={filters.uploader}
              onChange={(event) => filter('uploader', event.target.value)}
            >
              <option value="">Everyone</option>
              {people.map((person) => (
                <option key={person.id} value={person.id}>
                  {person.email}
                </option>
              ))}
            </select>
          </label>
          <label>
            From (UTC)
            <input
              type="date"
              value={filters.after}
              onChange={(event) => filter('after', event.target.value)}
            />
          </label>
          <label>
            Through (UTC)
            <input
              type="date"
              value={filters.before}
              onChange={(event) => filter('before', event.target.value)}
            />
          </label>
          {view === 'files' && (
            <>
              <label>
                Sort by
                <select
                  value={filters.sort}
                  onChange={(event) => filter('sort', event.target.value)}
                >
                  <option value="name">Name</option>
                  <option value="size">Size</option>
                  <option value="date">Upload date</option>
                </select>
              </label>
              <label>
                Order
                <select
                  value={filters.direction}
                  onChange={(event) => filter('direction', event.target.value)}
                >
                  <option value="asc">Ascending</option>
                  <option value="desc">Descending</option>
                </select>
              </label>
            </>
          )}
          <button
            type="button"
            className="secondary"
            onClick={() => {
              setFilters(initialFilters);
              setSearch('');
              setEventAction('');
              setOffset(0);
              setVersion((value) => value + 1);
              setLoading(true);
            }}
          >
            Reset filters
          </button>
        </div>
      </details>
    </form>
  );
  const hasNext =
    (view === 'activity' || view === 'admin' ? events : items).length === PAGE;
  return (
    <div
      className={`file-workspace immersive-workspace ${canvas ? 'canvas-mode' : ''}`}
      onKeyDown={(event) => {
        if (
          event.key === 'Escape' &&
          selected &&
          !(event.target as HTMLElement).closest('dialog')
        ) {
          event.stopPropagation();
          closeDetails();
        }
      }}
    >
      <button
        className="secondary menu-launch"
        aria-label="Open menu"
        aria-describedby={
          storage?.warning_percent ? 'storage-alert' : undefined
        }
        aria-haspopup="dialog"
        onClick={() => setSidebar(true)}
      >
        ☰
        {storage?.warning_percent && (
          <span className="menu-warning" aria-hidden="true" />
        )}
      </button>
      {storage?.warning_percent && (
        <span className="visually-hidden" id="storage-alert" role="status">
          Storage is at least {storage.warning_percent}% full. Open the menu for
          details.
        </span>
      )}
      {canvas && parent !== ROOT && (
        <button
          className="secondary folder-up"
          aria-label="Go to parent folder"
          onClick={() => navigate('files', crumbs.at(-2)?.id ?? ROOT)}
        >
          ←
        </button>
      )}
      {sidebar && (
        <NavigationDrawer onClose={() => setSidebar(false)}>
          <aside className="file-sidebar" aria-label="Cloud sidebar">
            <div className="sidebar-heading">
              <span className="eyebrow">Shared space</span>
              <button
                className="secondary icon-button"
                onClick={() => setSidebar(!sidebar)}
                aria-label="Close menu"
                aria-expanded={sidebar}
              >
                {sidebar ? '‹' : '›'}
              </button>
            </div>
            <div className="sidebar-content">
              <p className="menu-location">{label}</p>
              {canvas && <div className="menu-search" ref={setSearchTarget} />}
              <button
                className="secondary menu-refresh"
                disabled={busy}
                onClick={() => {
                  refresh();
                  setSidebar(false);
                }}
              >
                Refresh files
              </button>
              <nav aria-label="Main navigation">
                {(
                  [
                    'files',
                    'activity',
                    'trash',
                    ...(session.user.role === 'admin' ? ['admin'] : []),
                  ] as View[]
                ).map((next) => (
                  <button
                    key={next}
                    className={`nav-button ${view === next ? 'current' : ''}`}
                    aria-current={view === next ? 'page' : undefined}
                    onClick={() => {
                      navigate(next, next === 'files' ? ROOT : parent);
                      setSidebar(false);
                    }}
                  >
                    {next === 'files'
                      ? '▱  All files'
                      : next === 'activity'
                        ? '◷  Activity'
                        : next === 'trash'
                          ? '♧  Recycle Bin'
                          : '◇  Administration'}
                  </button>
                ))}
              </nav>
              <div className="sidebar-create">
                <button
                  disabled={busy || view !== 'files'}
                  onClick={() => {
                    uploadInput.current?.click();
                    setSidebar(false);
                  }}
                >
                  ＋ Upload files
                </button>
                <button
                  className="secondary"
                  disabled={busy || view !== 'files'}
                  onClick={() => {
                    begin({ kind: 'folder' });
                    setSidebar(false);
                  }}
                >
                  New folder
                </button>
                <details className="upload-options">
                  <summary>Optional upload icon</summary>
                  <label htmlFor="upload-icon">
                    PNG, JPEG or WebP · up to 2 MB
                  </label>
                  <input
                    ref={uploadIconInput}
                    id="upload-icon"
                    type="file"
                    accept="image/png,image/jpeg,image/webp"
                    disabled={busy}
                    onChange={(event) => {
                      setUploadIcon(event.target.files?.[0] ?? null);
                    }}
                  />
                  {uploadIcon && (
                    <>
                      <small>
                        {uploadIcon.name} will apply to these uploads.
                      </small>
                      <button
                        className="secondary"
                        disabled={busy}
                        onClick={() => {
                          setUploadIcon(null);
                          if (uploadIconInput.current)
                            uploadIconInput.current.value = '';
                        }}
                      >
                        Clear icon
                      </button>
                    </>
                  )}
                </details>
              </div>
              {storage && (
                <section className="storage-card" aria-label="Shared storage">
                  <span>Shared storage</span>
                  <strong>
                    {bytes(storage.used_bytes)}{' '}
                    <small>of {bytes(storage.pool_bytes)}</small>
                  </strong>
                  <progress
                    value={storage.used_bytes + storage.reserved_bytes}
                    max={storage.pool_bytes}
                    aria-label="Storage used and reserved"
                  />
                  <small>
                    {bytes(storage.available_bytes)} available ·{' '}
                    {bytes(storage.reserved_bytes)} reserved
                  </small>
                  <small>
                    Includes Recycle Bin, recovery copies and icons.
                  </small>
                  {storage.warning_percent && (
                    <p role="status" className="storage-warning">
                      Storage is at least {storage.warning_percent}% full.
                    </p>
                  )}
                </section>
              )}
              <div className="account-card">
                <span className="eyebrow">Your account</span>
                <p>{session.user.email}</p>
                <button
                  className="secondary"
                  disabled={busy}
                  onClick={() => void theme()}
                >
                  {session.user.theme === 'light'
                    ? '☾ Dark mode'
                    : '☀ Light mode'}
                </button>
                <button className="secondary" onClick={onSignOut}>
                  Sign out
                </button>
              </div>
            </div>
          </aside>
        </NavigationDrawer>
      )}
      <section
        className="file-main"
        aria-labelledby="files-title"
        onDragOver={(event) => {
          if (view === 'files' && event.dataTransfer.types.includes('Files'))
            event.preventDefault();
        }}
        onDrop={(event) => {
          if (view === 'files') {
            event.preventDefault();
            void uploads(event.dataTransfer.files);
          }
        }}
      >
        <input
          ref={uploadInput}
          className="visually-hidden"
          tabIndex={-1}
          type="file"
          multiple
          aria-label="Choose files to upload"
          onChange={(event) => {
            if (event.target.files) void uploads(event.target.files);
            event.target.value = '';
          }}
        />
        <div
          className={`file-heading ${view === 'trash' ? 'trash-heading' : ''}`}
        >
          <div>
            <p className="eyebrow">
              {view === 'files' ? 'Room for what matters' : 'Your shared cloud'}
            </p>
            <h1 id="files-title">{label}</h1>
          </div>
          {view === 'trash' && (
            <button
              className="secondary"
              onClick={() => navigate('files', ROOT)}
              aria-label="Back to dashboard"
            >
              ← Dashboard
            </button>
          )}
          <button className="secondary" onClick={refresh} disabled={busy}>
            ↻ Refresh
          </button>
        </div>
        {view === 'files' && (
          <nav className="breadcrumbs" aria-label="Folder path">
            {crumbs.map((folder) => (
              <button
                className="crumb"
                key={folder.id}
                onClick={() => navigate('files', folder.id)}
              >
                {folder.id === ROOT ? 'All files' : folder.name}
              </button>
            ))}
          </nav>
        )}
        {view !== 'trash' &&
          (canvas
            ? sidebar && searchTarget
              ? createPortal(searchForm, searchTarget)
              : null
            : searchForm)}
        {error && (
          <p role="alert" className="error">
            {error}{' '}
            <button className="secondary" onClick={refresh}>
              Try again
            </button>
          </p>
        )}
        {notice && (
          <p role="status" className="success">
            {notice}
          </p>
        )}
        {progress && (
          <section className="upload-progress" aria-label="Upload progress">
            <strong>
              {progress.index} of {progress.total} · {progress.name}
            </strong>
            <progress
              value={progress.percent}
              max={100}
              aria-label={`Uploading ${progress.name}`}
            />
            <span>
              {progress.percent === 100
                ? 'Saved'
                : progress.percent >= 99
                  ? 'Finishing safely…'
                  : `${progress.percent}%`}
            </span>
            <button
              className="secondary"
              onClick={() => {
                controller.current?.abort();
                collisionRef.current?.resolve('cancel');
                collisionRef.current = null;
                setCollision(null);
              }}
            >
              Cancel upload
            </button>
          </section>
        )}
        {view === 'admin' && (
          <>
            <section className="admin-storage card">
              <h2>Storage overview</h2>
              {storage && (
                <div className="storage-metrics">
                  <p>
                    <strong>{bytes(storage.used_bytes)}</strong>Stored bytes
                  </p>
                  <p>
                    <strong>{bytes(storage.reserved_bytes)}</strong>Active
                    reservations
                  </p>
                  <p>
                    <strong>{bytes(storage.available_bytes)}</strong>Available
                    safely
                  </p>
                </div>
              )}
              <p>
                Trash and retained replacement copies count toward storage.
                Permanent deletion requires confirmation in Recycle Bin.
              </p>
              <button className="secondary" onClick={() => navigate('trash')}>
                Manage Recycle Bin
              </button>
            </section>
            <DeletionQueue
              session={session}
              version={version}
              onExpired={onExpired}
            />
            <Administration session={session} onExpired={onExpired} />
            <h2>Activity monitor</h2>
          </>
        )}
        {loading ? (
          <p role="status" className="loading-state">
            Opening your space…
          </p>
        ) : view === 'activity' || view === 'admin' ? (
          <>
            <ul className="activity-list">
              {events.map((entry) => (
                <li key={entry.id}>
                  <span className="activity-dot" aria-hidden="true">
                    ◦
                  </span>
                  <div>
                    <strong>{entry.action.replaceAll('_', ' ')}</strong>
                    <p>{entry.target_name}</p>
                    <small>
                      {nameOf(entry.actor_id)} ·{' '}
                      {new Date(entry.occurred_at).toLocaleString()}
                    </small>
                  </div>
                </li>
              ))}
            </ul>
            {!events.length && (
              <p className="empty-small">No matching activity.</p>
            )}
            <small>
              Download history reflects server streaming, not confirmed device
              receipt.
            </small>
          </>
        ) : (
          <div
            className={`browser-content ${selected && !detailsPending ? 'has-details' : ''} ${canvas ? 'spatial-layout' : ''}`}
          >
            <div>
              <div className="items-summary">
                <span>
                  {view === 'trash'
                    ? 'Shared Recycle Bin · nothing is automatically deleted'
                    : filters.scope === 'all'
                      ? 'Results across all folders'
                      : 'Shared with your circle'}
                </span>
                <span>
                  {items.length} items{' '}
                  {canvas ? 'in this space' : 'on this page'}
                </span>
              </div>
              {canvas ? (
                <SpatialCanvas
                  key={parent}
                  items={items}
                  parent={parent}
                  session={session}
                  selected={selected?.id}
                  onSelect={selectSpatial}
                  onOpen={open}
                  onUpload={() => uploadInput.current?.click()}
                  onExpired={onExpired}
                  onShowTrash={() => navigate('trash')}
                  onTrash={async (item) => {
                    if (busy || progress)
                      throw new Error(
                        'Another file action is still running. Try again when it finishes.',
                      );
                    setBusy(true);
                    try {
                      await api(
                        `/items/${item.id}/trash`,
                        'POST',
                        { expected_revision: item.revision },
                        session,
                      );
                      closeDetails();
                      refresh();
                    } catch (failure) {
                      if (failure instanceof ApiError && failure.status === 401)
                        onExpired();
                      throw failure;
                    } finally {
                      setBusy(false);
                    }
                  }}
                />
              ) : (
                <>
                  <ul
                    className={`file-list ${grid ? 'file-grid' : ''}`}
                    aria-label={
                      view === 'trash' ? 'Deleted items' : 'Files and folders'
                    }
                  >
                    {items.map((item) => (
                      <li
                        key={item.id}
                        className={selected?.id === item.id ? 'selected' : ''}
                      >
                        <button
                          className="file-select"
                          aria-label={`Select ${item.name}`}
                          aria-pressed={selected?.id === item.id}
                          onClick={() => setSelected(item)}
                          onDoubleClick={() => {
                            if (view !== 'trash') open(item);
                          }}
                        >
                          <FileIcon item={item} />
                          <span className="file-label">
                            <strong>{item.name}</strong>
                            <small>
                              {item.replacement_of ? 'Recovery copy · ' : ''}
                              {bytes(item.size_bytes)}
                            </small>
                          </span>
                          <span className="file-date">
                            {new Date(item.created_at).toLocaleDateString()}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                  {!items.length && (
                    <div className="empty-files">
                      <span className="empty-symbol" aria-hidden="true">
                        ◇
                      </span>
                      <h2>
                        {view === 'trash'
                          ? 'Nothing in the Recycle Bin'
                          : filters.q ||
                              filters.category !== 'all' ||
                              filters.uploader ||
                              filters.after ||
                              filters.before
                            ? 'No matching files'
                            : 'A little room for everything.'}
                      </h2>
                      <p>
                        {view === 'trash'
                          ? 'Items moved here can be restored by your circle.'
                          : 'Upload a file or drop it here. Your circle shares this space.'}
                      </p>
                      {view === 'files' && (
                        <button
                          disabled={busy}
                          onClick={() => uploadInput.current?.click()}
                        >
                          Upload your first file
                        </button>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>
            {selected && (!canvas || !detailsPending) && (
              <aside
                ref={detailsPanel}
                className="details-panel"
                aria-label="Item details"
                onKeyDown={(event) => {
                  if (event.key === 'Escape') {
                    event.stopPropagation();
                    closeDetails();
                  }
                }}
              >
                <div className="details-top">
                  <FileIcon item={selected} />
                  <button
                    className="secondary icon-button"
                    aria-label="Close details"
                    onClick={closeDetails}
                  >
                    ×
                  </button>
                </div>
                <h2>{selected.name}</h2>
                {selected.replacement_of && (
                  <p className="badge">Replacement recovery copy</p>
                )}
                <dl>
                  <dt>Type</dt>
                  <dd>
                    {selected.kind === 'folder'
                      ? 'Folder'
                      : selected.name.split('.').pop()?.toUpperCase() + ' file'}
                  </dd>
                  <dt>Size</dt>
                  <dd>{bytes(selected.size_bytes)}</dd>
                  <dt>Uploaded by</dt>
                  <dd>{nameOf(selected.uploader_id)}</dd>
                  <dt>Added</dt>
                  <dd>{new Date(selected.created_at).toLocaleString()}</dd>
                  <dt>Updated</dt>
                  <dd>{new Date(selected.updated_at).toLocaleString()}</dd>
                </dl>
                {view === 'trash' ? (
                  <div className="detail-actions">
                    <button
                      disabled={busy}
                      onClick={() => begin({ kind: 'restore', item: selected })}
                    >
                      Restore
                    </button>
                    {session.user.role === 'admin' && (
                      <button
                        className="secondary danger"
                        disabled={busy}
                        onClick={() =>
                          begin({ kind: 'delete', item: selected })
                        }
                      >
                        Delete permanently
                      </button>
                    )}
                  </div>
                ) : (
                  <>
                    <div className="detail-actions">
                      <button disabled={busy} onClick={() => open(selected)}>
                        Open
                      </button>
                      {selected.kind === 'file' && (
                        <a
                          className="button-link secondary"
                          href={`/api/items/${selected.id}/download`}
                        >
                          Download
                        </a>
                      )}
                      <button
                        className="secondary"
                        disabled={busy}
                        onClick={() =>
                          begin({ kind: 'rename', item: selected })
                        }
                      >
                        Rename
                      </button>
                      <button
                        className="secondary"
                        disabled={busy}
                        onClick={() => begin({ kind: 'move', item: selected })}
                      >
                        Move
                      </button>
                      <button
                        className="secondary danger"
                        disabled={busy}
                        onClick={() => begin({ kind: 'trash', item: selected })}
                      >
                        Move to Recycle Bin
                      </button>
                    </div>
                    {selected.kind === 'file' && (
                      <div className="custom-icon">
                        <label htmlFor="item-icon">Custom icon</label>
                        <small>PNG, JPEG or WebP · up to 2 MB</small>
                        <input
                          id="item-icon"
                          type="file"
                          accept="image/png,image/jpeg,image/webp"
                          disabled={busy}
                          onChange={(event) => {
                            const file = event.target.files?.[0];
                            if (file) void changeIcon(file);
                            event.target.value = '';
                          }}
                        />
                        {selected.has_icon && (
                          <button
                            className="secondary"
                            disabled={busy}
                            onClick={() =>
                              void save(
                                `/items/${selected.id}/icon`,
                                'DELETE',
                                { expected_revision: selected.revision },
                              )
                            }
                          >
                            Remove icon
                          </button>
                        )}
                      </div>
                    )}
                  </>
                )}
              </aside>
            )}
          </div>
        )}
        {!loading && !canvas && (
          <div className="pager">
            <button
              className="secondary"
              disabled={offset === 0 || busy}
              onClick={() => {
                setOffset(Math.max(0, offset - PAGE));
                setSelected(null);
                setLoading(true);
              }}
            >
              Previous
            </button>
            <span>Page {Math.floor(offset / PAGE) + 1}</span>
            <button
              className="secondary"
              disabled={!hasNext || busy || offset + PAGE > 100000}
              onClick={() => {
                setOffset(offset + PAGE);
                setSelected(null);
                setLoading(true);
              }}
            >
              Next
            </button>
          </div>
        )}
      </section>
      {action && (
        <ItemAction
          key={`${action.kind}-${action.item?.id ?? 'new'}`}
          action={action}
          parent={parent}
          onClose={() => setAction(null)}
          onSave={save}
          busy={busy}
          error={actionError}
        />
      )}
      {preview && (
        <Preview
          key={preview.id}
          item={preview}
          onClose={() => setPreview(null)}
          onExpired={onExpired}
        />
      )}
      {collision && (
        <Dialog title="A name already exists" onClose={() => decide('cancel')}>
          <p>
            <strong>{collision.file.name}</strong> already exists in this
            folder.
          </p>
          <p>
            Keep both saves a separate copy. Replace retains the previous file
            in Recycle Bin for recovery.
          </p>
          {collision.target?.kind === 'file' && (
            <label className="check">
              <input
                type="checkbox"
                checked={replaceConfirmed}
                onChange={(event) => setReplaceConfirmed(event.target.checked)}
              />
              I confirm replacing the current file.
            </label>
          )}
          <div className="dialog-actions">
            <button className="secondary" onClick={() => decide('cancel')}>
              Cancel this file
            </button>
            <button className="secondary" onClick={() => decide('keep_both')}>
              Keep Both
            </button>
            {collision.target?.kind === 'file' && (
              <button
                disabled={!replaceConfirmed}
                onClick={() => decide('replace')}
              >
                Replace
              </button>
            )}
          </div>
        </Dialog>
      )}
    </div>
  );
}
