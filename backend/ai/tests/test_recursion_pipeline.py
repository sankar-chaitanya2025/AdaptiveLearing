import asyncio
import json
import os
from ai.brain_b import BrainB

async def verify_stage_7():
    # Ensure we can talk to the model
    teacher = BrainB()

    # TEST CASE: Student submits factorial without a base case
    mock_problem = {
        "statement": "Write a recursive function 'factorial(n)' to calculate the factorial of a number.",
        "topic": "recursion"
    }
    
    # Infinite recursion code (Missing base case)
    mock_student_code = "def factorial(n):\n    return n * factorial(n-1)"
    
    # Simulation of Brain A and Sandbox results
    # Setting sq to 0.25 (1/4 tests) triggers the Socratic/Refinement loop
    mock_sandbox_learning = {"visible_passed": 1, "visible_total": 4} 
    mock_brain_a = {"failure_mode": "timeout", "consecutive_fails": 1}

    print("🛰️  STARTING STAGE 7 INTEGRATION TEST...")
    print("💡 Note: 8B 'Thinking Mode' may take 15-30 seconds. Do not cancel.")
    
    try:
        # Run the full co-evolutionary pipeline
        result = await teacher.full_pipeline(
            problem=mock_problem,
            code=mock_student_code,
            sandbox=mock_sandbox_learning, 
            brain_a=mock_brain_a
        )

        print("\n✅ TEST COMPLETED. VERIFYING OUTPUT:")
        print(f"--- ZPD Zone: {result['zpd']['zone']} (Utility: {result.get('plato_utility', 0.0):.2f})")
        
        # Verify Classification
        print(f"--- Gap Detected: {result['classification']['gap_type']}")
        print(f"--- Root Cause: {result['classification']['root_cause']}")
        
        # Verify Socratic Dialogue
        print(f"--- Socratic Question: {result['socratic_question']}")
        
        # Verify Problem Refinement
        print(f"--- New Task: {result['refined_problem']['title']}")
        print(f"--- New Solution Extracted: {'YES' if result['refined_problem'].get('solution') else 'NO'}")

    except Exception as e:
        print(f"❌ TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(verify_stage_7())