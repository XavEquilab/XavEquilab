#!/usr/bin/env python3
"""Génère dark_mode.svg et light_mode.svg : carte de profil façon neofetch.

Les stats viennent de l'API GraphQL GitHub. Il faut un token qui voit les
repos privés des orgs (secret ACCESS_TOKEN dans le workflow, ou
GH_TOKEN="$(gh auth token)" en local). Seuls des totaux sont publiés :
aucun nom de repo privé ne sort, hormis la liste PROJECTS choisie à la main.
"""
import json
import os
import sys
import urllib.request
from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path

ROOT = Path(__file__).parent
USER = "XavEquilab"

# ─── Contenu de la carte : à éditer librement ───────────────────────────────
HEADER = "xav@equilab"
BIRTHDATE = date(2001, 7, 14)  # None = ancienneté du compte GitHub
INFO = [
    ("OS", "macOS, Linux"),
    ("Uptime", "{uptime}"),
    ("Kernel", "Full-stack Developer"),
    ("IDE", "VS Code, Claude Code, Codex"),
    None,
    ("Languages.Programming", "Java, TypeScript, Python, Go, PHP"),
    ("Languages.Computer", "HTML, CSS, SQL, Docker, LaTeX"),
    ("Languages.Real", "Français, English"),
    None,
    ("Projects", "Gubernat, PylierGO, Configurateur"),
    ("Projects", "Hyperviseur, JavotPivot"),
]
CONTACT = [
    ("Email", "lescieux@ga.fr"),
    ("LinkedIn", "xavier-lescieux-63b385172"),
    ("GitHub", USER),
]
# ────────────────────────────────────────────────────────────────────────────

WIDTH_CH = 62           # largeur de la colonne de droite, en caractères
FONT = "'JetBrains Mono','SF Mono',Menlo,Consolas,'DejaVu Sans Mono','Liberation Mono',monospace"
TXT_SIZE, TXT_LINE, TXT_CW = 15, 21, 9.0      # police, interligne, largeur d'un caractère
ART_SIZE, ART_LINE, ART_CW = 11.5, 14.5, 6.9    # idem pour l'art ASCII (cf. ascii_art.py)
PAD = 28

THEMES = {
    "dark": dict(bg="#161b22", border="#30363d", text="#c9d1d9", key="#ffa657",
                 value="#a5d6ff", dots="#484f58", add="#3fb950", dele="#f85149", art="#c9d1d9"),
    "light": dict(bg="#f6f8fa", border="#d0d7de", text="#24292f", key="#953800",
                  value="#0a3069", dots="#afb8c1", add="#1a7f37", dele="#cf222e", art="#24292f"),
}


# ─── Stats GitHub ───────────────────────────────────────────────────────────
def graphql(query, token, **variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": "profile-card"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.load(resp)
    if payload.get("errors"):
        # Les logs Actions sont publics : on ne recopie jamais le message brut,
        # qui peut contenir des noms de repos privés.
        kinds = sorted({e.get("type", "UNKNOWN") for e in payload["errors"]})
        raise RuntimeError(f"GraphQL: {len(payload['errors'])} erreur(s) {kinds}")
    return payload["data"]


USER_Q = """
query($login: String!, $after: String) {
  user(login: $login) {
    id createdAt
    followers { totalCount }
    owned: repositories(ownerAffiliations: OWNER, first: 1) { totalCount }
    repos: repositories(ownerAffiliations: [OWNER, COLLABORATOR, ORGANIZATION_MEMBER],
                        first: 100, after: $after) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes { nameWithOwner stargazerCount owner { login } }
    }
  }
}"""

HISTORY_Q = """
query($owner: String!, $name: String!, $author: ID!, $after: String) {
  repository(owner: $owner, name: $name) {
    defaultBranchRef { target { ... on Commit {
      history(first: 100, after: $after, author: { id: $author }) {
        totalCount
        pageInfo { hasNextPage endCursor }
        nodes { additions deletions }
      }
    } } }
  }
}"""


def fetch_stats(token):
    repos, after = [], None
    while True:
        u = graphql(USER_Q, token, login=USER, after=after)["user"]
        repos += u["repos"]["nodes"]
        if not u["repos"]["pageInfo"]["hasNextPage"]:
            break
        after = u["repos"]["pageInfo"]["endCursor"]

    commits = additions = deletions = 0
    for repo in repos:
        owner, name = repo["nameWithOwner"].split("/")
        after = None
        while True:
            ref = graphql(HISTORY_Q, token, owner=owner, name=name, author=u["id"], after=after)
            ref = ref["repository"]["defaultBranchRef"]
            if not ref:  # repo vide
                break
            hist = ref["target"]["history"]
            additions += sum(n["additions"] for n in hist["nodes"])
            deletions += sum(n["deletions"] for n in hist["nodes"])
            if not hist["pageInfo"]["hasNextPage"]:
                commits += hist["totalCount"]
                break
            after = hist["pageInfo"]["endCursor"]

    return dict(
        created=datetime.fromisoformat(u["createdAt"].replace("Z", "+00:00")).date(),
        repos=u["owned"]["totalCount"],
        contributed=u["repos"]["totalCount"],
        stars=sum(r["stargazerCount"] for r in repos if r["owner"]["login"] == USER),
        followers=u["followers"]["totalCount"],
        commits=commits, additions=additions, deletions=deletions,
    )


# ─── Mise en forme ──────────────────────────────────────────────────────────
def uptime(since: date, today: date) -> str:
    y, m, d = today.year - since.year, today.month - since.month, today.day - since.day
    if d < 0:
        m -= 1
        d += (today.replace(day=1) - timedelta(days=1)).day  # jours du mois précédent
    if m < 0:
        y, m = y - 1, m + 12
    plural = lambda n, w: f"{n} {w}{'s' if n != 1 else ''}"
    return ", ".join([plural(y, "year"), plural(m, "month"), plural(d, "day")])


def seg(text, cls=None):
    return (text, cls)


def pair(key, value, width):
    """'Key: ........ value' sur exactement `width` caractères."""
    head = f"{key}:"
    dots = max(width - len(head) - len(value) - 2, 1)
    return [seg(head, "key"), seg(" " + "." * dots + " ", "dots"), seg(value, "value")]


def leader(key, value, width):
    return [seg(". ", "dots")] + pair(key, value, width - 2)


def rule(title, width):
    head = f"- {title} "
    return [seg(head, "text"), seg("─" * (width - len(head)), "dots")]


def build_lines(stats, today):
    w = WIDTH_CH
    since = BIRTHDATE or stats["created"]
    lines = [[seg(HEADER, "value"), seg(" "), seg("─" * (w - len(HEADER) - 1), "dots")]]
    for item in INFO:
        if item is None:
            lines.append([seg(". ", "dots")])
            continue
        key, value = item
        if key == "Uptime" and not BIRTHDATE:
            key = "GitHub.Uptime"  # sans date de naissance : ancienneté du compte
        lines.append(leader(key, value.format(uptime=uptime(since, today)), w))
    lines.append([seg(". ", "dots")])
    lines.append(rule("Contact", w))
    lines += [leader(k, v, w) for k, v in CONTACT]
    lines.append([seg(". ", "dots")])
    lines.append(rule("GitHub Stats", w))
    s = stats
    lines.append(leader("Repos", f"{s['repos']} {{Contributed: {s['contributed']}}}", w))
    lines.append(leader("Commits", f"{s['commits']:,}", w))
    loc = f"{s['additions'] - s['deletions']:,}"
    add, dele = f"{s['additions']:,}++", f"{s['deletions']:,}--"
    tail = f"{loc} ( {add}, {dele} )"
    lines.append(leader("Lines of Code", tail, w)[:-1]
                 + [seg(loc, "value"), seg(" ( "), seg(add, "add"), seg(", "), seg(dele, "dele"), seg(" )")])
    lines.append([])
    # Prompt final avec curseur clignotant (un glyphe, donc calé quelle que soit la police).
    lines.append([seg(HEADER, "value"), seg(":"), seg("~", "key"), seg("$ "), seg("█", "cursor")])
    return lines


def render(theme, art, lines):
    c = THEMES[theme]
    art_w = max(len(l) for l in art) * ART_CW
    text_x = PAD + art_w + 30
    width = text_x + WIDTH_CH * TXT_CW + PAD
    height = max(len(art) * ART_LINE, len(lines) * TXT_LINE) + 2 * PAD
    art_y0 = (height - len(art) * ART_LINE) / 2 + ART_SIZE
    txt_y0 = (height - len(lines) * TXT_LINE) / 2 + TXT_SIZE

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
        f'viewBox="0 0 {width:.0f} {height:.0f}" font-family="{FONT}" xml:space="preserve">',
        "<style>",
        f"text{{white-space:pre}} .text{{fill:{c['text']}}} .key{{fill:{c['key']}}} .value{{fill:{c['value']}}} "
        f".dots{{fill:{c['dots']}}} .add{{fill:{c['add']}}} .dele{{fill:{c['dele']}}} "
        f".art{{fill:{c['art']}}} .cursor{{fill:{c['value']};animation:blink 1.1s steps(1) infinite}} "
        "@keyframes blink{50%{fill:transparent}}",
        "</style>",
        f'<rect width="100%" height="100%" rx="12" fill="{c["bg"]}" stroke="{c["border"]}"/>',
        f'<text class="art" font-size="{ART_SIZE}">',
    ]
    for i, row in enumerate(art):
        out[-1] += (f'<tspan x="{PAD}" y="{art_y0 + i * ART_LINE:.1f}">{escape(row)}</tspan>')
    out[-1] += "</text>"
    out.append(f'<text class="text" font-size="{TXT_SIZE}">')
    for i, line in enumerate(lines):
        y = txt_y0 + i * TXT_LINE
        spans = "".join(f'<tspan class="{cls}">{escape(t)}</tspan>' if cls else escape(t) for t, cls in line)
        out[-1] += (f'<tspan x="{text_x:.0f}" y="{y:.1f}">{spans}</tspan>')
    out[-1] += "</text>"
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main():
    token = os.environ.get("ACCESS_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("Pas de ACCESS_TOKEN/GH_TOKEN : SVG inchangés.", file=sys.stderr)
        return
    try:
        stats = fetch_stats(token)
    except Exception as exc:  # pas de traceback : il pourrait citer un repo privé
        print(f"Échec de la récupération des stats ({type(exc).__name__}): {exc if isinstance(exc, RuntimeError) else ''}",
              file=sys.stderr)
        sys.exit(1)
    print(json.dumps(stats, default=str))
    art = (ROOT / "ascii.txt").read_text(encoding="utf-8").rstrip("\n").split("\n")
    lines = build_lines(stats, date.today())
    for theme in THEMES:
        (ROOT / f"{theme}_mode.svg").write_text(render(theme, art, lines), encoding="utf-8")


if __name__ == "__main__":
    main()
