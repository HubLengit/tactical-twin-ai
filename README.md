# ⚽ TacticalTwin AI - End-to-End Football Analytics Platform

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![PyTorch](https://img.shields.io/badge/PyTorch-MPS%2FCUDA-EE4C2C.svg)
![OpenCV](https://img.shields.io/badge/OpenCV-Computer_Vision-5C3EE8.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-API_Backend-009688.svg)
![Celery](https://img.shields.io/badge/Celery-Asynchronous-37814A.svg)
![Ollama](https://img.shields.io/badge/Ollama-Local_LLM-black.svg)

> **TacticalTwin AI** is a production-ready, distributed computer vision pipeline designed to analyze football match videos. It transforms raw pixel data into structured tactical state machines and generates natural language coaching reports using local Large Language Models.

*Insert GIF*

## 🧠 System Architecture Overview

This project goes beyond simple object detection. It is built as a complete Data Engineering and Machine Learning system:

1. **Distributed Backend:** Built with **FastAPI** for instant request handling, backed by **Celery** and **Redis (Docker)** for heavy, asynchronous GPU video processing.
2. **Robust Computer Vision Pipeline:**
   * **Camera Calibration:** Uses a custom YOLO Pose model to detect pitch keypoints and applies `cv2.findHomography` with RANSAC and an Exponential Moving Average (EMA) filter to project 2D pixels into real-world pitch coordinates (meters).
   * **Multi-Agent Tracking:** Integrates **YOLOv8** and **ByteTrack** for persistent player IDs, coupled with a cinematic speed estimator.
   * **Intelligent Team Classification:** Uses HSV color extraction with active "grass filtering" and a stateful **K-Means** clustering algorithm (color anchoring) to permanently assign players to their teams, completely solving the "ID Switching" issue.
   * **Ball Tracking:** Dedicated high-confidence inference layer to track ball possession dynamics.
3. **Tactical State Engine:** Transforms raw coordinates into high-level metrics at 5Hz (Barycenters, Convex Hull Compactness, Team Block Dimensions) and identifies tactical phases (`ATTACK`, `TRANSITION_DEFENSE`).
4. **Local LLM Coach (RAG):** Uses a local **Ollama** instance (Mistral/Llama3) to read the generated discrete event log (`tactical_events.json`) and output a strict, data-grounded natural language coaching report.

## ⚙️ Repository Structure

```text
tactical-twin-ai/
├── api/
│   ├── main.py                # FastAPI endpoints (/analyze, /status, /report)
│   └── worker.py              # Celery background tasks (GPU processing)
├── app/
│   └── app.py                 # Streamlit frontend for coach interaction
├── src/
│   ├── cv/
│   │   ├── clustering.py      # Stateful HSV K-Means team assignment
│   │   ├── homography.py      # Pitch projection & EMA smoothing
│   │   ├── tracking.py        # Cinematic speed calculation
│   │   └── tactical_state.py  # Spatial math (Barycenter, Convex Hull) & Event Sourcing
│   └── llm/
│       └── coach_agent.py     # Local LLM integration prompt engineering
├── docker-compose.yml         # Redis Message Broker
└── requirements.txt           # Environment dependencies
```

## 🚀 Quickstart (macOS Apple Silicon / Linux)

### 1. Environment Setup

```bash
# Clone the repository
git clone [https://github.com/VOTRE_USERNAME/tactical-twin-ai.git](https://github.com/VOTRE_USERNAME/tactical-twin-ai.git)
cd tactical-twin-ai

# Create a virtual environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Infrastructure (Redis)

Start the Redis message broker using Docker:

```bash
docker compose up -d
```

### 3. Launching the Distributed System

You need to open three separate terminal windows (ensure your `.venv` is activated in all of them).

**Terminal 1: Start the Celery Worker (GPU Processing)**
```bash
# For macOS M1/M2 (MPS support enabled):
celery -A api.worker worker --loglevel=info --pool=solo
```

**Terminal 2: Start the FastAPI Server**
```bash
uvicorn api.main:app --reload
```

**Terminal 3: Start the Streamlit Frontend**
```bash
streamlit run app/app.py
```

## 📊 How it works

1. Upload a `.mp4` football clip via the Streamlit interface.
2. The frontend sends the video path to the FastAPI backend, which instantly returns a `task_id` and delegates the heavy lifting to the Celery queue.
3. The Celery worker processes the video on the GPU, outputting an annotated radar video (`.mp4`) and a highly structured discrete event log (`tactical_events.json`).
4. Once completed, the frontend triggers the LLM Coach Agent via FastAPI, which reads the JSON events and generates a professional tactical summary grounded strictly in the computed spatial data.