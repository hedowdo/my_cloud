# Stage 8 preparation and verification

Date: 2026-10-23 (Africa/Cairo). Branch: stage-8-deployment-readiness. **Local preparation passed; no cloud resource, public release, main merge or Stage 7/8 operational completion.** Owner authorized Stage 8 and chose free DuckDNS. Actual deployment still depends on specific configuration/cost approval and native backup/recovery acceptance.

## Changes and executed evidence

Production settings now allow a deliberately configured production environment while rejecting unknown environment values, insecure cookies, HTTP/local/multiple origins, nonstandard HTTPS ports, relative storage roots and a runtime role other than cloud_app. The prior unconditional development-only startup rejection was an explicit foundation guard; it was identified by source review and replaced under Stage 8 authorization. Interactive bootstrap retains terminal/hidden-password and one-admin protections; no public bootstrap or default credentials were added. Maintenance retains its existing conservative cleanup semantics, including no automatic trash purge.

Separate compose.production.yaml and infrastructure/Caddyfile.production require immutable artifact references, measured storage values, secure cookies and exact origin. Database/API have no published ports; the internal network has an explicit trusted Caddy address. Application containers have read-only roots, bounded tmpfs, UID 10001, dropped capabilities/no-new-privileges; logs are bounded for all services. Every data bind refuses implicit source-directory creation. Development Compose/source volumes and the local preview remain intact.

scripts/production_preflight.py performs read-only configuration validation and optional actual Linux mount/UUID/private-permission/capacity checks. It never starts services or provisions/mounts/formats storage. Unit tests prove invalid configuration and mutable/reused-secret boundaries; actual Linux-host checks remain unexecuted. The example environment contains placeholders only. No Python/Node dependencies or locks changed.

### PostgreSQL release regression

Command: RECOVERY_GPG set to the existing documented local GPG binary; .venv/Scripts/python.exe scripts/verify_postgres.py --bin-dir .cache/postgres-runtime/pgsql/bin.

Private evidence: .local/verification/5c9e2a5c9f56. **118 tests passed in 141.45s before restoration and 118 passed in 152.98s after restoration**, with one existing Starlette TestClient deprecation warning each. The harness also passed initial/idempotent migrations, runtime-role schema constraints/readiness, PostgreSQL restart, populated-downgrade refusal, disposable fresh migrations and real pg_dump/pg_restore. It stopped its own new disposable cluster. This is a complete executed suite, including the final 24 Stage 7 crypto/recovery tests and the 22 new production/settings-preflight cases.

A standalone restricted-context foundation run produced no completed result and was interrupted. It is not counted as acceptance; the complete suite above ran under approved local execution. No application failure was established by the interrupted attempt. An initial Ruff import-order finding in a new test and test-harness formatting/name issues were corrected before acceptance.

### Isolated production-profile integration

Command: scripts/verify_production_compose.py with the local Docker binary. Private evidence: .local/stage8/6a56aaaca378/result.json. **Passed**:

- Production Compose renders; original production data binds retain create_host_path:false and internal-only database/API ports.
- A new synthetic project uses uniquely created volumes and random loopback ports. Its explicit test override replaces production binds with those volumes and replaces public certificate issuance with a local CA. No primary project/volume is repurposed.
- Actual TLS chain/hostname verification trusts only the fixture CA in the test client; certificate verification is not disabled and no CA is installed into the system trust store.
- The actual production Caddy route serves the application, sends HSTS, proxies readiness and denies unauthenticated file access. HTTP redirects to the correct HTTPS hostname/default public port.
- A fresh synthetic administrator can log in using exact Origin. Session and CSRF cookies use __Host names, Secure and SameSite=strict; the session is HttpOnly. Wrong Origin is rejected. A forged incoming forwarded-IP value does not become a rate-limit identity.
- The authenticated session and a file marker survive actual container replacement, preserving DB/files/certificate volumes.
- Actual API/frontend/migration container inspection confirms UID 10001, read-only root and CapDrop ALL.

Only the new synthetic project was stopped afterward; its volumes/evidence are retained. The working localhost:8080 preview was never replaced. The bootstrap service was exercised programmatically inside the isolated API; the eventual human terminal interaction remains a host acceptance check. The local CA test does not prove public ACME/DNS/renewal, actual data-volume binds, host reboot/mount order, native backup operation or native A1 performance.

### DNS and provider inspection

The owner registered hedowdohub.duckdns.org. A public DNS lookup resolved and matched the provided current connection address; no IPv6 answer was observed. Evidence .local/stage8/dns-check.json contains boolean comparison results rather than the private address. No HTTP request was made to the owner's connection, DuckDNS token was requested/accessed, or DNS update submitted. The hostname is not yet pointed at an OCI VM.

Fresh official references and candidate resource ledger are in [deployment procedure](deployment.md). They support the 2-OCPU/12-GB, 50+150-GB, five-backup planning baseline; they do not verify current account consumption, all current price dimensions or physical capacity. The account remains non-upgraded/no-resources by owner report. A fresh browser inventory attempt failed at initialization: "failed to write kernel assets: The system cannot find the path specified. (os error 3)". No Oracle state was inspected or changed in this turn.

## Pending acceptance

- [x] Final ARM64 builds/emulated dependency execution and source checks recorded below; native A1 acceptance remains open.
- [ ] Current console inventory, exact resource/image/performance/address/agent/SSH configuration and cost reconciliation; resource-specific approval.
- [ ] Actual Ubuntu host patches, permissions/UUID mount and boot dependency, native execution, OS image review and production secret custody.
- [ ] DNS updated to the approved VM; public HTTPS/renewal verified without a private CA.
- [ ] Coordinated native daily backups and five-slot policy, outside-VM failed/missed/host-down alert delivery and quota-safe full-size recovery/RPO/RTO.
- [ ] Approved production release, host restart/rollback/core browser acceptance and owner handover. No operational completion inferred from these local results.


## Final architecture and source checks

Both API and frontend images built successfully with --platform linux/arm64 from existing versioned Dockerfiles and frozen dependency locks. Private metadata: .local/stage8/arm64-images.json. The ARM64 API executed as UID 10001 under Docker emulation, imported the application and psycopg, encoded a PNG with Pillow, and hashed/verified a synthetic password with Argon2. The ARM64 Caddy binary executed at the expected version. These are actual emulated architecture checks, not native Oracle A1 or full ARM64-stack/OS acceptance. No runtime/build dependency version or lock was changed; production image provenance/OS advisories remain a release review.

Final Ruff lint and format checks passed for 48 Python files; Prettier checked 39 frontend/config files; the heuristic secret scan and git diff --check passed. An explicit UTF-8/trailing-whitespace scan passed for 104 source/document files, and relative documentation links resolved. The current local preview readiness endpoint returned 200 after the isolated project stopped. No frontend application code was changed, so Stage 7's browser UI evidence is retained rather than claimed as newly executed browser tests. Stage 8's isolated HTTPS tests and full PostgreSQL suite are newly executed as recorded above.


## Live OCI progress — 2026-10-23

Owner completed the reviewed VCN/public subnet/internet gateway and default internet route through the console. Supplied security-list screenshots show SSH restricted to the owner's supplied /32, stateful public TCP 80/443 and retained ICMP rules. A fresh instance review showed Ubuntu 24.04 Minimal aarch64, A1 Flex 2 OCPUs/12 GB, existing public subnet, public IPv4 enabled, 50 GB Balanced boot/10 VPU with in-transit encryption and only Compute Instance Monitoring enabled. Published free allowances and the displayed EUR 1.98 estimate's tier-pricing exclusion were explained before the owner submitted Create. Owner screenshots confirm creation succeeded and instance Running. This supersedes earlier statements that no cloud resources exist; no additional cloud resource operation is inferred as approved.

SSH read-only checks succeeded using the newly owner-generated private key in Downloads; key contents were never printed or copied into the repository. Host: aarch64, Ubuntu 24.04.5 LTS, 2 CPUs, about 11 GiB reported RAM, cloud-init done, 50 GB boot disk with approximately 47 GiB root free. No separate data disk or Docker executable was present. Administrative access worked; effective SSH config has passwordauthentication no and pubkeyauthentication yes. SSH and rpcbind listeners were observed; the supplied OCI ingress list does not admit public rpcbind. Host firewall/patch/service hardening and external acceptance are still pending.

The first observed ED25519 host key is pinned in ignored .local/stage8/host-check/known_hosts; subsequent SSH used StrictHostKeyChecking=yes. This is trust on first use, not independent console fingerprint validation. Independently verify before sensitive release/configuration transfer. All remote commands this turn were read-only; no package, daemon, storage, DNS or application deployment change was made. Native backup/alerts/full-size restore and Stage 7/8 completion remain open. Next storage proposal: a separate eligible 150 GB data volume, giving 50+150=200 GB combined; review its exact form/eligibility and obtain specific approval before creation/attachment or filesystem initialization.


## Approved data-volume initialization — 2026-10-23

Owner supplied screenshots of the created 150 GB hedowdo-data volume, Available/Always Free, Balanced 10 VPU, Oracle-managed encryption, auto-tune/reservations/replication off and no backup policy. Owner attached it paravirtualized read/write to the reviewed VM with in-transit encryption. Read-only SSH inspection identified a separate 161061273600-byte /dev/sdb by its stable by-id serial, no partitions/mounts/filesystem signatures; the 50 GB boot disk remained separate. Owner explicitly approved ext4 initialization/mount after explanation.

The guarded script checked exact serial-derived by-id path, size, disk type, no signatures/mount and no existing target/fstab entry before non-forced ext4 initialization. Created filesystem UUID 63c9b747-a658-4a0d-8b1f-1a1dcc8a2ea9, mounted /srv/my-cloud-data and backed up /etc/fstab before adding the UUID mount with nodev,nosuid,noexec,_netdev. Created private files/caddy directories owned by 10001, postgres by 999 and root-owned configuration/releases directories. No extra resource or disk resize was performed.

First execution completed initialization/mount but exited 1 on a trailing carriage-return line introduced by the PowerShell text pipeline. It also revealed that the mounted ext4 root retained default mode 0755 despite the pre-mount directory mode. No formatting retry was attempted. Follow-up used exact LF bytes over subprocess stdin, set the mounted root to 0700 and tested UUID/ownership/mode after a controlled unmount/remount of this unused volume. findmnt --verify reported no errors/warnings. Final checks passed: root/files/caddy/postgres all mode 0700, intended owners, UUID correct and mount flags retained. Private evidence: .local/stage8/host-check/data-volume-verification.txt.

Measured filesystem total 157396975616 bytes, available 149327085568 bytes (about 149.3 decimal GB / 139.1 GiB). This supports the proposed 100 decimal GB pool with further DB/configuration/emergency headroom, subject to later measured operational checks. Persistent fstab remount passed; a full host reboot/missing-volume startup test has not run. No application/database/Docker install, production configuration/secret transfer, DNS update, native backup or release deployment occurred in this step. Native backup/alerts/recovery, independent host-key validation and Stage 7/8 release gates stay open.


Owner requested finishing deployment. Public DNS now resolves hedowdohub.duckdns.org to the approved VM; no IPv6 answer observed. The combined Docker/host-hardening execution was rejected by automatic approval review before running, requiring explicit scope approval because it installs a repository/daemon and changes persistent SSH/services. No host installation or SSH change from that rejected command occurred. Concrete proposal: [host approval scope](stage-8-host-approval.md). Await specific approval; DNS verification and proposal preparation completed independently.


## Approved host software and security controls — 2026-10-23

Owner explicitly approved the exact host scope in stage-8-host-approval.md after automatic approval review rejected the previous broad command. The resubmitted approved command ran: official Docker apt repository, Docker Engine/CLI 29.9.2, Compose 5.6.1, containerd 2.4.2 and Buildx 0.38.1 were installed. Docker is active/enabled, RequiresMountsFor=/srv/my-cloud-data is present, default logs are bounded to 3x10 MB, and journal caps were configured. The existing SSH key remains installed; sshd validation passed, root login/password authentication are disabled, and a fresh independent SSH connection succeeded. rpcbind service/socket are inactive and no longer listen on 111. Data-volume UUID/owners/private modes remained correct. A fresh native ARM64 hello-world container passed and was removed after completion; no app/database container was started. No host reboot occurred.

The initial local wrapper could not print a Unicode arrow in the install log using Windows cp1252. The remote log contained HOST_SOFTWARE_INSTALLED and effective SSH values; no installer rerun was attempted. Wrapper output was corrected to UTF-8 and the separate fresh-login/runtime checks passed. Private evidence: .local/stage8/install-host.sh.log and check-host.sh.log. Public application start, native backup IAM/capture/alerts/restore and release acceptance remain pending.

Owner explicitly supplied the operational alert email destination, including a test notification. The address is stored only in ignored local operational configuration. No subscription, external message or alarm has been created/sent yet. Native OCI API authorization remains absent; [backup-access preparation](oci-backup-access.md) records the next reviewed IAM steps.


## Native release preparation — 2026-10-23

Prepared immutable ARM64 API/frontend image archive (117103104 bytes), source archive and SHA-256 manifests; 146 selected source/config/document files, with ignored runtime files/private credentials and docs/evidence excluded. Transferred into a new private staging directory, then verified all archive and restored-source hashes on the VM before loading images. Root-owned staged release is /srv/my-cloud-data/releases/20261023-stage8. No public app or database was started. The initial staging preflight ran before SCP finished and refused the absent manifest without changes; after transfer completed the same checks passed. A Docker inspection template assumed an optional PostgreSQL Config.User field existed and stopped after image loading; a corrected inspection and separate native runtime checks passed without re-extracting/replacing the staged release.

Native OCI ARM64 checks passed for application/Psycopg import, Pillow encoding, Argon2 hashing/verification and Caddy execution. Image IDs match the local tested ARM64 artifacts; PostgreSQL 17.11-bookworm resolved to immutable sha256:858bb5e98eed02eb8cafbcdc007f9a65d1b613972028944a8ec2133ccaf80d27, ARM64, with postgres UID 999 verified. API/frontend run as UID 10001. Evidence: .local/stage8/stage-release.sh.log and check-release.sh.log. OS/image advisory review and the actual full-stack cloud workflow/recovery tests remain open; binary checks alone do not complete them.

Generated four independent new production secrets directly on the host into root-only mode-0600 /srv/my-cloud-data/configuration/production.env; no secret contents were printed, copied into Git or reused from development. Config fixes the real hostname/mount UUID, 100000000000-byte pool, 10000000000-byte reserve and immutable local image IDs. Actual Linux host preflight passed UUID/mount/private-owner/mode/measured-capacity checks; production Compose config --quiet also passed. Private evidence: .local/stage8/configure-release.sh.log. No first administrator was created. Public application startup, TLS, independent recovery-material custody, native backup API authorization/adapter/scheduling/alerts and full-size restore remain pending. Owner-provided email authorizes operational alerts/test notification, but no message/subscription was created.

Next dependency: owner-assisted OCI identity-domain dynamic-group/policy preparation, since browser runtime remains unavailable and SSH alone grants no OCI API privilege. See oci-backup-access.md. Do not create snapshots, delete recovery points, add monitoring resources or start production merely because host preparation passed.
