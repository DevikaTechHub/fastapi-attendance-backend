from fastapi import FastAPI
from pydantic import BaseModel, EmailStr
from app import auth
from app.middleware import log_requests
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from datetime import datetime
import math
from fastapi.security import OAuth2PasswordBearer
import requests
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os
import shutil
from PIL import Image
from PIL.ExifTags import TAGS

app = FastAPI()

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.get("/")
def serve_ui():
    return FileResponse("static/index.html")

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
UPLOAD_FOLDER = "uploads"

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

def identify_employee_from_image(image):
    # AI face recognition placeholder
    return "Face identified successfully"

def is_inside_work_zone(latitude: float, longitude: float):

    campus_latitude = 11.276794
    campus_longitude = 75.9347535

    allowed_radius_meters = 100

    earth_radius = 6371000

    lat1 = math.radians(campus_latitude)
    lon1 = math.radians(campus_longitude)

    lat2 = math.radians(latitude)
    lon2 = math.radians(longitude)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a)
    )

    distance = earth_radius * c

    return distance <= allowed_radius_meters

def get_location_name(latitude, longitude):

    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={latitude}&lon={longitude}"

    headers = {
        "User-Agent": "attendance-system"
    }

    response = requests.get(
        url,
        headers=headers
    )

    data = response.json()

    return data.get(
        "display_name",
        "Unknown Location"
    )

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

def check_image_metadata(filepath):

    try:

        image = Image.open(filepath)

        exif_data = image.getexif()

        metadata = {}

        for tag_id, value in exif_data.items():

            tag = TAGS.get(tag_id, tag_id)

            metadata[tag] = value

        return metadata

    except:

        return {}
    

@app.post("/clock-in")
def clock_in(
    image: UploadFile = File(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    captured_at: str = Form(...),
    current_user: dict = Depends(get_current_user)
):

    identified_employee = identify_employee_from_image(image)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    filename = f"{current_user['email']}_{timestamp}.jpg"

    filepath = os.path.join(
        UPLOAD_FOLDER,
        filename
    )

    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(
            image.file,
            buffer
        )

    metadata = check_image_metadata(
        filepath
    )

    location_valid = is_inside_work_zone(
        latitude,
        longitude
    )

    suspicious_location = not location_valid

    location_name = get_location_name(
        latitude,
        longitude
    )

    attendance_records[current_user["email"]] = {

        "employee_name": current_user["name"],

        "employee_email": current_user["email"],

        "clock_in_time":
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

        "captured_at": captured_at,

        "clock_out_time": None,

        "latitude": latitude,

        "longitude": longitude,

        "location_name": location_name,

        "identity_status": identified_employee,

        "location_valid": location_valid,

        "saved_image_path": filepath,

        "image_metadata": metadata,

        "suspicious_location": suspicious_location
    }

    return {

        "message": "Clock-in successful",

        "employee_name": current_user["name"],

        "employee_email": current_user["email"],

        "clock_in_time":
        attendance_records[current_user["email"]]["clock_in_time"],

        "captured_at": captured_at,

        "latitude": latitude,

        "longitude": longitude,

        "location_name": location_name,

        "identity_status": identified_employee,

        "location_valid": location_valid,

        "saved_image_path": filepath,

        "image_metadata": metadata,

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

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    filename = f"{current_user['email']}_clockout_{timestamp}.jpg"

    filepath = os.path.join(
        UPLOAD_FOLDER,
        filename
    )

    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(
            image.file,
            buffer
        )

    existing_record["clock_out_time"] = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    existing_record["clock_out_identity_status"] = identified_employee

    existing_record["clock_out_image"] = filepath

    return {

        "message": "Clock-out successful",

        "employee_name": current_user["name"],

        "employee_email": current_user["email"],

        "clock_in_time": existing_record["clock_in_time"],

        "clock_out_time": existing_record["clock_out_time"],

        "clock_out_image": filepath,

        "identity_status": identified_employee
    }