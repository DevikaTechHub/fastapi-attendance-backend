from fastapi import FastAPI
from pydantic import BaseModel, EmailStr
from app import auth
from app.middleware import log_requests

app = FastAPI()

app.middleware("http")(log_requests)

# Temporary storage
users = {}

# Request models
class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    
#login
class UserLogin(BaseModel):
    email: EmailStr
    password: str

# Server alive check
@app.get("/")
def home():
    return {
        "message": "Attendance Backend API Running"
    }

# Register API
@app.post("/register")
def register_user(user: UserCreate):

    users[user.email] = {
        "name": user.name,
        "email": user.email,
        "password": auth.hash_password(user.password)
    }

    return {
        "message": "User registered successfully"
    }

# Login API
@app.post("/login")
def login_user(user: UserLogin):

    db_user = users.get(user.email)

    if not db_user:
        return {
            "message": "Invalid email"
        }

    if not auth.verify_password(
        user.password,
        db_user["password"]
    ):
        return {
            "message": "Invalid password"
        }

    access_token = auth.create_access_token(
        data={
            "sub": db_user["email"]
        }
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }