import pytest
import subprocess
import time
import requests

@pytest.fixture(scope="module", autouse=True)
def start_server():
    # Start the FastAPI server in the background on port 8001 to avoid conflicts
    process = subprocess.Popen(["uv", "run", "uvicorn", "backend.main:app", "--port", "8001"])
    
    # Wait for the server to be up
    timeout = time.time() + 30
    while time.time() < timeout:
        try:
            response = requests.get("http://localhost:8001/static/index.html")
            if response.status_code == 200:
                break
        except requests.ConnectionError:
            time.sleep(0.5)
            
    yield
    # Teardown
    process.terminate()
    process.wait()

def test_mobile_ui_elements(page):
    """
    Test that the Patient Mobile UI has the required elements for the demo.
    """
    page.goto("http://localhost:8001/static/index.html")
    
    # Verify title
    assert "Senior Care" in page.title()
    
    # Verify layout elements exist
    assert page.locator("#answer-btn").count() > 0, "Answer button missing"
    assert page.locator("#status-text").count() > 0, "Status text missing"
