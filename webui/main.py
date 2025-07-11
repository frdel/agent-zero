from fastapi import FastAPI, Request, Response, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from .users import get_user, verify_password
from .auth import create_access_token, get_current_user
from datetime import timedelta
import os

app = FastAPI()
from .middleware import SecurityHeadersMiddleware, AntiBotMiddleware, SuspiciousActivityLoggerMiddleware
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(AntiBotMiddleware)
app.add_middleware(SuspiciousActivityLoggerMiddleware)

# CORS for local dev
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(429, _rate_limit_exceeded_handler)

@app.post("/api/auth/login")
@limiter.limit("5/minute")
def login(request: Request, response: Response):
    data = request.json() if hasattr(request, 'json') else request._json
    username = data.get("username")
    password = data.get("password")
    user = get_user(username)
    if not user or not verify_password(password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access_token = create_access_token({"sub": username}, expires_delta=timedelta(minutes=60))
    response = JSONResponse({"msg": "ok"})
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,  # Set True in prod
        samesite="lax",
        max_age=60*60,
        path="/"
    )
    return response

@app.post("/api/auth/logout")
def logout(response: Response):
    response = JSONResponse({"msg": "logged out"})
    response.delete_cookie("access_token", path="/")
    return response

@app.get("/api/auth/me")
def me(user=Depends(get_current_user)):
    return {"username": user["username"]}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
