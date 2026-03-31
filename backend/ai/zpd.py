import math
from dataclasses import dataclass

@dataclass
class ZPDResult:
    zone: str       # "mastered" | "learning_zone" | "too_difficult"
    utility: float  # Gaussian score U(q')
    sq: float       # Success rate (0.0 - 1.0)

def compute_zpd_utility(sq: float, mu: float = 0.5, sigma: float = 0.2) -> float:
    """
    Paper Eq.6: Gaussian reward function centered at mu=0.5.
    Targets the 'frontier' of student capability.
    """
    return math.exp(-((sq - mu)**2) / (2 * sigma**2))

def zpd_router(sq: float) -> ZPDResult:
    """
    Partitions student performance into ZPD zones.
    sq = visible_passed / visible_total
    """
    utility = compute_zpd_utility(sq)
    
    if sq == 0.0:
        zone = "too_difficult" # Exclude from generation to avoid noise
    elif sq == 1.0:
        zone = "mastered"      # Generate harder variants
    else:
        zone = "learning_zone" # Optimal frontier for Socratic refinement
        
    return ZPDResult(zone=zone, utility=utility, sq=sq)