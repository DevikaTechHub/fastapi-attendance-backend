from fastapi import FastAPI
from pydantic import BaseModel, EmailStr
from app import auth
from app.middleware import log_requests
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from datetime import datetime
from fastapi.security import OAuth2PasswordBearer

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



# Temporary attendance storage
attendance_records = {}

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

def identify_employee_from_image(image):
    # AI face recognition placeholder
    return "Face identified successfully"

def is_inside_work_zone(latitude: float, longitude: float):

    office_latitude = 11.2588
    office_longitude = 75.7804

    allowed_range = 0.01

    if (
        abs(latitude - office_latitude) <= allowed_range
        and
        abs(longitude - office_longitude) <= allowed_range
    ):
        return True

    return False

def get_current_user(token: str = Depends(oauth2_scheme)):

    try:
        payload = auth.jwt.decode(
            token,
            auth.SECRET_KEY,
            algorithms=[auth.ALGORITHM]
        )

        email = payload.get("sub")

        if email is None:
            raise HTTPException(
                status_code=401,
                detail="Invalid token"
            )

        user = users.get(email)

        if user is None:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )

        return user

    except:
        raise HTTPException(
            status_code=401,
            detail="Could not validate token"
        )
    
@app.get("/me")
def who_am_i(current_user: dict = Depends(get_current_user)):

    return {
        "message": "User identity fetched successfully",
        "name": current_user["name"],
        "email": current_user["email"]
    }
@app.post("/clock-in")
def clock_in(
    image: UploadFile = File(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    current_user: dict = Depends(get_current_user)
):

    identified_employee = identify_employee_from_image(image)

    location_valid = is_inside_work_zone(latitude, longitude)

    suspicious_location = not location_valid

    attendance_records[current_user["email"]] = {
        "employee_name": current_user["name"],
        "employee_email": current_user["email"],
        "clock_in_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "clock_out_time": None,
        "latitude": latitude,
        "longitude": longitude,
        "identity_status": identified_employee,
        "location_valid": location_valid,
        "suspicious_location": suspicious_location
    }

    return {
        "message": "Clock-in successful",
        "employee_name": current_user["name"],
        "employee_email": current_user["email"],
        "clock_in_time": attendance_records[current_user["email"]]["clock_in_time"],
        "identity_status": identified_employee,
        "location_valid": location_valid,
        "suspicious_location": suspicious_location
    }

@app.post("/clock-out")
def clock_out(
    image: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):

    identified_employee = identify_employee_from_image(image)

    existing_record = attendance_records.get(
        current_user["email"]
    )

    if not existing_record:

        raise HTTPException(
            status_code=404,
            detail="No clock-in record found"
        )

    existing_record["clock_out_time"] = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    existing_record["clock_out_identity_status"] = identified_employee

    return {

        "message": "Clock-out successful",

        "employee_name": current_user["name"],

        "employee_email": current_user["email"],

        "clock_in_time": existing_record["clock_in_time"],

        "clock_out_time": existing_record["clock_out_time"],

        "identity_status": identified_employee
    }