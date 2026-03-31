from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import uuid

from database import SessionLocal
from models.submission import Submission
from services.problem_service import get_problem_by_id, get_problems, select_problem
from services.capability_service import update_capability
from services.sandbox import run_code

router = APIRouter(prefix="/submissions", tags=["submissions"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class SubmissionRequest(BaseModel):
    user_id: str
    problem_id: str
    code: str

@router.post("")
def create_submission(request: SubmissionRequest, db: Session = Depends(get_db)):
    try:
        user_uuid = uuid.UUID(request.user_id)
        problem_uuid = uuid.UUID(request.problem_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")

    problem = get_problem_by_id(db, request.problem_id)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    visible_res = run_code(request.code, problem.visible_tests)
    if visible_res.get("error") and visible_res["error"] != "timeout":
        raise HTTPException(status_code=500, detail="Sandbox error: " + visible_res["error"])

    hidden_res = run_code(request.code, problem.hidden_tests)
    if hidden_res.get("error") and hidden_res["error"] != "timeout":
        raise HTTPException(status_code=500, detail="Sandbox error: " + hidden_res["error"])

    visible_score = visible_res.get("score", 0.0)
    hidden_score = hidden_res.get("score", 0.0)

    gamed = False
    if visible_score > 0.8 and hidden_score < 0.3:
        gamed = True

    if not gamed:
        update_capability(
            user_id=user_uuid,
            topic=problem.topic,
            submission_score=hidden_score,
            time_taken=30.0,
            time_limit=120.0,
            hint_used=False,
            attempt_num=1,
            db=db
        )

    brain_a_feedback = "Good attempt. Review edge cases."

    student_vector = {problem.topic: hidden_score}
    available_problems = get_problems(db)
    next_problem = select_problem(
        student_vector=student_vector,
        available_problems=available_problems,
        target_topic=problem.topic
    )
    next_problem_id = str(next_problem["id"]) if next_problem else None

    submission = Submission(
        user_id=user_uuid,
        problem_id=problem_uuid,
        code=request.code,
        visible_score=visible_score,
        hidden_score=hidden_score,
        brain_a_feedback=brain_a_feedback,
        gamed=gamed
    )
    db.add(submission)
    db.commit()

    return {
        "visible_score": visible_score,
        "hidden_score": hidden_score,
        "gamed": gamed,
        "feedback": brain_a_feedback,
        "next_problem_id": next_problem_id
    }
