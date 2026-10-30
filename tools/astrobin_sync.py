#!/usr/bin/env python3
"""Récupère la liste de vos images AstroBin publiques pour AstroPlan.

Utilise l'interface publique v2 d'AstroBin (aucune clé d'API nécessaire).

    python3 tools/astrobin_sync.py VOTRE_NOM_ASTROBIN
    python3 tools/astrobin_sync.py VOTRE_NOM_ASTROBIN --debug

Sans nom en argument, le nom est lu dans /etc/astroplan/astrobin.conf :

    [astrobin]
    username = votre_nom_astrobin

Écrit site/astrobin.json (titre, objets, vignettes, lien) à côté de la page.
À lancer par cron, par exemple toutes les heures.
"""
import configparser
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

BASE = "https://www.astrobin.com/api/v2"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "site", "astrobin.json")
DEBUG = "--debug" in sys.argv


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (AstroPlan astrobin_sync)",
                                               "Accept": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception:  # noqa: BLE001  (réseau ou limite de débit : on réessaie)
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))


def user_id(username):
    data = fetch(f"{BASE}/common/users/?username={urllib.parse.quote(username)}")
    users = data if isinstance(data, list) else data.get("results", [])
    for u in users:
        if str(u.get("username", "")).lower() == username.lower() or \
                str(u.get("display_name", "")).lower() == username.lower():
            return u["id"]
    if users:
        return users[0]["id"]
    sys.exit(f"Utilisateur AstroBin introuvable : {username}")


def objects_of(im):
    """Objets reconnus par la résolution astrométrique, plus le sujet."""
    names = []
    sol = im.get("solution") or {}
    for key, val in sol.items():
        if "object" in key.lower() and isinstance(val, (str, list)):
            if isinstance(val, str):
                names += [s.strip() for s in re.split(r"[,;\n]", val) if s.strip()]
            else:
                names += [str(s).strip() for s in val if str(s).strip()]
    for key in ("solarSystemMainSubject", "constellation"):
        if isinstance(im.get(key), str) and im[key].strip():
            names.append(im[key].strip())
    seen, out = set(), []
    for n in names:
        if n.lower() not in seen and not n.isdigit():
            seen.add(n.lower())
            out.append(n)
    return out


def thumb_of(im, prefer=("story", "regular", "gallery")):
    th = {t.get("alias"): t.get("url") for t in (im.get("thumbnails") or []) if isinstance(t, dict)}
    for alias in prefer:
        if th.get(alias):
            return th[alias]
    return next(iter(th.values()), "")


def image_entry(im):
    key = im.get("hash") or im.get("pk")
    return {
        "id": str(key),
        "title": im.get("title") or "",
        "subjects": objects_of(im),
        "thumb": thumb_of(im),
        "image": thumb_of(im, ("regular", "story", "gallery")),
        "page": f"https://www.astrobin.com/{key}/",
        "date": (im.get("published") or im.get("uploaded") or "")[:10],
        "likes": im.get("likeCount") or 0,
    }


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    username = args[0] if args else None
    if not username:
        cfg = configparser.ConfigParser()
        cfg.read("/etc/astroplan/astrobin.conf")
        username = cfg.get("astrobin", "username", fallback=None)
    if not username:
        sys.exit("Indiquez votre nom AstroBin : astrobin_sync.py VOTRE_NOM")
    uid = user_id(username)
    url = f"{BASE}/images/image/?user={uid}"
    images = []
    while url:
        data = fetch(url)
        results = data.get("results", []) if isinstance(data, dict) else data
        if DEBUG and results and not images:
            sol = results[0].get("solution") or {}
            print("champs de la résolution :", sorted(sol))
        images += [image_entry(im) for im in results]
        url = data.get("next") if isinstance(data, dict) else None
        if url:
            time.sleep(0.5)          # rester poli avec le serveur d'AstroBin
        if len(images) > 5000:
            break
    out = {"user": username, "count": len(images), "images": images}
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    os.replace(tmp, OUT)
    with_objects = sum(1 for i in images if i["subjects"])
    print(f"{len(images)} image(s) écrites dans {os.path.normpath(OUT)} "
          f"({with_objects} avec des objets identifiés)")
    if DEBUG:
        for i in images[:5]:
            print(" ", i["title"], "→", ", ".join(i["subjects"][:8]) or "(aucun objet)")


if __name__ == "__main__":
    main()
