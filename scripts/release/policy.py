"""Fail-closed preflight for direct publication; never uses bypass permissions."""
import argparse
import fnmatch
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from promote import ReleaseError


class GitHub:
    def __init__(self, repository, token):
        self.repository = repository
        self.token = token

    def get(self, path):
        request = Request(f"https://api.github.com/repos/{self.repository}/{path}", headers={
            "Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })
        try:
            with urlopen(request, timeout=30) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code == 404:
                raise NotFound(path) from None
            raise ReleaseError(f"Policy API failed (HTTP {error.code}); publication refused.") from None
        except (URLError, ValueError, TimeoutError):
            raise ReleaseError("Policy API unavailable or malformed; publication refused.") from None

    def pages(self, path, key=None):
        items = []
        for page in range(1, 101):
            separator = "&" if "?" in path else "?"
            result = self.get(f"{path}{separator}per_page=100&page={page}")
            batch = result[key] if key else result
            if not isinstance(batch, list):
                raise ReleaseError("Malformed policy pagination response.")
            items.extend(batch)
            if len(batch) < 100:
                return items
        raise ReleaseError("Policy pagination exceeded safe limit.")


class NotFound(ReleaseError):
    pass


def required_checks(api, sha, requirements):
    if not requirements:
        return
    runs = api.pages(f"commits/{sha}/check-runs?filter=latest", "check_runs")
    statuses = api.pages(f"commits/{sha}/statuses")
    for name, app_id in requirements:
        matching = [run for run in runs if run["name"] == name and (app_id in (None, -1) or run.get("app", {}).get("id") == app_id)]
        if matching:
            latest_by_app = {}
            for run in sorted(matching, key=lambda item: item["id"]):
                latest_by_app[run.get("app", {}).get("id")] = run
            passed = all(run["status"] == "completed" and run["conclusion"] in ("success", "neutral", "skipped") for run in latest_by_app.values())
            # GitHub requires both a check and a status when names coincide.
            matching_status = [status for status in statuses if status["context"] == name]
            if matching_status and app_id in (None, -1):
                passed = passed and max(matching_status, key=lambda status: status["id"])["state"] == "success"
        else:
            matching_status = [status for status in statuses if status["context"] == name]
            passed = app_id in (None, -1) and bool(matching_status) and max(matching_status, key=lambda status: status["id"])["state"] == "success"
        if not passed:
            raise ReleaseError(f"Required check {name!r} is not successful for {sha}; local builds cannot substitute a required GitHub check.")


def applicable_tag(ruleset, tag):
    conditions = ruleset.get("conditions", {})
    if set(conditions) - {"ref_name"}:
        raise ReleaseError("Unsupported tag ruleset conditions; publication refused.")
    ref = "refs/tags/" + tag
    names = conditions.get("ref_name", {})
    def matches(pattern):
        return pattern == "~ALL" or fnmatch.fnmatchcase(ref, pattern)
    return any(matches(pattern) for pattern in names.get("include", ["~ALL"])) and not any(matches(pattern) for pattern in names.get("exclude", []))


def validate_rules(rules, requirements, tag=False):
    for rule in rules:
        kind = rule["type"]
        if kind in ("deletion", "non_fast_forward"):
            continue  # Publication never deletes or force-updates a ref.
        if kind == "required_status_checks" and not tag:
            requirements.extend((check["context"], check.get("integration_id")) for check in rule["parameters"]["required_status_checks"])
            continue
        # Direct unsigned merge cannot satisfy PR, linear history, signatures,
        # queue, deployment, restricted creation/update or unknown future rules.
        raise ReleaseError(f"Policy {kind!r} cannot be satisfied by direct promotion; publication refused without bypass.")


def preflight(api, state):
    branch = api.get("branches/main")
    try:
        protection = api.get("branches/main/protection")
    except NotFound:
        if branch.get("protected") is not False:
            raise ReleaseError("Main is protected but protection details are unavailable; administration read permission is required.") from None
        protection = {}
    requirements = []
    if protection.get("required_pull_request_reviews"):
        raise ReleaseError("Main requires a pull request; direct promotion is incompatible and will not bypass it.")
    for field in ("required_linear_history", "required_signatures", "lock_branch"):
        if protection.get(field, {}).get("enabled"):
            raise ReleaseError(f"Main policy {field} prevents this direct merge.")
    if protection.get("restrictions"):
        raise ReleaseError("Main restricts push actors; this preflight does not use actor exemptions or bypass.")
    checks = protection.get("required_status_checks") or {}
    if protection and api.get("branches/main/protection/required_signatures").get("enabled"):
        raise ReleaseError("Main requires signed commits; this unsigned merge cannot be published.")
    explicit = checks.get("checks", [])
    requirements.extend((check["context"], check.get("app_id")) for check in explicit)
    requirements.extend((name, None) for name in checks.get("contexts", []) if name not in {check["context"] for check in explicit})
    validate_rules(api.pages("rules/branches/main"), requirements)
    for summary in api.pages("rulesets?includes_parents=true"):
        if summary.get("target") != "tag" or summary.get("enforcement") != "active":
            continue
        detail = api.get(f"rulesets/{summary['id']}")
        if applicable_tag(detail, state["tag"]):
            validate_rules(detail["rules"], [], tag=True)
    for sha in (state["source"], state["candidate"]):
        required_checks(api, sha, requirements)
    print("Policy preflight passed; server still enforces policies at atomic push.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", required=True)
    args = parser.parse_args()
    try:
        token = os.environ.get("RELEASE_TOKEN")
        repository = os.environ.get("GITHUB_REPOSITORY")
        if not token or not repository:
            raise ReleaseError("Explicit GitHub App token and repository are required; no GITHUB_TOKEN fallback.")
        with open(args.state, encoding="utf-8") as stream:
            state = json.load(stream)
        preflight(GitHub(repository, token), state)
    except (ReleaseError, KeyError, TypeError, ValueError, OSError) as error:
        print(f"Release policy failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
