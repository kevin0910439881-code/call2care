import pytest
from backend.stt_service import transcribe_audio_bytes

def test_transcribe_audio_success(mocker):
    # Mock the Groq client to prevent real API calls
    mock_client = mocker.Mock()
    # Assume the create method returns the transcription text directly when response_format='text'
    mock_client.audio.transcriptions.create.return_value = "阿公你好"
    
    mocker.patch('backend.stt_service.client', mock_client)
    
    result = transcribe_audio_bytes("dummy.wav", b"dummy audio data")
    assert "阿公你好" in result
