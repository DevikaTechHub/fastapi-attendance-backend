

from fastapi import FastAPI, Depends

from sqlalchemy.orm import Session

from app.database import engine, Base, get_db

from app import models, schemas

from app import auth

from app.middleware import log_requests

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI()

app.middleware("http")(log_requests)


@app.get("/")
def home():

    return {
        "message": "Attendance Backend API Running"
    }


# Registration API
@app.post("/register")
def register_user(
    user: schemas.UserCreate,
    db: Session = Depends(get_db)
):

    # Create new user
    new_user = models.User(

        name=user.name,

        email=user.email,

        password=auth.hash_password(user.password)

    )

    # Save to database
    db.add(new_user)

    db.commit()

    db.refresh(new_user)

    return {
        "message": "User registered successfully"
    }

@app.post("/login")
def login_user(
    user: schemas.UserLogin,
    db: Session = Depends(get_db)
):

    # Find user by email
    db_user = db.query(models.User).filter(
        models.User.email == user.email
    ).first()

    # Check email exists
    if not db_user:

        return {
            "message": "Invalid email"
        }

    # Verify password
    if not auth.verify_password(
        user.password,
        db_user.password
    ):

        return {
            "message": "Invalid password"
        }

    # Generate JWT token
    access_token = auth.create_access_token(
        data={
            "sub": db_user.email
        }
    )

    return {

        "access_token": access_token,

        "token_type": "bearer"
    }

@app.post("/clock-in")
def clock_in(
    user_id: int,
    db: Session = Depends(get_db)
):
    attendance = models.Attendance(user_id=user_id)

    db.add(attendance)
    db.commit()
    db.refresh(attendance)

    return {
        "message": "Clock-in successful",
        "attendance_id": attendance.id
    }