"""Release tests only ever push to disposable local bare repositories."""
import contextlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import promote


class PromotionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.remote = self.root / "remote.git"
        self.repo = self.root / "checkout"
        self.old = Path.cwd()
        subprocess.run(["git", "init", "--bare", str(self.remote)], check=True, capture_output=True)
        subprocess.run(["git", "clone", str(self.remote), str(self.repo)], check=True, capture_output=True)
        os.chdir(self.repo)
        promote.git("config", "user.name", "Release test")
        promote.git("config", "user.email", "test@example.invalid")
        promote.git("checkout", "-b", "main")
        self.commit("base.txt", "base")
        promote.git("push", "origin", "main")
        promote.git("checkout", "-b", "integracao")
        self.commit("feature.txt", "feature")
        promote.git("push", "origin", "integracao")
        self.state = self.root / "state.json"

    def tearDown(self):
        os.chdir(self.old)
        self.temp.cleanup()

    def commit(self, name, value):
        Path(name).write_text(value, encoding="utf-8")
        promote.git("add", name)
        promote.git("commit", "-m", value)

    def prepare(self):
        return promote.prepare("1.2.3", self.state)

    def refs(self):
        return promote.git("ls-remote", "--refs", "origin")

    def test_merge_and_annotated_tag_point_to_main(self):
        state = self.prepare()
        self.assertNotIn("v1.2.3", self.refs())
        promote.publish(self.state)
        self.assertEqual(promote.git("ls-remote", "origin", "refs/heads/main").split()[0], state["candidate"])
        self.assertEqual(promote.git("rev-parse", "v1.2.3^{}"), state["candidate"])
        self.assertEqual(promote.git("cat-file", "-t", "v1.2.3"), "tag")

    def test_invalid_semver(self):
        for version in ("v1.2.3", "1.2", "01.2.3", "1.2.3-01", "1.2.3\n", "../main"):
            with self.subTest(version=version), self.assertRaises(promote.ReleaseError):
                promote.version_tag(version)
        self.assertEqual(promote.version_tag("1.2.3-rc.1+build.2"), "v1.2.3-rc.1+build.2")

    def test_duplicate_tag_rejected(self):
        promote.git("tag", "v1.2.3")
        promote.git("push", "origin", "refs/tags/v1.2.3")
        before = self.refs()
        with self.assertRaisesRegex(promote.ReleaseError, "already exists"):
            self.prepare()
        self.assertEqual(before, self.refs())

    def test_noop_rejected(self):
        promote.git("checkout", "main")
        promote.git("merge", "--ff-only", "integracao")
        promote.git("push", "origin", "main")
        with self.assertRaisesRegex(promote.ReleaseError, "Nothing to promote"):
            self.prepare()

    def test_conflict_leaves_remote_unchanged(self):
        promote.git("checkout", "main")
        self.commit("base.txt", "main change")
        promote.git("push", "origin", "main")
        promote.git("checkout", "integracao")
        self.commit("base.txt", "integration change")
        promote.git("push", "origin", "integracao")
        before = self.refs()
        with self.assertRaisesRegex(promote.ReleaseError, "conflict"):
            self.prepare()
        self.assertEqual(before, self.refs())
        self.assertFalse(Path(".git/MERGE_HEAD").exists())

    def test_main_or_source_race_rejected(self):
        for branch in ("main", "integracao"):
            with self.subTest(branch=branch):
                self.prepare()
                promote.git("checkout", branch)
                self.commit(branch + ".txt", "advance " + branch)
                promote.git("push", "origin", branch)
                before = self.refs()
                with self.assertRaisesRegex(promote.ReleaseError, "Branches changed"):
                    promote.publish(self.state)
                self.assertEqual(before, self.refs())

    def test_tag_race_rejected(self):
        self.prepare()
        promote.git("tag", "v1.2.3")
        promote.git("push", "origin", "refs/tags/v1.2.3")
        before = self.refs()
        with self.assertRaisesRegex(promote.ReleaseError, "already exists"):
            promote.publish(self.state)
        self.assertEqual(before, self.refs())

    def test_atomic_rejection_does_not_publish_main_or_tag(self):
        self.prepare()
        # Disable the bare remote's atomic capability, simulating unsupported server.
        subprocess.run(["git", "--git-dir", str(self.remote), "config", "receive.advertiseAtomic", "false"], check=True)
        before = self.refs()
        with self.assertRaisesRegex(promote.ReleaseError, "Atomic publication rejected"):
            promote.publish(self.state)
        self.assertEqual(before, self.refs())

    def test_tampered_candidate_rejected(self):
        state = self.prepare()
        state["candidate"] = state["source"]
        import json
        self.state.write_text(json.dumps(state), encoding="utf-8")
        with self.assertRaisesRegex(promote.ReleaseError, "validated merge"):
            promote.publish(self.state)

    def test_server_policy_rejects_each_ref_atomically(self):
        # A bare update hook rejects one ref while accepting the other.
        for rejected in ("refs/heads/main", "refs/tags/v1.2.3"):
            with self.subTest(rejected=rejected):
                self.prepare()
                hook = self.remote / "hooks" / "update"
                hook.write_text('#!/bin/sh\n[ "$1" != "' + rejected + '" ]\n', encoding="utf-8")
                hook.chmod(0o755)
                before = self.refs()
                with self.assertRaisesRegex(promote.ReleaseError, "Atomic publication rejected"):
                    promote.publish(self.state)
                self.assertEqual(before, self.refs())
                promote.git("tag", "-d", "v1.2.3")

    def test_dirty_checkout_rejected(self):
        Path("untracked.txt").write_text("unsaved")
        with self.assertRaisesRegex(promote.ReleaseError, "clean disposable"):
            self.prepare()


if __name__ == "__main__":
    unittest.main()
