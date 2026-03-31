from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import uuid

from database import SessionLocal
from models.submission import Submission
from services.problem_service import get_problem_by_id, get_problems, select_problem
from services.capability_service import update_capability
from services.sandbox import run_code
from ai.brain_a import evaluate_submission
from ai.brain_b import BrainB

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
async def create_submission(request: SubmissionRequest, db: Session = Depends(get_db)):
    try:
        user_uuid = uuid.UUID(request.user_id)
        problem_uuid = uuid.UUID(request.problem_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")

    problem = get_problem_by_id(db, request.problem_id)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    visible_res = run_code(request.code, problem.visible_tests)
    if visible_res.get("error") and visible_res["error"] not in ("timeout", "no output", "parse error"):
        raise HTTPException(status_code=500, detail="Sandbox error: " + visible_res["error"])

    hidden_res = run_code(request.code, problem.hidden_tests)
    if hidden_res.get("error") and hidden_res["error"] not in ("timeout", "no output", "parse error"):
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

    # Build combined sandbox result for Brain A
    student_vector = {problem.topic: hidden_score}
    sandbox_result = {"visible": visible_res, "hidden": hidden_res}

    # Brain A LLM evaluation — never crashes submission
    brain_a_result = await evaluate_submission(
        problem=problem,
        student_vector=student_vector,
        code=request.code,
        sandbox_result=sandbox_result,
    )

    # Brain B Socratic pipeline — triggered when Brain A flags it
    brain_b_data = None
    plato_logged = False
    if brain_a_result.call_brain_b:
        brain_b = BrainB()
        brain_b_data = await brain_b.full_pipeline(
            problem=problem,
            code=request.code,
            sandbox_result=sandbox_result,
            brain_a_failure_mode=brain_a_result.failure_mode,
            db=db,
        )
        plato_logged = brain_b_data.get("refined_problem") is not None

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
        brain_a_feedback=brain_a_result.feedback,
        gamed=gamed
    )
    db.add(submission)
    db.commit()

    response = {
        "visible_score": visible_score,
        "hidden_score": hidden_score,
        "gamed": gamed,
        "feedback": brain_a_result.feedback,
        "call_brain_b": brain_a_result.call_brain_b,
        "failure_mode": brain_a_result.failure_mode,
        "next_problem_id": next_problem_id,
    }

    if brain_b_data:
        response["brain_b"] = brain_b_data
        response["plato_logged"] = plato_logged

    return response

