"""Integration tests for Streamlit application pages and offline exam simulation workflows."""

import os
import unittest
from streamlit.testing.v1 import AppTest

APP_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app.py"))


class TestStreamlitAppIntegration(unittest.TestCase):
    """Integration test suite executing app.py via Streamlit's official AppTest runner."""

    def test_app_initial_load(self):
        """Verify the app initializes and renders default Dashboard without exceptions."""
        at = AppTest.from_file(APP_PATH, default_timeout=25)
        at.run()
        self.assertFalse(at.exception, f"App raised exception on launch: {at.exception}")
        # Verify navigation radio exists in sidebar
        self.assertTrue(len(at.sidebar.radio) > 0)
        self.assertEqual(at.sidebar.radio[0].value, "Dashboard")

    def test_navigate_to_offline_exam_simulation(self):
        """Verify navigation to '🖨️ Offline Exam & OMR Simulation' renders cleanly."""
        at = AppTest.from_file(APP_PATH, default_timeout=25)
        at.run()
        self.assertFalse(at.exception)

        # Select '🖨️ Offline Exam & OMR Simulation'
        radio = at.sidebar.radio[0]
        radio.set_value("🖨️ Offline Exam & OMR Simulation").run()
        self.assertFalse(at.exception, f"Offline Exam page raised exception: {at.exception}")
        self.assertIn("Offline Exam & OMR Simulation", at.title[0].value)

    def test_offline_exam_load_bank_questions_and_eval_flow(self):
        """Verify assembling offline paper from question bank and running OMR evaluation."""
        at = AppTest.from_file(APP_PATH, default_timeout=25)
        at.run()
        self.assertFalse(at.exception)

        # Navigate to Offline Exam Simulation
        at.sidebar.radio[0].set_value("🖨️ Offline Exam & OMR Simulation").run()
        self.assertFalse(at.exception)

        # Switch to "📚 From Question Bank & Previous Vaults"
        source_radio = at.radio(key="offline_source_mode_radio")
        source_radio.set_value("📚 From Question Bank & Previous Vaults").run()
        self.assertFalse(at.exception)

        # Find and click "📋 Load Selected Questions into Offline Paper"
        load_btn = [b for b in at.button if "Load Selected Questions" in b.label]
        self.assertTrue(len(load_btn) > 0, "Load questions button not found")
        load_btn[0].click().run()
        self.assertFalse(at.exception)

        # Verify offline_paper_questions loaded into session state
        active_qs = at.session_state.get("offline_paper_questions", [])
        self.assertGreater(len(active_qs), 0, "Expected questions to be loaded from bank")

        # Find and click "📌 Set as Active Paper for OMR Evaluation & Analysis"
        set_active_btn = [b for b in at.button if "Set as Active Paper" in b.label]
        self.assertTrue(len(set_active_btn) > 0, "Set active paper button not found")
        set_active_btn[0].click().run()
        self.assertFalse(at.exception)

        active_paper = at.session_state.get("active_offline_paper")
        self.assertIsNotNone(active_paper)
        self.assertEqual(len(active_paper["questions"]), len(active_qs))

    def test_navigate_all_core_pages(self):
        """Verify that every core page in NAV_PAGES renders without crashing."""
        nav_pages = [
            "Dashboard",
            "Question Bank",
            "Practice & Mock Tests",
            "🖨️ Offline Exam & OMR Simulation",
            "AI Study Tutor",
            "AI Performance Coach",
            "Error Notebook",
            "Revision Planner",
            "Settings & Data",
        ]
        at = AppTest.from_file(APP_PATH, default_timeout=25)
        at.run()

        for page in nav_pages:
            with self.subTest(page=page):
                at.sidebar.radio[0].set_value(page).run()
                self.assertFalse(at.exception, f"Page '{page}' raised exception: {at.exception}")


if __name__ == "__main__":
    unittest.main()
