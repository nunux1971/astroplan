#!/usr/bin/env python3
"""Assemble site/index.html (et site/sw.js) à partir de src/."""
import hashlib
import os

here = os.path.dirname(os.path.abspath(__file__))
src = lambda *p: open(os.path.join(here, "src", *p), encoding="utf-8").read()
page = src("template.html").replace("/*CATALOG*/[]", src("catalog.json")).replace("/*SKY*/null", src("sky.json"))
head = (
    '<meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
    '<link rel="manifest" href="manifest.webmanifest" crossorigin="use-credentials">'
    '<meta name="theme-color" content="#0d1422">'
    '<meta name="mobile-web-app-capable" content="yes">'
    '<meta name="apple-mobile-web-app-capable" content="yes">'
    '<meta name="apple-mobile-web-app-title" content="AstroPlan">'
    '<link rel="icon" href="icons/icon-192.png">'
    '<link rel="apple-touch-icon" href="icons/apple-touch-icon.png">'
)
sw_reg = ('<script>if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost")) '
          'navigator.serviceWorker.register("sw.js").catch(() => {});</script>')
html = f'<!doctype html>\n<html lang="fr"><head>{head}</head><body>\n{page}\n{sw_reg}\n</body></html>\n'
site = os.path.join(here, "site")
os.makedirs(site, exist_ok=True)
with open(os.path.join(site, "index.html"), "w", encoding="utf-8") as f:
    f.write(html)
version = hashlib.sha1(html.encode("utf-8")).hexdigest()[:10]
with open(os.path.join(site, "sw.js"), "w", encoding="utf-8") as f:
    f.write(src("sw.js").replace("__VERSION__", version))
print(f"site/index.html et site/sw.js écrits (version {version})")
