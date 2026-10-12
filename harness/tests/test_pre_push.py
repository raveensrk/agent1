"""Tests for harness/githooks/pre-push, through real `git push` runs to local bare repos.

Run: timeout 120 python3 -m pytest -q harness/tests/test_pre_push.py
"""
import os
import subprocess
import tempfile

HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "githooks")


def setup(tmp):
    """A repo with one commit and a bare remote; returns (repo, remote url)."""
    repo, bare = os.path.join(tmp, "repo"), os.path.join(tmp, "bare.git")
    subprocess.run(["git", "init", "-q", "--bare", bare], check=True)
    subprocess.run(["git", "init", "-q", repo], check=True)
    for key, value in (("user.name", "Test"), ("user.email", "t@example.com"), ("core.hooksPath", HOOKS)):
        subprocess.run(["git", "-C", repo, "config", key, value], check=True)
    with open(os.path.join(repo, "f.txt"), "w") as fh:
        fh.write("x\n")
    subprocess.run(["git", "-C", repo, "add", "f.txt"], check=True)
    subprocess.run(["git", "-C", repo, "commit", "-q", "-m", "init"], check=True)
    subprocess.run(["git", "-C", repo, "remote", "add", "origin", bare], check=True)
    return repo, bare


def push(repo):
    return subprocess.run(["git", "-C", repo, "push", "-q", "origin", "HEAD:main"], capture_output=True, text=True)


def test_a_repo_without_the_flag_pushes():
    with tempfile.TemporaryDirectory() as tmp:
        repo, _ = setup(tmp)
        run = push(repo)
        assert run.returncode == 0, run.stderr


def test_a_private_repo_refuses_a_remote_not_allowed():
    with tempfile.TemporaryDirectory() as tmp:
        repo, bare = setup(tmp)
        subprocess.run(["git", "-C", repo, "config", "repo.private", "true"], check=True)
        run = push(repo)
        assert run.returncode != 0
        assert "push refused" in run.stderr and f"repo.allowRemote {bare}" in run.stderr, run.stderr


def test_a_private_repo_pushes_to_an_allowed_remote():
    with tempfile.TemporaryDirectory() as tmp:
        repo, bare = setup(tmp)
        subprocess.run(["git", "-C", repo, "config", "repo.private", "true"], check=True)
        subprocess.run(["git", "-C", repo, "config", "--add", "repo.allowRemote", bare], check=True)
        run = push(repo)
        assert run.returncode == 0, run.stderr


def test_an_unverifiable_github_remote_is_refused():
    """An allowed GitHub URL still needs gh to confirm it is private; no answer refuses."""
    import importlib.machinery
    import importlib.util

    loader = importlib.machinery.SourceFileLoader("pre_push", os.path.join(HOOKS, "pre-push"))
    spec = importlib.util.spec_from_loader("pre_push", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    url = "git@github.com:someone/meds.git"
    module.config = lambda *args: (
        ["true"] if "repo.private" in args else [url] if "repo.allowRemote" in args else []
    )
    module.github_private = lambda u: None
    assert "could not confirm" in module.refusal(url)
    module.github_private = lambda u: False
    assert "public GitHub repo" in module.refusal(url)
    module.github_private = lambda u: True
    assert module.refusal(url) is None
