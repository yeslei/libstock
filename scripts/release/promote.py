"""Prepare and publish a release. No remote writes occur during preparation."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys


class ReleaseError(RuntimeError):
    pass


def git(*args):
    result = subprocess.run(["git", *args], text=True, capture_output=True)
    if result.returncode:
        # Git's diagnostic may include a credential-bearing URL: do not echo it.
        raise ReleaseError(f"Git failed ({result.returncode}): {args[0]}; check conflicts, permissions and branch policy.")
    return result.stdout.strip()


def version_tag(version):
    number = r"(?:0|[1-9][0-9]*)"
    identifier = r"(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
    if not re.fullmatch(rf"{number}\.{number}\.{number}(?:-{identifier}(?:\.{identifier})*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?", version):
        raise ReleaseError("Invalid version: use SemVer without the v prefix, for example 1.2.3.")
    return "v" + version


def remote_refs(tag):
    lines = git("ls-remote", "--refs", "origin", "refs/heads/main", "refs/heads/integracao", f"refs/tags/{tag}")
    refs = dict(line.split("\t")[::-1] for line in lines.splitlines())
    if f"refs/tags/{tag}" in refs:
        raise ReleaseError(f"Tag already exists: {tag}.")
    if not all(f"refs/heads/{branch}" in refs for branch in ("main", "integracao")):
        raise ReleaseError("Required remote branch main or integracao is missing.")
    return refs


def output(state):
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as stream:
            for key, value in state.items():
                stream.write(f"{key}={value}\n")
    print(json.dumps(state))


def next_tag(bump="patch"):
    """Increment the greatest stable remote vMAJOR.MINOR.PATCH tag numerically."""
    if bump not in ("patch", "minor", "major"):
        raise ReleaseError("Invalid increment: choose patch, minor or major.")
    versions = []
    for line in git("ls-remote", "--refs", "--tags", "origin").splitlines():
        ref = line.split("\t", 1)[1]
        match = re.fullmatch(r"refs/tags/v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", ref)
        if match:
            versions.append(tuple(map(int, match.groups())))
    major, minor, patch = max(versions, default=(0, 0, 0))
    if bump == "major":
        return f"v{major + 1}.0.0"
    if bump == "minor":
        return f"v{major}.{minor + 1}.0"
    return f"v{major}.{minor}.{patch + 1}"


def prepare(state_path, bump="patch"):
    if git("status", "--porcelain"):
        raise ReleaseError("Preparation requires a clean disposable checkout.")
    tag = next_tag(bump)
    refs = remote_refs(tag)
    git("fetch", "--no-tags", "origin", "refs/heads/main:refs/remotes/origin/main", "refs/heads/integracao:refs/remotes/origin/integracao")
    base = git("rev-parse", "refs/remotes/origin/main")
    source = git("rev-parse", "refs/remotes/origin/integracao")
    if (base, source) != (refs["refs/heads/main"], refs["refs/heads/integracao"]):
        raise ReleaseError("Branches changed while fetching; start a new manual run.")
    ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", source, base], capture_output=True)
    if ancestor.returncode == 0:
        raise ReleaseError("Nothing to promote: integracao is already contained in main.")
    if ancestor.returncode != 1:
        raise ReleaseError("Cannot determine branch ancestry.")
    git("checkout", "--detach", base)
    try:
        git("merge", "--no-ff", "--no-edit", source, "-m", f"Release {tag}: promote integracao")
    except ReleaseError:
        subprocess.run(["git", "merge", "--abort"], capture_output=True)
        raise ReleaseError("Candidate merge failed: conflict or invalid Git configuration. No remote refs were changed.") from None
    state = {"tag": tag, "base": base, "source": source, "candidate": git("rev-parse", "HEAD")}
    Path(state_path).write_text(json.dumps(state), encoding="utf-8")
    output(state)
    return state


def publish(state_path):
    state = json.loads(Path(state_path).read_text(encoding="utf-8"))
    if version_tag(state["tag"][1:]) != state["tag"]:
        raise ReleaseError("Invalid release state.")
    for key in ("base", "source", "candidate"):
        if not re.fullmatch(r"[0-9a-f]{40}", state[key]):
            raise ReleaseError("Invalid SHA in release state.")
    parents = git("rev-list", "--parents", "-n", "1", state["candidate"]).split()
    if parents != [state["candidate"], state["base"], state["source"]]:
        raise ReleaseError("Candidate must be the validated merge of captured main and integracao.")
    refs = remote_refs(state["tag"])
    if refs["refs/heads/main"] != state["base"] or refs["refs/heads/integracao"] != state["source"]:
        raise ReleaseError("Branches changed since validation; start a new manual run.")
    # Tag creation is local. The single atomic push publishes both refs or neither.
    git("tag", "-a", state["tag"], state["candidate"], "-m", f"Release {state['tag']}")
    try:
        git("push", "--atomic", "origin", f"{state['candidate']}:refs/heads/main", f"refs/tags/{state['tag']}:refs/tags/{state['tag']}")
    except ReleaseError:
        raise ReleaseError("Atomic publication rejected: branch policy, concurrent update, tag collision, or unsupported atomic push. No fallback or force push is attempted.") from None
    print(f"Published {state['tag']} at main commit {state['candidate']}; deploy completion must be checked separately.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--state", required=True)
    prep.add_argument("--bump", choices=("patch", "minor", "major"), default="patch")
    pub = sub.add_parser("publish")
    pub.add_argument("--state", required=True)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            prepare(args.state, args.bump)
        else:
            publish(args.state)
    except (ReleaseError, ValueError, KeyError, OSError) as error:
        print(f"Release failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
