#!/usr/bin/env python3
"""Envoi de secours (12/10/2026) : si le declencheur d'envoi de 15 min d'Apps Script ne tourne pas, GitHub fait partir les mails au meme rythme.
Memes regles que le script : plage horaire du Sheet, plafond du jour, repartition par creneaux de 15 min, interrupteur MFE_ENVOI_AUTO.
Aucun doublon possible : le plafond et le compteur du jour sont ceux du Sheet (le script d'envoi refuse de depasser)."""
import sys, math, datetime, json
from zoneinfo import ZoneInfo
sys.path.insert(0, "automation/scripts")
import sheet_bridge


def main():
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
    n = min(3, allowed - sent, cap - sent)
    print(f"envoi secours : {sent} envoyes, {allowed} attendus a ce creneau, plafond {cap} -> {max(n, 0)} a envoyer")
    if n <= 0:
        return
    res = sheet_bridge.call(payload={"action": "cmd", "cmd": "test_real", "slug": "", "n": n, "confirm": True})
    print(f"::notice title=Envoi de secours::{json.dumps(res, ensure_ascii=False)[:300]}")
    if not res.get("ok"):
        sys.exit(1)


if __name__ == "__main__":
    main()
