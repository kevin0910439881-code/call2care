import os
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.stt_service import transcribe_audio_bytes
from backend.llm_engine import process_patient_input, initiate_call, summarize_call
from backend.tts_service import generate_tts_async
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()

# Global call state
call_session = {
    "patient_id": "patient_001",
    "history": [],
    "status": "idle",
    "model_name": "gemini-3.5-flash-lite"
}

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")

if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast_json(self, data: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(data)
            except:
                pass

manager = ConnectionManager()
patient_manager = ConnectionManager()

@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.websocket("/ws/patient")
async def websocket_patient(websocket: WebSocket):
    await patient_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        patient_manager.disconnect(websocket)

@app.post("/api/call/ring")
async def ring_patient(patient_id: str):
    logger.info(f"Ringing patient {patient_id} from dashboard")
    await patient_manager.broadcast_json({"type": "incoming_call", "patient_id": patient_id})
    return {"status": "ringing"}

@app.get("/api/patients")
async def get_patients():
    db_path = os.path.join(BASE_DIR, "data", "mock_database.json")
    try:
        with open(db_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            patients = []
            if isinstance(data, list):
                for item in data:
                    if item.get("metadata", {}).get("type") == "patient_profile":
                        patients.append({
                            "id": item["id"],
                            "name": item["metadata"]["name"],
                            "conditions": item["metadata"].get("conditions", []),
                            "details": item["text"]
                        })
            return patients
    except Exception as e:
        logger.error(f"Error reading patients: {e}")
        return []

@app.post("/api/call/start")
async def call_start_endpoint(patient_id: str = "patient_001"):
    logger.info(f"Initializing new call for {patient_id}.")
    call_session["patient_id"] = patient_id
    call_session["status"] = "ongoing"
    call_session["history"] = []
    
    model_name = call_session.get("model_name", "gemini-3.6-flash")
    result = initiate_call(patient_id, model_name=model_name)
    ai_text = result["ai_spoken_reply"]
    logger.info(f"AI initial greeting: {ai_text}")
    call_session["history"].append({"role": "model", "content": ai_text})
    
    current_time = datetime.now().isoformat()
    symptoms_with_time = [{"name": s, "timestamp": current_time} for s in result.get("symptoms", [])]
    
    msg = {
        "type": "ai_transcript",
        "text": ai_text,
        "risk_status": result.get("risk_status", "GREEN"),
        "symptoms": symptoms_with_time,
        "action_taken": result.get("action_taken", ""),
        "case_status": result.get("case_status", "CLOSED"),
        "blood_glucose": result.get("blood_glucose")
    }
    await manager.broadcast_json(msg)
    await patient_manager.broadcast_json(msg)
    
    output_audio_path = "response.mp3"
    await generate_tts_async(ai_text, output_audio_path)
    
    if os.path.exists(output_audio_path):
        return FileResponse(output_audio_path, media_type="audio/mpeg")
    return {"error": "Failed to generate audio"}

@app.post("/api/chat")
async def chat_endpoint(audio_file: UploadFile = File(...)):
    # 1. Read audio bytes directly
    audio_bytes = await audio_file.read()
        
    # 2. STT (Groq)
    transcript = transcribe_audio_bytes(audio_file.filename, audio_bytes)
        
    # Log patient side
    call_session["history"].append({"role": "user", "content": transcript})
    msg = {
        "type": "patient_transcript",
        "text": transcript
    }
    await manager.broadcast_json(msg)
    await patient_manager.broadcast_json(msg)
        
    # 3. LLM Processing
    logger.info(f"Processing patient input: '{transcript}'")
    model_name = call_session.get("model_name", "gemini-3.6-flash")
    llm_result = process_patient_input(call_session["patient_id"], transcript, call_session["history"], model_name=model_name)
    ai_text = llm_result["ai_spoken_reply"]
    logger.info(f"LLM generated reply: '{ai_text}', End call? {llm_result.get('end_call')}")
    call_session["history"].append({"role": "model", "content": ai_text})
    
    # 4. Broadcast to Dashboard
    current_time = datetime.now().isoformat()
    symptoms_with_time = [{"name": s, "timestamp": current_time} for s in llm_result.get("symptoms", [])]
    
    ai_msg = {
        "type": "ai_transcript",
        "text": ai_text,
        "risk_status": llm_result.get("risk_status", "GREEN"),
        "symptoms": symptoms_with_time,
        "action_taken": llm_result.get("action_taken", ""),
        "case_status": llm_result.get("case_status", "CLOSED"),
        "blood_glucose": llm_result.get("blood_glucose")
    }
    await manager.broadcast_json(ai_msg)
    await patient_manager.broadcast_json(ai_msg)
    
    headers = {}
    if llm_result.get("end_call"):
        logger.info("Call marked as ended. Generating summary.")
        call_session["status"] = "ended"
        model_name = call_session.get("model_name", "gemini-3.6-flash")
        summarize_call(call_session["patient_id"], call_session["history"], model_name=model_name)
        headers["X-Call-Ended"] = "true"
    
    # 5. TTS (edge-tts)
    output_audio_path = "response.mp3"
    await generate_tts_async(ai_text, output_audio_path)
    
    # 6. Return Audio file
    if os.path.exists(output_audio_path):
        return FileResponse(output_audio_path, media_type="audio/mpeg", headers=headers)
    return {"error": "Failed to generate audio"}

from pydantic import BaseModel
class ModelSettings(BaseModel):
    model_name: str

@app.post("/api/settings/model")
async def update_model_settings(settings: ModelSettings):
    call_session["model_name"] = settings.model_name
    logger.info(f"Model updated to: {settings.model_name}")
    return {"status": "success", "model_name": call_session["model_name"]}

