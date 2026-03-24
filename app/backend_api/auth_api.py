from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from db.db_manager import DatabaseManager
import hashlib

router = APIRouter(prefix="/api/auth", tags=["认证"])

class UserAuth(BaseModel):
    username: str
    password: str

def get_db():
    return DatabaseManager()

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

@router.post("/register")
async def register(auth: UserAuth, db: DatabaseManager = Depends(get_db)):
    pwd_hash = hash_password(auth.password)
    result = db.create_user(auth.username, pwd_hash)
    if not result:
        raise HTTPException(status_code=400, detail="User already exists")
    return {
        "message": "User created", 
        "user_id": str(result.inserted_id),
        "username": auth.username
    }

@router.post("/login")
async def login(auth: UserAuth, db: DatabaseManager = Depends(get_db)):
    user = db.get_user_by_username(auth.username)
    if not user or user["password_hash"] != hash_password(auth.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {
        "message": "Login successful",
        "username": user["username"],
        "user_id": str(user["_id"])
    }
