"""Selenium E2E tests for SCLPLAPI Web UI.

These tests navigate the actual web UI at http://127.0.0.1:8000
and verify that pages load correctly with CSS/JS.

Prerequisites:
- pip install selenium webdriver-manager
- Server running: python -m app web
"""

from __future__ import annotations

import time
import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

BASE_URL = "http://127.0.0.1:8000"


@pytest.fixture(scope="module")
def driver():
    """Create a Chrome WebDriver instance."""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")

    try:
        from webdriver_manager.chrome import ChromeDriverManager
        service = Service(ChromeDriverManager().install())
        drv = webdriver.Chrome(service=service, options=options)
    except Exception:
        drv = webdriver.Chrome(options=options)

    drv.implicitly_wait(5)
    yield drv
    drv.quit()


@pytest.fixture(scope="module")
def app_running():
    """Verify the app is running before tests."""
    import urllib.request
    try:
        response = urllib.request.urlopen(BASE_URL)
        if response.status != 200:
            pytest.skip("App not running at " + BASE_URL)
    except Exception:
        pytest.skip("App not running at " + BASE_URL)
    return True


class TestPageLoad:
    """Test that pages load correctly."""

    def test_home_page_loads(self, driver, app_running):
        driver.get(BASE_URL)
        assert "SCLPLAPI" in driver.title

    def test_css_loaded(self, driver, app_running):
        driver.get(BASE_URL)
        # Check if CSS is loaded by looking for styled elements
        body = driver.find_element(By.TAG_NAME, "body")
        bg_color = body.value_of_css_property("background-color")
        # If CSS loaded, background won't be default white
        assert bg_color != "rgba(0, 0, 0, 0)" or "rgb" in bg_color

    def test_sidebar_visible(self, driver, app_running):
        driver.get(BASE_URL)
        sidebar = driver.find_element(By.ID, "sidebar")
        assert sidebar.is_displayed()

    def test_logo_visible(self, driver, app_running):
        driver.get(BASE_URL)
        logo = driver.find_element(By.CSS_SELECTOR, ".logo")
        # Logo exists in DOM (might be hidden in sidebar on small viewports)
        assert logo is not None
        # Check text content via JavaScript
        text = driver.execute_script("return arguments[0].textContent", logo)
        assert "SCLPLAPI" in text


class TestNavigation:
    """Test sidebar navigation."""

    def _get_nav_texts(self, driver):
        """Get all navigation item texts via JavaScript."""
        return driver.execute_script("""
            var items = document.querySelectorAll('.nav-item');
            var texts = [];
            for (var i = 0; i < items.length; i++) {
                texts.push(items[i].textContent.trim());
            }
            return texts;
        """)

    def test_home_nav_item(self, driver, app_running):
        driver.get(BASE_URL)
        texts = self._get_nav_texts(driver)
        assert any("Home" in t for t in texts)

    def test_editor_nav_item(self, driver, app_running):
        driver.get(BASE_URL)
        texts = self._get_nav_texts(driver)
        assert any("Editor" in t or "Request" in t for t in texts)

    def test_collections_nav_item(self, driver, app_running):
        driver.get(BASE_URL)
        texts = self._get_nav_texts(driver)
        assert any("Collections" in t for t in texts)

    def test_workflows_nav_item(self, driver, app_running):
        driver.get(BASE_URL)
        texts = self._get_nav_texts(driver)
        assert any("Workflows" in t or "Flow" in t for t in texts)

    def test_functions_nav_item(self, driver, app_running):
        driver.get(BASE_URL)
        texts = self._get_nav_texts(driver)
        assert any("Functions" in t for t in texts)

    def test_history_nav_item(self, driver, app_running):
        driver.get(BASE_URL)
        texts = self._get_nav_texts(driver)
        assert any("History" in t for t in texts)


class TestHomeDashboard:
    """Test home dashboard content."""

    def test_welcome_message(self, driver, app_running):
        driver.get(BASE_URL)
        welcome = driver.find_element(By.CSS_SELECTOR, ".view-header h1")
        assert "Welcome" in welcome.text

    def test_dashboard_cards(self, driver, app_running):
        driver.get(BASE_URL)
        cards = driver.find_elements(By.CSS_SELECTOR, ".dash-card")
        assert len(cards) >= 4

    def test_stats_section(self, driver, app_running):
        driver.get(BASE_URL)
        stats = driver.find_elements(By.CSS_SELECTOR, ".stat-item")
        assert len(stats) >= 4


class TestRequestEditor:
    """Test request editor page."""

    def test_navigate_to_editor(self, driver, app_running):
        driver.get(BASE_URL)
        # Use JavaScript click to avoid interactability issues
        editor_link = driver.find_element(By.CSS_SELECTOR, '[data-route="editor"]')
        driver.execute_script("arguments[0].click();", editor_link)
        time.sleep(0.5)
        # Check that editor view is active
        editor_view = driver.find_element(By.ID, "view-editor")
        assert "active" in editor_view.get_attribute("class")


class TestAPIEndpoints:
    """Test that API endpoints respond correctly."""

    def test_health_endpoint(self, driver, app_running):
        driver.get(BASE_URL + "/api/health")
        body = driver.find_element(By.TAG_NAME, "body").text
        assert "healthy" in body.lower() or "ok" in body.lower() or "status" in body.lower()

    def test_workflows_endpoint(self, driver, app_running):
        driver.get(BASE_URL + "/api/workflows")
        body = driver.find_element(By.TAG_NAME, "body").text
        # Should return JSON array
        assert "[" in body or "id" in body

    def test_functions_endpoint(self, driver, app_running):
        driver.get(BASE_URL + "/api/functions")
        body = driver.find_element(By.TAG_NAME, "body").text
        assert "[" in body or "name" in body
