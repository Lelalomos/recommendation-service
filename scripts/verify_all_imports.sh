#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
POSTGRES_ENV_FILE="$ROOT_DIR/postgresql/.env"
QDRANT_ENV_FILE="$ROOT_DIR/vector_db/.env"
QDRANT_COMPOSE_FILE="$ROOT_DIR/vector_db/docker-compose.yml"
POSTGRES_COMPOSE_FILE="$ROOT_DIR/postgresql/docker-compose.yml"

get_env_value() {
  local env_file="$1"
  local key="$2"
  awk -F= -v target="$key" '$1 == target {print $2}' "$env_file" | tail -n 1
}

container_is_running() {
  local container_name="$1"
  local status
  status="$(docker inspect --format '{{.State.Status}}' "$container_name" 2>/dev/null || true)"
  [[ "$status" == "running" ]]
}

POSTGRES_CONTAINER_NAME="$(get_env_value "$POSTGRES_ENV_FILE" "POSTGRES_CONTAINER_NAME")"
QDRANT_CONTAINER_NAME="$(get_env_value "$QDRANT_ENV_FILE" "QDRANT_CONTAINER_NAME")"

if ! container_is_running "$POSTGRES_CONTAINER_NAME"; then
  echo "PostgreSQL service is not running. Start it first with bash postgresql/scripts/start_postgres_compose.sh" >&2
  exit 1
fi

if ! container_is_running "$QDRANT_CONTAINER_NAME"; then
  echo "Qdrant service is not running. Start it first with bash vector_db/scripts/start_qdrant_compose.sh" >&2
  exit 1
fi

docker compose --env-file "$POSTGRES_ENV_FILE" -f "$POSTGRES_COMPOSE_FILE" run --build --rm postgres-tests \
  python postgresql/scripts/verify_postgres_import.py

docker compose -f "$QDRANT_COMPOSE_FILE" run --build --rm qdrant-tests \
  python vector_db/scripts/verify_qdrant_import.py
