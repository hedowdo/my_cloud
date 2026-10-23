# Stage 1 — OCI draft inspection

Date: 2026-10-20 (Africa/Cairo). Status: draft inspected; no resources created, stack saved or application code written. Stage 1 remains incomplete. Governing documents: `plan.md`, `capacity-and-backups.md`, `decisions.md`.

## Observed console evidence

Signed-in Jeddah console inspected through the in-app browser at the owner's request. The root-compartment Instances list displayed no items. This does not prove every compartment/resource type is empty.

Opened the Create compute instance form and changed only the unsubmitted draft. Selected Canonical Ubuntu 24.04 Minimal aarch64, build 2026.09.18-0, listed as Free in the image picker. The compatible shape was VM.Standard.A1.Flex, labeled Always Free-eligible. Set and verified 2 OCPUs and 12 GB memory in both picker and final review. Burstable performance was not enabled.

The CPU change triggered an automatic memory update; the first text fill briefly produced invalid 1212 GB. Validation rejected it and disabled Select shape. Cleared/re-entered the field, committed it with Tab and verified 12 GB and no memory error before applying the shape. No provisioning occurred during this transient form-validation error.

Storage default displayed 46.6 GB. Enabled an explicit custom 50 GB boot volume; reviewed 10 VPU Balanced performance and in-transit encryption enabled. No data volume attached. Planned 150 GB data volume is still a proposal, not part of a created environment.

## Cost evidence and interpretation

Initial default boot estimate was EUR 1.85/month. After explicit 50 GB selection, the estimate was EUR 1.98/month, entirely attributed to boot volume; no separate compute amount shown. The dialog explicitly says tier unit pricing is excluded. [Saved screenshot](evidence/oci-draft-cost-2026-10-20.jpg).

Oracle documents that console estimates exclude tier unit pricing and omit other resource costs; its separate estimator supports a 200 GB Free Tier storage discount. [Official estimate guidance](https://docs.oracle.com/en-us/iaas/Content/Billing/Tasks/signingup_topic-Estimating_Costs.htm).

Inference: the estimate is consistent with a pre-discount storage calculation, given the documented combined free storage and the owner's screenshot showing 200 GB unused free quota. This is not proof of a zero bill or a quote for the whole architecture. Exact volume eligibility, performance/network choices, optional plugins and any unrelated usage must be reconciled before provisioning. Do not ignore a cost simply because credits would cover it.

## Why this draft is not ready to launch

- Final review shows Public IPv4 address: No, SSH keys: absent. Networking drafts propose a new VCN/public subnet but are not configured for the approved production access model. No credential files downloaded; no persistent access installed.
- Final review shows optional Cloud Guard Workload Protection enabled by default, plus monitoring/logging/run-command agent settings. No corresponding service/IAM policy was enabled by the agent. Verify their dependency, eligibility, privacy and potential charges; do not infer that a plugin toggle alone means a service is activated or free. [Oracle Cloud Agent](https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/manage-plugins.htm), [Oracle Cloud Guard overview](https://www.oracle.com/security/cloud-security/cloud-guard/).
- Secure Boot, Measured Boot and TPM are off in the draft; assess image/shape support and the security baseline before production. Existing live security settings were not modified.
- No 150 GB data disk, coordinated daily backup, DNS/TLS, alerts or tested recovery exists.
- Shape visibility/free label does not prove physical capacity; no launch request was made to test capacity.
- Owner acceptance of the backup failure-domain trade-off and proposed defaults is still pending. No cloud approval has been requested for this incomplete configuration.

## Recommendation and next gates

Recommend one Ubuntu ARM64 A1 VM at 2 OCPUs/12 GB, 50 GB boot + 150 GB data, with a target 100 GB shared pool including trash/replacement recovery/icons. Evaluate four retained successful daily native data-volume backups and one in-flight slot. Prove consistent restoration before important data is accepted. This is the practical candidate under the verified quotas, not a guarantee of persistent free capacity or provider-independent recovery.

If the owner accepts that backup design, record the decision and finish Stage 1 cost/access/default checks. Local development should precede production deployment as planned. Any early disposable cloud restore test needs a concrete separate resource/cost approval and quota-safe procedure. Maintain the full-size restore gate; no payment, upgrade or independent-storage subscription is implied.

When asked to accept backup limitations, owner instead asked for a recommendation. Recommendation was given; acceptance has not been inferred.

## Verification

Actual browser review reached the final Review step, verified CPU/RAM/boot settings, and captured the final estimate. Final Create and Save as stack were not clicked. Screenshot was inspected locally. No host, network, disk, application or backup runtime tests have run. Documentation link, evidence-file, stage-checklist and whitespace checks are recorded in `plan.md`.
