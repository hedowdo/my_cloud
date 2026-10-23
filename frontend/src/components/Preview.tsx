import { useEffect, useRef, useState } from 'react';
import { type Item } from '../api/files';
import { ApiError } from '../api/identity';
import { Dialog } from './Dialog';

function PdfPage({ item }: { item: Item }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [page, setPage] = useState(1);
  const [count, setCount] = useState(0);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    let cleanup = () => {};
    const timeout = window.setTimeout(() => {
      if (!active) return;
      active = false;
      controller.abort();
      cleanup();
      setError(
        'This PDF took too long to preview. Download the original to open it.',
      );
      setLoading(false);
    }, 30000);
    async function render() {
      const pdfjs = await import('pdfjs-dist');
      const worker = await import('pdfjs-dist/build/pdf.worker.min.mjs?url');
      pdfjs.GlobalWorkerOptions.workerSrc = worker.default;
      const response = await fetch(`/api/items/${item.id}/preview`, {
        signal: controller.signal,
        credentials: 'same-origin',
      });
      if (!response.ok)
        throw new Error(
          'Unable to preview PDF. Download the original to open it.',
        );
      const data = new Uint8Array(await response.arrayBuffer());
      if (!active) return;
      const task = pdfjs.getDocument({
        data,
        useWasm: false,
        disableFontFace: true,
        useSystemFonts: true,
        canvasMaxAreaInBytes: 16_000_000,
        maxImageSize: 16_000_000,
        stopAtErrors: true,
      });
      cleanup = () => {
        void task.destroy();
      };
      const document = await task.promise;
      if (!active) return;
      setCount(document.numPages);
      const pdfPage = await document.getPage(page);
      if (!active || !canvas.current) return;
      const original = pdfPage.getViewport({ scale: 1 });
      const viewport = pdfPage.getViewport({
        scale: Math.min(1.6, 1600 / Math.max(original.width, original.height)),
      });
      const target = canvas.current;
      target.width = viewport.width;
      target.height = viewport.height;
      await pdfPage.render({ canvas: target, viewport }).promise;
      if (active) {
        window.clearTimeout(timeout);
        setLoading(false);
      }
    }
    void render().catch((failure) => {
      if (active) {
        window.clearTimeout(timeout);
        setError(failure.message);
        setLoading(false);
      }
    });
    return () => {
      active = false;
      window.clearTimeout(timeout);
      controller.abort();
      cleanup();
    };
  }, [item.id, page]);
  return (
    <div className="pdf-preview">
      {loading && <p role="status">Preparing page…</p>}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <canvas
        ref={canvas}
        role="img"
        aria-label={`${item.name}, page ${page}`}
      />
      <div className="pager">
        <button
          className="secondary"
          disabled={page === 1 || loading}
          onClick={() => {
            setLoading(true);
            setPage(page - 1);
          }}
        >
          Previous page
        </button>
        <span>
          Page {page}
          {count > 0 && ` of ${count}`}
        </span>
        <button
          className="secondary"
          disabled={page >= count || loading}
          onClick={() => {
            setLoading(true);
            setPage(page + 1);
          }}
        >
          Next page
        </button>
      </div>
      <small>
        Visual preview. Download the original for accessible document reading.
      </small>
    </div>
  );
}

export function Preview({
  item,
  onClose,
  onExpired,
}: {
  item: Item;
  onClose: () => void;
  onExpired: () => void;
}) {
  const [kind, setKind] = useState('loading');
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    // A small range preflight still performs independent authorization/signature checks.
    fetch(`/api/items/${item.id}/preview`, {
      headers: { Range: 'bytes=0-0' },
      signal: controller.signal,
      credentials: 'same-origin',
    })
      .then(async (response) => {
        if (!response.ok) {
          const value = await response.json().catch(() => null);
          throw new ApiError(
            response.status,
            value?.error?.message ??
              'Preview unavailable. Download the original.',
          );
        }
        const type = response.headers.get('Content-Type') ?? '';
        await response.body?.cancel();
        if (active)
          setKind(
            type.startsWith('image/')
              ? 'image'
              : type === 'application/pdf'
                ? 'pdf'
                : 'video',
          );
      })
      .catch((failure) => {
        if (active) {
          if (failure instanceof ApiError && failure.status === 401)
            onExpired();
          setError(failure.message);
          setKind('unsupported');
        }
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [item.id, onExpired]);
  const url = `/api/items/${item.id}/preview`;
  return (
    <Dialog title={item.name} onClose={onClose} wide>
      {kind === 'loading' && <p role="status">Preparing preview…</p>}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {kind === 'image' && (
        <img
          className="image-preview"
          src={url}
          alt={item.name}
          onError={() =>
            setError('Image could not be opened. Download the original.')
          }
        />
      )}
      {kind === 'pdf' && <PdfPage item={item} />}
      {kind === 'video' && (
        <>
          <video
            className="video-preview"
            controls
            playsInline
            preload="metadata"
            src={url}
            onError={() =>
              setError(
                'Your browser cannot play this video. Download the original.',
              )
            }
          />
          <small>
            Video preview has no generated captions. Download to use your
            preferred player.
          </small>
        </>
      )}
      <div className="actions preview-actions">
        <a className="button-link" href={`/api/items/${item.id}/download`}>
          Download original
        </a>
        <button className="secondary" onClick={onClose}>
          Close preview
        </button>
      </div>
    </Dialog>
  );
}
