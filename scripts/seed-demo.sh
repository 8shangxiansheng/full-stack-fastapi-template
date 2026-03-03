#! /usr/bin/env bash

set -e
set -x

cd backend
UV_CACHE_DIR=/tmp/uv-cache POSTGRES_PASSWORD=changethis uv run alembic upgrade head
UV_CACHE_DIR=/tmp/uv-cache POSTGRES_PASSWORD=changethis uv run python app/seed_demo_data.py
