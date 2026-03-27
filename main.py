"""
FastAPI 앱 진입점.
uvicorn main:app --reload
"""

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI

from controller.meeting import router as meeting_router
from controller.persona import router as persona_router
from controller.research import router as research_router

app = FastAPI(title="Interactive Multi-Agent", version="0.1.0")

app.include_router(research_router)
app.include_router(persona_router)
app.include_router(meeting_router)
