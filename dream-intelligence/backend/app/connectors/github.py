import json
import os
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.request import Request, build_opener, HTTPRedirectHandler
from .base import BaseConnector, CollectionResult, NormalizedItem

REPOSITORIES = {"Comfy-Org/ComfyUI": "ComfyUI", "browser-use/browser-use": "browser-use", "unclecode/crawl4ai": "Crawl4AI"}
API_URL = "https://api.github.com"

class GitHubError(Exception):
    def __init__(self, status, rate_limited=False):
        self.status = status
        self.rate_limited = rate_limited
        super().__init__(f"GitHub HTTP {status}" + (" rate limit; stopped" if rate_limited else ""))

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

class GitHubConnector(BaseConnector):
    def __init__(self, token=None, timeout=20):
        self._token = os.environ.get("GITHUB_TOKEN", "").strip() if token is None else token
        self.timeout = timeout
        self.opener = build_opener(NoRedirect())

    @property
    def auth_mode(self):
        return "token" if self._token else "anonymous"

    def _request(self, path):
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "DSIH-GitHub-Radar/0.1", "X-GitHub-Api-Version": "2026-03-10"}
        if self._token:
            headers["Authorization"] = "Bearer " + self._token
        try:
            with self.opener.open(Request(API_URL + path, headers=headers), timeout=self.timeout) as response:
                return json.load(response)
        except HTTPError as error:
            # Conservatively stop all requests on 403/429; do not retry or switch auth.
            raise GitHubError(error.code, error.code in (403, 429)) from None
        except Exception:
            raise RuntimeError("GitHub transport or JSON response failed") from None

    def _fetch(self, repo):
        try:
            return {"kind": "release", "data": self._request(f"/repos/{repo}/releases/latest")}
        except GitHubError as error:
            if error.status != 404:
                raise
        # Omitted sha means the repository default branch; no code clone required.
        commits = self._request(f"/repos/{repo}/commits?per_page=1")
        if not isinstance(commits, list) or not commits:
            raise ValueError("No latest release or default branch commit")
        return {"kind": "commit", "data": commits[0]}

    def normalize(self, source, raw):
        if source not in REPOSITORIES:
            raise ValueError("Unsupported repository")
        data = raw["data"]
        if raw["kind"] == "release":
            identity = data.get("id") or data.get("tag_name")
            if identity is None or data.get("draft") or data.get("prerelease"):
                raise ValueError("Invalid latest release")
            title = source + " — " + (data.get("name") or data["tag_name"])
            content = data.get("body") or ""
            author = (data.get("author") or {}).get("login")
            published = data.get("published_at")
        elif raw["kind"] == "commit":
            identity = data["sha"]
            commit = data["commit"]
            content = commit["message"]
            title = content.splitlines()[0]
            author = (data.get("author") or {}).get("login") or (commit.get("author") or {}).get("name")
            published = (commit.get("author") or {}).get("date")
        else:
            raise ValueError("Unsupported GitHub item kind")
        if not identity or not title.strip():
            raise ValueError("Missing identity or title")
        return NormalizedItem(source=source, external_id=f"github:{source.lower()}:{raw['kind']}:{identity}",
            title=title, url=data["html_url"], content=content[:20000], author=author,
            published_at=datetime.fromisoformat(published.replace("Z", "+00:00")) if published else None,
            captured_at=datetime.now(timezone.utc))

    def collect(self):
        results = []
        stopped = False
        for repo in REPOSITORIES:
            if stopped:
                results.append(CollectionResult(repo, [], error="Not requested: GitHub rate-limit/access stop"))
                continue
            try:
                item = self.normalize(repo, self._fetch(repo))
                results.append(CollectionResult(repo, [item], 1))
            except GitHubError as error:
                stopped = error.rate_limited
                results.append(CollectionResult(repo, [], error=str(error)))
            except Exception:
                results.append(CollectionResult(repo, [], error="Repository fetch or normalization failed"))
        return results

    def health(self):
        try:
            self._request("/rate_limit")
            return True
        except Exception:
            return False
