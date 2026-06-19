#!/bin/bash
# Run a visa check RIGHT NOW (no jitter delay) and always email the result.
# Use this for an immediate manual check; the scheduled jobs keep their jitter.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/.." && pwd)"
exec "$REPO/.venv/bin/python" "$REPO/run_check.py" --summary --print
