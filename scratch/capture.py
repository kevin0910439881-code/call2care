import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # Dashboard
        dashboard_context = await browser.new_context(viewport={'width': 1280, 'height': 800})
        dashboard_page = await dashboard_context.new_page()
        await dashboard_page.goto("http://localhost:8000/static/dashboard.html")
        
        # Mobile
        mobile_context = await browser.new_context(viewport={'width': 390, 'height': 844})
        mobile_page = await mobile_context.new_page()
        await mobile_page.goto("http://localhost:8000/static/index.html")
        
        # Actions
        await dashboard_page.wait_for_selector(".patient-card")
        await dashboard_page.click(".patient-card")
        await dashboard_page.wait_for_timeout(1000)
        
        await dashboard_page.click("#initiate-call-btn")
        
        await mobile_page.wait_for_selector("#answer-btn:visible")
        await mobile_page.click("#answer-btn")
        
        # Wait for AI greeting on dashboard
        await dashboard_page.wait_for_selector(".message.ai", timeout=30000)
        
        # Wait a bit for layout to settle
        await dashboard_page.wait_for_timeout(2000)
        
        # Save screenshots
        await dashboard_page.screenshot(path="assets/dashboard.png")
        await mobile_page.screenshot(path="assets/mobile.png")
        
        await browser.close()
        print("Screenshots captured successfully!")

if __name__ == "__main__":
    asyncio.run(main())
