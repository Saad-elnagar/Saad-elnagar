#!/usr/bin/env python3
"""Refresh the Open Source Contributions table in the profile README."""

import json
import os
import re
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
API_PREFIX = "https://api.github.com/repos/"


def github_get(url: str) -> dict:
    """Fetch JSON from GitHub with clear API and network errors."""
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
    """Find merged PRs authored by the profile owner in other repositories."""
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


def markdown_cell(value: str) -> str:
    """Keep text readable inside a Markdown table cell."""
    return re.sub(r"\s+", " ", value or "").strip().replace("|", "&#124;")


def extract_summary(body: str) -> str:
    """Prefer the PR's Summary section; otherwise use useful body lines."""
    body = body or ""
    match = re.search(
        r"(?ims)^#{1,6}\s+Summary\s*\n(.*?)(?=^#{1,6}\s+|\Z)",
        body,
    )
    text = match.group(1) if match else body
    parts = []

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.lower().startswith(("fixes #", "closes #", "resolves #")):
            continue
        if line.startswith("#") or line.startswith(chr(96) * 3):
            continue
        if line.startswith(("- ", "* ", "+ ")):
            line = line[2:].strip()
        parts.append(line)

    summary = markdown_cell(" ".join(parts))
    if len(summary) > 220:
        summary = summary[:217].rsplit(" ", 1)[0] + "…"
    return summary or "Merged contribution to an open-source project."


def render_contributions(payload: dict) -> str:
    """Render a concise, recruiter-friendly contribution table."""
    all_items = payload.get("items", [])
    items = all_items[:MAX_DISPLAYED]
    total_count = payload.get("total_count", len(all_items))

    if not items:
        return (
            "**No merged contributions to external repositories found yet.**\n\n"
            "*Once a pull request is merged, it will appear here automatically.*"
        )

    noun = "merged contribution" if total_count == 1 else "merged contributions"
    lines = [
        f"**{total_count} {noun}** · Showing the latest {len(items)}",
        "",
        "| Contribution | Project | Impact |",
        "|---|---|---|",
    ]

    for item in items:
        title = markdown_cell(item.get("title", "Merged pull request"))
        title = title.replace("[", r"\[").replace("]", r"\]")
        pr_url = item.get("html_url", "")
        repository_api_url = item.get("repository_url", "")

        if repository_api_url.startswith(API_PREFIX):
            repository = repository_api_url[len(API_PREFIX):]
            project = f"[{repository}](https://github.com/{repository})"
        else:
            project = "Open-source project"

        summary = extract_summary(item.get("body", ""))
        lines.append(f"| [{title}]({pr_url}) | {project} | {summary} |")

    return "\n".join(lines)


def main() -> None:
    if not TOKEN:
        raise RuntimeError("GITHUB_TOKEN is required to query merged pull requests.")

    readme = README.read_text(encoding="utf-8")
    if readme.count(START_MARKER) != 1 or readme.count(END_MARKER) != 1:
        raise RuntimeError(
            "Expected exactly one pair of contribution markers in README.md."
        )

    payload = fetch_merged_external_prs()
    generated = render_contributions(payload)
    before, remainder = readme.split(START_MARKER, maxsplit=1)
    _, after = remainder.split(END_MARKER, maxsplit=1)
    updated = f"{before}{START_MARKER}\n{generated}\n{END_MARKER}{after}"

    if updated == readme:
        print("Open-source contributions are already up to date.")
        return

    README.write_text(updated, encoding="utf-8")
    print(
        "Updated the Open Source Contributions section with "
        f"{payload.get('total_count', 0)} merged contribution(s)."
    )


if __name__ == "__main__":
    main()
