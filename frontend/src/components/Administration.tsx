import { useEffect, useState } from 'react';
import {
  api,
  ApiError,
  type Invitation,
  type Session,
  type User,
} from '../api/identity';
export function Administration({
  session,
  onExpired,
}: {
  session: Session;
  onExpired: () => void;
}) {
  const [users, setUsers] = useState<User[]>([]);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [link, setLink] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [pendingDeactivation, setPendingDeactivation] = useState<string | null>(
    null,
  );
  const [loadedAt, setLoadedAt] = useState(() => Date.now());
  async function load() {
    const [people, invites] = await Promise.all([
      api<User[]>('/admin/users'),
      api<Invitation[]>('/admin/invitations'),
    ]);
    setLoadedAt(Date.now());
    setUsers(people);
    setInvitations(invites);
  }
  function failed(failure: unknown) {
    if (failure instanceof ApiError && failure.status === 401) onExpired();
    else
      setError(failure instanceof Error ? failure.message : 'Request failed');
  }
  useEffect(() => {
    let active = true;
    Promise.all([
      api<User[]>('/admin/users'),
      api<Invitation[]>('/admin/invitations'),
    ])
      .then(([people, invites]) => {
        if (active) {
          setUsers(people);
          setInvitations(invites);
          setLoadedAt(Date.now());
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
  }, [onExpired]);
  async function change(path: string, method = 'POST', body?: unknown) {
    setBusy(true);
    setError('');
    try {
      const result = await api<{ token: string }>(path, method, body, session);
      if (path === '/admin/invitations' && result)
        setLink(`${window.location.origin}/#invite=${result.token}`);
      await load();
    } catch (failure) {
      failed(failure);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="administration" aria-labelledby="admin-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Administrator</p>
          <h2 id="admin-title">Your circle</h2>
        </div>
        <span>{users.length} of 5 accounts</span>
      </div>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <div className="admin-grid">
        <section className="card">
          <h3>People</h3>
          <p className="fine-print">
            Deactivated accounts retain their place in the five-account limit.
          </p>
          <ul className="rows">
            {users.map((user) => (
              <li key={user.id}>
                <div className="person">
                  <strong>{user.email}</strong>
                  <small>
                    {user.role === 'admin' ? 'Administrator' : 'Member'} ·{' '}
                    {user.active ? 'Active' : 'Deactivated'}
                    {user.id === session.user.id ? ' · You' : ''}
                  </small>
                </div>
                {user.id !== session.user.id && (
                  <div className="actions">
                    <button
                      className="secondary"
                      disabled={busy || !user.active}
                      onClick={() =>
                        void change(`/admin/users/${user.id}/revoke-sessions`)
                      }
                    >
                      Sign out sessions
                    </button>
                    <button
                      className="secondary danger"
                      disabled={busy || !user.active}
                      onClick={() => setPendingDeactivation(user.id)}
                    >
                      Deactivate
                    </button>
                  </div>
                )}
                {pendingDeactivation === user.id && (
                  <div className="confirmation" role="alert">
                    <p>
                      Deactivate {user.email}? They will be signed out and
                      cannot sign in.
                    </p>
                    <div className="actions">
                      <button
                        disabled={busy}
                        onClick={() => {
                          setPendingDeactivation(null);
                          void change(`/admin/users/${user.id}`, 'PATCH', {
                            active: false,
                          });
                        }}
                      >
                        Confirm deactivation
                      </button>
                      <button
                        className="secondary"
                        disabled={busy}
                        onClick={() => setPendingDeactivation(null)}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </section>
        <section className="card">
          <h3>Invitations</h3>
          <p>Single use. Expires after 24 hours.</p>
          <button
            disabled={busy || users.length >= 5 || Boolean(link)}
            onClick={() => void change('/admin/invitations')}
          >
            Create invitation
          </button>
          {link && (
            <div className="invitation-result">
              <label htmlFor="invitation-link">
                Private invitation link · shown once
              </label>
              <input
                id="invitation-link"
                value={link}
                readOnly
                onFocus={(event) => event.currentTarget.select()}
              />
              <p className="fine-print">
                Copy this link and share it privately with your guest.
              </p>
              <button className="secondary" onClick={() => setLink('')}>
                Done
              </button>
            </div>
          )}
          <ul className="rows">
            {invitations.map((invitation) => {
              const state = invitation.revoked_at
                ? 'Revoked'
                : invitation.redeemed_at
                  ? 'Used'
                  : new Date(invitation.expires_at).getTime() <= loadedAt
                    ? 'Expired'
                    : 'Available';
              return (
                <li key={invitation.id}>
                  <div>
                    <strong>{state}</strong>
                    <small>
                      Expires {new Date(invitation.expires_at).toLocaleString()}
                    </small>
                  </div>
                  {state === 'Available' && (
                    <button
                      className="secondary"
                      disabled={busy}
                      onClick={() =>
                        void change(
                          `/admin/invitations/${invitation.id}/revoke`,
                        )
                      }
                    >
                      Revoke
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
          {!invitations.length && (
            <p className="fine-print">No invitations yet.</p>
          )}
        </section>
      </div>
    </section>
  );
}
