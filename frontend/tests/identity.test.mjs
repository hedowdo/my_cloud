import assert from 'node:assert/strict';
import test from 'node:test';
import {
  api,
  ApiError,
  cookieValue,
  invitationFromHash,
} from '../src/api/identity.ts';

test('invitation fragments require an exact high-entropy token', () => {
  assert.equal(invitationFromHash('#invite=' + 'x'.repeat(43)), 'x'.repeat(43));
  for (const value of [
    '#invite=short',
    '#invite=' + 'x'.repeat(44),
    '#invite=%3Cscript%3E',
    '#other=x',
  ])
    assert.equal(invitationFromHash(value), null);
});
test('CSRF cookie lookup matches exact names, never another prefix', () => {
  assert.equal(
    cookieValue(
      'pc_csrf_dev_other=wrong; pc_csrf_dev=right; another=value',
      'pc_csrf_dev',
    ),
    'right',
  );
  assert.equal(cookieValue('something=else', 'pc_csrf_dev'), undefined);
});
test('mutations send only the current CSRF cookie and JSON; 401 remains actionable', async () => {
  const originalFetch = globalThis.fetch;
  const previousDocument = Object.getOwnPropertyDescriptor(
    globalThis,
    'document',
  );
  Object.defineProperty(globalThis, 'document', {
    configurable: true,
    value: { cookie: 'pc_csrf_dev=synthetic-csrf' },
  });
  try {
    globalThis.fetch = async (url, options) => {
      assert.equal(url, '/api/admin/invitations');
      assert.equal(options.credentials, 'same-origin');
      assert.equal(options.headers['X-CSRF-Token'], 'synthetic-csrf');
      assert.equal(options.headers['Content-Type'], 'application/json');
      assert.equal(options.body, '{}');
      return new Response(
        JSON.stringify({ error: { message: 'Please sign in' } }),
        { status: 401 },
      );
    };
    await assert.rejects(
      api('/admin/invitations', 'POST', {}, { csrf_cookie: 'pc_csrf_dev' }),
      (error) => error instanceof ApiError && error.status === 401,
    );
  } finally {
    globalThis.fetch = originalFetch;
    if (previousDocument)
      Object.defineProperty(globalThis, 'document', previousDocument);
    else delete globalThis.document;
  }
});
