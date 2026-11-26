#!/usr/bin/env bash
set -euo pipefail
runtime=/tmp/trajfix-docker
archive=/tmp/trajfix-docker-29.10.1.tgz
mkdir -p "$runtime/bin" "$runtime/run" "$runtime/data"
if [[ ! -x "$runtime/bin/dockerd" ]]; then
  if [[ ! -f "$archive" ]]; then
    curl -fsSL --retry 3 https://download.docker.com/linux/static/stable/x86_64/docker-29.10.1.tgz -o "$archive"
  fi
  tar -xzf "$archive" -C "$runtime/bin" --strip-components=1
fi
export PATH="$runtime/bin:$PATH"
export DOCKER_HOST="unix://$runtime/run/docker.sock"
if docker info >/dev/null 2>&1; then
  docker version --format '{{.Server.Version}}'
  exit 0
fi
cat > "$runtime/daemon.json" <<'JSON'
{
  "features": {"containerd-snapshotter": false},
  "storage-driver": "vfs",
  "bridge": "none",
  "iptables": false,
  "ip6tables": false,
  "ip-forward": false,
  "ip-masq": false,
  "log-driver": "json-file",
  "log-opts": {"max-size": "10m", "max-file": "2"}
}
JSON
nohup dockerd --config-file "$runtime/daemon.json" \
  --host "$DOCKER_HOST" --data-root "$runtime/data" \
  --exec-root "$runtime/run/exec" --pidfile "$runtime/run/docker.pid" \
  > "$runtime/dockerd.log" 2>&1 < /dev/null &
daemon_pid=$!
echo "Started isolated Docker daemon PID $daemon_pid; log: $runtime/dockerd.log"
for attempt in {1..15}; do
  if docker info >/dev/null 2>&1; then
    docker info --format 'Server={{.ServerVersion}} Driver={{.Driver}} Cgroup={{.CgroupVersion}}'
    # Keep the supervised exec session alive; this environment reaps detached
    # processes when their launching session exits.
    wait "$daemon_pid"
    exit $?
  fi
  sleep 1
done
tail -40 "$runtime/dockerd.log"
exit 1
