import { readdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import * as prettier from 'prettier';

// Explicit enumeration avoids formatter glob traversal inconsistencies on Windows/OneDrive.
async function sourceFiles(directory) {
  const files = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    if (['node_modules', 'dist'].includes(entry.name)) continue;
    const target = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...(await sourceFiles(target)));
    else if (/\.(?:ts|tsx|js|mjs|json|html|css)$/.test(entry.name))
      files.push(target);
  }
  return files;
}

const files = [
  ...(await sourceFiles('frontend')),
  'package.json',
  'pnpm-workspace.yaml',
  '.prettierrc.json',
  'scripts/format_frontend.mjs',
];
let failures = 0;
for (const file of files) {
  const source = await readFile(file, 'utf8');
  const options = { ...(await prettier.resolveConfig(file)), filepath: file };
  if (process.argv.includes('--write'))
    await writeFile(file, await prettier.format(source, options));
  else if (!(await prettier.check(source, options))) {
    console.error(`Formatting required: ${file}`);
    failures += 1;
  }
}
console.log(
  `Prettier ${process.argv.includes('--write') ? 'formatted' : 'checked'} ${files.length} files.`,
);
process.exitCode = failures ? 1 : 0;
