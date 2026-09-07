import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import joblib

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / 'backend'))

from backend.api.routes import router

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / 'ml' / 'model.pkl'
DATA_DIR = BASE_DIR / 'data'

app = FastAPI(title='CrowdTrack AI', version='1.0.0')
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(router, prefix='/api')

@app.get('/api/health')
def health():
    return {'status': 'ok', 'service': 'crowdtrack-ai'}

@app.get('/')
def root():
    return {'message': 'CrowdTrack AI backend running'}

# Create local model placeholder to ensure import path works even before training
@app.on_event('startup')
def startup_event():
    if not MODEL_PATH.exists():
        import shutil
        if not (BASE_DIR / 'ml').exists():
            (BASE_DIR / 'ml').mkdir(parents=True, exist_ok=True)
        # create default empty model placeholder file so startup won't fail
        with open(MODEL_PATH, 'wb') as f:
            joblib.dump({'status': 'not_trained'}, f)

try:
    app.mount('/static', StaticFiles(directory=str(BASE_DIR / 'frontend' / 'dist')), name='static')
except Exception:
    pass
