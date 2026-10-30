#!/usr/bin/env python3
"""Récupère la liste de vos images AstroBin pour AstroPlan.

Lit la clé d'API dans /etc/astroplan/astrobin.conf (ou le fichier donné en
argument) :

    [astrobin]
    username = votre_nom_astrobin
    api_key = ...
    api_secret = ...

et écrit site/astrobin.json (titre, objets, vignettes, lien) à côté de la page.
La clé et le secret ne sont jamais copiés dans ce fichier.
À lancer par cron, par exemple toutes les heures.
"""
import configparser
import json
import os
import sys
import urllib.parse
import urllib.request

API = "https://www.astrobin.com/api/v1/image/"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "site", "astrobin.json")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "AstroPlan (astrobin_sync)",
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def image_entry(im):
    """Ne garde que ce qu'AstroPlan affiche."""
    subjects = im.get("subjects") or []
    if isinstance(subjects, str):
        subjects = [s.strip() for s in subjects.split(",") if s.strip()]
    key = im.get("hash") or im.get("id")
    page = im.get("url") if str(im.get("url", "")).startswith("http") else \
        f"https://www.astrobin.com/{key}/"
    return {
        "id": str(key),
        "title": im.get("title") or "",
        "subjects": [str(s) for s in subjects],
        "thumb": im.get("url_thumb") or im.get("url_gallery") or "",
        "image": im.get("url_regular") or im.get("url_hd") or "",
        "page": page,
        "date": (im.get("uploaded") or im.get("published") or "")[:10],
        "likes": im.get("likes") or 0,
    }


def main(conf_path="/etc/astroplan/astrobin.conf"):
    cfg = configparser.ConfigParser()
    if not cfg.read(conf_path) or "astrobin" not in cfg:
        sys.exit(f"Configuration introuvable : {conf_path}")
    c = cfg["astrobin"]
    params = {"user": c["username"], "api_key": c["api_key"],
              "api_secret": c["api_secret"], "format": "json", "limit": 50}
    url = API + "?" + urllib.parse.urlencode(params)
    images = []
    while url:
        data = fetch(url)
        images += [image_entry(im) for im in data.get("objects", [])]
        nxt = (data.get("meta") or {}).get("next")
        url = urllib.parse.urljoin("https://www.astrobin.com", nxt) if nxt else None
        if len(images) > 5000:
            break
    out = {"user": c["username"], "count": len(images), "images": images}
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    os.replace(tmp, OUT)
    print(f"{len(images)} image(s) écrites dans {os.path.normpath(OUT)}")


if __name__ == "__main__":
    main(*sys.argv[1:2])
