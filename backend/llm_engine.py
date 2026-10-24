import os
import json
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List
from dotenv import load_dotenv
from backend.rag_engine import query_rag_context
import logging

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configure Gemini
api_key = os.getenv("GEMINI_API_KEY")
if api_key and api_key != "your_gemini_api_key_here":
    client = genai.Client(api_key=api_key)
else:
    client = genai.Client()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "mock_database.json")

def get_patient_profile(patient_id: str) -> tuple[str, list]:
    """Dynamically loads the patient profile text and conditions from mock database."""
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            for patient in data:
                if patient["id"] == patient_id:
                    conditions = patient.get("metadata", {}).get("conditions", [])
                    return patient["text"], conditions
    except Exception as e:
        logger.error(f"Error loading profile for {patient_id}: {e}")
    
    # Fallback if patient not found
    return f"【患者資料】\nID: {patient_id}\n資料無法載入，請進行一般關懷。", []


class DashboardOutput(BaseModel):
    ai_spoken_reply: str = Field(
        description="The exact text to send to the TTS engine (Traditional Chinese)."
    )
    risk_status: str = Field(
        description="'GREEN' for normal, 'YELLOW' for mild/borderline, 'RED' for high-risk events."
    )
    symptoms: List[str] = Field(
        default_factory=list,
        description="Extracted symptoms, e.g. ['dizziness', 'shaking']."
    )
    action_taken: str = Field(
        default="",
        description="System action, e.g. 'Alerted Pharmacist Chen'."
    )
    case_status: str = Field(
        description="'CLOSED' for GREEN, 'PENDING_FAMILY_REVIEW' for YELLOW and RED."
    )
    end_call: bool = Field(
        default=False,
        description="True if the check-in is complete and the call should end."
    )
    blood_glucose: int | None = Field(
        default=None,
        description="Extracted blood glucose value if mentioned by the patient, else null."
    )


def process_patient_input(patient_id: str, transcript: str, conversation_history: list, model_name: str = "gemini-3.6-flash") -> dict:
    """
    Takes a patient_id, transcribed voice input, conversation history,
    retrieves RAG context, and queries the LLM for a structured response.
    """
    if not transcript or len(transcript.strip()) < 2:
        return {
            "ai_spoken_reply": "阿公阿嬤拍謝，我剛剛沒聽清楚，可以再說一次嗎？",
            "risk_status": "GREEN",
            "symptoms": [],
            "action_taken": "",
            "case_status": "CLOSED",
            "end_call": False,
        }

    patient_profile, conditions = get_patient_profile(patient_id)
    # Enhance the RAG query to pull relevant medical guidelines based on patient's specific conditions
    conditions_str = " ".join(conditions)
    rag_query = f"{transcript} {conditions_str} 衛教 飲食 處置"
    context = query_rag_context(rag_query, n_results=3)

    system_prompt = f"""你是一位「私人健康秘書」。你具有同理心，說話簡潔，使用自然口語化的台灣正體中文。
請根據病人的性別與年齡，使用適當的尊稱（例如：張先生、林太太等）。

{patient_profile}

【從醫療知識庫檢索到的相關資料】
---
{context}
---

### 一、你的核心任務與流程（動態關懷清單）
你必須在這次通話中，根據【患者資料】完成對應的關懷清單。
1. **建立專屬清單**：根據病史，自行決定需要詢問哪些數值。
   - 若有糖尿病，須詢問「血糖」。
   - 若有高血壓，須詢問「血壓」。
   - 若有氣喘，須詢問「呼吸或氣喘狀況」。
2. **最後必問**：無論病史為何，清單的最後一項永遠是「關心今天身體有無不舒服」。
3. **推進原則（拒絕與忘記處理）**：
   - 若病人說「還沒量」、「忘記了」或給出無關回答，請先溫和地嘗試引導（例如：「那您現在方便量一下嗎？」）。
   - 若病人「明確拒絕」或「兩次表示不想量」（例如：「我不要」、「不想量」），**絕對不可以結束通話**！請溫和地說「沒關係，那我們下次再量」，然後**立刻放棄該項目，進行清單上的下一個項目**。同時，你必須將此拒絕行為記錄在 `symptoms` 中（例如 `["拒絕量測血壓"]`），並將 `risk_status` 設為 `YELLOW`，以便通知家屬。
4. **結束通話條件**：只有當清單上**所有項目都問完（包含最後的身體不舒服）**，或者病人明確表示想掛斷（例如「我要去忙了」、「不想講了」），才能道別並將 `end_call` 設為 true。否則 `end_call` 必須是 false。

### 二、風險評估與通報機制
請根據病人的具體病史與當下回報的數值/症狀來評估風險（risk_status）：
- GREEN（綠燈）：數值正常且無不適。清單問完後，道別並設 `end_call = true`。
- YELLOW（黃燈）：數值邊緣異常或輕微不適（如輕微頭暈）。設定 `case_status = "PENDING_FAMILY_REVIEW"`。
- RED（紅燈）：嚴重異常或高危險（如低血糖、摔倒、極端高血壓）。設定 `case_status = "PENDING_FAMILY_REVIEW"`。
⚠️ **高風險處置流程（黃/紅燈）**：不要立刻掛斷。請先安撫病人坐下休息，若需衛教請參考知識庫，並告知「我現在通報您的家屬，我15分鐘後再打給您確認狀況」。這些都交代完後，才能道別並設 `end_call = true`。並記錄 `action_taken = "已通報家屬"`。

### 三、嚴格禁忌與限制
- 【嚴禁無端臆測】：絕對不可預設病人有任何未提及的行為（例如：空腹喝酒、吃特定食物、忘記吃藥等），除非病人「親口說出」！
- 【家屬稱呼】：不可隨意提及特定家屬（如女兒），除非「患者資料」中有記載。
- 【嚴禁醫療處方】：若病人問可否停藥，必須回答「用藥調整請詢問醫師」。
- 【衛教限制】：只針對病人「主動提及」的症狀或行為提供對應衛教，絕不可生搬硬套知識庫。

### 四、語氣與對話節奏（極度重要）
1. **每次只問一個問題**：絕對不要連續問兩個數值。一句話只有一個重點。
2. **極度簡短**：每句話盡量不超過 15 個字，像日常聊天。例如：「一百一十二，數值很好。那血壓呢？」

【對話紀錄】
{json.dumps(conversation_history, ensure_ascii=False)}

【病人剛才說的話（語音轉文字）】
「{transcript}」

請根據以上規則，產生回覆 JSON：
{{
    "ai_spoken_reply": "string (自然口語化正體中文)",
    "risk_status": "GREEN, YELLOW, 或 RED",
    "symptoms": ["string"],
    "action_taken": "string (若無則空字串)",
    "case_status": "CLOSED 或 PENDING_FAMILY_REVIEW",
    "end_call": false,
    "blood_glucose": "integer 或 null"
}}
"""

    try:
        logger.info(f"Sending prompt to Gemini for {patient_id} (process_patient_input) using {model_name}...")
        response = client.models.generate_content(
            model=model_name,
            contents=system_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            )
        )
        logger.info(f"Gemini raw response: {response.text}")

        result = json.loads(response.text)

        if "ai_spoken_reply" not in result:
            raise ValueError("LLM returned JSON without 'ai_spoken_reply'.")

        result.setdefault("risk_status", "GREEN")
        result.setdefault("symptoms", [])
        result.setdefault("action_taken", "")
        result.setdefault("case_status", "CLOSED")
        result.setdefault("end_call", False)

        return result

    except Exception as e:
        logger.error(f"LLM Engine Error: {e}")
        return {
            "ai_spoken_reply": "系統現在有點問題，請稍後再試。",
            "risk_status": "GREEN",
            "symptoms": ["System Error"],
            "action_taken": "",
            "case_status": "CLOSED",
            "end_call": False,
        }


def initiate_call(patient_id: str, model_name: str = "gemini-3.6-flash") -> dict:
    """
    Initializes a call for a specific patient dynamically loading their profile.
    Generates an opening greeting using the correct title.
    """
    patient_profile, _ = get_patient_profile(patient_id)
    
    system_prompt = f"""你是一位「私人健康秘書」。你正在撥打電話給病人進行例行健康關懷。
請用溫暖、親切的口吻打招呼，並根據病人的性別與年齡使用適當的尊稱。

【極度重要：長輩友善原則與動態開場】
1. **開場白必須「極度簡短」**，例如：「張先生早，我是您的健康私人秘書。」
2. **第一個問題**：請根據下方的【患者資料】來決定你要問的第一個問題。
   - 若病史有糖尿病，請先問「今天早上血糖量了嗎？」
   - 若病史有高血壓（且無糖尿病），請先問「今天血壓量了嗎？」
   - 若無以上病史，請問「您今天身體感覺好嗎？」
3. **絕對不要一次問太多問題**，一句話只有一個重點。

{patient_profile}

輸出必須是合法的 JSON：
{{
    "ai_spoken_reply": "string",
    "risk_status": "GREEN",
    "symptoms": [],
    "action_taken": "",
    "case_status": "CLOSED",
    "end_call": false
}}
"""
    try:
        logger.info(f"Initiating call for {patient_id} via Gemini using {model_name}...")
        response = client.models.generate_content(
            model=model_name,
            contents=system_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            )
        )
        logger.info(f"Gemini initial greeting: {response.text}")
        result = json.loads(response.text)
        result.setdefault("risk_status", "GREEN")
        result.setdefault("symptoms", [])
        result.setdefault("action_taken", "")
        result.setdefault("case_status", "CLOSED")
        result.setdefault("end_call", False)
        return result
    except Exception as e:
        logger.error(f"Initiate Call Error: {e}")
        return {
            "ai_spoken_reply": "您好，我是您的健康秘書，最近身體好嗎？",
            "risk_status": "GREEN",
            "symptoms": [],
            "action_taken": "",
            "case_status": "CLOSED",
            "end_call": False,
        }


def summarize_call(patient_id: str, conversation_history: list, model_name: str = "gemini-3.5-flash-lite") -> str:
    """Summarizes the call transcript and saves notes to the database."""
    transcript_text = "\\n".join(
        [f"{msg['role']}: {msg['content']}" for msg in conversation_history]
    )

    system_prompt = f"""
    You are a clinical assistant. Summarize the following conversation transcript between an AI care assistant and a patient.
    Extract key clinical insights, medication status, and any reported symptoms.

    Transcript:
    {transcript_text}
    """

    try:
        logger.info(f"Generating summary via Gemini using {model_name}...")
        response = client.models.generate_content(
            model=model_name,
            contents=system_prompt,
        )
        summary = response.text
        logger.info(f"Generated summary: {summary}")

        logs_path = os.path.join(BASE_DIR, "data", "call_logs.json")
        logs = []
        if os.path.exists(logs_path):
            with open(logs_path, "r", encoding="utf-8") as f:
                try:
                    logs = json.load(f)
                except:
                    pass

        logs.append(
            {
                "patient_id": patient_id,
                "summary": summary,
                "transcript": conversation_history,
            }
        )

        with open(logs_path, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)

        return summary
    except Exception as e:
        logger.error(f"Summarize Error: {e}")
        return "Failed to generate summary."
