"""Colab notebook helpers: clone, publish artifacts back to GitHub.

Generic version — works with any living-research project.
Repo URL and org are auto-detected from git remote.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable


def _detect_repo_info(repo_dir: Path) -> tuple[str, str, str]:
    """Extract (org, repo_name, repo_url) from git remote."""
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=repo_dir, capture_output=True, text=True,
    )
    url = result.stdout.strip()
    match = re.search(r"github\.com[:/]([^/]+)/([^/.]+)", url)
    if not match:
        raise RuntimeError(f"Cannot parse GitHub org/repo from remote: {url}")
    return match.group(1), match.group(2), url


def clone_repo(
    repo_url: str | None = None,
    dest: str | Path | None = None,
    branch: str = "main",
    depth: int = 1,
) -> Path:
    """Clone a repo into Colab's /content directory.

    If repo_url is None, prints instructions. Returns the repo path.
    """
    if repo_url is None:
        raise ValueError("Pass your repo URL: clone_repo('https://github.com/org/repo')")

    match = re.search(r"github\.com[:/]([^/]+)/([^/.]+)", repo_url)
    repo_name = match.group(2) if match else "repo"
    repo_path = Path(dest) if dest else Path("/content") / repo_name

    if repo_path.exists():
        print(f"Already cloned at {repo_path}")
        return repo_path

    subprocess.run(
        ["git", "clone", "--depth", str(depth), "--branch", branch, repo_url, str(repo_path)],
        check=True,
    )
    print(f"Cloned to {repo_path}")
    return repo_path


# ---------------------------------------------------------------------------
# Publish
# ---------------------------------------------------------------------------

_GITHUB_SVG = """
<svg width="18" height="18" viewBox="0 0 98 96" fill="white"
     xmlns="http://www.w3.org/2000/svg">
  <path fill-rule="evenodd" clip-rule="evenodd"
    d="M48.854 0C21.839 0 0 22 0 49.217c0 21.756 13.993 40.172 33.405
    46.69 2.427.49 3.316-1.059 3.316-2.362 0-1.141-.08-5.052-.08-9.127
    -13.59 2.934-16.42-5.867-16.42-5.867-2.184-5.704-5.42-7.17-5.42-7.17
    -4.448-3.015.324-3.015.324-3.015 4.934.326 7.523 5.052 7.523 5.052
    4.367 7.496 11.404 5.378 14.235 4.074.404-3.178 1.699-5.378 3.074-6.6
    -10.839-1.141-22.243-5.378-22.243-24.283 0-5.378 1.94-9.778 5.014-13.2
    -.485-1.222-2.184-6.275.486-13.038 0 0 4.125-1.304 13.426 5.052
    a46.97 46.97 0 0 1 12.214-1.63c4.125 0 8.33.571 12.213 1.63
    9.302-6.356 13.427-5.052 13.427-5.052 2.67 6.763.97 11.816.485 13.038
    3.155 3.422 5.015 7.822 5.015 13.2 0 18.905-11.404 23.06-22.324 24.283
    1.78 1.548 3.316 4.481 3.316 9.126 0 6.6-.08 11.897-.08 13.526
    0 1.304.89 2.853 3.316 2.364 19.412-6.52 33.405-24.935 33.405-46.691
    C97.707 22 75.788 0 48.854 0z"/>
</svg>
"""

_BTN_STYLE = """
<style>
  .lr-btn {
    display: inline-flex; align-items: center; gap: 8px;
    padding: 10px 20px; border: none; border-radius: 6px;
    background: #24292f; color: #fff; font-size: 14px;
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    cursor: pointer; transition: background 0.15s;
  }
  .lr-btn:hover:not(:disabled) { background: #32383f; }
  .lr-btn:disabled { opacity: 0.7; cursor: default; }
  .lr-status { margin-top: 8px; font-size: 13px;
    font-family: monospace; color: #555; }
</style>
"""


def _do_publish(
    token: str,
    rel_paths: list[str],
    message: str,
    repo_path: Path,
    dry_run: bool,
) -> bool:
    """Git add, commit, rebase, push."""
    missing = [p for p in rel_paths if not (repo_path / p).exists()]
    if missing:
        raise FileNotFoundError("Cannot publish — files not found: " + ", ".join(missing))

    # Normalize .ipynb files
    for rel in rel_paths:
        if not rel.endswith(".ipynb"):
            continue
        nb_path = repo_path / rel
        with open(nb_path) as f:
            nb = json.load(f)
        if "ipynb" in nb and "cells" not in nb:
            nb = nb["ipynb"]
            nb.setdefault("nbformat", 4)
            nb.setdefault("nbformat_minor", 5)
            with open(nb_path, "w") as f:
                json.dump(nb, f, indent=1)
                f.write("\n")

    org, repo_name, _ = _detect_repo_info(repo_path)
    repo_url = f"https://x-access-token:{token}@github.com/{org}/{repo_name}.git"

    subprocess.run(["git", "config", "user.email", "colab-bot@living-research"], check=True, cwd=repo_path)
    subprocess.run(["git", "config", "user.name", "Colab Bot"], check=True, cwd=repo_path)
    subprocess.run(["git", "remote", "set-url", "origin", repo_url], check=True, cwd=repo_path)

    if (repo_path / ".git" / "shallow").exists():
        subprocess.run(["git", "fetch", "--unshallow", "origin", "main"], check=True, cwd=repo_path)

    subprocess.run(["git", "add", "--force", "--", *rel_paths], check=True, cwd=repo_path)

    status = subprocess.run(
        ["git", "status", "--porcelain", "--", *rel_paths],
        cwd=repo_path, capture_output=True, text=True, check=True,
    )
    staged = [line for line in status.stdout.splitlines() if line and line[0] not in (" ", "?")]
    if not staged:
        print("No artifact changes to commit.")
        return False

    if dry_run:
        print(f"[dry_run] Would commit: {', '.join(rel_paths)}")
        return False

    subprocess.run(["git", "commit", "-m", f"{message} [skip ci]"], check=True, cwd=repo_path)

    subprocess.run(["git", "stash", "--include-untracked"], cwd=repo_path, capture_output=True)
    subprocess.run(["git", "rebase", "--abort"], cwd=repo_path, capture_output=True)

    fetch = subprocess.run(["git", "fetch", "origin", "main"], cwd=repo_path, capture_output=True, text=True)
    if fetch.returncode != 0:
        subprocess.run(["git", "stash", "pop"], cwd=repo_path, capture_output=True)
        raise RuntimeError(f"git fetch failed:\n{fetch.stderr or fetch.stdout}")

    rebase = subprocess.run(["git", "rebase", "origin/main"], cwd=repo_path, capture_output=True, text=True)
    if rebase.returncode != 0:
        subprocess.run(["git", "rebase", "--abort"], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "stash", "pop"], cwd=repo_path, capture_output=True)
        raise RuntimeError(f"git rebase failed:\n{rebase.stderr or rebase.stdout}")

    subprocess.run(["git", "stash", "pop"], cwd=repo_path, capture_output=True)

    push = subprocess.run(["git", "push", "origin", "main"], cwd=repo_path, capture_output=True, text=True)
    if push.returncode != 0:
        err = push.stderr or push.stdout
        if "403" in err or "denied" in err.lower():
            raise RuntimeError(
                f"Push denied. Your GitHub account needs write access to {org}/{repo_name}.\n"
                f"Ask an org admin to add you as a collaborator, then re-run this cell.\n\n{err}"
            )
        raise RuntimeError(f"git push failed:\n{err}")

    print(f"Published {len(staged)} file(s) to {org}/{repo_name}.")
    return True


def publish_artifacts(
    message: str,
    paths: Iterable[str | Path] | None = None,
    repo_dir: str | Path | None = None,
    dry_run: bool = False,
) -> bool | None:
    """Commit and push artifacts from Colab back to GitHub.

    If paths is None, includes all files under results/ and docs/data/.
    Uses a stored secret if available; otherwise shows a Sign in & Publish button.
    """
    try:
        import google.colab  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("publish_artifacts only works from Google Colab.") from exc

    if repo_dir is None:
        # Auto-detect: look for a git repo in /content
        for d in Path("/content").iterdir():
            if (d / ".git").exists():
                repo_dir = d
                break
        if repo_dir is None:
            raise RuntimeError("No git repo found in /content. Clone your repo first.")

    repo_path = Path(repo_dir)
    org, repo_name, _ = _detect_repo_info(repo_path)

    if paths is None:
        paths = []
        for subdir in ["results", "docs/data"]:
            d = repo_path / subdir
            if d.exists():
                paths.extend(p for p in sorted(d.rglob("*")) if p.is_file())

    rel_paths = [str(Path(p).relative_to(repo_path)) for p in paths]

    # Try env var first
    token = os.environ.get("GITHUB_TOKEN")

    # Fall back to Colab secret
    if not token:
        try:
            from google.colab import userdata
            token = userdata.get("GITHUB_TOKEN")
        except Exception:
            token = None

    if token:
        return _do_publish(token, rel_paths, message, repo_path, dry_run)

    # Show OAuth button
    from IPython.display import display, HTML
    from google.colab import output

    def _on_token(token: str) -> None:
        print("Authenticated. Publishing…")
        try:
            _do_publish(token, rel_paths, message, repo_path, dry_run)
        except Exception as e:
            print(f"Publish failed: {e}")

    output.register_callback("_lr_publish_cb", _on_token)

    display(HTML(f"""
    {_BTN_STYLE}
    <button class="lr-btn" id="lr-pub-btn">
      {_GITHUB_SVG}
      Sign in &amp; Publish
    </button>
    <div class="lr-status" id="lr-pub-status"></div>
    <script type="module">
      import {{ connectGitHub }} from 'https://neevs.io/auth/lib.js';
      const btn = document.getElementById('lr-pub-btn');
      const status = document.getElementById('lr-pub-status');
      btn.addEventListener('click', async () => {{
        btn.disabled = true;
        status.textContent = 'Waiting for GitHub authorization\u2026';
        try {{
          const {{ token }} = await connectGitHub('repo', '{org}');
          btn.style.background = '#2da44e';
          btn.innerHTML = '\u2713 Authorized \u2014 publishing\u2026';
          status.textContent = '';
          google.colab.kernel.invokeFunction('_lr_publish_cb', [token], {{}});
        }} catch (e) {{
          btn.disabled = false;
          btn.style.background = '';
          status.textContent = 'Authorization failed \u2014 try again.';
          console.error(e);
        }}
      }});
    </script>
    """))
    return None


def save_notebook(
    notebook_name: str = "analysis.ipynb",
    repo_dir: str | Path | None = None,
) -> str | None:
    """Save the current Colab notebook state to the repo's notebooks/ directory."""
    try:
        from google.colab import _message
    except ImportError:
        return None

    if repo_dir is None:
        for d in Path("/content").iterdir():
            if (d / ".git").exists():
                repo_dir = d
                break

    repo_path = Path(repo_dir)

    try:
        nb = _message.blocking_request("get_ipynb", request="", timeout_sec=30)
        if not nb:
            return None

        if "ipynb" in nb and "cells" not in nb:
            nb = nb["ipynb"]

        nb.setdefault("nbformat", 4)
        nb.setdefault("nbformat_minor", 5)

        out = repo_path / "notebooks" / notebook_name
        with open(out, "w") as f:
            json.dump(nb, f, indent=1)

        rel = f"notebooks/{notebook_name}"
        print(f"Notebook snapshot saved to {rel}")
        return rel
    except Exception as e:
        print(f"Warning: could not save notebook — {e}")
        return None
