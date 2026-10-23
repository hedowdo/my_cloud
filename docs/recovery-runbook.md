# Recovery runbook — local tooling and pending OCI acceptance

Stage 7 local implementation is authorized. No cloud resources, production cutover, backup deletion policy activation or external notification sending is authorized by this document. Actual native daily backups are not configured. See [verification](stage-7-verification.md) and [cost boundary](zero-cost-policy.md).

## Recovery material and key custody

Keep the release source/locks, immutable image references, migration revision, Compose/proxy settings, database credentials and auth secret recoverable together. Keep the independent recovery key outside both the archive and the primary failure domain. Never upload it into chat, Git, a public bucket or the application's shared files. The key under ignored Stage 7 test evidence is synthetic and is not a production key.

Generate at least 48 random bytes encoded as a single line for a real recovery key. Protect files/directories with owner-only access (0600/0700 on Linux); use OS credentials rather than an argument containing a secret. The CLI reads the key file and passes its value to GnuPG through a private input pipe. Retain the key for every retained recovery point. A changed key or unknown archive blocks the local job until reviewed; never discard an old key simply because the next backup succeeded. Test the independently retained key on a separate recovery system before relying on it.

The local bundle uses GnuPG symmetric AES-256 and integrity verification, not custom cryptography. Wrong keys or corrupted ciphertext must fail before exposing a restored directory. Archives include a versioned SHA-256 manifest; traversal, links, unexpected/duplicate entries, size violations and checksum mismatches are rejected. Restores require a new destination and never overwrite an existing tree. On Windows a bounded retry handles a verified transient directory-publish denial; it does not change permissions or overwrite a competing destination.

The installed Git GnuPG 2.2.29/libgcrypt 1.9.3 was used only for synthetic local rehearsal. It has not been approved as a production cryptographic dependency. Select and audit a current vendor-supported Ubuntu package at the deployment gate. See [GnuPG commands](https://www.gnupg.org/documentation/manuals/gnupg/Operational-GPG-Commands.html) and [project distributions](https://www.gnupg.org/download/).

## Local rehearsal commands

`scripts/recovery_bundle.py` is deliberately a bounded local rehearsal tool, not the proposed 100 GB backup implementation. Payload admission is capped at 256 MB; the integration harness additionally caps its fixture at 64 MB. It temporarily needs plaintext scratch space under private directories. It does not create a consistent application snapshot itself, refresh a supplied snapshot, call OCI, upload data, send notifications or install a schedule.

Examples below use an already captured, immutable sample snapshot. They do not operate on a live PostgreSQL data directory or live shared files.

```sh
python3 scripts/recovery_bundle.py run --source /srv/cloud-rehearsal/snapshot --target /srv/cloud-rehearsal/repository --key-file /run/credentials/recovery.key --gpg /usr/bin/gpg
python3 scripts/recovery_bundle.py check --target /srv/cloud-rehearsal/repository
python3 scripts/recovery_bundle.py open --source /srv/cloud-rehearsal/repository/POINT.gpg --target /srv/cloud-rehearsal/NEW-restored-directory --key-file /run/credentials/recovery.key --gpg /usr/bin/gpg
```

The job verifies retained archive digests and key identity, reserves its exclusive lock, encrypts and decrypt-verifies the new point, durably publishes it, then retains four good points. A fifth slot is needed during capture. Failed capture never prunes the last good points. An interrupted lock, unknown point, corruption or incomplete retention requires operator reconciliation; do not blindly remove a lock or delete an unfamiliar backup. Verify the index, archive digest, key and restore result first.

`state.json` reports the latest job outcome. `alert.json` is a bounded last-failure record, not a delivered notification or necessarily the current health; correlate its timestamp with current state. `check` exits 0 when the recorded local job is healthy, 3 for missing/stale/failed state, and 1 for operational failure. The 26-hour age threshold is a local rehearsal setting. It measures job age, not the age of the supplied application's data. Re-encrypting an old static sample is not a new application recovery point or proof of a daily application backup.

The four units under `infrastructure/backup/` are disabled sample-rehearsal templates. They require an explicit REHEARSAL_ONLY sentinel, dedicated nonprivileged user, existing paths, a supported GnuPG package and protected key credentials. They parse as configuration but have not been installed, verified by systemd-analyze on a target host, enabled or exercised by an actual timer. They propose a daily 03:00 UTC rehearsal and a 15-minute status check. An outside-VM watchdog and actual notification delivery remain mandatory live acceptance work. The monitor returns failure to systemd on an alarm; no external notification is sent. References: [systemd timer semantics](https://www.freedesktop.org/software/systemd/man/260/systemd.timer.html), [service sandboxing](https://github.com/systemd/systemd/blob/main/man/systemd.exec.xml).

## Exact local integration rehearsal

Run `scripts/verify_recovery_compose.py --gpg PATH` only against its explicitly guarded synthetic loopback project. It checks local Docker context and fixture identity, briefly stops the API, dumps PostgreSQL, copies generated object/staging storage, captures private development configuration and source, and resumes the API in a finally block. It encrypts the immutable snapshot, opens it into a new host directory, restores into a new database owned by cloud_migrator, and restores files as the existing unprivileged API user. It compares every public table's sorted-row hash, all snapshot hashes, durable blob/icon checksums, restored administrator login and future migration permissions.

PostgreSQL roles must already exist from the reviewed init-roles configuration. For a fresh isolated database, create it with cloud_migrator as owner; restore with `--no-owner --role=cloud_migrator --exit-on-error`, revoke public database access, and grant only required roles. Do not restore as the runtime cloud_app role or leave tables owned by the database administrator. The rehearsal checks a disposable create/alter/drop probe after restoration. A logical dump does not independently preserve cluster-global roles; rebuild those from protected configuration. [PostgreSQL pg_dump scope](https://www.postgresql.org/docs/16/app-pgdump.html).

Never restore over the primary database/files to prove a test. The harness retains isolated databases/paths and private evidence. Its plaintext source/decrypted fixtures include development secrets; keep `.local/` private and ignored. Existing primary volumes are preserved. No test key or fixture credential is suitable for production.

## Approved-design OCI sequence — implementation/live validation pending

1. Reverify non-upgraded account, home region, ongoing eligibility, all disk allocations, all boot/data backup resources across relevant compartments, free slot headroom and exact configuration. Resolve any positive/ambiguous estimate before resource-specific approval. No trial-only service, paid fallback or automatic extra volume.
2. Put all persistent DB/blob/config recovery material on the approved data volume, not accidentally on the boot disk through default Docker storage. Capture a versioned manifest and encrypted configuration recovery material; protect the independent key separately.
3. With a reviewed native coordinator and least-privilege IAM, prevent new mutations, drain/stop API writes, checkpoint/cleanly stop PostgreSQL and sync the data filesystem. Use a durable run identifier/idempotency token so an unknown request outcome cannot create duplicate resources.
4. Initiate only the approved native data-volume backup. Oracle documents that writes can resume after REQUEST_RECEIVED changes to CREATING. Resume services safely; if that transition cannot be established, preserve existing good points, flag the new point unverified and reconcile before retrying. Validate this on the actual host. [Application-consistent backup guidance](https://docs.oracle.com/en-us/iaas/Content/Block/Concepts/blockvolumebackups.htm).
5. Poll to AVAILABLE, confirm the expected volume/region/capture identity, then apply the approved four-good-point retention. Pure slot/rotation rules are tested locally; the native adapter is not implemented/activated. Never delete unrelated backups or prune good points on failed capture. Retention activation requires resource-specific approval.
6. Monitor both failed/missed capture and the age of the latest usable data recovery point from outside the VM. Test delivery, host-down, destination/full-slot failure, interrupted capture and recovery. Approve measured RPO/RTO; do not treat the local 26-hour job threshold as an approved production RPO.

Oracle currently documents 200 GB combined free boot/block storage and five combined volume backups in the home region, with encryption at rest. This supports the proposal only; it does not verify this tenancy's current consumption, physical availability or final charges. [Always Free resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm), [backup encryption](https://docs.oracle.com/en-us/iaas/Content/Block/Concepts/blockvolumebackups.htm).

## Full recovery, rollback and release gates

With 50 GB boot + 150 GB source allocated, a parallel 150 GB restored volume would total 350 GB. Do not create it under the 200 GB plan. Obtain separate approval for a quota-safe disposable source/restore drill or a revised allocation, preserving all real data and a verified recovery point. A small native drill is not full-size restoration evidence. Oracle account/region/provider loss remains outside this single-provider compromise.

For cutover, restore first into isolated storage/database, verify manifests/content/icons/users/positions/trash/recovery copies, test migration ownership, and approve the exact switch. After an incident, assess credential rotation and revocation of restored sessions/open invitations before public access; this avoids trusting stale pre-incident revocations. These actions require owner-controlled cutover; they are not performed by the local harness.

Record immutable current/previous image references and retain versioned source/configuration. `verify_frontend_rollback.py` tests two already-local immutable frontend artifacts in labelled loopback-only containers with tmpfs and no data mounts, then removes only those test containers. It proves assets, proxy health and anonymous auth denial, not production cutover or arbitrary backend/schema compatibility. Never blindly downgrade a populated schema. Rehearse the release's backup/restore or compatible code rollback on a copy, then obtain separate deployment/merge approval.

The current Compose profile is explicitly development-only, uses loopback HTTP and named local volumes, and is not deployable as production. Public TLS/DNS, production startup settings/secret provisioning, data-volume binding, firewall/SSH, outside-host monitoring, image/OS advisory review and ARM64 runtime verification remain gates. Do not enable these sample timers and call Stage 7 complete.
