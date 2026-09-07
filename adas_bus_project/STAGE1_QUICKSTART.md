# 🚀 STAGE 1 QUICK START GUIDE

## ✅ What's Ready Now (Stage 1)

**COMPLETE:**
- ✅ YOLOv8 Object Detection (6 classes: person, bicycle, motorcycle, car, bus, truck)
- ✅ ByteTrack Object Tracking (persistent IDs, track history)
- ✅ Zone-Based Safety Detection (4 configurable zones)
- ✅ Real-time Visualization (bounding boxes, track IDs, alerts)
- ✅ Object Filtering & Categorization
- ✅ Fully Documented Codebase

---

## 📦 Installation (5 Minutes)

### 1. Open Terminal/Command Prompt

### 2. Navigate to Project
```bash
cd C:\Users\DELL01\Downloads\adas_bus_project
```

### 3. Create Virtual Environment (Optional)
```bash
python -m venv venv
venv\Scripts\activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

⏱️ **Installation Time:** ~2-5 minutes (depending on internet speed)

---

## 🎬 Running Stage 1 Demo

### **Option 1: Webcam (Live Feed)**
```bash
python stage1_demo.py --webcam
```
✅ **Works immediately - no video file needed!**

### **Option 2: Video File**
```bash
python stage1_demo.py --video your_video.mp4
```

### **Option 3: Save Output Video**
```bash
python stage1_demo.py --webcam --output output.mp4
```

### **Option 4: Use Different Config**
```bash
python stage1_demo.py --webcam --config config/config.json
```

---

## ⌨️ Keyboard Controls While Running

| Key | Action |
|-----|--------|
| **q** | Quit the application |
| **p** | Pause/Resume video |
| **s** | Save screenshot |

---

## 🎯 What You'll See

### On Screen:
1. **Bounding Boxes** - Green boxes around detected objects
2. **Track IDs** - "ID: 1", "ID: 2" labels
3. **Class Labels** - "person", "car", "motorcycle" with confidence
4. **Track History** - Thin lines showing object movement
5. **Zone Overlays** - Colored semi-transparent areas for safety zones
6. **Info Panel** (top-left):
   - Frame count
   - FPS
   - Total objects detected
   - Count by class (Pedestrians, Motorcycles, Vehicles, etc.)
   - Active tracks

### Alerts:
- **RED BOUNDING BOX** = Object in safety zone
- **Alert Message** = Zone intrusion alert (e.g., "BLIND SPOT WARNING")

---

## 📁 Project Structure

```
adas_bus_project/
├── stage1_demo.py           ← RUN THIS FILE!
├── config/
│   └── config.json          ← Edit zones here
├── detection/
│   ├── detector.py          (YOLOv8 wrapper)
│   ├── tracker.py           (ByteTrack implementation)
│   └── object_filter.py     (Object categorization)
├── zones/
│   ├── zone_manager.py      (Zone system)
│   └── zone_utils.py        (Visualization)
└── README.md                (Full documentation)
```

---

## ⚙️ Configuration

### Edit Zones (config/config.json)

**Current Zones:**
1. `left_blind_spot` - Left side of bus
2. `right_blind_spot` - Right side of bus
3. `door_safety_zone` - Near bus doors
4. `left_turn_risk_zone` - During left turns

**Zone Format (Normalized Coordinates 0.0-1.0):**
```json
"zones": {
    "zone_name": {
        "name": "Display Name",
        "points": [[x1, y1], [x2, y2], [x3, y3], [x4, y4]],
        "color": [B, G, R],
        "alert_message": "ALERT TEXT"
    }
}
```

**Example: Edit Left Blind Spot**
```json
"left_blind_spot": {
    "name": "Left Blind Spot",
    "points": [[0.02, 0.40], [0.28, 0.34], [0.34, 0.95], [0.02, 0.95]],
    "color": [0, 0, 255],
    "alert_message": "BLIND SPOT WARNING"
}
```

- `points`: Clockwise polygon vertices (top-left, top-right, bottom-right, bottom-left)
- `color`: BGR format ([Blue, Green, Red]) - e.g., [0, 0, 255] = Red
- Coordinates: 0.0 = left/top, 1.0 = right/bottom

### Adjust Detection Confidence
```json
"yolo_settings": {
    "confidence_threshold": 0.50
}
```
- **0.50** = Default (balanced)
- **0.30** = More detections (more false positives)
- **0.70** = Fewer detections (more reliable)

---

## 🔍 Understanding Output

### Console Output:
```
2026-06-22 12:34:56 - root - INFO - Initializing ADAS Stage 1 components...
2026-06-22 12:34:57 - root - INFO - ✓ YOLOv8 Detector loaded
2026-06-22 12:34:57 - root - INFO - ✓ ByteTracker initialized
2026-06-22 12:34:58 - root - INFO - Starting ADAS Stage 1 demo...
2026-06-22 12:35:10 - root - INFO - Processed 100 frames | Active tracks: 5 | Objects: 12
```

### Metrics Shown:
- **Frame**: Current frame number
- **FPS**: Frames per second (target: 20+)
- **Objects**: Total detected objects
- **Pedestrians**: Count of people
- **Motorcycles**: Count of motorcycles
- **Vehicles**: Count of cars/buses/trucks
- **Tracks**: Active tracked objects

---

## 🐛 Common Issues & Fixes

### **Issue: "ModuleNotFoundError: No module named 'ultralytics'"**
**Fix:**
```bash
pip install --upgrade ultralytics
```

### **Issue: "Camera not found" or Webcam doesn't work**
**Fix 1:** Try different camera index
```bash
python stage1_demo.py --webcam  # Default is camera 0
```

**Fix 2:** Use a video file instead
```bash
python stage1_demo.py --video test_video.mp4
```

### **Issue: Low FPS (slower than 20)**
**Fixes:**
- Use GPU instead of CPU (if available): Install `torch` with CUDA support
- Reduce frame size in code
- Close other applications
- Use simpler model (already using yolov8n - the fastest)

### **Issue: "No module named 'detection'" or similar**
**Fix:** Make sure you're in the project root directory
```bash
# Correct location
cd C:\Users\DELL01\Downloads\adas_bus_project
python stage1_demo.py --webcam

# Wrong location - don't run from subdirectories
```

### **Issue: Video file not processing**
**Fix:**
```bash
# Use absolute path
python stage1_demo.py --video C:\Users\DELL01\Downloads\video.mp4

# Or copy video to videos/ folder
python stage1_demo.py --video videos/test.mp4
```

---

## 📊 Performance Expectations

| Hardware | YOLOv8n FPS |
|----------|-----------|
| Intel i5 CPU | 15-25 FPS |
| Intel i7 CPU | 25-35 FPS |
| RTX 3060 GPU | 100-150 FPS |
| RTX 4090 GPU | 200+ FPS |

**Note:** FPS varies based on frame resolution, object count, and system load.

---

## 🎓 Understanding the Code

### Stage 1 Flow:
```
1. Load Frame (from video/webcam)
   ↓
2. Run YOLOv8 Detection
   → Returns: boxes, confidences, class IDs
   ↓
3. Update ByteTrack
   → Assigns persistent track IDs
   → Removes old tracks
   ↓
4. Check Zone Intrusions
   → Tests if track center is in zone
   → Triggers alerts
   ↓
5. Visualize
   → Draw boxes, IDs, zones, alerts
   ↓
6. Display Frame
```

### Key Classes:

**YOLODetector** (detection/detector.py)
```python
detector = YOLODetector("models/yolov8n.pt", confidence=0.5)
detections = detector.detect(frame)
# detections = {boxes, confidences, class_ids, class_names}
```

**ByteTracker** (detection/tracker.py)
```python
tracker = ByteTracker(track_buffer=30)
tracks = tracker.update(detections, frame_id)
# tracks = [Track(id, class_name, bbox, confidence, history)]
```

**ZoneManager** (zones/zone_manager.py)
```python
zone_mgr = ZoneManager(1600, 900)
zone_mgr.add_zone("blind_spot", "Left Blind Spot", points)
is_in = zone_mgr.object_in_zone(bbox, "blind_spot")
```

---

## 🎬 Example Commands

### Test with Webcam (Easiest)
```bash
python stage1_demo.py --webcam
```

### Process Video & Save Output
```bash
python stage1_demo.py --video input.mp4 --output results.mp4
```

### Use Custom Configuration
```bash
python stage1_demo.py --webcam --config custom_config.json
```

### Extended Session (Verbose Logging)
```bash
python stage1_demo.py --webcam 2> debug.log
```

---

## 📚 Next Steps

### To Test More:
1. ✅ Run with webcam
2. ✅ Edit zones in config.json
3. ✅ Try different video files
4. ✅ Adjust confidence threshold
5. ✅ Check console output for errors

### To Understand Code:
1. Read docstrings in each file
2. Check class implementations in `detection/` folder
3. Review zone visualization in `zones/zone_utils.py`
4. Trace execution flow in `stage1_demo.py`

### For Stage 2 Features (Coming Soon):
- Risk scoring engine
- Event logging to SQLite
- Analytics dashboard
- CSV/Excel export
- PDF report generation
- Full PyQt6 GUI

---

## ✨ Key Features of Stage 1

| Feature | Status | Details |
|---------|--------|---------|
| YOLOv8 Detection | ✅ | 6 classes, 0.50 confidence |
| ByteTrack Tracking | ✅ | Persistent IDs, history |
| 4 Safety Zones | ✅ | Configurable polygons |
| Real-time Alerts | ✅ | Displayed on video |
| FPS Counter | ✅ | Shows performance |
| Object Categorization | ✅ | Pedestrians, vehicles, etc. |
| Screenshot Saving | ✅ | Press 's' while running |
| Video Export | ✅ | --output flag |
| Configuration System | ✅ | JSON-based |
| Documentation | ✅ | Full code docs |

---

## 🚀 Ready to Start?

### Quickest Path (30 seconds):
```bash
cd C:\Users\DELL01\Downloads\adas_bus_project
pip install -r requirements.txt
python stage1_demo.py --webcam
```

**That's it! You should see live detection and tracking within seconds.**

---

## 📞 Troubleshooting Checklist

- [ ] Python 3.11+ installed? (`python --version`)
- [ ] In correct directory? (`cd adas_bus_project`)
- [ ] Dependencies installed? (`pip list | grep ultralytics`)
- [ ] Webcam/video file accessible?
- [ ] config.json exists and is valid JSON?
- [ ] No other application using your webcam?

If still stuck, check `README.md` for detailed troubleshooting.

---

**Version:** 1.0.0 - Stage 1 Complete
**Status:** ✅ Ready to Use
**Last Updated:** June 2026
