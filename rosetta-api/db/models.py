import uuid
from sqlalchemy import Boolean, Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from db.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=True) # Nullable for OAuth later
    auth_provider = Column(String, default="local", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class SavedCircuit(Base):
    __tablename__ = "saved_circuits"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    qasm_string = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class RunHistory(Base):
    __tablename__ = "run_histories"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    circuit_id = Column(String(36), ForeignKey("saved_circuits.id"), nullable=True, index=True)
    s3_object_key = Column(String, nullable=False, unique=True, index=True)
    run_name = Column(String, nullable=False, default="Unknown")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
