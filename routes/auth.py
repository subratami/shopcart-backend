from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
from database import users_collection
import os

router = APIRouter()

# Auth Settings
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
ACCESS_SECRET_KEY = "access_secret_key"
REFRESH_SECRET_KEY = "refresh_secret_key"
ALGORITHM = "HS256"
ACCESS_EXPIRE_MINUTES = 360  # 6 hours
REFRESH_EXPIRE_DAYS = 7

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Models
class UserIn(BaseModel):
    name: str
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    email: EmailStr

class Token(BaseModel):
    access_token: str
    token_type: str

class RefreshRequest(BaseModel):
    refresh_token: str

# Helper functions
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, ACCESS_SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, REFRESH_SECRET_KEY, algorithm=ALGORITHM)

# ✅ Dependency
async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, ACCESS_SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid access token")

    user = await users_collection.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "email": user["email"],
        "name": user.get("name", "")
    }

# Routes
@router.post("/signup", response_model=UserOut)
async def signup(user: UserIn):
    if await users_collection.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_pw = hash_password(user.password)
    await users_collection.insert_one({
        "name": user.name,
        "email": user.email,
        "hashed_password": hashed_pw,
        "refresh_token": None
    })

    return UserOut(email=user.email)

@router.post("/login")
async def login(user: LoginRequest):
    db_user = await users_collection.find_one({"email": user.email})
    if not db_user or not verify_password(user.password, db_user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token({"sub": user.email})
    refresh_token = create_refresh_token({"sub": user.email})

    await users_collection.update_one(
        {"email": user.email},
        {"$set": {"refresh_token": refresh_token}}
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

@router.post("/refresh", response_model=Token)
async def refresh_token(body: RefreshRequest):
    try:
        payload = jwt.decode(body.refresh_token, REFRESH_SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = await users_collection.find_one({"email": email})
    if not user or user.get("refresh_token") != body.refresh_token:
        raise HTTPException(status_code=403, detail="Refresh token has expired or is invalid")

# Rotate tokens
    new_access = create_access_token({"sub": email})
    new_refresh = create_refresh_token({"sub": email})
    await users_collection.update_one(
        {"email": email},
        {"$set": {"refresh_token": new_refresh}}
    )
    return JSONResponse(content={
        "access_token": new_access,
        "refresh_token": new_refresh
    })
    #return Token(access_token=new_access, token_type="bearer")

@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    await users_collection.update_one(
        {"email": current_user["email"]},
        {"$set": {"refresh_token": None}}
    )
    return {"message": "Logged out successfully"}

@router.get("/protected")
async def protected(current_user: dict = Depends(get_current_user)):
    return {"message": f"Welcome, {current_user['email']}! You are authenticated ✅"}

@router.get("/health")
async def health_check():
    return {"status": "ok"}