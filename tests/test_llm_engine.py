import json
import pytest
from backend.llm_engine import process_patient_input, get_patient_profile


class MockResponse:
    def __init__(self, text):
        self.text = text


def test_process_patient_input_green(mocker):
    """Normal vitals → GREEN, CLOSED."""
    mock_client_instance = mocker.Mock()
    mock_response_json = json.dumps({
        "ai_spoken_reply": "張先生，您的血糖正常，今天先這樣囉，保重！",
        "risk_status": "GREEN",
        "symptoms": [],
        "action_taken": "",
        "case_status": "CLOSED",
        "end_call": True,
    })
    mock_client_instance.models.generate_content.return_value = MockResponse(mock_response_json)
    mocker.patch("backend.llm_engine.client", mock_client_instance)
    mocker.patch("backend.llm_engine.query_rag_context", return_value="Mock context")
    mocker.patch("backend.llm_engine.get_patient_profile", return_value=("Mock profile", ["MockCondition"]))

    result = process_patient_input("patient_001", "我的血糖 120，血壓正常", [])

    assert result["risk_status"] == "GREEN"
    assert result["case_status"] == "CLOSED"
    assert "ai_spoken_reply" in result


def test_process_patient_input_yellow(mocker):
    """Mild symptoms → YELLOW, PENDING_PHARMACIST_REVIEW."""
    mock_client_instance = mocker.Mock()
    mock_response_json = json.dumps({
        "ai_spoken_reply": "林太太，血壓稍微偏高，請多休息，我會請藥師注意。",
        "risk_status": "YELLOW",
        "symptoms": ["mild headache"],
        "action_taken": "已通報家屬",
        "case_status": "PENDING_FAMILY_REVIEW",
        "end_call": False,
    })
    mock_client_instance.models.generate_content.return_value = MockResponse(mock_response_json)
    mocker.patch("backend.llm_engine.client", mock_client_instance)
    mocker.patch("backend.llm_engine.query_rag_context", return_value="Mock context")
    mocker.patch("backend.llm_engine.get_patient_profile", return_value=("Mock profile", ["MockCondition"]))

    result = process_patient_input("patient_002", "我的血壓 135，頭有點緊緊的", [])

    assert result["risk_status"] == "YELLOW"
    assert result["case_status"] == "PENDING_FAMILY_REVIEW"
    assert len(result["symptoms"]) > 0


def test_process_patient_input_red_hypoglycemia(mocker):
    """Low blood sugar + symptoms → RED, PENDING_PHARMACIST_REVIEW."""
    mock_client_instance = mocker.Mock()
    mock_response_json = json.dumps({
        "ai_spoken_reply": "張先生，血糖65有點低，您有頭暈嗎？",
        "risk_status": "RED",
        "symptoms": ["dizziness", "shaking"],
        "action_taken": "已通報家屬",
        "case_status": "PENDING_FAMILY_REVIEW",
        "end_call": False,
    })
    mock_client_instance.models.generate_content.return_value = MockResponse(mock_response_json)
    mocker.patch("backend.llm_engine.client", mock_client_instance)
    mocker.patch("backend.llm_engine.query_rag_context", return_value="Mock context")
    mocker.patch("backend.llm_engine.get_patient_profile", return_value=("Mock profile", ["MockCondition"]))

    result = process_patient_input("patient_001", "我的血糖 65，頭有點暈", [])

    assert result["risk_status"] == "RED"
    assert result["case_status"] == "PENDING_FAMILY_REVIEW"
    assert len(result["symptoms"]) > 0


def test_process_patient_input_empty():
    """Empty transcript returns fallback."""
    result = process_patient_input("patient_001", "", [])
    assert result["risk_status"] == "GREEN"
    assert "拍謝" in result["ai_spoken_reply"]


def test_initiate_call(mocker):
    from backend.llm_engine import initiate_call
    mock_client_instance = mocker.Mock()
    mock_response_json = json.dumps({
        "ai_spoken_reply": "張先生您好，我是您的健康秘書。",
        "risk_status": "GREEN",
        "symptoms": [],
        "action_taken": "",
        "case_status": "CLOSED",
        "end_call": False,
    })
    mock_client_instance.models.generate_content.return_value = MockResponse(mock_response_json)
    mocker.patch("backend.llm_engine.client", mock_client_instance)
    mocker.patch("backend.llm_engine.get_patient_profile", return_value=("Mock profile", ["MockCondition"]))

    result = initiate_call("patient_001")
    assert "ai_spoken_reply" in result
    assert "risk_status" in result


def test_process_patient_input_end_call(mocker):
    """When the LLM says end_call=True, it should come through."""
    mock_client_instance = mocker.Mock()
    mock_response_json = json.dumps({
        "ai_spoken_reply": "好的，今天的關心就到這邊，再見。",
        "end_call": True,
        "risk_status": "GREEN",
        "symptoms": [],
        "action_taken": "",
        "case_status": "CLOSED",
    })
    mock_client_instance.models.generate_content.return_value = MockResponse(mock_response_json)
    mocker.patch("backend.llm_engine.client", mock_client_instance)
    mocker.patch("backend.llm_engine.query_rag_context", return_value="Mock context")
    mocker.patch("backend.llm_engine.get_patient_profile", return_value=("Mock profile", ["MockCondition"]))

    history = [{"role": "user", "content": "我沒事了"}]
    result = process_patient_input("patient_001", "我沒事了", history)

    assert result.get("end_call") is True


def test_summarize_call(mocker):
    from backend.llm_engine import summarize_call
    mock_client_instance = mocker.Mock()
    mock_client_instance.models.generate_content.return_value = MockResponse("Summary text")
    mocker.patch("backend.llm_engine.client", mock_client_instance)
    mocker.patch("builtins.open", mocker.mock_open())
    mocker.patch("os.path.exists", return_value=False)

    history = [{"role": "user", "content": "你好"}, {"role": "model", "content": "你好嗎"}]
    result = summarize_call("patient_001", history)
    assert result == "Summary text"


def test_get_patient_profile_not_found(mocker):
    from backend.llm_engine import get_patient_profile
    mocker.patch("builtins.open", mocker.mock_open(read_data="[]"))
    profile, conditions = get_patient_profile("non_existent")
    assert "資料無法載入" in profile
    assert conditions == []
