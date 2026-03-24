#!/bin/bash
set -e
uv run fastapi run src/opentaion_api/main.py --host 0.0.0.0 --port ${PORT:-8000}
