# Stage 1 — feasibility assessment for approval

Date: 2026-10-20 (Africa/Cairo). Result: CONDITIONAL GO for local development; NO GO for provisioning the current draft. Technical assessment and model checks are finished; owner acceptance and the unchecked stage gates remain pending. No application code or cloud resources created.

## Recommended baseline

One Jeddah Ubuntu 24.04 ARM64 A1 VM, 2 OCPUs/12 GB, 50 GB boot + 150 GB data. Target counted shared pool: 100 GB; data-volume remainder: 10 GB DB/logs, 20 GB emergency reserve, 10 GB workspace, 10 GB filesystem/uncertainty headroom. Measure actual capacity later; lower exposed quota if needed. Four successful daily native data backups, fifth slot for the next capture. Keep the account on non-upgraded Free Tier permanently; no trial-dependent or paid fallback services.

This retains the requested 1–5-user shared file manager, desktop spatial dashboard and mobile list. Residual compromise: free compute can be unavailable/reclaimed, no SLA, and native backups share Oracle account/provider/region risk. Owner delegated selection of the recommended compromise after these limits were explained; no repeated backup-choice question is required. This does not imply production acceptance or resource approval.

## Evidence and decision matrix

| Area | Evidence / decision | Stage 1 outcome |
| --- | --- | --- |
| Account | Owner screenshots: Free Tier/Promo, start 2026-10-20; confirmed Jeddah. Expected 30-day end around 2026-11-19, subject to earlier credit exhaustion. | Evidence sufficient for planning; recheck account type before resource actions. |
| Compute | Regional A1 quota 16 cores/96 memory, usage 0; draft A1 Always Free-eligible at 2 OCPUs/12 GB. Monthly model 1,488 OCPU-hours/8,928 GB-hours for 744 hours. | Proposed size fits published free hours; quota and shape visibility do not prove physical availability. |
| Disk/backups | Console free regional quota 200 GB/5 backups, both unused in displayed root scope. | Baseline arithmetic fits; free eligibility and account-wide consumption rechecked at provision. |
| Positive estimate | Draft 50 GB/10 VPU boot estimate EUR 1.98/month; console expressly excludes tier pricing. [Official estimate guidance](https://docs.oracle.com/en-us/iaas/Content/Billing/Tasks/signingup_topic-Estimating_Costs.htm). | Consistent with pre-discount storage estimate; not a $0 bill proof. Reconcile exact free resource designation before provisioning; never rely on credits. |
| Network | One public subnet and internet gateway, one public IPv4, no load balancer/NAT/FastConnect/managed firewall. [Oracle VCN FAQ](https://www.oracle.com/cloud/networking/virtual-cloud-network/faq/) says VCN itself has no charge, while other service/transfer charges still apply. [Oracle network training](https://www.oracle.com/a/ocom/docs/cloud/virtual-cloud-network-100.pdf) documents public IPs without charge, but is older material. | Suitable baseline; recheck current IP/network terms with exact console configuration before resource approval. No billable fallback. |
| Optional agents | Exclude Cloud Guard Workload Protection, Custom Logs Monitoring and Run Command from the new resource baseline unless separately justified and verified free. Retain basic Instance Monitoring within verified free allowance; bounded structured host/app logs supply diagnostics. | Resolves uncertainty by exclusion, not by claiming every default integration is free. Existing draft/live settings have not been changed. No paid Cloud Guard/IAM activation. |
| Access/security | Public TCP 80/443 only for proxy/ACME. TCP 22 only from owner-approved current administrative /32; key authentication, no password SSH/root login; DB/API unpublished externally. | Security design specified. Obtain address/key directly and privately at deployment; no persistent credentials or access changes during Stage 1. |
| DNS/TLS | Select Duck DNS free subdomain + HTTPS update API and Caddy automatic public HTTPS with persistent TLS data. [Duck DNS API](https://www.duckdns.org/spec.jsp), [Caddy HTTPS requirements](https://caddyserver.com/docs/automatic-https). | Documented feasibility established. Domain signup/name ownership, DNS resolution, staging issuance and renewal must be tested when an approved host exists. No invented available hostname or paid domain. |
| Alerts | OCI Instance Monitoring/custom backup metric -> absence/age alarms -> one email subscription in OCI Notifications. | Runs outside the VM; design survives VM shutdown, but not every Oracle-wide failure. Delivery/subscription confirmation and fault injection later. No third-party subscription required. |
| Recovery | Four-good-plus-one-in-flight slot budget; coherent capture and full-size disposable restore procedure below. | Quota model feasible; actual restoration NOT tested or accepted yet. Important files must wait for proof. |

The live browser was rechecked: still at the unsubmitted Create compute instance review, no public IP/SSH key/data disk configured. Do not launch this incomplete draft. Selected network/access/plugin baseline is a proposal for later explicit resource approval, not an applied configuration.

## Network and operational baseline

Propose one dedicated VCN/private CIDR and regional public subnet. Validate no overlap with any existing owner network before applying. A default route uses the internet gateway; authorize traffic through explicit security rules and host firewall. All ingress not explicitly allowed is denied. Keep PostgreSQL inside private Compose networking with no public port mapping; only the reverse proxy publishes web ports. Use restrictive host SSH config, least-privilege runtime accounts, secure sessions and application authorization from `plan.md`.

Use a locally generated SSH key with the private key retained outside Git, docs and browser downloads; install only the public key after explicit access/provisioning approval. Avoid unnecessary persistent OCI API keys. For backups, prefer an instance principal scoped to the dedicated data volume and its backup management in a dedicated compartment where feasible; verify exact IAM conditions/API support before granting. Broader account/admin access is not authorized by this plan.

For the initial host there is no working VCN/subnet. Create the approved network first in the deployment stage, then select it when drafting the VM, so public-IP availability and security rules can be checked explicitly. This avoids relying on the current wizard's disabled public-IP control. Do not label the draft UI as a proven product bug or apply speculative fixes.

Use one email notification destination and grouped alerts with repeat notifications disabled or bounded, including daily all-clear/backup health only where useful. Planning budget: fewer than 100 email notifications/month, leaving margin against the documented 1,000 free notifications. Five metric streams each minute produce 223,200 datapoints in 31 days, far below the documented 500 million ingestion allowance. Limit polling/retrieval as well. [Always Free monitoring and notification allowances](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm).

Host-down: OCI CPU metric absent for five minutes -> one alarm. Backup coordinator reports last successful capture timestamp and a heartbeat every five minutes; missing reports or stale capture age alarms identify failures, even when the coordinator stops. Verify alarm queries and duration behavior in the deployed environment; [Oracle absence alarms](https://docs.oracle.com/en-us/iaas/Content/Monitoring/Tasks/create-alarm-absence.htm). This is outside-VM detection, not provider-independent synthetic HTTPS monitoring. Also alert on actual HTTPS/TLS health from a verified free external vantage point if one is later approved; this enhancement must not delay basic alarms or introduce cost.

No alert, firewall rule, IAM principal, plugin change or DNS update has been applied during assessment.

## Coherent daily backup and retention procedure

1. Put application into maintenance: reject new mutations, finish/cancel in-flight transfers safely; preserve download/read access only where consistency permits.
2. Prepare DB/config recovery state: encrypted configuration export, manifest of referenced blobs/icons/recovery items, database dump and clean PostgreSQL shutdown; flush filesystem buffers. Persist these on the data volume with the DB and file store. Record manifest checksums and application/migration versions. Store encryption recovery keys separately from the VM.
3. Request one native data-volume backup; wait for provider confirmation of the snapshot capture's safe point before restarting DB/writes. Oracle documents quiescing and resuming when backup state changes from REQUEST_RECEIVED to CREATING. Verify that sequence against the actual service/API during rehearsal. [Oracle backup consistency guidance](https://docs.oracle.com/en-us/iaas/Content/Block/Concepts/blockvolumebackups.htm).
4. Monitor until successful completion; validate backup status, recorded capture time and manifest provenance. A successful API request alone is not completion or checksum restore proof. If capture fails, preserve last good backups and alert; do not claim daily protection.
5. With four retained good points, create the fifth before removing the oldest eligible good backup. Never prune the last known good point. A failed fifth may need cleanup under an approved backup-retention policy; do not silently exceed slots or destroy last-good data. Explicitly approve the retention deletion policy when configuring backup automation; it does not authorize deleting user files/trash.

Nightly coordination can interrupt writes. Measure maintenance duration, backup lag and latest recoverable-point age. RPO targets roughly daily; it is not a strict 24-hour guarantee. Stage 7 must establish achievable timing and Stage 8 operational acceptance must disclose it.

## Full-size restore rehearsal within free quota

Before any real uploads, use disposable test data on an approved 150 GB data volume and 50 GB boot volume (200 GB total). Include a representative dataset and interrupted operations, DB records, users, icons, trash, retained replacements, positions and checksums; generate no sensitive personal data. Test near-full behavior in a controlled environment without starving the OS/DB reserve.

Take a consistent verified-success backup, record its identifier privately and preserve it. Obtain explicit confirmation to detach/remove this named disposable source volume; it must contain no real user files. Releasing 150 GB brings allocation to 50 GB. Restore the 150 GB backup into the released quota, returning total allocation to 200 GB. Reattach, recover DB/config, verify all references/checksums and repeat authenticated download/permission tests. The restored volume can become the initial empty/test-cleaned data volume after acceptance, preserving quota. Any removal of test records follows an explicitly approved disposable-data workflow.

This is a feasible quota sequence, not a completed restore. If restore is unavailable, preserve the backup and pause release; never buy temporary storage. With live data, do not repeat source removal as a routine drill: a parallel 150 GB restore would total 350 GB and exceed quota. Plan a separately approved recovery exercise or choose a smaller pool with parallel headroom. Actual recovery after source failure requires preservation of backup and fresh destructive-action approval.

Stage 1 does not need to provision a VM just to prove its planning assumptions. Stage 7 requires actual restoration before release and Stage 8 requires scheduled backup evidence after deployment; those gates remain unchanged. Without a backup destination now, sample encryption/restore cannot honestly pass in Stage 1.

## Executed tests and stage boundary

Source review and signed-in draft inspection performed. Arithmetic tests cover 31-day compute, disk allocations/reserve, empty/80%/90%/full usage, simultaneous reservations, retained replacement rejection, unchanged trash bytes, slot rotation, failed/fifth/extra backup behavior, full-size restore quota sequence, ordinary-bucket insufficiency and high churn. Document link/checkbox consistency is validated separately.

Unexecuted: physical capacity/provisioning, exact resource billing, ARM64 application/container compatibility, real DNS ownership/update/renewal, email subscription/delivery, firewall/SSH connectivity, backup consistency/duration/full restore. These are explicitly recorded deployment/recovery gates; no checkbox should imply they passed.

Stage 1 original checklist includes account-wide resource reconciliation, owner acceptance, and a sample backup/restore when a destination is available. Existing evidence supports a conditional development recommendation; it does not establish every gate as passed. The assessment is ready for owner review. Stage 1 remains open for acceptance and any remaining resource-specific uncertainty; do not mark it complete just because analysis is finished.

## Concrete next approval proposal

Approve this feasibility assessment for local Stage 2 work, with the documented residual risks and later resource gates. Stage 2 scope: `frontend/`, `backend/`, `infrastructure/`, `scripts/`, root Compose/README/ignore examples and `docs/` architecture/API/security/testing contracts; pin compatible dependencies and set up lint/build/test tooling. Use disposable local PostgreSQL/file volumes and safe templates, with no production secrets or cloud writes. Main risk is local runtime/dependency compatibility (Docker was not found on PATH), which must be checked before declaring the foundation working. No automatic installation, cloud creation, main merge or deployment is implied by this approval proposal.
