#!/usr/bin/env python3
"""
diagnose_rss.py — Inspecte un flux RSS Ausha et affiche la richesse des champs
SANS appeler l'API Claude (donc gratuit). Sert à décider de la stratégie GEO.

Variable d'env requise : RSS_URL
"""
import os
import re
import html
import xml.etree.ElementTree as ET
import urllib.request

RSS_URL = os.environ["RSS_URL"]
NS = {"itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
      "content": "http://purl.org/rss/1.0/modules/content/"}


def strip_html(raw):
    if not raw:
        return ""
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = html.unescape(raw)
    return re.sub(r"\s+", " ", raw).strip()


req = urllib.request.Request(RSS_URL, headers={"User-Agent": "ListenlyDiag/1.0"})
with urllib.request.urlopen(req, timeout=30) as resp:
    xml_bytes = resp.read()

root = ET.fromstring(xml_bytes)
channel = root.find("channel")
show_title = (channel.findtext("title") or "").strip()
items = channel.findall("item")

print("=" * 60)
print(f"PODCAST : {show_title}")
print(f"NB EPISODES DANS LE FLUX : {len(items)}")
print("=" * 60)

# Analyse des 5 premiers épisodes
for i, item in enumerate(items[:5]):
    title = (item.findtext("title") or "").strip()
    desc_raw = item.findtext("description") or item.findtext("content:encoded", default="", namespaces=NS) or ""
    desc = strip_html(desc_raw)
    print(f"\n--- EPISODE {i+1} ---")
    print(f"TITRE ({len(title)} car) : {title}")
    print(f"DESCRIPTION ({len(desc)} car) :")
    print(f"  {desc[:600]}{'...' if len(desc) > 600 else ''}")

# Stats globales sur la richesse des descriptions
desc_lengths = []
for item in items:
    d = strip_html(item.findtext("description") or item.findtext("content:encoded", default="", namespaces=NS) or "")
    desc_lengths.append(len(d))

if desc_lengths:
    avg = sum(desc_lengths) // len(desc_lengths)
    print("\n" + "=" * 60)
    print(f"RICHESSE DES DESCRIPTIONS :")
    print(f"  Longueur moyenne : {avg} caractères")
    print(f"  Min : {min(desc_lengths)} / Max : {max(desc_lengths)}")
    if avg < 150:
        print("  VERDICT : descriptions PAUVRES -> s'appuyer surtout sur le titre")
    elif avg < 500:
        print("  VERDICT : descriptions MOYENNES -> titre + description suffisent")
    else:
        print("  VERDICT : descriptions RICHES -> excellent matériau GEO")
print("=" * 60)
