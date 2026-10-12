#!/usr/bin/env python3
"""Envoi de secours (12/10/2026) : si le declencheur d'envoi de 15 min d'Apps Script ne tourne pas, GitHub fait partir les mails au meme rythme.
Memes regles que le script : plage horaire du Sheet, plafond du jour, repartition par creneaux de 15 min, interrupteur MFE_ENVOI_AUTO.
Aucun doublon possible : le plafond et le compteur du jour sont ceux du Sheet (le script d'envoi refuse de depasser)."""
import sys, os, math, datetime, json
from zoneinfo import ZoneInfo
sys.path.insert(0, "automation/scripts")
import sheet_bridge


def garder_chaine():
    """La chaine ne s'arrete jamais (meme hors plage, la nuit) : elle se relance seule chaque jour, sans planificateur GitHub."""
    open(os.environ.get("GITHUB_OUTPUT", "/dev/null"), "a").write("continuer=true\n")


def main():
    garder_chaine()
    now = datetime.datetime.now(ZoneInfo("Europe/Paris"))
    st = sheet_bridge.call({"action": "status"})
    reg = st.get("reglages", {}) or {}
    if str(reg.get("MFE_ENVOI_AUTO", "")).upper() != "TRUE" or str(reg.get("MFE_EMAIL_TEST", "")).strip():
        print("envoi secours : envoi automatique coupe ou mode test -> rien a faire"); return
    try:
        h0, h1 = [int(x) for x in str(reg.get("MFE_HEURES_ENVOI", "14-23")).split("-")]
    except Exception:
        h0, h1 = 14, 23
    if not (h0 <= now.hour < h1):
        print(f"envoi secours : hors plage ({now.hour}h)"); return
    cap = int(st.get("cap_jour_effectif") or reg.get("MFE_MAX_ENVOIS_JOUR") or 30)
    sent = int(st.get("envoyes_aujourdhui") or 0)
    slots = (h1 - h0) * 4
    slot = (now.hour - h0) * 4 + now.minute // 15 + 1
    allowed = math.ceil(cap * slot / slots)
    a_envoyer = min(6, allowed - sent, cap - sent)   # 6 par passage au maximum (rattrapage progressif)
    print(f"envoi secours : {sent} envoyes, {allowed} attendus a ce creneau, plafond {cap} -> {max(a_envoyer, 0)} a envoyer")
    while a_envoyer > 0:
        n = min(3, a_envoyer)
        res = sheet_bridge.call(payload={"action": "cmd", "cmd": "test_real", "slug": "", "n": n, "confirm": True})
        print(f"::notice title=Envoi de secours::{json.dumps(res, ensure_ascii=False)[:300]}")
        if not res.get("ok"):
            sys.exit(1)
        faits = int(res.get("envoyes") or 0)
        sent += faits
        a_envoyer -= n
        if faits == 0:
            break   # plus de ligne "Pret" envoyable


if __name__ == "__main__":
    main()
