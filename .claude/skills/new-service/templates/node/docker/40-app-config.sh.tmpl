#!/bin/sh
# Writes the SPA's runtime config (/config.js) from the container environment, so one image
# serves every environment. Runs from the nginx image's /docker-entrypoint.d/ before nginx starts.
set -eu

envsubst '${APP_API_BASE_URL}' \
	< /etc/nginx/app/config.js.template \
	> /usr/share/nginx/html/config.js
echo "40-app-config.sh: wrote /config.js (apiBaseUrl=${APP_API_BASE_URL})"
