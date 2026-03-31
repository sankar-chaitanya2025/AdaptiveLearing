import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# Use the Docker URL but allow for local overrides
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://adaptlab:adaptlab@postgres:5432/adaptlab")

# For local development (outside Docker), swap 'postgres' for 'localhost'
if "postgres:5432" in DATABASE_URL and os.name == 'nt':
    DATABASE_URL = DATABASE_URL.replace("postgres:5432", "localhost:5432")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

# --- ADD THIS: The missing 'get_db' function ---
def get_db():
    """
    Dependency provider for the API.
    Creates a new database session for each request and 
    closes it when the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()