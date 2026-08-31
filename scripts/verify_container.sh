#!/usr/bin/env bash
set -euo pipefail

IMAGE="${1:-howedo:r16-local}"
CONTAINER="howedo-r16-verify-$$"

cleanup() {
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT

if [ "${HOWEDO_SKIP_BUILD:-0}" = "1" ]; then
  echo "=== BUILD ==="
  echo "BUILD=SKIPPED_PREBUILT_IMAGE"
  docker image inspect "$IMAGE" >/dev/null
else
  echo "=== BUILD ==="
  docker build --pull -t "$IMAGE" .
fi

echo "=== NON-ROOT CONTRACT ==="
USER_VALUE="$(docker image inspect "$IMAGE" --format '{{.Config.User}}')"
echo "IMAGE_USER=$USER_VALUE"

case "$USER_VALUE" in
  10001|10001:10001) ;;
  *)
    echo "FAIL: unexpected runtime user: $USER_VALUE"
    exit 1
    ;;
esac

echo "=== HARDENED START ==="
docker run \
  --detach \
  --name "$CONTAINER" \
  --publish 127.0.0.1::8000 \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=16m \
  --cap-drop ALL \
  --security-opt no-new-privileges:true \
  "$IMAGE" >/dev/null

PORT="$(
  docker port "$CONTAINER" 8000/tcp |
  sed -E 's/.*:([0-9]+)$/\1/'
)"

test -n "$PORT"
echo "PORT=$PORT"

echo "=== HEALTH ==="

HEALTH_OK=0
for _ in $(seq 1 30); do
  if curl --fail --silent \
      "http://127.0.0.1:${PORT}/health" \
      >/tmp/howedo-health.json
  then
    HEALTH_OK=1
    break
  fi
  sleep 1
done

test "$HEALTH_OK" = "1"
cat /tmp/howedo-health.json
grep -q '"status":"ok"' /tmp/howedo-health.json

echo
echo "=== DOCKER HEALTHCHECK ==="

DOCKER_HEALTH_OK=0

for _ in $(seq 1 40); do
  HEALTH_STATUS="$(
    docker inspect       --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}'       "$CONTAINER"
  )"

  echo "DOCKER_HEALTH_STATUS=$HEALTH_STATUS"

  if [ "$HEALTH_STATUS" = "healthy" ]; then
    DOCKER_HEALTH_OK=1
    break
  fi

  if [ "$HEALTH_STATUS" = "unhealthy" ]; then
    docker inspect "$CONTAINER"       --format '{{json .State.Health}}'
    exit 1
  fi

  sleep 1
done

test "$DOCKER_HEALTH_OK" = "1"

echo
echo "=== READY ==="

curl --fail --silent \
  "http://127.0.0.1:${PORT}/ready" \
  | tee /tmp/howedo-ready.json

grep -q '"status":"ready"' /tmp/howedo-ready.json

echo
echo "=== API SMOKE ==="

curl --fail --silent \
  -H 'content-type: application/json' \
  -d '{
    "snapshot": [{
      "resource_id": "repo://example",
      "revision": "git:abc",
      "digest": "sha256:abc"
    }],
    "current_heads": [{
      "resource_id": "repo://example",
      "revision": "git:abc",
      "digest": "sha256:abc"
    }]
  }' \
  "http://127.0.0.1:${PORT}/v1/continuity/check" \
  | tee /tmp/howedo-api.json

grep -q '"action":"CONTINUE"' /tmp/howedo-api.json

echo
echo "=== IMAGE ==="
docker image inspect \
  "$IMAGE" \
  --format 'IMAGE_ID={{.Id}} USER={{.Config.User}}'

echo
echo "R16_2_CONTAINER_VERIFY=PASS"
