# FastAPI Attendance Backend

Backend attendance management system built using FastAPI and PostgreSQL.

## Features

- User Registration
- User Login
- JWT Authentication
- Password Hashing
- Clock-in Attendance API
- PostgreSQL Integration
- Pydantic Validation
- Dependency Injection
- Middleware

## Technologies Used

- FastAPI
- PostgreSQL
- SQLAlchemy
- Pydantic
- JWT
- Passlib
- Uvicorn

## Project Structure

attendance-system/
│
├── app/
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── auth.py
│   └── middleware.py
│
├── requirements.txt
└── README.md

## Run Project

Activate virtual environment:

```bash
.\myenv\Scripts\activate
```

Run FastAPI server:

```bash
uvicorn app.main:app --reload
```

## API Documentation

Open in browser:

```text
http://127.0.0.1:8000/docs
```

## Author

Devika