#!/bin/sh
# Run the seeder inside a backend-ot container from a bundle made by `make seed-bundle` (the dev
# cloud VM's seed path: the root `make cloud-seed-site env=dev SITE=...`). The bundle may be copied
# anywhere in the container: seed_db.py finds its sibling modules and the contract files next to
# itself, and the image puts /app/src on PYTHONPATH. Nothing is written under /app.
#   sh <bundle>/run_in_container.sh <powerflow site>
set -eu
site="${1:?usage: run_in_container.sh <powerflow site>}"
bundle="$(cd "$(dirname "$0")" && pwd)"
cd /app
exec python "$bundle/seed_db.py" powerflow "$site"
