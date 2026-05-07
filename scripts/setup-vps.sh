#!/usr/bin/env bash
###############################################################################
# scripts/setup-vps.sh
#
# Idempotent provisioning script for a fresh Ubuntu 24.04 VPS (root).
# Installs Docker, configures UFW + fail2ban, hardens SSH, creates the deploy
# user and writes them an authorized_keys file.
#
# Usage:
#   scp scripts/setup-vps.sh root@164.92.240.90:/tmp/
#   ssh -p 22 root@164.92.240.90 'DEPLOY_USER=nurbek SSH_PORT=2222 bash /tmp/setup-vps.sh'
###############################################################################
set -euo pipefail

DEPLOY_USER="${DEPLOY_USER:-nurbek}"
SSH_PORT="${SSH_PORT:-2222}"
DEPLOY_PUBKEY="${DEPLOY_PUBKEY:-}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root (sudo)." >&2
  exit 1
fi

echo "==> Updating apt"
DEBIAN_FRONTEND=noninteractive apt-get update
DEBIAN_FRONTEND=noninteractive apt-get -y upgrade
DEBIAN_FRONTEND=noninteractive apt-get -y install \
    ca-certificates curl gnupg lsb-release ufw fail2ban unattended-upgrades \
    htop ncdu jq git-core rsync tzdata

echo "==> Enabling unattended-upgrades"
dpkg-reconfigure -f noninteractive unattended-upgrades || true

echo "==> Installing Docker Engine + compose plugin"
install -m 0755 -d /etc/apt/keyrings
if [[ ! -f /etc/apt/keyrings/docker.gpg ]]; then
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
    gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
fi
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker

echo "==> Creating deploy user '${DEPLOY_USER}'"
if ! id -u "${DEPLOY_USER}" >/dev/null 2>&1; then
  adduser --disabled-password --gecos "" "${DEPLOY_USER}"
fi
usermod -aG sudo,docker "${DEPLOY_USER}"
echo "${DEPLOY_USER} ALL=(ALL) NOPASSWD: /usr/bin/docker, /usr/bin/docker-compose, /usr/bin/systemctl" \
  > "/etc/sudoers.d/${DEPLOY_USER}"
chmod 440 "/etc/sudoers.d/${DEPLOY_USER}"

if [[ -n "${DEPLOY_PUBKEY}" ]]; then
  install -d -m 700 -o "${DEPLOY_USER}" -g "${DEPLOY_USER}" "/home/${DEPLOY_USER}/.ssh"
  echo "${DEPLOY_PUBKEY}" >> "/home/${DEPLOY_USER}/.ssh/authorized_keys"
  chown "${DEPLOY_USER}:${DEPLOY_USER}" "/home/${DEPLOY_USER}/.ssh/authorized_keys"
  chmod 600 "/home/${DEPLOY_USER}/.ssh/authorized_keys"
fi

echo "==> Hardening SSH (port ${SSH_PORT}, key-only auth)"
sshd_config=/etc/ssh/sshd_config
cp "${sshd_config}" "${sshd_config}.bak.$(date +%s)"
sed -i \
  -e "s/^#\?Port .*/Port ${SSH_PORT}/" \
  -e "s/^#\?PermitRootLogin .*/PermitRootLogin prohibit-password/" \
  -e "s/^#\?PasswordAuthentication .*/PasswordAuthentication no/" \
  -e "s/^#\?KbdInteractiveAuthentication .*/KbdInteractiveAuthentication no/" \
  -e "s/^#\?ChallengeResponseAuthentication .*/ChallengeResponseAuthentication no/" \
  -e "s/^#\?UsePAM .*/UsePAM yes/" \
  -e "s/^#\?X11Forwarding .*/X11Forwarding no/" \
  "${sshd_config}"
systemctl restart ssh

echo "==> Configuring UFW"
ufw default deny incoming
ufw default allow outgoing
ufw allow "${SSH_PORT}/tcp" comment "ssh"
ufw allow 80/tcp  comment "http"
ufw allow 443/tcp comment "https"
ufw --force enable

echo "==> Configuring fail2ban"
cat >/etc/fail2ban/jail.d/linkforge.local <<JAIL
[DEFAULT]
bantime  = 1h
findtime = 10m
maxretry = 5
backend  = systemd

[sshd]
enabled = true
port    = ${SSH_PORT}

[nginx-limit-req]
enabled = true
filter  = nginx-limit-req
logpath = /var/log/nginx/error.log
maxretry = 10
JAIL
systemctl enable --now fail2ban
systemctl restart fail2ban

echo "==> Done.  Now log in as ${DEPLOY_USER}@<ip> -p ${SSH_PORT} and run scripts/deploy.sh."
