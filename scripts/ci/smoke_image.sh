#!/bin/sh
# Smoke-test one production image before CI pushes it: the image must start (or at least import
# its app) with no database or other service around.
#   scripts/ci/smoke_image.sh <service> <image>
# Python services: import the ASGI app inside the image (catches missing modules, bad settings
# defaults). web-plusdas: start nginx and fetch / and /config.js (nginx must start with no
# upstream reachable; its upstreams resolve per request).
set -eu

service=$1
image=$2

case "$service" in
backend-ot)
	# config.py requires POSTGRES_PASSWORD at import time; any value works for an import.
	docker run --rm --entrypoint python -e POSTGRES_PASSWORD=ci-smoke "$image" \
		-c "from config import settings; from app import app; print('backend-ot imports', app.title)"
	;;
intelli-gateway)
	docker run --rm --entrypoint python "$image" \
		-c "from intelli_gateway.app import app; print('intelli-gateway imports', app.title)"
	;;
powerflow)
	docker run --rm --entrypoint python "$image" \
		-c "from powerflow.app import app; print('powerflow imports', app.title)"
	;;
web-plusdas)
	name="smoke-web-plusdas-$$"
	docker run -d --rm --name "$name" -p 127.0.0.1:18080:80 \
		-e API_UPSTREAM=http://backend-ot:8000 \
		-e POWERFLOW_UPSTREAM=http://powerflow:8000 \
		-e INTELLI_GATEWAY_UPSTREAM=http://intelli-gateway:8000 \
		"$image" >/dev/null
	trap 'docker rm -f "$name" >/dev/null 2>&1 || true' EXIT
	attempt=0
	until curl -fsS -o /dev/null http://127.0.0.1:18080/; do
		attempt=$((attempt + 1))
		if [ "$attempt" -ge 30 ]; then
			docker logs "$name" >&2 || true
			echo "web-plusdas: nginx did not serve / within 30 s" >&2
			exit 1
		fi
		sleep 1
	done
	curl -fsS http://127.0.0.1:18080/config.js | grep -q "__APP_CONFIG__"
	echo "web-plusdas serves / and /config.js"
	;;
*)
	echo "smoke_image.sh: no smoke test for '$service'" >&2
	exit 2
	;;
esac
