#!/bin/sh
set -eu

WG_CONF_PATH="${WG_CONF_PATH:-/app/config/wireguard/wg0.conf}"
WG_INTERFACE="${WG_INTERFACE:-wg0}"

if [ -f "$WG_CONF_PATH" ] && [ -c /dev/net/tun ]; then
  if command -v wireguard-go >/dev/null 2>&1; then
    export WG_QUICK_USERSPACE_IMPLEMENTATION=wireguard-go
    export WG_QUICK_USERSPACE_IMPLEMENTATION_FORCE=1
  fi
  if ! ip link show "$WG_INTERFACE" >/dev/null 2>&1; then
    if command -v wg-quick >/dev/null 2>&1; then
      wg-quick up "$WG_CONF_PATH" || echo "WARN: wg-quick failed; starting Gateway without tunnel"
    else
      echo "WARN: wg-quick not found; starting Gateway without tunnel"
    fi
  fi
else
  echo "INFO: WireGuard config or /dev/net/tun missing; skipping tunnel setup"
fi

exec "$@"
