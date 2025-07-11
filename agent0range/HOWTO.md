# agent0range HOW-TO

## 1. Backend (FastAPI)
- Install dependencies:
  ```bash
  cd backend
  pip install -r requirements.txt
  ```
- Run the server:
  ```bash
  uvicorn main:app --reload --host 0.0.0.0 --port 8000
  ```
- Default user: `admin` / `agent0range` (change in users.py for production)

## 2. Agent Core (gRPC)
- Install dependencies:
  ```bash
  cd agent_core
  pip install grpcio grpcio-tools
  ```
- Generate gRPC code:
  ```bash
  python -m grpc_tools.protoc -I./proto --python_out=. --grpc_python_out=. ./proto/agent.proto
  ```
- Run the agent core server:
  ```bash
  python server.py
  ```
- Hot-swap: Deploy new Docker image, update backend config, check /Status endpoint

## 3. Frontend (React+Vite)
- Install dependencies:
  ```bash
  cd webui
  npm install
  ```
- Run the dev server:
  ```bash
  npm run dev
  ```
- Security: In `App.tsx`, call:
  ```ts
  import { hardenDOM, addNoiseOverlay, addWatermark } from './security';
  useEffect(() => {
    hardenDOM();
    addNoiseOverlay();
    addWatermark('agent0range // ultra secure');
  }, []);
  ```

## 4. Integration
- Backend talks to agent core via gRPC (see `agent_client.py`)
- Frontend talks to backend via REST (see API contract in README)

## 5. Security Tips
- Change all default secrets and passwords before production
- Use HTTPS and set `secure=True` for cookies in production
- Monitor logs for suspicious activity (backend logs warnings)
- Consider adding CAPTCHA or 2FA for extra protection

## 6. Upgrading/Hot-Swapping
- Build new agent core Docker image
- Deploy alongside old one
- Use `/Status` endpoint to verify health/version
- Update backend config to point to new agent
- Remove old container after switchover

---

> _agent0range: Quietly better. If you need more, just ask._
