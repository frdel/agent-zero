# AgentZero Commerce Sandbox

This folder contains a minimal FastAPI service exposing a single test endpoint for use with Open WebUI as a Tool Server.

## Quick start
1. **Clone** this repo and open the `agentzero-commerce` directory.
2. Run `docker compose up --build` to start the API and a Postgres service.
3. Test the service with `curl http://localhost:8080/ga/healthcheck`.
4. View the OpenAPI schema at `http://localhost:8080/openapi.json`.
5. In Open WebUI go to *Settings → OpenAPI Tool Servers → +* and enter `http://<host>:8080/openapi.json` to add the service.

Prerequisites: Docker Desktop and `git`.

### Cómo probar GA
docker compose exec agentzero-api python -m scripts.mock_ga_run

### Cómo inicializar BD
alembic upgrade head
