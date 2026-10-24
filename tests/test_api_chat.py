import pytest
from fastapi.testclient import TestClient
import os

def test_api_chat_endpoint(mocker):
    from backend.main import app
    client = TestClient(app)
    
    # Mock the internal services
    mocker.patch('backend.main.transcribe_audio_bytes', return_value="我頭暈")
    mocker.patch('backend.main.process_patient_input', return_value={
        "ai_spoken_reply": "阿公你好，有按時吃藥嗎？",
        "end_call": False,
        "clinical_dashboard_data": {
            "medication_status": "Unknown",
            "risk_level": "Red",
            "symptoms": ["Dizziness"]
        }
    })
    async def mock_tts(*args, **kwargs):
        return "dummy_response.mp3"
    mocker.patch('backend.main.generate_tts_async', side_effect=mock_tts)
    
    # We need to mock os.path.exists for FileResponse
    original_exists = os.path.exists
    def mock_exists(path):
        if path == "response.mp3" or path == "dummy_response.mp3":
            return True
        return original_exists(path)
    mocker.patch('os.path.exists', side_effect=mock_exists)
    
    # We need to mock stat for FileResponse so it doesn't crash
    mock_stat = mocker.Mock()
    mock_stat.st_size = 100
    mock_stat.st_mtime = 0
    mock_stat.st_mode = 33188 # 0o100644 regular file
    mocker.patch('os.stat', return_value=mock_stat)
    
    # Mock open for FileResponse streaming
    mocker.patch('builtins.open', mocker.mock_open(read_data=b"mp3 bytes"))
    
    # Send a dummy audio file
    files = {"audio_file": ("test.wav", b"fake audio data", "audio/wav")}
    # Simulate state
    response = client.post("/api/chat", files=files)
    
    assert response.status_code == 200
    assert response.headers["content-type"] in ["audio/mpeg", "audio/mp3"]

def test_api_call_start(mocker):
    from backend.main import app
    client = TestClient(app)

    mocker.patch('backend.main.initiate_call', return_value={
        "ai_spoken_reply": "你好，我是健康助理。",
        "end_call": False,
        "clinical_dashboard_data": {
            "medication_status": "Unknown",
            "risk_level": "Green",
            "symptoms": []
        }
    })
    
    async def mock_tts(*args, **kwargs):
        return "dummy_response.mp3"
    mocker.patch('backend.main.generate_tts_async', side_effect=mock_tts)

    original_exists = os.path.exists
    def mock_exists(path):
        if path == "response.mp3" or path == "dummy_response.mp3":
            return True
        return original_exists(path)
    mocker.patch('os.path.exists', side_effect=mock_exists)

    mock_stat = mocker.Mock()
    mock_stat.st_size = 100
    mock_stat.st_mtime = 0
    mock_stat.st_mode = 33188
    mocker.patch('os.stat', return_value=mock_stat)
    mocker.patch('builtins.open', mocker.mock_open(read_data=b"mp3 bytes"))

    response = client.post("/api/call/start")
    
    assert response.status_code == 200
    assert response.headers["content-type"] in ["audio/mpeg", "audio/mp3"]
