import uvicorn
from fastapi import FastAPI

from app.api.routers.payment import payment_router

app = FastAPI()

app.include_router(payment_router, prefix="/api/v1")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
