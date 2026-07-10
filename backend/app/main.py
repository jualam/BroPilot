from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.routes.review import router as review_router
from app.routes.runs import router as runs_router

load_dotenv()

app = FastAPI(title="BroPilot API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(runs_router)
app.include_router(review_router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "bropilot-api"
    }
