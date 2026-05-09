
from pydantic import BaseModel, EmailStr


# User Registration Schema
class UserCreate(BaseModel):

    name: str

    email: EmailStr

    password: str

class UserLogin(BaseModel):

    email: EmailStr

    password: str