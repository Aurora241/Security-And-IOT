from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1 import employees, access_credentials, access_logs, access_policies, devices
from app.api.v1 import alarm
from app.services import mqtt_subscriber


@asynccontextmanager
async def lifespan(app: FastAPI):
    mqtt_subscriber.start()
    yield
    mqtt_subscriber.stop()


app = FastAPI(title="Smart Access Control API", version="0.1.0", lifespan=lifespan)

# Dashboard React (Vite dev server, port 5173 mac dinh) goi API tu origin khac - can CORS.
# Chi mo cho dev local, chua co danh sach domain production (he thong van dang chay local).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# RuntimeError tu access_control.get_primary_access_point() (vd: chua chay SQL migration
# tao access_point) la loi config, khong phai loi 500 ngau nhien - tra JSON + CORS binh
# thuong thay vi de ServerErrorMiddleware tra "Internal Server Error" thuan text KHONG co
# header CORS (lam browser bao sai thanh "Failed to fetch", an mat thong bao loi that).
@app.exception_handler(RuntimeError)
async def runtime_error_handler(request: Request, exc: RuntimeError):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


app.include_router(employees.router, prefix="/api/v1")
app.include_router(access_credentials.router, prefix="/api/v1")
app.include_router(access_logs.router, prefix="/api/v1")
app.include_router(access_policies.router, prefix="/api/v1")
app.include_router(devices.router, prefix="/api/v1")
app.include_router(alarm.router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok"}


app.mount("/demo", StaticFiles(directory="app/static", html=True), name="demo")
