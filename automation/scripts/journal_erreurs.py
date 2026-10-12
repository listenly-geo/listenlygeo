#!/usr/bin/env python3
"""Journal des erreurs MarketForge (12/10/2026).

Lance apres chaque workflow (voir marketforge-journal.yml). Lit les etapes du run via l'API GitHub,
releve celles en echec (meme si le workflow continue : continue-on-error) et les lignes d'erreur de leur log,
puis les ajoute a automation/marketforge_engine/journal.json (300 entrees max), lisible depuis le depot.
Aucun secret : adresses mail et longs jetons masques.
"""
import os, re, json, subprocess, datetime

JOURNAL = "automation/marketforge_engine/journal.json"
MOTIFS = re.compile(r"(Traceback|Error|error|ERROR|Exception|HTTP [45]\d\d|impossible|echec|échec|refus|invalid_grant|::error)", re.I)
BRUIT = re.compile(r"(Node\.js 20|ubuntu-latest|deprecated|0 erreur|erreurs?: 0|errors?=0)", re.I)


def sh(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return r.stdout


def propre(s):
    s = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "[mail]", s)
    s = re.sub(r"\b[A-Za-z0-9_\-]{28,}\b", "[jeton]", s)
    s = re.sub(r"^\S+\s+\S+\s+\d{4}-\d\d-\d\dT[\d:.]+Z\s?", "", s)
    return s.strip()[:300]


def main():
    run_id = os.environ["RUN_ID"]
    repo = os.environ["GITHUB_REPOSITORY"]
    run = json.loads(sh(f"gh api repos/{repo}/actions/runs/{run_id}") or "{}")
    jobs = json.loads(sh(f"gh api repos/{repo}/actions/runs/{run_id}/jobs --paginate --jq '{{jobs: .jobs}}'") or "{}").get("jobs", [])
    log = sh(f"gh run view {run_id} --repo {repo} --log")
    # Une etape "continue-on-error" qui echoue est notee "success" par l'API : on repere donc les etapes dont le log contient ##[error].
    par_etape = {}
    for l in log.splitlines():
        p = l.split("\t")
        if len(p) < 3 or "##[error]" not in p[2]:
            continue
        par_etape.setdefault(p[1].strip(), []).append(propre("\t".join(p[2:])))
    for j in jobs:
        for s in j.get("steps", []):
            if s.get("conclusion") == "failure" and s["name"] not in par_etape:
                par_etape[s["name"]] = []
    entrees = []
    for nom, err in par_etape.items():
        lignes = list(err)
        for l in log.splitlines():
            p = l.split("\t")
            if len(p) >= 3 and p[1].strip() == nom and MOTIFS.search(p[2]) and not BRUIT.search(p[2]) and "##[error]" not in p[2]:
                lignes.append(propre("\t".join(p[2:])))
        entrees.append({"etape": nom, "messages": (lignes[-8:]) or ["(echec sans message d'erreur lisible dans le log)"]})
    if not entrees:
        print("journal : aucun echec dans ce run")
        return
    try:
        j = json.load(open(JOURNAL, encoding="utf-8"))
    except Exception:
        j = {"_aide": "Erreurs des workflows MarketForge, la plus recente en premier. Alimente par journal_erreurs.py.", "entrees": []}
    for e in entrees:
        j["entrees"].insert(0, {
            "date": datetime.datetime.utcnow().strftime("%d/%m/%Y %H:%M UTC"),
            "workflow": run.get("name", "?"), "run": run_id, "lien": run.get("html_url", ""),
            "etape": e["etape"], "messages": e["messages"]})
    j["entrees"] = j["entrees"][:300]
    json.dump(j, open(JOURNAL, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"journal : {len(entrees)} echec(s) note(s)")


if __name__ == "__main__":
    main()
