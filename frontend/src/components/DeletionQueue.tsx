import { useEffect, useState } from 'react';
import { api, ApiError, type Session } from '../api/identity';

type Job = {
  id: string;
  target_id: string;
  state: 'pending' | 'complete';
  item_count: number;
  created_at: string;
  last_error: string | null;
};
export function DeletionQueue({
  session,
  version,
  onExpired,
}: {
  session: Session;
  version: number;
  onExpired: () => void;
}) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let active = true;
    api<Job[]>(`/admin/deletions?limit=10&offset=${offset}`)
      .then((rows) => {
        if (active) {
          setJobs(rows);
          setError('');
        }
      })
      .catch((failure) => {
        if (active) {
          if (failure instanceof ApiError && failure.status === 401)
            onExpired();
          else setError(failure.message);
        }
      });
    return () => {
      active = false;
    };
  }, [offset, version, revision, onExpired]);
  async function retry(job: Job) {
    setBusy(true);
    setError('');
    try {
      const result = await api<Job>(
        `/admin/deletions/${job.id}/retry`,
        'POST',
        {},
        session,
      );
      setNotice(
        result.state === 'complete'
          ? 'Approved deletion completed.'
          : 'Storage is still unavailable. The approved deletion remains pending and counted; retry later.',
      );
      setRevision((value) => value + 1);
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 401) onExpired();
      else
        setError(
          failure instanceof Error
            ? failure.message
            : 'Unable to retry deletion.',
        );
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="card deletion-queue" aria-labelledby="deletion-title">
      <h2 id="deletion-title">Pending deletions</h2>
      <p className="fine-print">
        Only previously confirmed permanent deletions appear here. Their bytes
        remain counted until cleanup succeeds.
      </p>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      <ul className="rows">
        {jobs.map((job) => (
          <li key={job.id}>
            <div>
              <strong>
                {job.item_count} {job.item_count === 1 ? 'item' : 'items'}
              </strong>
              <small>
                Requested {new Date(job.created_at).toLocaleString()}
              </small>
              <small>
                Reference {job.id.slice(0, 8)} ·{' '}
                {job.last_error ? 'Storage unavailable' : 'Pending cleanup'}
              </small>
            </div>
            <button
              className="secondary"
              disabled={busy}
              onClick={() => void retry(job)}
            >
              Retry approved deletion
            </button>
          </li>
        ))}
      </ul>
      {!jobs.length && <p>No pending deletions.</p>}
      {(offset > 0 || jobs.length === 10) && (
        <div className="pager">
          <button
            className="secondary"
            disabled={busy || offset === 0}
            onClick={() => setOffset(Math.max(0, offset - 10))}
          >
            Earlier jobs
          </button>
          <button
            className="secondary"
            disabled={busy || jobs.length < 10}
            onClick={() => setOffset(offset + 10)}
          >
            More jobs
          </button>
        </div>
      )}
    </section>
  );
}
