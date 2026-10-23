# Dependency decisions — Stage 2

Direct dependencies are restricted to the approved stack and foundational tooling. Use exact resolved versions/hashes in `pnpm-lock.yaml`, `uv.lock` and exported hashed `requirements*.lock`. Package manifests constrain major families; review lockfile changes and advisories before merging. No runtime package auto-updates or cloud subscriptions.

| Dependency | Purpose | Published license family / rationale |
| --- | --- | --- |
| React / React DOM | Approved UI stack | MIT; no extra UI framework, icons, animation or state dependency at this stage. |
| Vite / React plugin | TypeScript/React dev and production build | MIT; Node 24 meets current engine requirements. |
| TypeScript / ESLint / typescript-eslint / React Hooks ESLint / Prettier / globals / type definitions | Strict compile, lint and formatting | Apache-2.0/MIT/ISC families; development-only. Verify resolved transitive licenses as part of actual inventory. |
| FastAPI / Uvicorn / Pydantic Settings | API, ASGI host and typed environment configuration | MIT/BSD families; no auth/storage dependencies before features need them. |
| SQLAlchemy / Alembic | PostgreSQL connections/transactions and versioned DDL | MIT; migrations are independent of runtime startup and models. |
| psycopg with binary package | PostgreSQL driver, portable local testing | LGPL-3.0 driver; binary wheel bundles additional libraries/licenses. Review redistributed wheel notices before publishing images. No database bytes in Python packages. |
| pytest / HTTPX | Backend logic/ASGI integration testing | MIT/BSD; avoid a large end-to-end harness before user flows exist. |
| Ruff | Mandatory Python lint/format | MIT; development-only. |
| pip-audit / pre-commit | Advisory review and local secret guard wiring | Apache-2.0/MIT families; heuristic pattern scanner does not replace review. |
| uv | Reproducible Python resolver/lock/export | MIT/Apache-2.0; local tooling, not application runtime. |
| PostgreSQL / Caddy | DB and static/proxy containers | PostgreSQL license / Apache-2.0; official explicit image versions, digest pinning before production. |

Sources: [FastAPI container guidance](https://fastapi.tiangolo.com/deployment/docker/), [Vite requirements](https://vite.dev/guide/), [PostgreSQL license](https://www.postgresql.org/about/licence/), [psycopg license](https://www.psycopg.org/psycopg3/docs/basic/install.html). License family descriptions are not a substitute for the actual locked inventory. Record audit command outcomes, advisories, exceptions and compatibility limits after installation. Never claim an unexecuted scan or missing container scan passed.

2026-10-21 Linux acceptance: exact official image manifests advertise amd64/ARM64, and the local amd64 stack passed. The Python base bundled old pip 25.0.1 with known audit findings; the finished immutable API image removes pip after the hash-checked dependency install. Its actual 22-distribution inventory passed pip-audit with zero known findings. Dependencies are updated by changing/auditing locks and rebuilding. OS-image advisories, ARM64 execution and production digest pinning remain release gates. See `stage-2-compose-verification.md`.

## Stage 3 additions (2026-10-21)

Argon2-cffi 25.1.0 supplies maintained Argon2id hashing, with bindings 26.1.0. Email-validator 2.3.0 supplies Pydantic EmailStr normalization/validation; no DNS check or email sending occurs on registration. No new frontend dependency. Resolved additions and installed metadata license expressions: argon2-cffi/bindings MIT, cffi 2.1.1 MIT-0, pycparser 3.11 BSD-3-Clause, email-validator Unlicense, dnspython 2.9.0 ISC. Hash locks were regenerated with uv and installed with --require-hashes; pip check passed. Locked runtime pip-audit and pnpm audit returned no known vulnerabilities. This is a known-advisory check, not proof of absence of vulnerabilities; OS-image/ARM64 review stays a release gate.

## Stage 4 addition (2026-10-22)

python-multipart 0.0.32 (Apache-2.0 from installed distribution metadata) supplies maintained streaming multipart callbacks. It is the only new runtime dependency; no new frontend dependency. The low-level parser is fed bounded chunks and metadata/header/part limits are enforced before publication, rather than buffering an UploadFile. Hash-locked uv/export installation and pip check passed; locked pip-audit and pnpm audit reported no known vulnerabilities. Actual Linux inventory audit is recorded in stage-4-verification.md. Official parser API: https://multipart.fastapiexpert.com/api/.

## Stage 5 additions (2026-10-22)

Pillow 13.0.0 (installed license expression MIT-CMU) provides bounded PNG/JPEG/WebP decoding and metadata-free PNG generation. PDF.js/pdfjs-dist 6.4.299 (Apache-2.0) supplies local canvas PDF rendering; its optional native Node canvas package is excluded because browser canvas is used. Playwright is development-only, using the existing Chrome executable with isolated headless profiles; no browser binary was downloaded and no real browser profile is opened. Exact versions are locked. Runtime Python hash-lock and frontend pnpm advisory audits returned no known vulnerabilities during implementation; final runtime inventory audit remains an acceptance gate.

Official references: [Pillow security](https://pillow.readthedocs.io/en/stable/handbook/security.html), [PDF.js examples](https://mozilla.github.io/pdf.js/examples/), [pnpm dependency settings](https://github.com/pnpm/pnpm/blob/main/pnpm/docs/settings/dependency-resolution.md). These controls reduce exposure; they do not prove the absence of parser/codec vulnerabilities. OS/image/ARM64 review remains later work.

## Stage 6 (2026-10-22)

No runtime or development dependency was added or changed. The spatial UI uses existing React, native pointer events, SVG and browser APIs; geometry tests use existing Node tooling and browser tests reuse locked Playwright/installed Chrome. Stage 5 package inventory/lock decisions remain unchanged. No new advisory audit is claimed from this no-dependency change; ongoing advisory/image/ARM64 review remains a release requirement.


## Stage 7 local operations (2026-10-23)

No Node/Python application dependency or lockfile change. Operational bundle tooling uses Python standard library plus an explicitly supplied GnuPG executable, invoked as a separate program. Synthetic Windows tests used existing Git GnuPG 2.2.29 (GPL-3.0-or-later as reported by its version command) and libgcrypt 1.9.3; these are not approved production cryptographic versions. Select a current supported/patched host package at deployment and verify its provenance/advisories. No executable was installed or bundled into the app image. [GnuPG distributions](https://www.gnupg.org/download/).

Fresh pnpm production and all-frontend/build advisory reports returned zero known findings. Locked Python runtime report (31 applicable entries) and exact running API inventory (30 distributions) returned zero known findings; host pip check passed. These checks do not cover all OS/image/crypto vulnerabilities or ARM64 execution. [Stage 7 evidence](stage-7-verification.md).

## OCI operational access check (2026-10-23)

Official Oracle SDK 2.189.0 (UPL-1.0 or Apache-2.0) was installed only in an isolated operational venv on the existing VM, to use instance-principal authentication without an administrator API key. No application dependency/lock changed. All 25 resolved wheels were downloaded as binaries, SHA-256 locked and installed offline with --require-hashes; pip check passed. Version inventory/hash lock is retained privately beside the operational environment. Actual ARM64 authentication and inventory calls passed. OSV querybatch for the exact 25 distribution versions returned no known findings at 14:19 UTC; this does not audit host OS/images. The environment is an access-check tool, not an installed production backup worker. [Oracle installation guide](https://docs.oracle.com/en-us/iaas/tools/python/latest/installation.html).
