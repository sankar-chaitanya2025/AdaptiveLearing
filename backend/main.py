from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.capability import router as capability_router
from routers.problems import router as problems_router
from routers.submissions import router as submissions_router

app = FastAPI(title="AdaptLab API", version="0.1.0")

# Enable CORS for the Vite frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routers ---
app.include_router(capability_router)
app.include_router(problems_router)
app.include_router(submissions_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
