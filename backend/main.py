from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# --- Existing Routers ---
from routers.capability import router as capability_router
from routers.problems import router as problems_router
from routers.submissions import router as submissions_router

# --- Stage 8: Socratic Dialogue Router ---
# Note: Ensure the path matches the folder you just created!
from api.dialogue import router as dialogue_router

app = FastAPI(title="AdaptLab API", version="0.1.0")

# Enable CORS for the Vite frontend (React/Vite typically runs on 5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Register Routers ---
app.include_router(capability_router)
app.include_router(problems_router)
app.include_router(submissions_router)

# This plugs the Socratic loop into your server
app.include_router(dialogue_router)

@app.get("/health")
def health_check():
    """Simple endpoint to verify the backend is breathing."""
    return {"status": "ok", "stage": 8, "mode": "Socratic"}