import { ApiError, cookieValue, type Session } from './identity.ts';

export const ROOT = '00000000-0000-0000-0000-000000000001';
export const FILE_LIMIT = 500_000_000;
export type Item = {
  id: string;
  parent_id: string | null;
  kind: 'file' | 'folder';
  name: string;
  revision: number;
  uploader_id: string | null;
  size_bytes: number | null;
  checksum_sha256: string | null;
  created_at: string;
  updated_at: string;
  trashed_at: string | null;
  replacement_of: string | null;
  has_icon: boolean;
};
export type Person = { id: string; email: string };
export type Storage = {
  used_bytes: number;
  reserved_bytes: number;
  pool_bytes: number;
  available_bytes: number;
  warning_percent: 80 | 90 | null;
};
export type Event = {
  id: string;
  actor_id: string;
  action: string;
  target_name: string;
  occurred_at: string;
  details: Record<string, string | number>;
};
export function bytes(value: number | null): string {
  if (value === null) return 'Folder';
  if (value < 1000) return `${value} B`;
  if (value < 1_000_000) return `${(value / 1000).toFixed(1)} KB`;
  if (value < 1_000_000_000) return `${(value / 1_000_000).toFixed(1)} MB`;
  return `${(value / 1_000_000_000).toFixed(1)} GB`;
}
export function symbol(item: Pick<Item, 'kind' | 'name'>): string {
  if (item.kind === 'folder') return '▱';
  const extension = item.name.split('.').pop()?.toLowerCase() ?? '';
  if (['png', 'jpg', 'jpeg', 'webp', 'gif'].includes(extension)) return '▧';
  if (['mp4', 'webm', 'mov'].includes(extension)) return '▷';
  if (extension === 'pdf') return 'PDF';
  if (['zip', 'tar', 'gz', '7z'].includes(extension)) return 'ZIP';
  return '≡';
}
export function validateFile(file: Pick<File, 'name' | 'size'>): string | null {
  if (file.size > FILE_LIMIT) return 'Each file must be 500 MB or smaller.';
  const name = file.name.normalize('NFC');
  if (
    !name ||
    name.trim() !== name ||
    name.endsWith('.') ||
    ['.', '..'].includes(name) ||
    /[/\\:\p{C}]/u.test(name) ||
    new TextEncoder().encode(name).length > 255
  )
    return 'Use a name of 1–255 UTF-8 bytes without path or control characters.';
  return null;
}
export function transfer(
  file: File,
  metadata: Record<string, unknown>,
  session: Session,
  progress: (value: number) => void,
  signal: AbortSignal,
): Promise<Item> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(new ApiError(0, 'Upload canceled.'));
      return;
    }
    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/uploads');
    xhr.timeout = 30 * 60 * 1000;
    const csrf = cookieValue(document.cookie, session.csrf_cookie);
    if (csrf) xhr.setRequestHeader('X-CSRF-Token', csrf);
    const stop = () => xhr.abort();
    signal.addEventListener('abort', stop, { once: true });
    xhr.onloadend = () => signal.removeEventListener('abort', stop);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable)
        progress(Math.min(99, Math.round((event.loaded * 100) / event.total)));
    };
    xhr.onerror = () =>
      reject(
        new ApiError(
          0,
          'Connection lost. Refresh to check whether your upload finished before retrying.',
        ),
      );
    xhr.ontimeout = () =>
      reject(new ApiError(0, 'Upload timed out. Refresh to check its status.'));
    xhr.onabort = () =>
      reject(
        new ApiError(0, 'Upload canceled. Refresh to confirm its status.'),
      );
    xhr.onload = () => {
      let value;
      try {
        value = JSON.parse(xhr.responseText);
      } catch {
        reject(
          new ApiError(
            xhr.status,
            'Unexpected response. Refresh to check upload status.',
          ),
        );
        return;
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        progress(100);
        resolve(value as Item);
      } else
        reject(
          new ApiError(
            xhr.status,
            value?.error?.message ?? 'Upload failed. Please try again.',
          ),
        );
    };
    const body = new FormData();
    body.append(
      'metadata',
      JSON.stringify({
        ...metadata,
        name: file.name.normalize('NFC'),
        size_bytes: file.size,
      }),
    );
    body.append('file', file, 'upload');
    xhr.send(body);
  });
}
export async function putIcon(
  file: File,
  item: Item,
  session: Session,
): Promise<Item> {
  if (file.size > 2_000_000)
    throw new ApiError(413, 'Custom icons must be at most 2 MB.');
  const response = await fetch(
    `/api/items/${item.id}/icon?expected_revision=${item.revision}`,
    {
      method: 'PUT',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/octet-stream',
        'X-CSRF-Token': cookieValue(document.cookie, session.csrf_cookie) ?? '',
      },
      body: file,
      signal: AbortSignal.timeout(60000),
    },
  );
  const value = await response.json();
  if (!response.ok)
    throw new ApiError(
      response.status,
      value?.error?.message ?? 'Unable to save icon.',
    );
  return value as Item;
}
