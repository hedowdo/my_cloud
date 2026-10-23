# Proposed host software and hardening changes

Date: 2026-10-23 (Africa/Cairo). Owner asked to finish deployment. Automatic approval review rejected the combined host modification command before execution, requiring explicit approval for its persistent changes and possible connection/service impact. No installer or hardening step from that command ran. This proposal does not create/resize a cloud resource, upgrade the OCI account, publish the application, send notifications or reboot the host.

## Exact changes requiring approval

1. Update the Ubuntu package index and install ca-certificates, curl and gnupg if missing. Configure Docker's official signed Ubuntu Noble ARM64 apt repository with a dedicated scoped signing-key file. Install Docker Engine, CLI, containerd, Buildx and Compose from that repository. This starts/enables the Docker daemon. No broad distribution upgrade, automatic paid service or convenience installer is included. Record the actual package versions.
2. Add a systemd Docker dependency on the already approved /srv/my-cloud-data mount, so Docker startup waits for the data filesystem. Add default container log limits of three 10 MB files. Do not move or remove existing storage or add the login user to the root-equivalent docker group.
3. Disable the observed unused rpcbind service/socket to remove its port-111 listener. Leave SSH running and preserve existing public-key access.
4. Add an SSH configuration drop-in: PermitRootLogin no, PasswordAuthentication no, PubkeyAuthentication yes. The existing ubuntu key login already works and password authentication is already off. Validate with sshd -t before reload, then verify a fresh independent ubuntu SSH connection. Do not stop SSH, replace authorized_keys or remove the existing key. This has a residual connection/lockout risk if configuration or service reload behaves unexpectedly; recovery could require the OCI console.
5. Bound system journal storage to 500 MB persistent/100 MB runtime and restart only journald. Verify Docker/Compose, mount dependency, effective SSH settings, retained data-volume ownership and a new key login. No host reboot or public application start is included.

Existing server is a newly created ARM64 Ubuntu VM without an application or Docker; only SSH and system services have been observed. The approved data volume is mounted and its UUID/remount/permissions already passed. Recheck those conditions before executing. Keep command logs private and update the plan/evidence after actual results. Do not represent this document as execution or owner approval.

[Official Docker installation procedure](https://docs.docker.com/engine/install/ubuntu/), [deployment plan](deployment.md), [Stage 8 evidence](stage-8-verification.md).

Owner approved this exact proposal with "go ahead" on 2026-10-23. Installation and fresh-login/native Docker checks passed; see stage-8-verification.md. No public application start or reboot was part of this approval.
