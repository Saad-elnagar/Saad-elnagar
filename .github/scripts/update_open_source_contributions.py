#!/usr/bin/env python3
"""Refresh the Open Source Contributions section in the profile README."""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

USERNAME = os.environ.get("GITHUB_USERNAME", "Saad-elnagar")
TOKEN = os.environ.get("GITHUB_TOKEN")
README = Path("README.md")
START_MARKER = "<!-- OPEN_SOURCE_CONTRIBUTIONS:START -->"
END_MARKER = "<!-- OPEN_SOURCE_CONTRIBUTIONS:END -->"
MAX_DISPLAYED = 10


def github_get(url: str) -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "open-source-profile-updater",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"GitHub API request failed ({error.code}): {details}"
        ) from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Could not reach the GitHub API: {error}") from error


def fetch_merged_external_prs() -> dict:
    # Show contributions merged into repositories owned by other maintainers.
    query = f"author:{USERNAME} is:pr is:merged -user:{USERNAME}"
    params = urllib.parse.urlencode(
        {
            "q": query,
            "sort": "updated",
            "order": "desc",
            "per_page": 100,
            "page": 1,
        }
    )
    return github_get(f"https://api.github.com/search/issues?{params}")


def render_contributions(payload: dict) -> str:
    items = payload.get("items", [])
    if not items:
        return "*No merged pull requests to external repositories found yet.*"

    lines = [
        f"*{payload.get('total_count', len(items))} merged external pull request(s) found; showing the latest {min(MAX_DISPLAYED, len(items))}.*",
        "",
    ]

    for item in items[:MAX_DISPLAYED]:
        title = item.get("title", "Merged pull request").replace("[", r"\[").replace("]", r"\]")
        pr_url = item.get("html_url", "")
        repository_api_url = item.get("repository_url", "")
        prefix = "https://api.github.com/repos/"
        if repository_api_url.startswith(prefix):
            repository = repository_api_url[len(prefix):]
            repository_link = f"[\`{repository}\`](https://github.com/{repository})"
            lines.append(f"- [{title}]({pr_url}) — {repository_link}")
        else:
            lines.append(f"- [{title}]({pr_url})")

    return "\n".join(lines)


def main() -> None:
    if not TOKEN:
        raise RuntimeError("GITHUB_TOKEN is required to query merged pull requests.")

    readme = README.read_text(encoding="utf-8")
    if START_MARKER not in readme or END_MARKER not in readme:
        raise RuntimeError("Contribution markers were not found in README.md.")

    payload = fetch_merged_external_prs()
    generated = render_contributions(payload)
    before, remainder = readme.split(START_MARKER, maxsplit=1)
    _, after = remainder.split(END_MARKER, maxsplit=1)
    updated = f"{before}{START_MARKER}\n{generated}\n{END_MARKER}{after}"

    if updated == readme:
        print("Open-source contributions are already up to date.")
        return

    README.write_text(updated, encoding="utf-8")
    print("Updated the Open Source Contributions section.")


if __name__ == "__main__":
    main()
