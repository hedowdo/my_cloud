import assert from 'node:assert/strict';
import test from 'node:test';
import { bytes, validateFile, FILE_LIMIT } from '../src/api/files.ts';

test('client file admission matches decimal byte limit and Unicode/path boundaries', () => {
  for (const size of [0, FILE_LIMIT - 1, FILE_LIMIT])
    assert.equal(validateFile({ name: 'report.bin', size }), null);
  assert.match(
    validateFile({ name: 'report.bin', size: FILE_LIMIT + 1 }),
    /500 MB/,
  );
  for (const name of [
    '../file',
    'path\\file',
    'a:b',
    '.',
    '..',
    'trailing.',
    ' padded ',
    'a\u0000b',
    'é'.repeat(128),
  ])
    assert.ok(validateFile({ name, size: 1 }), name);
  assert.equal(validateFile({ name: 'é'.repeat(127), size: 1 }), null);
  assert.equal(validateFile({ name: 'e\u0301'.repeat(127), size: 1 }), null);
});
test('capacity labels use the same decimal units as the enforced file contract', () => {
  assert.equal(bytes(FILE_LIMIT), '500.0 MB');
  assert.equal(bytes(1_000_000_000), '1.0 GB');
  assert.equal(bytes(null), 'Folder');
});
