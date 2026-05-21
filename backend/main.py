# backend/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from app.api.routes import auth, standards
from app.api.routes import auth, standards, audits, risks

load_dotenv()

app = FastAPI(
    title="GRC Vault API",
    description="Compliance AI Platform",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────
app.include_router(auth.router, prefix="/api/v1")
app.include_router(standards.router, prefix="/api/v1")
app.include_router(audits.router, prefix="/api/v1")
app.include_router(risks.router, prefix="/api/v1")


@app.get("/")
def root():
    return {"message": "GRC Vault API is running", "status": "ok"}


@app.get("/health")
def health():
    return {"status": "healthy"}


# # backend/main.py

# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware
# from dotenv import load_dotenv
# from app.api.routes import auth

# load_dotenv()

# app = FastAPI(
#     title="GRC Vault API",
#     description="Compliance AI Platform",
#     version="1.0.0"
# )

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["http://localhost:5173"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # ── Register routers ───────────────────────────────────────
# app.include_router(auth.router, prefix="/api/v1")


# @app.get("/")
# def root():
#     return {"message": "GRC Vault API is running", "status": "ok"}


# @app.get("/health")
# def health():
#     return {"status": "healthy"}
