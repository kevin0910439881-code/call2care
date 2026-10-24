import pytest
import subprocess
import time
import requests

@pytest.fixture(scope="module", autouse=True)
def start_server():
    # Start the FastAPI server in the background
    process = subprocess.Popen(["uv", "run", "uvicorn", "backend.main:app", "--port", "8000"])
    
    # Wait for the server to be up
    timeout = time.time() + 10
    while time.time() < timeout:
        try:
            response = requests.get("http://localhost:8000/static/dashboard.html")
            if response.status_code == 200:
                break
        except requests.ConnectionError:
            time.sleep(0.5)
            
    yield
    # Teardown
    process.terminate()
    process.wait()

def test_dashboard_ui_elements(page):
    """
    Test that the Doctor Dashboard UI has the required elements for the demo.
    """
    page.goto("http://localhost:8000/static/dashboard.html")
    
    # Verify title
    assert "Dashboard" in page.title()
    
    # Verify layout elements exist
    assert page.locator("#transcript-box").count() > 0, "Transcript box missing"
    assert page.locator("#risk-badge").count() > 0, "Risk badge missing"
    assert page.locator("#symptoms-list").count() > 0, "Symptoms list missing"
