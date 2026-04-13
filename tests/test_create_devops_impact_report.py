import importlib
import json
import tempfile
import unittest
from pathlib import Path


class CreateDevopsImpactReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = importlib.import_module("create_devops_impact_report")

    def test_get_default_user_inputs_matches_calculator_defaults(self):
        defaults = self.module.get_default_user_inputs()

        self.assertEqual(defaults["dev_hourly_rate"], 50)
        self.assertEqual(defaults["incident_resolution_hours"], 1)
        self.assertEqual(defaults["revenue_per_feature_per_day"], 30)
        self.assertEqual(defaults["manual_testing_hours_saved"], 2)
        self.assertEqual(defaults["testing_team_size"], 1)

    def test_build_user_inputs_overrides_selected_values_only(self):
        user_inputs = self.module.build_user_inputs(
            {
                "dev_hourly_rate": 125,
                "manual_testing_hours_saved": 6,
                "testing_team_size": 3,
            }
        )

        self.assertEqual(user_inputs["dev_hourly_rate"], 125)
        self.assertEqual(user_inputs["manual_testing_hours_saved"], 6)
        self.assertEqual(user_inputs["testing_team_size"], 3)
        self.assertEqual(user_inputs["incident_resolution_hours"], 1)
        self.assertEqual(user_inputs["revenue_per_feature_per_day"], 30)

    def test_calculate_cost_savings_includes_manual_testing_in_time_saved(self):
        report_payload = {
            "monthly_data": {
                "months": ["2024-01"],
                "avg_deployment_days": [2.8],
                "failure_rates": [0.1],
                "total_pipelines": [10],
                "completion_rates": [90.0],
                "auto_percentages": [50.0],
                "is_after_autodeploy": [True],
            },
            "ec2_data": {"months": ["2024-01"], "costs": [42.0]},
        }

        baseline = self.module.calculate_cost_savings_data(
            report_payload,
            self.module.build_user_inputs({"manual_testing_hours_saved": 2, "testing_team_size": 1}),
        )
        increased = self.module.calculate_cost_savings_data(
            report_payload,
            self.module.build_user_inputs({"manual_testing_hours_saved": 6, "testing_team_size": 4}),
        )

        self.assertGreater(increased["total_time_saved_hours"], baseline["total_time_saved_hours"])
        self.assertGreater(increased["total_time_saved_business_days"], baseline["total_time_saved_business_days"])

    def test_render_html_uses_static_json_fetch_and_header_logo_layout(self):
        user_inputs = self.module.build_user_inputs({})

        html = self.module.render_html(user_inputs)

        self.assertIn("<script src=\"https://cdn.jsdelivr.net/npm/chart.js\"></script>", html)
        self.assertIn("fetch('report-data.json')", html)
        self.assertIn("src=\"cosmic-doge-gradient.png\"", html)
        self.assertIn("class=\"title-row\"", html)
        self.assertIn("class=\"title-logo\"", html)
        self.assertIn("grid-template-columns: repeat(5, 1fr);", html)
        self.assertIn("id=\"manual_testing_hours_saved\"", html)
        self.assertIn("id=\"testing_team_size\"", html)
        self.assertIn("function calculateSavings", html)
        self.assertIn("Feature environments setup followed by continuous deployment to production", html)
        self.assertIn("<h2>Financial Impact</h2>", html)
        self.assertNotIn("Monthly savings breakdown", html)
        self.assertNotIn("const data =", html)
        self.assertNotIn("cost_savings_calculator", html)

    def test_write_report_files_creates_html_and_json(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            html_path = Path(tmp_dir) / "report.html"
            json_path = Path(tmp_dir) / "report-data.json"
            payload = {"hello": "world"}

            self.module.write_report_files("<html>ok</html>", payload, html_path, json_path)

            self.assertTrue(html_path.exists())
            self.assertTrue(json_path.exists())
            self.assertEqual(html_path.read_text(encoding="utf-8"), "<html>ok</html>")
            self.assertEqual(json.loads(json_path.read_text(encoding="utf-8")), payload)

    def test_preview_script_exists_and_serves_static_site(self):
        preview_script = Path("/Users/tony/Projects/devops-impact-report/preview.sh")
        self.assertTrue(preview_script.exists())
        content = preview_script.read_text(encoding="utf-8")
        self.assertIn("python3 -m http.server", content)
        self.assertIn("autodeploy_impact_dashboard.html", content)


if __name__ == "__main__":
    unittest.main()
