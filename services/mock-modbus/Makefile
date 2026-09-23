.PHONY: network build up down restart logs clean

network:
	docker network inspect shared-network >nul 2>&1 || docker network create shared-network

build: network
	docker compose build

up: network
	docker compose up --build -d

down:
	docker compose down

restart: down up

logs:
	docker compose logs -f mock-modbus

clean: down
	docker rmi mock-modbus-server-mock-modbus 2>/dev/null || true
