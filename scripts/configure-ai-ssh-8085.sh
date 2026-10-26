#!/usr/bin/env bash
set -Eeuo pipefail

die() { printf '[ERROR] %s\n' "$*" >&2; exit 1; }

[[ "$(id -u)" == 0 ]] || die 'Run as root.'
[[ "$(hostname)" == ai-ct-1 ]] || die 'Unexpected host; expected ai-ct-1.'
systemctl is-active --quiet ssh.socket || die 'ssh.socket is not active.'
/usr/sbin/sshd -t || die 'Invalid sshd configuration.'
effective="$(/usr/sbin/sshd -T)"
grep -qx 'port 22' <<< "$effective" || die 'sshd must keep port 22.'
grep -qx 'port 8085' <<< "$effective" || die 'sshd_config must already include port 8085.'

dropin_dir=/etc/systemd/system/ssh.socket.d
dropin="$dropin_dir/50-olympus-port-8085.conf"
marker='# Managed by Olympus: expose SSH on ports 22 and 8085.'
if [[ -e "$dropin" ]] && ! grep -qxF "$marker" "$dropin"; then
  die "$dropin exists but is not managed by Olympus."
fi

tmp="$(mktemp)"
backup="$(mktemp)"
had_previous=false
changed=false
cleanup() { rm -f -- "$tmp" "$backup"; }
rollback() {
  if [[ "$changed" == true ]]; then
    changed=false
    if [[ "$had_previous" == true ]]; then
      install -m 0644 -- "$backup" "$dropin"
    else
      rm -f -- "$dropin"
    fi
    systemctl daemon-reload
    systemctl restart ssh.socket
    printf '[ERROR] SSH socket change failed; previous configuration restored.\n' >&2
  fi
  cleanup
}
trap rollback ERR
trap cleanup EXIT

cat > "$tmp" <<'EOF'
# Managed by Olympus: expose SSH on ports 22 and 8085.
[Socket]
ListenStream=
ListenStream=22
ListenStream=8085
EOF

if [[ -e "$dropin" ]]; then
  cp -- "$dropin" "$backup"
  had_previous=true
fi
if ! cmp -s -- "$tmp" "$dropin"; then
  install -d -m 0755 -- "$dropin_dir"
  install -m 0644 -- "$tmp" "$dropin"
  changed=true
  systemctl daemon-reload
  systemd-analyze verify ssh.socket
  systemctl restart ssh.socket
fi

if ! systemctl is-active --quiet ssh.socket; then
  rollback
  die 'ssh.socket did not become active.'
fi
listen="$(systemctl show ssh.socket -p Listen --value)"
if [[ "$listen" != *'[::]:22 (Stream)'* || "$listen" != *'[::]:8085 (Stream)'* ]]; then
  rollback
  die "Unexpected SSH socket listeners: $listen"
fi
printf '[OK] SSH socket listens on ports 22 and 8085.\n'
