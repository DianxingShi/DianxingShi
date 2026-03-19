import os
import requests
from datetime import datetime, timezone
from collections import defaultdict

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

def gh_get(url, params=None):
    r = requests.get(url, headers=HEADERS, params=params, timeout=30)
    if r.status_code >= 400:
        raise RuntimeError(f"GitHub API error {r.status_code} for {url}: {r.text}")
    return r.json(), r.links

def get_public_repos(user):
    repos = []
    page = 1
    while True:
        data, links = gh_get(
            f"https://api.github.com/users/{user}/repos",
            params={"per_page": 100, "page": page, "type": "public", "sort": "updated"},
        )
        repos.extend(data)
        if "next" not in links:
            break
        page += 1
    return repos

def get_views(owner, repo):
    url = f"https://api.github.com/repos/{owner}/{repo}/traffic/views"
    r = requests.get(url, headers=HEADERS, timeout=30)
    if r.status_code in (403, 404):
        print(f"[WARN] views unavailable for {owner}/{repo}: {r.status_code}")
        return []
    r.raise_for_status()
    return r.json().get("views", [])

def get_clones(owner, repo):
    url = f"https://api.github.com/repos/{owner}/{repo}/traffic/clones"
    r = requests.get(url, headers=HEADERS, timeout=30)
    if r.status_code in (403, 404):
        print(f"[WARN] clones unavailable for {owner}/{repo}: {r.status_code}")
        return []
    r.raise_for_status()
    return r.json().get("clones", [])

def date_only(ts):
    return ts[:10]

def build_section(user):
    repos = get_public_repos(user)
    repos = [r for r in repos if not r.get("fork", False)]
    print(f"[INFO] public non-fork repos: {len(repos)}")

    per_repo_daily = {}
    all_repo_clone_sum_daily = defaultdict(int)

    for r in repos:
        name = r["name"]
        owner = r["owner"]["login"]
        print(f"[INFO] processing {owner}/{name}")

        views = get_views(owner, name)
        clones = get_clones(owner, name)

        v_map = {date_only(x["timestamp"]): x.get("uniques", 0) for x in views}
        c_map = {date_only(x["timestamp"]): x.get("count", 0) for x in clones}

        dates = sorted(set(v_map.keys()) | set(c_map.keys()))
        repo_daily = {}
        for d in dates:
            u = v_map.get(d, 0)
            c = c_map.get(d, 0)
            repo_daily[d] = {"uniques": u, "clone_count": c}
            all_repo_clone_sum_daily[d] += c

        per_repo_daily[name] = repo_daily

    all_dates = sorted(all_repo_clone_sum_daily.keys())
    recent_dates = all_dates[-14:]

    lines = []
    lines.append("## 📈 Public Repositories Traffic (Last 14 Days)")
    lines.append("")
    lines.append(f"_Last updated (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}_")
    lines.append("")
    lines.append("### 每日新增总 Clone（所有公开仓库汇总）")
    lines.append("")
    lines.append("| 日期 | 新增 Clone 总数 |")
    lines.append("|---|---:|")
    for d in recent_dates:
        lines.append(f"| {d} | {all_repo_clone_sum_daily[d]} |")
    if not recent_dates:
        lines.append("| - | 0 |")
    lines.append("")

    lines.append("### 每个仓库每天独特访问者 / 总Clone")
    lines.append("")
    for repo in sorted(per_repo_daily.keys()):
        lines.append(f"#### `{repo}`")
        lines.append("")
        lines.append("| 日期 | 独特访问者 | Clone 数 |")
        lines.append("|---|---:|---:|")
        daily = per_repo_daily[repo]
        repo_dates = [d for d in recent_dates if d in daily]
        if not repo_dates:
            lines.append("| - | 0 | 0 |")
        else:
            for d in repo_dates:
                lines.append(f"| {d} | {daily[d]['uniques']} | {daily[d]['clone_count']} |")
        lines.append("")

    return "\n".join(lines)

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

    section = build_section(GH_USER)

    if os.path.exists(README_PATH):
        with open(README_PATH, "r", encoding="utf-8") as f:
            old = f.read()
    else:
        old = "# Profile\n"

    new = replace_section(old, section)
    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(new)

    print(f"[INFO] README updated: {README_PATH}")

if __name__ == "__main__":
    main()
