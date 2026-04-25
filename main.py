from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import pathlib

from database import init_db
from routers import cantieri, dipendenti, attestati, visite, tipi_formazione, dashboard, cantieri_temp, auth
from routers.auth import verify_token

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Gestione Formazioni e Visite Mediche",
    description="API CRUD per la gestione di attestati e visite mediche dei dipendenti",
    version="1.0.0",
)

# ── CORS — necessario per GitHub Pages ───────────────────────────────────────
# In produzione sostituisci "*" con il tuo dominio GitHub Pages, es.:
# "https://tuonome.github.io"
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)   # pubblico — nessuna protezione
app.include_router(cantieri.router, dependencies=[Depends(verify_token)])
app.include_router(dipendenti.router, dependencies=[Depends(verify_token)])
app.include_router(attestati.router, dependencies=[Depends(verify_token)])
app.include_router(visite.router, dependencies=[Depends(verify_token)])
app.include_router(tipi_formazione.router, dependencies=[Depends(verify_token)])
app.include_router(dashboard.router, dependencies=[Depends(verify_token)])
app.include_router(cantieri_temp.router, dependencies=[Depends(verify_token)])

# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
def startup():
    init_db()


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["Sistema"])
def health():
    return {"status": "ok"}


# ── Root ──────────────────────────────────────────────────────────────────────
@app.get("/", tags=["Sistema"])
def root():
    return {
        "app": "Gestione Formazioni",
        "docs": "/docs",
        "versione": "1.0.0",
    }
