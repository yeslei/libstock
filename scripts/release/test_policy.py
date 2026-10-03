import unittest
from unittest.mock import patch

import policy
from promote import ReleaseError


class FakeAPI:
    def __init__(self):
        self.responses = {
            "branches/main": {"protected": False},
            "branches/main/protection": policy.NotFound("unprotected"),
            "branches/main/protection/required_signatures": {"enabled": False},
            "rules/branches/main": [],
            "rulesets?includes_parents=true": [],
        }

    def get(self, path):
        result = self.responses[path]
        if isinstance(result, Exception):
            raise result
        return result

    def pages(self, path, key=None):
        result = self.get(path)
        return result[key] if key else result


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeAPI()
        self.state = {"source": "source", "candidate": "candidate", "tag": "v1.2.3"}

    def test_unprotected_allowed(self):
        policy.preflight(self.api, self.state)

    def test_protection_not_readable_refused(self):
        self.api.responses["branches/main"]["protected"] = True
        with self.assertRaisesRegex(ReleaseError, "details are unavailable"):
            policy.preflight(self.api, self.state)

    def test_pr_policy_refused_even_if_actor_can_bypass(self):
        self.api.responses["branches/main/protection"] = {"required_pull_request_reviews": {"required_approving_review_count": 0}}
        with self.assertRaisesRegex(ReleaseError, "requires a pull request"):
            policy.preflight(self.api, self.state)

    def test_incompatible_rules_refused(self):
        for name in ("pull_request", "required_linear_history", "required_signatures", "merge_queue", "required_deployments", "unknown_new_rule", "update"):
            with self.subTest(name=name):
                self.api.responses["rules/branches/main"] = [{"type": name}]
                with self.assertRaises(ReleaseError):
                    policy.preflight(self.api, self.state)

    def test_safe_rules_allowed(self):
        self.api.responses["rules/branches/main"] = [{"type": "deletion"}, {"type": "non_fast_forward"}]
        policy.preflight(self.api, self.state)

    def test_tag_creation_rule_refused(self):
        self.api.responses["rulesets?includes_parents=true"] = [{"id": 2, "target": "tag", "enforcement": "active"}]
        self.api.responses["rulesets/2"] = {"conditions": {"ref_name": {"include": ["refs/tags/v*"]}}, "rules": [{"type": "creation"}]}
        with self.assertRaisesRegex(ReleaseError, "creation"):
            policy.preflight(self.api, self.state)

    def test_nonapplicable_tag_ruleset_ignored(self):
        self.api.responses["rulesets?includes_parents=true"] = [{"id": 2, "target": "tag", "enforcement": "active"}]
        self.api.responses["rulesets/2"] = {"conditions": {"ref_name": {"include": ["refs/tags/archive-*"]}}, "rules": [{"type": "creation"}]}
        policy.preflight(self.api, self.state)

    def check_data(self, sha, app=5, conclusion="success", state="success"):
        self.api.responses[f"commits/{sha}/check-runs?filter=latest"] = {"check_runs": [{"id": 1, "name": "CI", "app": {"id": app}, "status": "completed", "conclusion": conclusion}]}
        self.api.responses[f"commits/{sha}/statuses"] = [{"id": 1, "context": "CI", "state": state}]

    def test_required_checks_both_source_and_candidate(self):
        self.api.responses["rules/branches/main"] = [{"type": "required_status_checks", "parameters": {"required_status_checks": [{"context": "CI", "integration_id": 5}]}}]
        self.check_data("source")
        self.check_data("candidate")
        policy.preflight(self.api, self.state)
        self.check_data("candidate", conclusion="failure")
        with self.assertRaisesRegex(ReleaseError, "candidate"):
            policy.preflight(self.api, self.state)

    def test_required_check_app_identity(self):
        self.check_data("source", app=99)
        with self.assertRaisesRegex(ReleaseError, "Required check"):
            policy.required_checks(self.api, "source", [("CI", 5)])

    def test_same_name_failing_status_refused(self):
        self.check_data("source", state="failure")
        with self.assertRaises(ReleaseError):
            policy.required_checks(self.api, "source", [("CI", None)])

    def test_signed_commit_policy_refused(self):
        self.api.responses["branches/main/protection"] = {"enabled": True}
        self.api.responses["branches/main/protection/required_signatures"] = {"enabled": True}
        with self.assertRaisesRegex(ReleaseError, "signed commits"):
            policy.preflight(self.api, self.state)

    def test_api_errors_fail_closed(self):
        self.api.responses["rules/branches/main"] = ReleaseError("HTTP 403")
        with self.assertRaises(ReleaseError):
            policy.preflight(self.api, self.state)

    def test_pagination_includes_later_page(self):
        api = policy.GitHub("owner/repo", "placeholder")
        with patch.object(api, "get", side_effect=[list(range(100)), [101]]) as get:
            self.assertEqual(len(api.pages("rulesets?includes_parents=true")), 101)
            self.assertIn("&per_page=100&page=2", get.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
