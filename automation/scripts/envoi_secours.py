#!/usr/bin/env python3
"""Envoi de secours (12/10/2026) : si le declencheur d'envoi de 15 min d'Apps Script ne tourne pas, GitHub fait partir les mails au meme rythme.
Memes regles que le script : plage horaire du Sheet, plafond du jour, repartition par creneaux de 15 min, interrupteur MFE_ENVOI_AUTO, reservoir MFE_STOCK_MIN (27/10/2026 : rien ne part tant que 30 prospects ne sont pas prets).
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
    g = st.get("stock_pret")
    seuil = int(reg.get("MFE_STOCK_MIN") or 30)
    if isinstance(g, dict):
        if seuil > 0 and not g.get("ouvert"):
            print(f"envoi secours : reservoir {g.get('stock')}/{seuil} -> aucun envoi tant que le stock n'est pas pret"); return
    elif seuil > 0:   # script pas encore a jour : on compte nous-memes (Pret + fiche N1)
        stock = sum(1 for p in st.get("prospects", []) if p.get("statut") == "Pret" and "/podcast-btb/" in str(p.get("fiche_url", "")))
        if stock < seuil:
            print(f"envoi secours : reservoir {stock}/{seuil} -> aucun envoi"); return
    # 27/10/2026 (rafales de 6 mails a 20h18 et 20h48) : meme calendrier que le script Apps Script. Le jour d'envoi commence a h0 ;
    # le calendrier part du creneau d'OUVERTURE du reservoir et, si l'ouverture est tardive (apres MFE_NUIT_SI_OUVERT_APRES h),
    # court jusqu'a MFE_NUIT_JUSQU_A h du matin. Un seul mail par passage au maximum : jamais de rattrapage en rafale.
    try:
        nuit = int(reg.get("MFE_NUIT_JUSQU_A") if str(reg.get("MFE_NUIT_JUSQU_A", "")).strip() != "" else 6)
        apres = int(reg.get("MFE_NUIT_SI_OUVERT_APRES") or 18)
    except Exception:
        nuit, apres = 6, 18
    slot_now = ((now.hour - h0 + 24) % 24) * 4 + now.minute // 15
    normal = (h1 - h0) * 4
    night = (24 - h0 + nuit) * 4 if nuit > 0 else normal
    ouverture = int(g.get("ouverture") or 0) if isinstance(g, dict) else 0
    tard = nuit > 0 and ouverture >= (apres - h0) * 4
    fin = night if tard else normal
    if slot_now >= fin:
        print(f"envoi secours : hors plage ({now.hour}h)"); return
    cap = int(st.get("cap_jour_effectif") or reg.get("MFE_MAX_ENVOIS_JOUR") or 30)
    sent = int(st.get("envoyes_aujourdhui") or 0)
    slots = max(1, fin - ouverture)
    slot = max(1, slot_now - ouverture + 1)
    allowed = math.ceil(cap * slot / slots)
    a_envoyer = min(1, allowed - sent, cap - sent)   # 1 par passage au maximum : pas de rafale de rattrapage
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
