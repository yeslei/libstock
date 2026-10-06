"""Version promotion PRs and publish their merged commits as GitHub Releases."""
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
    result = subprocess.run(['git', *args], text=True, capture_output=True)
    if result.returncode:
        raise ReleaseError(f'Git failed: {args[0]}; check permissions and refs.')
    return result.stdout.strip()


def next_tag(bump='patch'):
    if bump not in ('patch', 'minor', 'major'):
        raise ReleaseError('Invalid increment: choose patch, minor or major.')
    versions = []
    for line in git('ls-remote', '--refs', '--tags', 'origin').splitlines():
        ref = line.split('\t', 1)[1]
        match = re.fullmatch(r'refs/tags/v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', ref)
        if match:
            versions.append(tuple(map(int, match.groups())))
    major, minor, patch = max(versions, default=(0, 0, 0))
    if bump == 'major':
        return f'v{major + 1}.0.0'
    if bump == 'minor':
        return f'v{major}.{minor + 1}.0'
    return f'v{major}.{minor}.{patch + 1}'


def merged_release(event):
    pr = event['pull_request']
    repository = event['repository']['full_name']
    if (pr['merged'] is not True or pr['base']['ref'] != 'main'
            or pr['head']['ref'] != 'integracao'
            or pr['head']['repo']['full_name'] != repository
            or pr['base']['repo']['full_name'] != repository):
        raise ReleaseError('Only a merged integracao -> main PR can publish a release.')
    title = re.fullmatch(r'Release (v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*))', pr['title'])
    body = pr.get('body') or ''
    source = re.search(r'^Release-source: ([0-9a-f]{40})$', body, re.MULTILINE)
    if not title or '<!-- libstock-release -->' not in body or not source:
        raise ReleaseError('Missing or invalid promotion metadata.')
    if source.group(1) != pr['head']['sha']:
        raise ReleaseError('integracao advanced after PR creation; start a new promotion.')
    target = pr['merge_commit_sha']
    if not re.fullmatch(r'[0-9a-f]{40}', target):
        raise ReleaseError('Invalid merged commit SHA.')
    return title.group(1), target


def publish(event):
    tag, target = merged_release(event)
    # Use the actual commit of this PR, even if main has advanced since its merge.
    git('cat-file', '-e', f'{target}^{{commit}}')
    lines = git('ls-remote', '--tags', 'origin', f'refs/tags/{tag}', f'refs/tags/{tag}^{{}}')
    refs = dict(line.split('\t')[::-1] for line in lines.splitlines())
    tagged = refs.get(f'refs/tags/{tag}^{{}}') or refs.get(f'refs/tags/{tag}')
    if tagged and tagged != target:
        raise ReleaseError('Release tag already points to another commit; no overwrite attempted.')
    existing = subprocess.run(['gh', 'api', f'repos/{os.environ["GH_REPO"]}/releases/tags/{tag}'], text=True, capture_output=True)
    if existing.returncode == 0:
        if not tagged:
            raise ReleaseError('Existing release has no matching remote tag.')
        url = json.loads(existing.stdout)['html_url']
    else:
        if '(HTTP 404)' not in existing.stderr:
            raise ReleaseError('Cannot query existing release; check permissions or API availability.')
        if not tagged:
            git('tag', tag, target)
            git('push', 'origin', f'refs/tags/{tag}')
        result = subprocess.run(['gh', 'release', 'create', tag, '--verify-tag', '--title', tag, '--generate-notes'], text=True, capture_output=True)
        if result.returncode:
            raise ReleaseError('Release creation failed. The tag may exist; rerun this job to retry.')
        url = result.stdout.strip()
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a', encoding='utf-8') as stream:
            stream.write(f'Release [{tag}]({url}) publicada no commit {target}.\n')
    print(url)
    return tag, target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    version = commands.add_parser('version')
    version.add_argument('--bump', choices=('patch', 'minor', 'major'), default='patch')
    release = commands.add_parser('publish')
    release.add_argument('--event', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'version':
            tag = next_tag(args.bump)
            if os.environ.get('GITHUB_OUTPUT'):
                with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as stream:
                    stream.write(f'tag={tag}\n')
            print(tag)
        else:
            publish(json.loads(Path(args.event).read_text(encoding='utf-8')))
    except (ReleaseError, ValueError, KeyError, TypeError, OSError) as error:
        print(f'Release failed: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
