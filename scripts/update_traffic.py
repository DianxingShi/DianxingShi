import os
import requests
from datetime import datetime, timezone, timedelta

GH_TOKEN = os.environ.get("GH_TOKEN", "")
GH_USER = os.environ.get("GH_USER", "")
README_PATH = os.environ.get("README_PATH", "README.md")

HEADERS = {
    "Authorization": f"Bearer {GH_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

START = "<!--TRAFFIC_START-->"
END = "<!--TRAFFIC_END-->"

def safe_get(url, params=None):
    return requests.get(url, headers=HEADERS, params=params, timeout=30)

def get_public_repos(user):
    repos = []
    page = 1
    while True:
        r = safe_get(
            f"https://api.github.com/users/{user}/repos",
            params={"per_page": 100, "page": page, "type": "public", "sort": "updated"},
        )
        if r.status_code >= 400:
            raise RuntimeError(f"List repos failed: {r.status_code} {r.text[:300]}")
        data = r.json()
        repos.extend(data)
        if "next" not in r.links:
            break
        page += 1
    return [x for x in repos if not x.get("fork", False)]

def get_clones(owner, repo):
    r = safe_get(f"https://api.github.com/repos/{owner}/{repo}/traffic/clones")
    if r.status_code in (403, 404):
        return []
    if r.status_code >= 400:
        return []
    return r.json().get("clones", [])

def replace_section(readme, new_section):
    if START in readme and END in readme:
        a = readme.index(START) + len(START)
        b = readme.index(END)
        return readme[:a] + "\n\n" + new_section + "\n\n" + readme[b:]
    return readme + f"\n\n{START}\n\n{new_section}\n\n{END}\n"

def main():
    if not GH_TOKEN:
        raise RuntimeError("GH_TOKEN is empty. Please set secret TRAFFIC_TOKEN.")
    if not GH_USER:
        raise RuntimeError("GH_USER is empty.")

    repos = get_public_repos(GH_USER)

    today_utc = datetime.now(timezone.utc).date()
    yesterday_utc = today_utc - timedelta(days=1)

    rows = []
    for r in repos:
        owner = r["owner"]["login"]
        name = r["name"]

        clones = get_clones(owner, name)
        # clones entries are daily buckets for recent ~14 days
        count_14d = sum(item.get("count", 0) for item in clones)

        count_24h = 0
        for item in clones:
            d = item.get("timestamp", "")[:10]  # YYYY-MM-DD
            if d == yesterday_utc.isoformat():
                count_24h = item.get("count", 0)
                break

        rows.append((name, count_24h, count_14d))

    rows.sort(key=lambda x: (x[1], x[2], x[0].lower()), reverse=True)

    total_24h = sum(x[1] for x in rows)
    total_14d = sum(x[2] for x in rows)

    lines = []
    lines.append("## Public Repository Clone Summary")
    lines.append("")
    lines.append(f"_Last updated (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}_")
    lines.append("")
    lines.append(f"**All repos total** → New Clones (24h): **{total_24h}** | Total New Clones (14d): **{total_14d}**")
    lines.append("")
    lines.append("| Repository | New Clones (24h) | Total New Clones (14d) |")
    lines.append("|---|---:|---:|")

    if not rows:
        lines.append("| - | 0 | 0 |")
    else:
        for repo, c24, c14 in rows:
            lines.append(f"| `{repo}` | {c24} | {c14} |")

    section = "\n".join(lines)

    old = "# Profile\n"
    if os.path.exists(README_PATH):
        with open(README_PATH, "r", encoding="utf-8") as f:
            old = f.read()

    new = replace_section(old, section)
    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(new)

if __name__ == "__main__":
    main()
