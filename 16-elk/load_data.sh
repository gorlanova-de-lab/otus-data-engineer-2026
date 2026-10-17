#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
docker compose up -d elasticsearch kibana
docker compose --profile load up -d logstash
