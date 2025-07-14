# agent0range

A quietly elite, modular, and ultra-secure agent system.

## Features
- 🔒 Hardened FastAPI backend (JWT, rate limiting, security headers, anti-bot)
- 🦾 Modular agent core (gRPC, hot-swappable, Docker-ready)
- 🖥️ React+Vite frontend (glassmorphism, animated noise, anti-OCR, decoy DOM)
- 🧩 Strict API boundaries for easy upgrades

---

## Quickstart

### 🚀 One-Command Start (Recommended)
Start the entire stack (frontend, backend, agent core, and mailhog) with Docker Compose:
```bash
docker compose up --build
```

- Web UI: http://localhost:42069
- Backend API: http://localhost:43069/docs
- MailHog (email testing): http://localhost:43070

All dependencies are containerized. No manual setup needed.

---

## Upgrade & Hot-Swap
- Agent core is modular: swap Docker images, check health via gRPC Status
- Backend/frontend can be upgraded independently (API contract enforced)

---

## Security Notes
- Backend: CSP, X-Frame-Options, anti-bot, suspicious activity logging
- Frontend: Anti-OCR overlays, decoy fields, randomized IDs

---

## How-Tos
- **Add a new agent core:** Build new Docker image, deploy, update backend config
- **Change security settings:** Edit `middleware.py` (backend) or `security.ts` (frontend)
- **Integrate new modules:** Respect API boundaries, update proto/contracts as needed

---

> _agent0range: You bring the vision. I’ll handle the rest._
