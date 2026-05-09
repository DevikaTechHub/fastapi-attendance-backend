from sqlalchemy import Column, Integer, String,ForeignKey,DateTime

from app.database import Base

from sqlalchemy.sql import func


class User(Base):

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String)

    email = Column(String, unique=True)

    password = Column(String)

class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    clock_in_time = Column(DateTime(timezone=True), server_default=func.now())