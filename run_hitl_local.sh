#!/usr/bin/env bash
[ -f venv/bin/activate ] || python3 -m venv venv
# shellcheck disable=SC1091
source venv/bin/activate
python3 -m pip install -e '.[dev]'
python3 -m pytest -v "$@"