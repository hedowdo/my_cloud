import assert from 'node:assert/strict';
import { test } from 'node:test';
import { fetchHealth } from '../src/api/health.ts';

test('only a successful, well-formed ready response reports readiness', async (context) => {
  for (const [body, status, expected] of [
    [{ status: 'ready' }, 200, 'ready'],
    [{ status: 'unavailable' }, 503, 'unavailable'],
    [{ status: 'ready' }, 500, 'unavailable'],
    [{ message: 'ready' }, 200, 'unavailable'],
    [null, 200, 'unavailable'],
    ['ready', 200, 'unavailable'],
  ]) {
    context.mock.method(globalThis, 'fetch', async (_url, options) => {
      assert.equal(options.cache, 'no-store');
      assert.equal(options.credentials, 'same-origin');
      return Response.json(body, { status });
    });
    assert.equal(await fetchHealth(new AbortController().signal), expected);
    context.mock.restoreAll();
  }
});

test('connection and malformed-payload failures propagate to the unavailable UI path', async (context) => {
  context.mock.method(globalThis, 'fetch', async () => {
    throw new TypeError('offline');
  });
  await assert.rejects(fetchHealth(new AbortController().signal), TypeError);
  context.mock.restoreAll();
  context.mock.method(
    globalThis,
    'fetch',
    async () => new Response('not json'),
  );
  await assert.rejects(fetchHealth(new AbortController().signal), SyntaxError);
});
