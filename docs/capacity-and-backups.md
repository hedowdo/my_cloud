# Stage 1 — capacity, hosting and backup feasibility

Date: 2026-10-20 (Africa/Cairo). Status: IN PROGRESS; public-source review, arithmetic and owner-provided console evidence. Owner created an account; no resources created by the agent, no credentials requested. See `plan.md` and `decisions.md`.

## Evidence and conclusion

Owner completed signup after the initial investigation, confirmed Jeddah and shared a Free Tier account banner showing trial status. Latest screenshot: scope `me-jeddah-1`, root compartment; `standard-a1-core-regional-count` limit 16/usage 0/available 16; `standard-a1-memory-regional-count` limit 96/usage 0/available 96. The screenshot does not label the memory unit. These account quotas do not establish the permanent free entitlement or physical host capacity. Trial expiry, disk/backup usage and exact configuration cost remain open.

Additional owner screenshot (2026-10-20): Block Volume service, regional scope `me-jeddah-1`, root compartment. `total-free-storage-gb-regional`: limit 200 GB, usage 0, available 200. `free-backup-count`: limit 5, usage 0, available 5. General `backup-count`: limit 100,000, usage 0, available 100,000. The latter is not a free allowance. This is console quota evidence for the displayed scope; exact resource eligibility and successful backups/restoration remain separate gates.

Subscription screenshot (2026-10-20) confirms plan type Free Tier, account type Promo and start date 2026-10-20. Expected calendar trial expiry is approximately 2026-11-19, calculated from the start date using the [official 30-day rule](https://docs.oracle.com/en-us/iaas/Content/GSG/Tasks/signingup_topic-What_Happens_When_the_Promotion_Expires.htm); exhaustion of credits can end it sooner. Exact expiry time was not shown. Retain only these non-sensitive subscription facts, not personal identifiers visible in the screenshot.

There is no separate daily-reachable backup storage. Evaluate OCI backups first. This selects an investigation path, not acceptance of provider-loss risk or approval to provision.

Published limits make the proposed single-VM deployment plausible at $0. End-to-end feasibility remains unverified until account eligibility, home-region resources, exact configuration, backups and restoration are tested. No permanently unchanged pricing or uninterrupted availability is guaranteed.

| Evidence ID | Official source reviewed on 2026-10-20 | Finding and limit of evidence |
| --- | --- | --- |
| S1 | [Always Free resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm) | Arm: 1,500 OCPU-hours/9,000 GB-hours monthly, equivalent to 2 OCPUs/12 GB. Combined boot/block allowance 200 GB; five combined volume backups; Always-Free-only bucket storage 20 GB; outbound allowance 10 TB/month. Ubuntu is listed. Home-region restrictions, shape availability and idle reclamation apply. Does not establish account eligibility. |
| S2 | [Free Tier lifecycle](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier.htm) | Always Free continues separately from the limited trial. Trial resources/credits cannot justify long-term $0. Stay unupgraded unless explicitly approved. |
| S3 | [Block Volume backups](https://docs.oracle.com/en-us/iaas/Content/Block/Concepts/blockvolumebackups.htm) | Encrypted regional backup storage, incremental backups and policies are supported. Restore and application consistency need testing; provider-managed encryption does not protect against account loss. |
| S4 | [OCI budgets](https://docs.oracle.com/en-us/iaas/Content/Billing/Concepts/budgetsoverview.htm) | Budgets are soft spending limits, evaluated periodically, not a hard $0 cutoff. |
| S5 | [Duck DNS FAQ](https://www.duckdns.org/faqs.jsp) | Free dynamic DNS and scripted updates are advertised. No subdomain reserved, DNS control or continued availability proven. |
| S6 | [Caddy automatic HTTPS](https://caddyserver.com/docs/automatic-https) | Public DNS, reachable challenge ports and persistent certificate data support automatic issuance/renewal. No actual certificate issued or renewal tested. |
| S7 | [OCI price list](https://www.oracle.com/cloud/price-list/) | Reviewed as a pricing cross-check; fetched page leaves many price cells empty. Exact public IP, performance and optional-service rates were not verified from this rendering. Obtain console/account evidence before any provisioning. |

## Candidate resource and cost ledger

Every line is proposed, not provisioned or owner-approved. A1 regional usage is zero in the supplied screenshot; other account-wide resource usage remains unverified.

| Component | Candidate configuration | $0 gate / failure response |
| --- | --- | --- |
| Compute | One eligible Ubuntu ARM64 A1 VM; up to 2 OCPUs/12 GB | Verify exact shape/image and home-region capacity; no paid fallback or upgrade. Validate application/container compatibility later. |
| Compute usage | At maximum proposal: 2 x 744 = 1,488 OCPU-hours and 12 x 744 = 8,928 GB-hours in a 31-day month | Below S1 allowances, assuming no other usage. Restarts/extra instances must not add uncounted usage. |
| Boot disk | Conservative 50 GB | S1 differs on minimum boot size in its sections; confirm actual console units and eligibility. Monitor OS/images separately. |
| Data disk | 150 GB | Combined proposal 200 GB; verify free label, account usage and exact performance cost. Disable unapproved performance auto-tuning/replication. |
| Backups | Native data-volume backup, four retained recovery points plus one in-flight slot | Shared allowance across boot/data backups; eligibility and policy behavior must be proven. No cross-region copies or paid overflow. |
| Network | Public VM, direct internet gateway, Caddy; private container DB | Confirm exact address/network charges. No managed load balancer/NAT/private endpoint required by proposal. |
| Egress | Warn well below verified free amount; proposal: 8 TB warning, 9 TB controlled transfer ceiling per month | Account-wide downloads and independent copies count. Ceiling implementation/units need approval; do not terminate in-progress writes unsafely. Provider usage reporting may lag. |
| DNS/TLS | Candidate Duck DNS + Caddy | Verify signup/hostname, DNS update control, ACME staging and renewal. No purchased domain assumed. |
| Alerts/logging | Bounded local logs; evaluate OCI notification email plus an external health check | No alert destination configured; verify current free limits and path that survives VM failure. No paid observability subscription. |

Do not accept a positive cost estimate on the assumption it will be waived later. Resolve discrepancies with explicit free eligibility/account evidence. Signing up, choosing a region and provisioning are distinct steps.

## Storage budget and admission model

Planning units: decimal GB (1,000,000,000 bytes); file limit 500 MB = 500,000,000 bytes. Provider/display units must be reconciled at provisioning. Actual filesystem capacity overrides nominal values.

| Volume/budget | GB | Notes |
| --- | ---: | --- |
| Boot | 50 | OS, images and bounded system logs |
| Data: user pool | 100 | Active files + trash + replacement recovery copies + icons |
| Data: DB/application logs | 10 | Proposed bound; no unapproved deletion of activity history; revise capacity before this fills |
| Data: emergency reserve | 20 | Uploads may not consume this reserve |
| Data: transfer/backup workspace | 10 | At least 2 GB for four maximum concurrent uploads; backup must not assume another full local copy |
| Data: filesystem/uncertainty margin | 10 | Replace with observed headroom later |
| Total | 200 | Data sub-budgets total 150; no spare cloud allocation for a second full data volume |

Track committed pool bytes `C`, final-file upload reservations `R`, and new requested bytes `N`. Admit only if `C + R + N <= 100 GB`, the appropriate workspace reservation fits, and actual free bytes remain above emergency reserve plus unmaterialized writes/workspace and uncertainty margin. Avoid double-counting reservations already materialized on disk. Recheck while streaming. Folder metadata/database growth also needs disk-level protection.

Warnings use committed plus reserved pool usage to give early notice: 80 GB and 90 GB. Show committed and in-flight bytes separately. Proposed concurrency: four uploads globally, two per user. Reserve workspace separately from final-file quota; streaming/atomic rename should not create an unnecessary second final copy. Reject unknown-size streams before crossing allowed byte/quota boundaries.

### Executable arithmetic scenarios

These are model checks, not API/storage tests. Input quantities below are decimal GB; enforcement is future work.

| Case | Calculation | Expected decision |
| --- | --- | --- |
| Empty pool | C=0, R=0, N=0.5 => 0.5 | Pool permits; disk/workspace checks still required |
| 80% warning | C=79.5, R=0.5 => 80 | Warn at 80%; no 90% warning |
| 90% warning | C=89.5, R=0.5 => 90 | Warn at both thresholds |
| Concurrent boundary | C=98.5, R=1, N=0.5 => 100 | Permit exactly; subsequent 0.5 upload rejected |
| Pool exhausted | C=100, N=0.5 => 100.5 | Reject regardless of unused system reserve |
| Replacement near full | C=99.8 including old file, N=0.5 => 100.3 | Reject; retained old content prevents subtracting it from C |
| Trash | Move 10 from active to trash | C unchanged; restoration also unchanged unless extra icon/bytes created |
| Inadequate free disk | Pool fits, but physical free space below required reserve/workspace | Reject; pool capacity cannot override filesystem safety |
| Native backup slots | Four good backups + next backup => five | Only prune oldest after new backup is verified; failed fifth does not delete good copies |
| Unrelated boot backup | Four retained data + one boot + next => six | Block schedule/configuration until slot policy resolved; no assumed free sixth backup |
| Full native restore | 50 boot + 150 source + 150 restore => 350 | Reject additional volume; 150 GB above the published total |
| Ordinary bucket baseline | 100 incompressible > 20 | Reject bucket-only protection for 100 GB |
| Independent churn example | 100 baseline + 56 retained changes + 20 margin => 176 | Fits hypothetical 200 GB destination; none exists here |
| Higher churn example | 100 baseline + 100 retained changes + 20 margin => 220 | Does not fit hypothetical 200 GB destination; reduce retention/capacity only by owner decision |

The 20 GB reserve and workload limits remain engineering proposals; Stage 2/4 runtime tests must prove memory/backpressure, disk behavior and DB needs before production. Stage 1 accepts a budget model, not measured application performance.

## OCI backup proposal for owner review

Evaluate Option A first. All persistent application state (DB, blobs/icons/recovery items and encrypted configuration recovery material) must be recoverable from the data volume; boot environment is rebuilt from versioned configuration. Backup encryption/recovery instructions must not depend solely on the lost VM. Secrets and private keys stay outside Git and chat.

Proposed daily sequence: prevent new mutations, drain transfers, put DB/files into a tested consistent state, initiate capture, resume at the documented safe point, monitor completion, verify backup status, then rotate only eligible old backups. Failed capture preserves the last known good backups and alerts. Implement least-privilege backup permissions and an outside-VM alert path later. Native policy scheduling alone cannot guarantee coordinated application consistency; use an approved coordinator if needed.

Retain four successful daily data recovery points and reserve the fifth slot for the next capture, assuming no unrelated backups. Define retention by successful recovery points, not blindly by elapsed age. Backups are not ordinary free-bucket objects in this plan; confirm resource eligibility rather than transferring them into a 20 GB bucket.

Residual risk: all copies remain in the same Oracle account/provider/region. This is distinct from same-disk backup, but does not survive every account/provider disaster or operator compromise. Owner acceptance of this limitation is pending. No independent destination has been found or claimed.

Daily scheduling targets roughly a 24-hour recovery interval. A strict maximum 24-hour RPO is not yet proven: completion lag, missed jobs and long captures can make the latest completed point older. Monitor the age of the latest recoverable capture, alert before it exceeds the approved limit, and measure duration in Stage 7. Owner must approve the achievable RPO; no guaranteed recovery time is stated.

## Restore rehearsal and deployment dependency

Native backups require cloud restoration; a local generic file-copy test cannot validate that mechanism. With full 50+150 GB allocation, no quota remains for a parallel restore. Initially test disposable 50 GB source + 50 GB restore + 50 GB boot = 150 GB after separate cloud approval. This proves a small native restore, not 150 GB recovery.

Full-size restore validation requires an approved procedure: restore after releasing a disposable source volume with no real user data, or preserve quota through an owner-approved reduced-capacity layout. Any release/delete is separately approved and must preserve the verified backup; never destroy real user data merely to complete a test. Rebuilding a VM may also be blocked by shape capacity. Do not declare complete Stage 7 recovery on the basis of the small test alone.

Arithmetic and documentation can be validated now. Actual sample backup, restore, DNS and TLS testing remain unchecked because no approved host/destination is configured. Early disposable cloud tests require a revised, explicit configuration/cost approval; they do not authorize production deployment.

## Account verification worksheet — signup complete, evidence incomplete

- [x] Owner completed signup; screenshot shows Free Tier currently in trial. No passwords, payment details, API keys or recovery codes shared.
- [x] Owner reviewed Saudi/Milan choices and confirmed Jeddah; supplied screenshots show `me-jeddah-1`. Recommendation used proximity, not measured latency or guaranteed free capacity.
- [x] Reviewed regional A1 quota screenshot: core limit/available 16, memory limit/available 96, both usage 0. Proposal remains no more than 2 OCPUs/12 GB under current published Always Free terms; a higher quota is not a higher free allowance.
- [x] Reviewed regional/root Block Volume screenshot: free storage quota 200 GB and free backups 5, both unused; general backup quota 100,000 is not free. Proposed 50+150 GB and four-retained-plus-one-slot arithmetic fits the displayed free quotas; no resources provisioned or recovery tested.
- [ ] Record only non-sensitive evidence: account category/trial expiry, home region, eligible limits/usage, existing boot/data volumes and backup counts across compartments, and billing/estimate outcomes.
- [x] Record subscription evidence: Free Tier / Promo, start 2026-10-20; calculated expected calendar trial end around 2026-11-19, subject to credit exhaustion. Exact expiry timestamp not verified; no identifiers or payment data retained.
- [ ] Review exact candidate shape/image/volume performance/public IP/network/backup eligibility in the console without launching resources. A displayed limit is not proof of host capacity; creation remains a later approval gate.
- [ ] Resolve any estimate/eligibility discrepancy before provisioning; confirm no account upgrade or paid fallback is selected.
- [ ] Owner chooses backup retention/failure-domain risk, capacity/defaults, and free DNS hostname preference. No hostname availability claimed until checked.
- [ ] Verify an available free alert delivery path and plan tests for host-down and backup-failed cases.
- [ ] Record Stage 1 owner acceptance after the account/resource ledger is reconciled. Stage 1 remains incomplete until required checks pass.

## Executed evidence and remaining limits

Signed-in draft inspected on 2026-10-20; see [OCI draft review](oci-draft-review.md). Ubuntu ARM64/A1 shape/free label, 2 OCPUs/12 GB, explicit 50 GB boot/10 VPU/encryption and EUR 1.98 pre-tier estimate observed. No Create/Save as stack action, no actual allocation, and no verified physical capacity. Network/SSH and optional plugin choices remain incomplete. This supersedes earlier statements that only owner-provided account screenshots had been inspected.

2026-10-20: reread `AGENTS.md` and `docs/plan.md`; inspected repository/docs and local tool availability. `Get-Command` did not find OCI CLI or Docker on PATH; default `~/.oci/config` absent; OCI auth/config-file environment overrides absent. No secret file contents were read. Initially no account existed; owner subsequently completed signup and supplied the console evidence above. No authenticated CLI access is configured.

Official sources S1–S7 were read. S7 did not expose complete numeric pricing, so no exact billable-rate claim is made. Arithmetic scenario execution and document validation will be recorded in `plan.md`. No API, real disk exhaustion, backup, restoration, DNS, TLS or cloud capacity tests have run.
