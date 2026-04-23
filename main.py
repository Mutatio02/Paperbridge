from fastapi import FastAPI
from backend.api.routes import router

app = FastAPI(title="PaperBridge API")

# 라우터 등록
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)