from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from app.database import create_tables
from app.routers import chat, stt, tts, history, debug, review
from app.routers.settings import router as settings_router
from app.routers.vad import router as vad_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    yield


app = FastAPI(title="Speakeasy API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(stt.router)
app.include_router(tts.router)
app.include_router(history.router)
app.include_router(debug.router)
app.include_router(review.router)
app.include_router(settings_router)
app.include_router(vad_router)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/.well-known/appspecific/com.chrome.devtools.json")
async def devtools_noop():
    from fastapi.responses import Response
    return Response(status_code=204)


@app.get("/")
async def root():
    return FileResponse("static/index.html")


@app.get("/review")
async def review_page():
    return FileResponse("static/review.html")
