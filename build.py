#!/usr/bin/env python3
"""Assemble site/index.html à partir de src/template.html et src/catalog.json."""
import os

here = os.path.dirname(os.path.abspath(__file__))
tpl = open(os.path.join(here, "src", "template.html"), encoding="utf-8").read()
cat = open(os.path.join(here, "src", "catalog.json"), encoding="utf-8").read()
page = tpl.replace("/*CATALOG*/[]", cat)
html = ('<!doctype html>\n<html lang="fr"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
        '</head><body>\n' + page + '\n</body></html>\n')
os.makedirs(os.path.join(here, "site"), exist_ok=True)
open(os.path.join(here, "site", "index.html"), "w", encoding="utf-8").write(html)
print("site/index.html écrit")
