from passlib.context import CryptContext

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# In-memory user store (replace with DB in prod)
users_db = {
    "admin": {
        "username": "admin",
        "hashed_password": pwd_context.hash("agent0range"),
        "disabled": False,
    }
}

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_user(username: str):
    user = users_db.get(username)
    if user:
        return user
    return None
