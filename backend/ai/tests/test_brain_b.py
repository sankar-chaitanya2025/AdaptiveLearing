import sys
import os

# FIXED: Go up 2 levels to project root (AdaptLab/)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
sys.path.insert(0, project_root)

# Import zpd (now finds backend.ai.zpd)
from backend.ai.zpd import zpd_router, compute_zpd_utility

def test_zpd_math():
    print("🧮 Testing Socratic-Zero Eq.6 (Gaussian Utility)...")
    assert abs(compute_zpd_utility(0.5) - 1.0) < 0.01, "Peak μ=0.5 FAILED"
    assert compute_zpd_utility(0.0) < 0.2, "Too difficult weight FAILED"  
    assert compute_zpd_utility(1.0) < 0.2, "Mastered weight FAILED"
    assert 0.7 < compute_zpd_utility(0.4) < 0.95, "Learning zone FAILED"
    print("✅ ZPD Math: PASS (Paper Eq.6 validated)")
    
    print("🗺️ Testing ZPD Router...")
    assert zpd_router(0.0).zone == "too_difficult"
    assert zpd_router(0.3).zone == "learning_zone"  
    assert zpd_router(1.0).zone == "mastered"
    print("✅ ZPD Router: PASS")
    print("🎯 Stage 7 Math Foundation: READY")

if __name__ == "__main__":
    test_zpd_math()