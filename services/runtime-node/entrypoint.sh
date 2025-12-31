#!/bin/sh
set -eu

CNI_GW_IP="${CNI_GW_IP:-10.88.0.1}"
DNAT_APPLY_OUTPUT="${DNAT_APPLY_OUTPUT:-1}"

DNAT_S3_IP="${DNAT_S3_IP:-}"
DNAT_DB_IP="${DNAT_DB_IP:-}"
DNAT_VL_IP="${DNAT_VL_IP:-}"

DNAT_DB_DPORT="${DNAT_DB_DPORT:-8001}"
DNAT_DB_PORT="${DNAT_DB_PORT:-8000}"

CONTAINERD_BIN="${CONTAINERD_BIN:-containerd}"
CONTAINERD_CONFIG="${CONTAINERD_CONFIG:-}"
FIRECRACKER_FIFO_READER="${FIRECRACKER_FIFO_READER:-1}"
VHOST_VSOCK_REQUIRED="${VHOST_VSOCK_REQUIRED:-0}"

DEVMAPPER_POOL="${DEVMAPPER_POOL:-}"
DEVMAPPER_DIR="${DEVMAPPER_DIR:-/var/lib/containerd/devmapper}"
DEVMAPPER_DATA_SIZE="${DEVMAPPER_DATA_SIZE:-10G}"
DEVMAPPER_META_SIZE="${DEVMAPPER_META_SIZE:-2G}"
DEVMAPPER_UDEV="${DEVMAPPER_UDEV:-0}"
WG_CONTROL_NET="${WG_CONTROL_NET:-}"
WG_CONTROL_GW="${WG_CONTROL_GW:-}"
WG_CONTROL_GW_HOST="${WG_CONTROL_GW_HOST:-gateway}"

if [ "$DEVMAPPER_UDEV" != "1" ]; then
  export DM_UDEV_DISABLE=1
  export DM_UDEV_DISABLE_DISK_RULES_FLAG=1
fi

ensure_ip_forward() {
  if [ -w /proc/sys/net/ipv4/ip_forward ]; then
    echo 1 > /proc/sys/net/ipv4/ip_forward
  fi
}

ensure_route_localnet() {
  for path in \
    /proc/sys/net/ipv4/conf/all/route_localnet \
    /proc/sys/net/ipv4/conf/default/route_localnet \
    /proc/sys/net/ipv4/conf/lo/route_localnet; do
    if [ -w "$path" ]; then
      echo 1 > "$path"
    fi
  done
}

ensure_wg_route() {
  if [ -z "$WG_CONTROL_NET" ]; then
    return
  fi
  gw="$WG_CONTROL_GW"
  if [ -z "$gw" ] && [ -n "$WG_CONTROL_GW_HOST" ]; then
    gw="$(getent hosts "$WG_CONTROL_GW_HOST" 2>/dev/null | awk '{print $1}' | head -n1)"
  fi
  if [ -z "$gw" ]; then
    gw="$(ip route show default 0.0.0.0/0 2>/dev/null | awk '{print $3}' | head -n1)"
  fi
  if [ -z "$gw" ]; then
    echo "WARN: default gateway not found; skipping WG route for $WG_CONTROL_NET"
    return
  fi
  ip route replace "$WG_CONTROL_NET" via "$gw" 2>/dev/null || true
}

start_wg_route_watcher() {
  if [ -z "$WG_CONTROL_NET" ] || [ -z "$WG_CONTROL_GW_HOST" ] || [ -n "$WG_CONTROL_GW" ]; then
    return
  fi
  (
    for _ in $(seq 1 30); do
      gw="$(getent hosts "$WG_CONTROL_GW_HOST" 2>/dev/null | awk '{print $1}' | head -n1)"
      if [ -n "$gw" ]; then
        ip route replace "$WG_CONTROL_NET" via "$gw" 2>/dev/null || true
        exit 0
      fi
      sleep 1
    done
  ) &
}

ensure_vhost_vsock() {
  if [ -e /dev/vhost-vsock ]; then
    return
  fi
  echo "WARN: /dev/vhost-vsock is missing. Load vhost_vsock on the host to enable vsock."
  if [ "$VHOST_VSOCK_REQUIRED" = "1" ]; then
    echo "ERROR: /dev/vhost-vsock is required but missing."
    exit 1
  fi
}

start_udevd() {
  if [ "$DEVMAPPER_UDEV" != "1" ]; then
    return
  fi
  if ! command -v udevadm >/dev/null 2>&1 && [ ! -x /lib/systemd/systemd-udevd ] && ! command -v udevd >/dev/null 2>&1; then
    echo "WARN: udev not available; devmapper may fail"
    return
  fi
  mkdir -p /run/udev
  if command -v udevd >/dev/null 2>&1; then
    udevd --daemon || true
  elif [ -x /lib/systemd/systemd-udevd ]; then
    /lib/systemd/systemd-udevd --daemon || true
  fi
  if command -v udevadm >/dev/null 2>&1; then
    udevadm trigger --action=add >/dev/null 2>&1 || true
    udevadm settle >/dev/null 2>&1 || true
  fi
}

start_firecracker_fifo_reader() {
  if [ "$FIRECRACKER_FIFO_READER" != "1" ]; then
    return
  fi
  fifo_root="/var/lib/firecracker-containerd/shim-base"
  state_dir="/run/firecracker-fifo-readers"
  mkdir -p "$state_dir"

  (
    while true; do
      if [ -d "$fifo_root" ]; then
        find "$fifo_root" -type p -name 'fc-*.fifo' 2>/dev/null | while read -r fifo; do
          key=$(echo "$fifo" | tr '/' '_')
          marker="$state_dir/$key"
          if [ ! -f "$marker" ]; then
            touch "$marker"
            (cat "$fifo" >/dev/null 2>&1 &) || true
          fi
        done
      fi
      sleep 0.2
    done
  ) &
}

add_dnat_rule() {
  chain="$1"
  dport="$2"
  dest="$3"
  if ! iptables -t nat -C "$chain" -d "${CNI_GW_IP}/32" -p tcp --dport "$dport" \
    -j DNAT --to-destination "$dest" 2>/dev/null; then
    iptables -t nat -A "$chain" -d "${CNI_GW_IP}/32" -p tcp --dport "$dport" \
      -j DNAT --to-destination "$dest"
  fi
}

add_snat_rule() {
  dest_ip="$1"
  if [ "$dest_ip" = "127.0.0.1" ]; then
    return
  fi
  if ! iptables -t nat -C POSTROUTING -s "${CNI_GW_IP}/32" -d "${dest_ip}/32" \
    -j MASQUERADE 2>/dev/null; then
    iptables -t nat -A POSTROUTING -s "${CNI_GW_IP}/32" -d "${dest_ip}/32" \
      -j MASQUERADE
  fi
}

apply_dnat() {
  chain="$1"
  if [ -n "$DNAT_S3_IP" ]; then
    add_dnat_rule "$chain" 9000 "${DNAT_S3_IP}:9000"
  fi
  if [ -n "$DNAT_DB_IP" ]; then
    add_dnat_rule "$chain" "$DNAT_DB_DPORT" "${DNAT_DB_IP}:${DNAT_DB_PORT}"
  fi
  if [ -n "$DNAT_VL_IP" ]; then
    add_dnat_rule "$chain" 9428 "${DNAT_VL_IP}:9428"
  fi
}

apply_snat() {
  if [ -n "$DNAT_S3_IP" ]; then
    add_snat_rule "$DNAT_S3_IP"
  fi
  if [ -n "$DNAT_DB_IP" ]; then
    add_snat_rule "$DNAT_DB_IP"
  fi
  if [ -n "$DNAT_VL_IP" ]; then
    add_snat_rule "$DNAT_VL_IP"
  fi
}

ensure_ip_forward
ensure_route_localnet
ensure_wg_route
start_wg_route_watcher
ensure_vhost_vsock
mkdir -p /run/containerd /var/lib/containerd
mkdir -p /var/lib/firecracker-containerd/runtime /var/lib/firecracker-containerd/shim-base
start_udevd
start_firecracker_fifo_reader

setup_devmapper() {
  if [ -z "$DEVMAPPER_POOL" ]; then
    return
  fi
  if ! command -v dmsetup >/dev/null 2>&1; then
    echo "WARN: dmsetup not found; skipping devmapper setup"
    return
  fi

  mkdir -p "$DEVMAPPER_DIR"
  data_file="$DEVMAPPER_DIR/data-device"
  meta_file="$DEVMAPPER_DIR/meta-device"

  if [ ! -f "$data_file" ]; then
    truncate -s "$DEVMAPPER_DATA_SIZE" "$data_file"
  fi
  if [ ! -f "$meta_file" ]; then
    truncate -s "$DEVMAPPER_META_SIZE" "$meta_file"
  fi

  data_dev="$(losetup --output NAME --noheadings --associated "$data_file" 2>/dev/null || true)"
  if [ -z "$data_dev" ]; then
    data_dev="$(losetup --find --show "$data_file")"
  fi

  meta_dev="$(losetup --output NAME --noheadings --associated "$meta_file" 2>/dev/null || true)"
  if [ -z "$meta_dev" ]; then
    meta_dev="$(losetup --find --show "$meta_file")"
  fi

  sector_size=512
  data_size="$(blockdev --getsize64 -q "$data_dev")"
  length_sectors=$((data_size / sector_size))
  data_block_size=128
  low_water_mark=32768
  table="0 ${length_sectors} thin-pool ${meta_dev} ${data_dev} ${data_block_size} ${low_water_mark} 1 skip_block_zeroing"
  dm_env="DM_UDEV_DISABLE=1 DM_UDEV_DISABLE_DISK_RULES_FLAG=1"
  dm_args="--noudevsync --noudevrules"

  if env $dm_env dmsetup status "$DEVMAPPER_POOL" >/dev/null 2>&1; then
    env $dm_env dmsetup reload $dm_args "$DEVMAPPER_POOL" --table "$table"
  else
    env $dm_env dmsetup create $dm_args "$DEVMAPPER_POOL" --table "$table"
  fi

  env $dm_env dmsetup mknodes "$DEVMAPPER_POOL" >/dev/null 2>&1 || true
  if [ ! -e "/dev/mapper/$DEVMAPPER_POOL" ]; then
    tries=10
    while [ "$tries" -gt 0 ] && [ ! -e "/dev/mapper/$DEVMAPPER_POOL" ]; do
      dmsetup mknodes "$DEVMAPPER_POOL" >/dev/null 2>&1 || true
      sleep 0.2
      tries=$((tries - 1))
    done
  fi
}

start_devmapper_watcher() {
  if [ -z "$DEVMAPPER_POOL" ]; then
    return
  fi
  if [ "$DEVMAPPER_UDEV" = "1" ]; then
    return
  fi
  if ! command -v dmsetup >/dev/null 2>&1; then
    return
  fi

  (
    while true; do
      for dev in $(dmsetup ls --noheadings 2>/dev/null | awk '{print $1}'); do
        case "$dev" in
          "${DEVMAPPER_POOL}-snap-"*)
            if [ ! -e "/dev/mapper/$dev" ]; then
              dmsetup mknodes "$dev" >/dev/null 2>&1 || true
            fi
            ;;
        esac
      done
      sleep 0.5
    done
  ) &
}

apply_dnat PREROUTING
if [ "$DNAT_APPLY_OUTPUT" = "1" ]; then
  apply_dnat OUTPUT
  apply_snat
fi

setup_devmapper
start_devmapper_watcher

if [ -n "$CONTAINERD_CONFIG" ]; then
  exec "$CONTAINERD_BIN" --config "$CONTAINERD_CONFIG" --address /run/containerd/containerd.sock
fi
exec "$CONTAINERD_BIN" --address /run/containerd/containerd.sock
