# Stage 8 deployment procedure

Date: 2026-10-23 (Africa/Cairo). **Preparation authorized; no OCI resource or public deployment has been performed or approved for a specific final configuration.** Stage 7 cloud backup/recovery gates remain open. Preparation can overlap those gates; operational acceptance cannot bypass them.

## Proposed infrastructure for review

| Component | Candidate configuration | Required live check |
| --- | --- | --- |
| Account/region | Non-upgraded Free Tier; home region Jeddah, me-jeddah-1 | Current subscription, all relevant compartments and resource consumption |
| Compute | One Always Free-eligible A1 Flex, 2 OCPUs/12 GB; eligible Ubuntu 24.04 ARM64 | Current image, eligibility label, availability, optional integrations and estimate |
| Boot/data | 50 GB boot + 150 GB data, eligible Balanced performance; no automatic growth/performance changes | All account boot/block volume usage, performance eligibility and encryption |
| Network | One VCN, public subnet, internet gateway, one VM public IPv4 | Exact address/network eligibility and existing consumption; no NAT gateway/load balancer |
| Ingress | TCP 80/443 public; SSH 22 only from the owner's current public IP /32 | Both OCI rules and host/Docker forwarding rules; never public API/DB ports |
| DNS/TLS | Owner selected a free DuckDNS name; Caddy HTTP challenge/automatic HTTPS | Name registration/control, correct A record, remove stale AAAA, actual public certificate/renewal |
| Backups | Native data-volume incremental backups; retain four good points and one next-capture slot | Five-slot account-wide inventory including boot backups, coordinated job, failures/alerts and restore |

Fresh published checks: Oracle lists 1,500 A1 OCPU-hours/9,000 GB-hours monthly, equivalent to 2 OCPUs/12 GB for an Always Free tenancy, plus 200 GB combined boot/block storage and five combined backups. Regional service limits of 16/96 do not enlarge the free allowance. [Oracle Always Free resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm). These published terms do not verify this account's current entitlement or physical capacity.

DuckDNS describes its free service and HTTPS update mechanism. [DuckDNS FAQ](https://www.duckdns.org/faqs.jsp). The owner registered hedowdohub.duckdns.org; a public DNS check confirms an A answer matching the owner-provided current connection, with no IPv6 answer observed. It is not an OCI target yet. No account/token was accessed and no DNS was changed by the agent. Keep its token private and outside Git, URLs printed in terminals and logs. With an ephemeral IPv4 address, recheck/update DNS after address replacement; an automated updater is not installed or tested.

Caddy requires a resolving name, inbound ports 80/443 and persistent writable certificate storage for its ordinary automatic HTTPS flow. [Caddy documentation](https://caddyserver.com/docs/automatic-https). The local rehearsal uses a private CA; it does not contact ACME or establish public renewal.

Optional resource/service integrations must be inspected individually. Exclude unverified paid integrations, paid domains, paid monitoring, managed database/firewall, cross-region copies, automatic upgrades and trial-only services. Keep the account non-upgraded. A positive draft estimate requires reconciliation rather than reliance on trial credits. See [zero-cost policy](zero-cost-policy.md). **This candidate is not yet a resource-specific approval request:** live account, address/performance costs, final SSH source and current exact draft still need inspection.

## Production artifacts and safety boundaries

Use **compose.production.yaml by itself**, not as an overlay on compose.yaml. The latter remains the development preview. The production file requires immutable image references, secure cookies, one exact HTTPS origin, explicit measured storage limits and bind sources that must already exist. Only the frontend publishes ports. API/migration/frontend run as UID 10001 with all capabilities dropped, no-new-privileges and read-only roots; their temporary directories are bounded tmpfs. PostgreSQL retains its standard image startup/privilege boundary and a private network, with no public port. All four services have 3 × 10 MB log bounds.

Backend network 172.29.86.0/24 is internal; Caddy alone has fixed address 172.29.86.10 there and an additional edge network. Uvicorn trusts forwarding headers only from that address. Before deployment, check subnet overlap with host/VPN/VCN/other Docker networks. If the subnet changes, change both the proxy address and trust configuration together, then repeat tests. Caddy does not trust arbitrary client forwarding headers. No API port is published. Host firewall testing must account for Docker forwarding rather than assume UFW input rules alone cover container ports.

Production Settings rejects unknown APP_ENV values, HTTP/multiple/local origins, nonstandard HTTPS ports, relative storage roots, insecure cookies and a runtime database username other than cloud_app. Bootstrap remains terminal-only with hidden password entry and refuses an existing first administrator; there is no public bootstrap route or default production credential. The sample administrator belongs only to synthetic tests. Lifecycle reconciliation does not purge the shared recycle bin.

Image references must be retained, reviewed immutable artifacts matching the selected architecture. Local sha256 IDs are acceptable for a local rehearsal; deployment requires retained/exported images or a verified registry reference available to that host. Do not assume an AMD64 digest is an A1 artifact. Existing source Dockerfiles retain explicit version tags; their resolved base manifests, runtime advisories and OS image need release review before approval. No new Python/Node dependency was added.

## Host preparation, after exact resource approval

1. Verify the VM identity, image/architecture, SSH fingerprint and accepted SSH public key. Never send private keys or production passwords through chat. Configure key-only access and a non-root sudo operator; verify a second session before changing SSH access. Review patched Ubuntu/Docker packages before installation. No host package installation or SSH policy has been executed yet.
2. Identify the attached data volume by provider metadata and device identity. Inspect existing filesystem/data before any filesystem operation. **Do not format a guessed device.** Formatting, replacing or releasing storage requires specific approval. Mount the verified filesystem at /srv/my-cloud-data and record its UUID, provider volume identity and mount procedure.
3. Prepare private mode-0700 directories on that mounted filesystem: files and caddy owned by UID/GID 10001, postgres owned by the verified PostgreSQL-image UID/GID (999 for the selected Debian image). Keep essential configuration, role initializer, exact Compose/Caddy source, source release and retained artifacts on this same backed-up volume under private configuration/release directories. Reserve space for them and DB/log growth; do not store the only configuration copy on the boot disk.
4. Use infrastructure/production.example.env as a template, stored privately outside Git. Generate four independent random 32-byte values encoded as 64 hexadecimal characters. Do not reuse development passwords, sessions or auth secret. Set actual hostname, data mount/UUID and immutable images. Measure usable space before accepting the 100 GB target. Require a 10 GB emergency reserve and at least 20 GB further capacity for DB/configuration/release growth; actual operational accounting remains necessary. Store an independently recoverable encrypted copy of essential configuration and recovery instructions outside the VM, with owner-approved custody.
5. From the approved release directory run the following **read-only checks**. Configuration output must not be printed or pasted because it contains secrets:

```sh
python3 scripts/production_preflight.py --env-file /etc/my-cloud/production.env --host
docker compose --env-file /etc/my-cloud/production.env -f compose.production.yaml config --quiet
```

The preflight refuses a missing/wrong UUID mount, boot-disk fallback, loose directory/config permissions, missing prepared data paths, mutable image tags, reused/weak secrets or inadequate measured headroom. It never creates/mounts/formats anything and does not verify OCI eligibility, image provenance, DNS, backups or deployment approval. Mode 0600 configuration may be a controlled link to the private data-volume copy. The mount's parent and all bind-source ancestors remain trusted root-owned configuration.

6. Ensure mount availability precedes Compose and Docker's automatic container restarts on the dedicated host. A reviewed systemd mount dependency/RequiresMountsFor plus preflight must guard startup. Bind sources use create_host_path:false, so missing data directories fail rather than silently initialize a new boot-disk database. Host boot/missing-volume behavior still needs execution on the actual Linux host; no systemd unit has been installed or tested.
7. Verify inbound/outbound rules and free DNS against the approved IPv4. Expose no application before production settings and private storage permissions pass. Do not copy local synthetic data or its credentials into production.

## Controlled first start and acceptance

After the exact release and provisioning/deployment approvals, start the reviewed artifacts with the explicit production file. The migration container waits for private PostgreSQL, migrates as cloud_migrator and must finish successfully before API startup. The API uses cloud_app, which cannot alter schema. Start/health failures must stop release progression without deleting volumes. Interactively run the first-admin bootstrap inside the production API terminal; keep the hidden password private. Test account creation once and confirm another bootstrap is refused.

Before real user data: verify public DNS/TLS/HTTP redirect, certificate persistence, secure cookies, Origin/CSRF and spoofed-forwarding behavior, shared upload/download/hash, invitations/admin isolation, preview safety, reserve warnings, trash/restore and dashboard navigation. Restart processes, recreate containers and reboot the host while checking data/session persistence and mount ordering. Verify that absent/wrong data mounts fail safely. Record rollback artifacts and run the [recovery runbook](recovery-runbook.md).

Finish native backup capture/rotation/IAM and outside-VM host-down/missed-job alerts on approved resources. A static encrypted local sample and local TLS test do not satisfy these. Complete the quota-safe full-size restore test with disposable cloud test data and measure accepted RPO/RTO. With 50+150 GB allocated, another 150 GB restore would exceed the 200 GB free disk allowance; no parallel full-volume restore is approved. Never free a source volume or remove backups without a separately reviewed data-preserving procedure and specific approval.

Record the first actual scheduled recovery point, failed/missed capture alert, restoration, restart/renewal evidence, accepted usable capacity and current costs. Only then consider Stage 7/8 operational acceptance. No cloud stack, production start, external alert, automatic task, main merge or public endpoint was created during local preparation.
