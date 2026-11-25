import re
from typing import Dict, List, Tuple
import httpx
from src.config import GITHUB_API_BASE, GITHUB_TOKEN, MAX_REPO_FILES, REQUEST_TIMEOUT_SECONDS

GITHUB_URL_REGEX = re.compile(
    r"^https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/#?]+)(?:/(?:blob|tree)/(?P<branch>[^/]+)/(?P<path>.+))?/?$"
)


def parse_github_url(url: str) -> Tuple[str, str, str, str]:
    match = GITHUB_URL_REGEX.match(url.strip())
    if not match:
        raise ValueError("Invalid GitHub URL. Expected https://github.com/<owner>/<repo> or .../blob/<branch>/<path>")
    return match.group("owner"), match.group("repo").removesuffix(".git"), match.group("branch") or "", match.group("path") or ""


def _build_headers() -> Dict[str, str]:
    headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "RepoLens-Analyzer"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers


def fetch_python_files_from_github(url: str) -> List[Dict[str, str]]:
    owner, repo, branch, path = parse_github_url(url)
    api_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}".rstrip("/")
    params = {"ref": branch} if branch else {}
    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS, headers=_build_headers()) as client:
            resp = client.get(api_url, params=params)
            if resp.status_code == 404:
                raise LookupError("GitHub repository or file path not found (404).")
            if resp.status_code == 403:
                raise PermissionError("GitHub API rate limit exceeded or access forbidden (403).")
            resp.raise_for_status()
            payload = resp.json()

            files_to_download = []
            if isinstance(payload, dict) and payload.get("type") == "file":
                if not payload["name"].endswith(".py"):
                    raise ValueError("Target GitHub file is not a Python (.py) file.")
                files_to_download.append(payload)
            elif isinstance(payload, list):
                py_items = [item for item in payload if item.get("type") == "file" and item["name"].endswith(".py")]
                if not py_items:
                    raise ValueError("No Python (.py) files found in the specified repository directory.")
                files_to_download.extend(py_items[:MAX_REPO_FILES])

            results: List[Dict[str, str]] = []
            for item in files_to_download:
                raw_resp = client.get(item["download_url"])
                raw_resp.raise_for_status()
                results.append({"filename": f"{owner}/{repo}/{item['path']}", "source_code": raw_resp.text})
            return results
    except httpx.RequestError as exc:
        raise ConnectionError(f"Network error contacting GitHub API: {exc}") from exc
