from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.multimodal import router as multimodal_router

app = FastAPI(title="NewsVerified AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(multimodal_router)

@app.get("/")
def home():
    return {
        "message": "NewsVerified AI Backend Running"
    }

@app.get("/health")
def health():
    return {
        "status": "online"
    }