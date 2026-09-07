# Crowd Track AI

A professional desktop UI prototype for monitoring urban electric bus surroundings. It includes a live simulation, tracked object overlays, configurable safety zones, risk scoring, event logging, analytics, and CSV/XLSX/PDF exports.

> Educational and research prototype only. This software is not a safety-certified automotive system.

## Run

```powershell
cd adas_bus_project
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

The app starts in demo mode so the entire interface can be reviewed without a YOLO model or video file. Use **Load Video** to select footage, or update `config/config.json` for camera and zone settings.

## Included UI

- Real-time camera viewport with bounding boxes, IDs, confidence, FPS, and polygon overlays
- Risk gauge with low, medium, and high states
- Object statistics and event counters
- Live event feed with SQLite persistence
- Analytics dashboard and event history table
- CSV, Excel, and PDF exports
- Operational settings for confidence and source selection
