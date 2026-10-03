"""Promotion tests use local bare remotes and mocked GitHub release calls."""
import copy
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
        self.remote = self.root / 'remote.git'
        self.repo = self.root / 'checkout'
        self.old = Path.cwd()
        subprocess.run(['git', 'init', '--bare', str(self.remote)], check=True, capture_output=True)
        subprocess.run(['git', 'clone', str(self.remote), str(self.repo)], check=True, capture_output=True)
        os.chdir(self.repo)
        promote.git('config', 'user.name', 'Release test')
        promote.git('config', 'user.email', 'test@example.invalid')
        promote.git('checkout', '-b', 'main')
        Path('base.txt').write_text('base')
        promote.git('add', '.')
        promote.git('commit', '-m', 'base')
        promote.git('push', 'origin', 'main')
        promote.git('checkout', '-b', 'integracao')
        Path('feature.txt').write_text('feature')
        promote.git('add', '.')
        promote.git('commit', '-m', 'feature')
        promote.git('push', 'origin', 'integracao')
        source = promote.git('rev-parse', 'HEAD')
        promote.git('checkout', 'main')
        promote.git('merge', '--ff-only', 'integracao')
        promote.git('push', 'origin', 'main')
        self.event = {'repository': {'full_name': 'yeslei/libstock'}, 'pull_request': {
            'merged': True, 'title': 'Release v0.0.1',
            'body': f'<!-- libstock-release -->\n\nRelease-source: {source}\n',
            'head': {'ref': 'integracao', 'sha': source, 'repo': {'full_name': 'yeslei/libstock'}},
            'base': {'ref': 'main', 'repo': {'full_name': 'yeslei/libstock'}},
            'merge_commit_sha': source,
        }}
        self.github_calls = []
        self.release_response = subprocess.CompletedProcess([], 1, '', 'gh: Not Found (HTTP 404)')
        self.create_response = subprocess.CompletedProcess([], 0, 'https://github.com/yeslei/libstock/releases/tag/v0.0.1', '')
        self.original_run = subprocess.run
        self.environment = patch.dict(os.environ, {'GH_REPO': 'yeslei/libstock', 'GITHUB_STEP_SUMMARY': str(self.root / 'summary.md')})
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        os.chdir(self.old)
        self.temp.cleanup()

    def github_run(self, args, **kwargs):
        if args[0] != 'gh':
            return self.original_run(args, **kwargs)
        self.github_calls.append(args)
        return self.release_response if args[1] == 'api' else self.create_response

    def publish(self):
        with patch.object(promote.subprocess, 'run', side_effect=self.github_run):
            return promote.publish(self.event)

    def remote_tag(self):
        return promote.git('ls-remote', '--tags', 'origin', 'refs/tags/v0.0.1')

    def test_version_choices_without_tags(self):
        for bump, expected in [('patch', 'v0.0.1'), ('minor', 'v0.1.0'), ('major', 'v1.0.0')]:
            self.assertEqual(promote.next_tag(bump), expected)

    def test_highest_remote_stable_version_and_component_resets(self):
        for tag in ['v1.2.9', 'v1.2.10', 'v0.9.99', 'v2.0.0-rc.1', 'other', 'v01.2.3']:
            promote.git('tag', tag)
            promote.git('push', 'origin', f'refs/tags/{tag}')
        promote.git('tag', 'v9.0.0')
        for bump, expected in [('patch', 'v1.2.11'), ('minor', 'v1.3.0'), ('major', 'v2.0.0')]:
            self.assertEqual(promote.next_tag(bump), expected)

    def test_invalid_increment(self):
        with self.assertRaises(promote.ReleaseError):
            promote.next_tag('invalid')

    def test_only_merged_internal_promotion_pr_is_allowed(self):
        modifications = [
            lambda pr: pr.update(merged=False),
            lambda pr: pr['head'].update(ref='feature/test'),
            lambda pr: pr['base'].update(ref='integracao'),
            lambda pr: pr['head']['repo'].update(full_name='someone/fork'),
            lambda pr: pr['base']['repo'].update(full_name='someone/fork'),
        ]
        for modify in modifications:
            event = copy.deepcopy(self.event)
            modify(event['pull_request'])
            with self.assertRaises(promote.ReleaseError):
                promote.merged_release(event)

    def test_invalid_metadata_or_advanced_source_rejected(self):
        for changes in [
            {'title': 'Release v01.2.3'}, {'title': 'Release v1.2.3-rc.1'},
            {'body': None}, {'body': '<!-- libstock-release -->'},
            {'merge_commit_sha': '../main'},
            {'body': '<!-- libstock-release -->\nRelease-source: ' + 'a' * 40},
        ]:
            event = copy.deepcopy(self.event)
            event['pull_request'].update(changes)
            with self.assertRaises(promote.ReleaseError):
                promote.merged_release(event)

    def test_tag_and_release_use_merged_sha_even_when_main_advances(self):
        target = self.event['pull_request']['merge_commit_sha']
        promote.git('commit', '--allow-empty', '-m', 'later main change')
        promote.git('push', 'origin', 'main')
        before = promote.git('ls-remote', 'origin', 'refs/heads/main')
        self.assertEqual(self.publish(), ('v0.0.1', target))
        self.assertEqual(self.remote_tag().split()[0], target)
        self.assertEqual(before, promote.git('ls-remote', 'origin', 'refs/heads/main'))
        self.assertIn('--generate-notes', self.github_calls[-1])
        self.assertIn('--verify-tag', self.github_calls[-1])

    def test_existing_tag_on_another_commit_rejected(self):
        promote.git('tag', 'v0.0.1', 'HEAD^')
        promote.git('push', 'origin', 'refs/tags/v0.0.1')
        before = self.remote_tag()
        with self.assertRaisesRegex(promote.ReleaseError, 'another commit'):
            self.publish()
        self.assertEqual(before, self.remote_tag())
        self.assertEqual(self.github_calls, [])

    def test_existing_release_is_idempotent(self):
        promote.git('tag', 'v0.0.1')
        promote.git('push', 'origin', 'refs/tags/v0.0.1')
        self.release_response = subprocess.CompletedProcess([], 0, '{"html_url":"https://example.invalid/release"}', '')
        self.publish()
        self.assertEqual(len(self.github_calls), 1)

    def test_api_failure_does_not_publish_tag(self):
        self.release_response = subprocess.CompletedProcess([], 1, '', 'gh: Forbidden (HTTP 403)')
        with self.assertRaisesRegex(promote.ReleaseError, 'Cannot query'):
            self.publish()
        self.assertEqual(self.remote_tag(), '')

    def test_release_failure_can_retry_using_existing_tag(self):
        self.create_response = subprocess.CompletedProcess([], 1, '', 'API unavailable')
        with self.assertRaisesRegex(promote.ReleaseError, 'rerun'):
            self.publish()
        self.assertTrue(self.remote_tag())
        self.create_response = subprocess.CompletedProcess([], 0, 'https://example.invalid/release', '')
        self.publish()

    def test_server_rejection_does_not_create_release(self):
        promote.git('config', '--file', str(self.remote / 'config'), 'receive.denyNonFastForwards', 'true')
        hook = self.remote / 'hooks' / 'update'
        hook.write_text('#!/bin/sh\nexit 1\n', encoding='utf-8')
        hook.chmod(0o755)
        with self.assertRaises(promote.ReleaseError):
            self.publish()
        self.assertEqual(self.remote_tag(), '')
        self.assertEqual(len(self.github_calls), 1)


if __name__ == '__main__':
    unittest.main()
