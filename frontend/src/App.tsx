import { useCallback, useEffect, useState, type FormEvent } from 'react';
import {
  api,
  ApiError,
  invitationFromHash,
  type Session,
} from './api/identity';
import { FileManager } from './components/FileManager';
const initialInvitation = invitationFromHash(window.location.hash);
// Strip bearer material before rendering, outside React's StrictMode double mount.
if (window.location.hash.startsWith('#invite='))
  window.history.replaceState(null, '', window.location.pathname);
export function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [checking, setChecking] = useState(true);
  const [invite, setInvite] = useState(initialInvitation);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function refresh() {
    try {
      setSession(await api<Session>('/auth/me'));
      setError('');
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 401)
        setSession(null);
      else
        setError(
          failure instanceof Error ? failure.message : 'Unable to connect',
        );
    } finally {
      setChecking(false);
    }
  }
  useEffect(() => {
    let active = true;
    api<Session>('/auth/me')
      .then((value) => {
        if (active) {
          setSession(value);
          setChecking(false);
        }
      })
      .catch((failure) => {
        if (active) {
          if (!(failure instanceof ApiError && failure.status === 401))
            setError(failure.message);
          setChecking(false);
        }
      });
    const onFocus = () => {
      void refresh();
    };
    const onInvitation = () => {
      if (!window.location.hash.startsWith('#invite=')) return;
      setInvite(invitationFromHash(window.location.hash));
      setError('');
      window.history.replaceState(null, '', window.location.pathname);
    };
    window.addEventListener('focus', onFocus);
    window.addEventListener('hashchange', onInvitation);
    return () => {
      active = false;
      window.removeEventListener('focus', onFocus);
      window.removeEventListener('hashchange', onInvitation);
    };
  }, []);
  const expired = useCallback(() => {
    setSession(null);
    setError('Your session ended. Please sign in again.');
  }, []);
  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError('');
    const form = event.currentTarget;
    const fields = new FormData(form);
    try {
      await api(invite ? '/auth/invitations/redeem' : '/auth/login', 'POST', {
        email: fields.get('email'),
        password: fields.get('password'),
        ...(invite ? { token: invite } : {}),
      });
      form.reset();
      setInvite(null);
      await refresh();
    } catch (failure) {
      setError(
        failure instanceof Error ? failure.message : 'Unable to sign in',
      );
    } finally {
      setBusy(false);
    }
  }
  async function signOut() {
    setBusy(true);
    setError('');
    try {
      await api('/auth/logout', 'POST', {}, session ?? undefined);
      setSession(null);
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 401)
        setSession(null);
      else
        setError(
          failure instanceof Error ? failure.message : 'Unable to sign out',
        );
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    document.documentElement.dataset.theme = session?.user.theme ?? 'light';
  }, [session?.user.theme]);
  return (
    <main className={session ? 'shell app-shell' : 'shell'}>
      <header className="masthead">
        <a href="/" className="brand" aria-label="Personal Cloud home">
          <span className="brand-mark" aria-hidden="true">
            ◈
          </span>
          Personal Cloud
        </a>
        {session ? (
          <button
            className="secondary"
            disabled={busy}
            onClick={() => void signOut()}
          >
            Sign out
          </button>
        ) : (
          <span className="badge">Invitation only</span>
        )}
      </header>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {checking ? (
        <section className="welcome" role="status">
          Connecting to your cloud…
        </section>
      ) : session ? (
        <FileManager
          session={session}
          onExpired={expired}
          onSignOut={() => void signOut()}
          onTheme={(theme) =>
            setSession({ ...session, user: { ...session.user, theme } })
          }
        />
      ) : (
        <section className="entry" aria-labelledby="welcome-title">
          <div className="welcome">
            <p className="eyebrow">A little space, shared together</p>
            <h1 id="welcome-title">
              Your files.
              <br />A calmer place.
            </h1>
            <p className="intro">
              A private home for the things you share. Just your people. Just
              your space.
            </p>
          </div>
          <form
            className="card sign-in"
            onSubmit={(event) => void signIn(event)}
          >
            <h2>{invite ? 'You’re invited' : 'Welcome back'}</h2>
            <p>
              {invite
                ? 'Create your account to join this private cloud. Your invitation can be used once.'
                : 'Sign in to your private cloud.'}
            </p>
            <label htmlFor="email">Email address</label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              maxLength={254}
              required
              disabled={busy}
            />
            <label htmlFor="password">
              {invite ? 'Choose a password' : 'Password'}
            </label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete={invite ? 'new-password' : 'current-password'}
              minLength={invite ? 12 : 1}
              maxLength={128}
              required
              disabled={busy}
              aria-describedby={invite ? 'password-help' : undefined}
            />
            {invite && (
              <small id="password-help">
                Use 12–128 characters. A long, unique passphrase works well.
              </small>
            )}
            <button type="submit" disabled={busy}>
              {busy ? 'Please wait…' : invite ? 'Create account' : 'Sign in'}
            </button>
            {invite ? (
              <button
                type="button"
                className="secondary"
                disabled={busy}
                onClick={() => {
                  setInvite(null);
                  setError('');
                }}
              >
                I already have an account
              </button>
            ) : (
              <p className="fine-print">
                New here? Ask your administrator for an invitation.
              </p>
            )}
          </form>
        </section>
      )}
      <footer>Personal Cloud · A space for your circle.</footer>
    </main>
  );
}
