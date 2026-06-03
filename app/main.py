from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from app import auth
from app.middleware import log_requests
from datetime import datetime
import math
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
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
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(log_requests)

users = {}
attendance_records = {}

UPLOAD_FOLDER = "uploads"
OFFICE_LATITUDE = 11.276794
OFFICE_LONGITUDE = 75.9347535
ALLOWED_RADIUS_METERS = 100
MAX_GPS_ACCURACY_METERS = 1000

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    office_latitude: float | None = None
    office_longitude: float | None = None
    allowed_radius_meters: float | None = None


@app.get("/")
def serve_ui():
    return FileResponse("static/index.html")


@app.post("/register")
def register_user(user: UserCreate):

    users[user.email] = {
        "name": user.name,
        "email": user.email,
        "password": auth.hash_password(user.password),
        "office_latitude": user.office_latitude or OFFICE_LATITUDE,
        "office_longitude": user.office_longitude or OFFICE_LONGITUDE,
        "allowed_radius_meters": user.allowed_radius_meters or ALLOWED_RADIUS_METERS
    }

    return {
        "message": "User registered successfully"
    }


@app.post("/login")
def login_user(form_data: OAuth2PasswordRequestForm = Depends()):

    db_user = users.get(form_data.username)

    if not db_user:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    if not auth.verify_password(
        form_data.password,
        db_user["password"]
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    access_token = auth.create_access_token(
        data={
            "sub": db_user["email"]
        }
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


def identify_employee_from_image(image):
    return "Face identified successfully"


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

    except HTTPException:
        raise

    except Exception:
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


def validate_coordinates(
    latitude: float,
    longitude: float,
    accuracy: float
):

    if latitude is None or longitude is None:
        raise HTTPException(
            status_code=400,
            detail="Latitude and longitude are required"
        )

    if latitude < -90 or latitude > 90:
        raise HTTPException(
            status_code=400,
            detail="Invalid latitude"
        )

    if longitude < -180 or longitude > 180:
        raise HTTPException(
            status_code=400,
            detail="Invalid longitude"
        )

    if latitude == 0 and longitude == 0:
        raise HTTPException(
            status_code=400,
            detail="Invalid GPS coordinates"
        )

    if accuracy is None or accuracy <= 0:
        raise HTTPException(
            status_code=400,
            detail="GPS accuracy is required"
        )

    if accuracy > MAX_GPS_ACCURACY_METERS:
        raise HTTPException(
            status_code=400,
            detail="GPS accuracy is too low"
        )


def calculate_distance_from_office(
    latitude: float,
    longitude: float,
    office_latitude: float,
    office_longitude: float
):

    earth_radius = 6371000

    lat1 = math.radians(office_latitude)
    lon1 = math.radians(office_longitude)

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

    return distance


def validate_geofence(
    latitude: float,
    longitude: float,
    current_user: dict
):

    distance = calculate_distance_from_office(
        latitude,
        longitude,
        current_user["office_latitude"],
        current_user["office_longitude"]
    )

    allowed_radius_meters = current_user["allowed_radius_meters"]

    if distance > allowed_radius_meters:
        raise HTTPException(
            status_code=403,
            detail=(
                "Outside allowed office radius. "
                f"Distance: {round(distance, 2)} meters"
            )
        )

    return distance


def get_location_name(
    latitude,
    longitude
):

    url = (
        "https://nominatim.openstreetmap.org/reverse"
        f"?format=json&lat={latitude}&lon={longitude}"
    )

    headers = {
        "User-Agent": "attendance-system"
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        return data.get(
            "display_name",
            "Unknown Location"
        )

    except requests.RequestException:
        return "Location lookup unavailable"


def save_uploaded_image(
    image: UploadFile,
    email: str,
    attendance_type: str
):

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    safe_email = (
        email.replace("@", "_")
        .replace(".", "_")
    )

    filename = f"{safe_email}_{attendance_type}_{timestamp}.jpg"

    filepath = os.path.join(
        UPLOAD_FOLDER,
        filename
    )

    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(
            image.file,
            buffer
        )

    return filepath


def check_image_metadata(filepath):

    try:
        image = Image.open(filepath)

        exif_data = image.getexif()

        metadata = {}

        for tag_id, value in exif_data.items():

            tag = TAGS.get(tag_id, tag_id)

            metadata[str(tag)] = str(value)

        return metadata

    except Exception:
        return {}


@app.post("/clock-in")
def clock_in(
    image: UploadFile = File(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    accuracy: float = Form(...),
    captured_at: str = Form(...),
    current_user: dict = Depends(get_current_user)
):

    validate_coordinates(
        latitude,
        longitude,
        accuracy
    )

    distance = validate_geofence(
        latitude,
        longitude,
        current_user
    )

    identified_employee = identify_employee_from_image(image)

    filepath = save_uploaded_image(
        image,
        current_user["email"],
        "clockin"
    )

    metadata = check_image_metadata(filepath)

    location_name = get_location_name(
        latitude,
        longitude
    )

    clock_in_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    attendance_records[current_user["email"]] = {

        "employee_name": current_user["name"],
        "employee_email": current_user["email"],
        "clock_in_time": clock_in_time,
        "captured_at": captured_at,
        "clock_out_time": None,
        "latitude": latitude,
        "longitude": longitude,
        "accuracy": accuracy,
        "distance_from_office_meters": round(distance, 2),
        "office_latitude": current_user["office_latitude"],
        "office_longitude": current_user["office_longitude"],
        "allowed_radius_meters": current_user["allowed_radius_meters"],
        "location_name": location_name,
        "identity_status": identified_employee,
        "location_valid": True,
        "saved_image_path": filepath,
        "image_metadata": metadata
    }

    return {
        "status": "success",
        "message": "Clock-in successful",

        "employee": {
            "name": current_user["name"],
            "email": current_user["email"]
        },

        "attendance": {
            "type": "clock_in",
            "clock_in_time": clock_in_time,
            "captured_at": captured_at,
            "image_path": filepath
        },

        "location": {
            "latitude": latitude,
            "longitude": longitude,
            "accuracy": accuracy,
            "distance_from_office_meters": round(distance, 2),
            "inside_geofence": True,
            "office_latitude": current_user["office_latitude"],
            "office_longitude": current_user["office_longitude"],
            "allowed_radius_meters": current_user["allowed_radius_meters"],
            "address": location_name
        },

        "identity": {
            "status": identified_employee
        },

        "image_metadata": metadata
    }


@app.post("/clock-out")
def clock_out(
    image: UploadFile = File(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    accuracy: float = Form(...),
    captured_at: str = Form(...),
    current_user: dict = Depends(get_current_user)
):

    existing_record = attendance_records.get(
        current_user["email"]
    )

    if not existing_record:
        raise HTTPException(
            status_code=404,
            detail="No clock-in record found"
        )

    validate_coordinates(
        latitude,
        longitude,
        accuracy
    )

    distance = validate_geofence(
        latitude,
        longitude,
        current_user
    )

    identified_employee = identify_employee_from_image(image)

    filepath = save_uploaded_image(
        image,
        current_user["email"],
        "clockout"
    )

    metadata = check_image_metadata(filepath)

    location_name = get_location_name(
        latitude,
        longitude
    )

    clock_out_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    existing_record["clock_out_time"] = clock_out_time
    existing_record["clock_out_captured_at"] = captured_at
    existing_record["clock_out_image"] = filepath
    existing_record["clock_out_latitude"] = latitude
    existing_record["clock_out_longitude"] = longitude
    existing_record["clock_out_accuracy"] = accuracy
    existing_record["clock_out_distance_from_office_meters"] = round(distance, 2)
    existing_record["clock_out_office_latitude"] = current_user["office_latitude"]
    existing_record["clock_out_office_longitude"] = current_user["office_longitude"]
    existing_record["clock_out_allowed_radius_meters"] = current_user["allowed_radius_meters"]
    existing_record["clock_out_location_name"] = location_name
    existing_record["clock_out_identity_status"] = identified_employee
    existing_record["clock_out_image_metadata"] = metadata

    return {
        "status": "success",
        "message": "Clock-out successful",

        "employee": {
            "name": current_user["name"],
            "email": current_user["email"]
        },

        "attendance": {
            "type": "clock_out",
            "clock_in_time": existing_record["clock_in_time"],
            "clock_out_time": clock_out_time,
            "captured_at": captured_at,
            "image_path": filepath
        },

        "location": {
            "latitude": latitude,
            "longitude": longitude,
            "accuracy": accuracy,
            "distance_from_office_meters": round(distance, 2),
            "inside_geofence": True,
            "office_latitude": current_user["office_latitude"],
            "office_longitude": current_user["office_longitude"],
            "allowed_radius_meters": current_user["allowed_radius_meters"],
            "address": location_name
        },

        "identity": {
            "status": identified_employee
        },

        "image_metadata": metadata
    }
