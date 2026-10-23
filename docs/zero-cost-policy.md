# Zero-cost operating boundary and recommended compromise

Date: 2026-10-20 (Africa/Cairo). Owner instruction: "make sure i do not pay anything, and come up with the best solution or best compromise as u recommend". This authorizes selecting a planning recommendation within the $0 constraint. It is not approval to create the incomplete OCI draft, change access, upgrade the account, or implement application code.

## Selected planning recommendation

Keep the existing non-upgraded Free Tier account. One Jeddah Ubuntu ARM64 A1 VM at no more than 2 OCPUs/12 GB, conservative 50 GB boot plus 150 GB data, and a target 100 GB counted shared pool. Count trash, replacement recovery and icons in the pool. Preserve disk reserve and measure usable capacity before opening the pool to users.

Use OCI native incremental daily data-volume backups, four successful recovery points retained with the fifth slot reserved for the next capture. This is the recommended initial compromise because no independent backup destination exists and an ordinary 20 GB bucket cannot protect an arbitrary 100 GB baseline. Backups remain in Oracle's account/provider/region. There is no claim of protection against losing that account or guaranteed 24/7 service. Verify app-consistent recovery before important files are accepted. Add an independent destination only if its permanently free capacity and operational costs are established and approved.

This preserves the shared file manager, desktop spatial dashboard and mobile file list requirements. The compromise concerns infrastructure availability and backup independence, not replacing the requested application with a weaker product.

## Mandatory spending boundary

- Never upgrade or convert the account to Pay As You Go/paid subscription. Do not add payment arrangements, accept paid add-ons or authorize charges. Check account category again before any resource action.
- Do not use trial credits as evidence that a resource is acceptable. Each component must independently qualify for ongoing Always Free usage.
- No paid fallback for missing A1 capacity. Prefer waiting or an explicit revised plan; never select a different paid shape automatically.
- Stay within the verified account-wide free CPU, memory, combined disk, backup and transfer allowances. Additional instances, restores, boot volumes, backups and unrelated resource usage must be included, not just the main VM.
- Do not activate unverified services/plugins, managed databases, managed firewalls, paid domains, paid monitoring, cross-region copies or other optional services. A toggle labeled Enabled in an unsubmitted draft does not establish pricing or actual activation. Review and exclude unnecessary optional integrations from the eventual approved baseline while retaining application/host security controls.
- No auto-scaling, automatic performance upgrades, volume growth, cross-region replication, paid backup overflow or automatic paid renewal. Capacity exhaustion must refuse new work safely instead of acquiring resources.
- Alerts and quota controls supplement explicit resource checks; budgets are soft limits, not a hard $0 billing switch. Do not advertise an automatic spending guard as implemented: no such controls have been configured yet.
- If a current charge, credit-consuming paid SKU or ambiguous eligibility appears, stop the affected operation and investigate; do not deploy and hope it is free. Do not automatically delete data or stop a live service as a billing workaround.

Oracle states that a credit card is not charged unless the account is upgraded; keeping this account non-upgraded is the principal account-level protection. This is a documented provider rule, not a guarantee by the agent about bank/provider behavior or future terms. [Oracle Free Tier documentation](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier.htm).

Trial resources can be reclaimed and free capacity may be unavailable. [Oracle Free Tier FAQ](https://www.oracle.com/cloud/free/faq/). Choosing $0 may therefore mean waiting or service interruption rather than paying. No uptime SLA or perpetual unchanged allowance is promised.

## Interpreting the current positive estimate

Observed final draft: boot volume EUR 1.98/month, 50 GB/10 VPU, with no tier pricing reflected. [Screenshot](evidence/oci-draft-cost-2026-10-20.jpg). Oracle describes these console estimate limitations and the separate estimator's Free Tier discount. [Estimate documentation](https://docs.oracle.com/en-us/iaas/Content/Billing/Tasks/signingup_topic-Estimating_Costs.htm).

The account screenshot confirms 200 GB unused free volume quota, making a free-allowance interpretation plausible. Still, no positive estimate is accepted blindly: verify exact resource eligibility, performance settings, account consumption and optional service dependencies before the resource-specific approval. A forecast or label cannot prove a bill in advance.

## Gates before a resource proposal is ready for approval

- [x] Owner's strict $0 instruction recorded, including preference for a recommended compromise.
- [x] Non-upgraded Free Tier/Promo account and Jeddah evidence reviewed; published free allowances and console quotas recorded.
- [x] Candidate shape/image/CPU/memory/boot draft inspected; positive estimate and its exclusions recorded honestly.
- [ ] Reconcile every proposed SKU/dependency against ongoing free eligibility, including disk performance, public access and optional agent integrations.
- [ ] Present the exact network/firewall/SSH credential procedure with least privilege; no broad default SSH exposure or credential installation implied.
- [ ] Finalize a quota-safe backup/restore test procedure before production use, including separately approved disposable source-volume release if needed. A 150 GB parallel restore exceeds the fully allocated 200 GB disk pool.
- [ ] Finalize no-cost DNS/HTTPS and outside-VM alert route; verify availability when those accounts/hosts exist.
- [ ] Present a concrete resource/cost configuration and obtain explicit approval immediately before provisioning. Plan selection is not this approval.

Later tests must prove denied oversize/concurrent uploads, reserve protection, safe backup-slot rotation, recovery checksum consistency and transfer-limit behavior. They are not implemented or passed during Stage 1. Preserve all existing milestone test gates in `plan.md`.
