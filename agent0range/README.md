# agent0range

A quietly elite, modular, and ultra-secure agent system.

## Features
- 🔒 Hardened FastAPI backend (JWT, rate limiting, security headers, anti-bot)
- 🦾 Modular agent core (gRPC, hot-swappable, Docker-ready)
- 🖥️ React+Vite frontend (glassmorphism, animated noise, anti-OCR, decoy DOM)
- 🧩 Strict API boundaries for easy upgrades

---

## Quickstart

### 1. Backend (FastAPI)
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
- Endpoints: `/api/auth/login`, `/api/auth/logout`, `/api/auth/me`
- Security: JWT in HttpOnly cookie, rate limiting, security headers, anti-bot

### 2. Agent Core (gRPC)
```bash
cd agent_core
pip install grpcio grpcio-tools
python -m grpc_tools.protoc -I./proto --python_out=. --grpc_python_out=. ./proto/agent.proto
python server.py
```
- Endpoints: Inference, Status, HotSwap (see proto)
- Hot-swap: Deploy new Docker image, update backend config

### 3. Frontend (React+Vite)
```bash
cd webui
npm install
npm run dev
```
- Security: Animated noise, decoy DOM, dynamic watermark
- Call `hardenDOM()`, `addNoiseOverlay()`, `addWatermark()` in `App.tsx`

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
