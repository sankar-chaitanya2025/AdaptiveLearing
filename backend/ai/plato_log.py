from sqlalchemy import Column, Integer, String, Float, JSON, DateTime, ForeignKey
from sqlalchemy.sql import func
from backend.database import Base # Adjust import based on your actual DB setup

class PlatoLog(Base):
    __tablename__ = "plato_logs"

    id = Column(Integer, primary_key=True, index=True)
    original_problem_id = Column(Integer, index=True)
    
    # Paper Critical: (q, y_fail, q', U) [cite: 201-203]
    original_statement = Column(String) # q
    failed_code = Column(String)        # y_fail (Actual student code)
    refined_problem = Column(JSON)      # q' (The full RefinedProblem dict)
    utility_score = Column(Float)       # U(q') Gaussian weight
    
    # Metadata for filtering
    topic = Column(String, index=True)
    gap_type = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    used_in_training = Column(Integer, default=0) # Flag for Stage 9 pipeline