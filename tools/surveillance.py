#!/usr/bin/env python3
"""Surveillance des deux serveurs : sites joignables, certificats, disques, services et
sauvegardes. Prévient sur le téléphone (ntfy) quand un problème apparaît, puis une fois par
jour tant qu'il dure, et quand il est réglé.

Chaque serveur surveille aussi le site de l'autre : si l'un tombe, l'autre prévient.

Réglages : /etc/surveillance.json (créé par installer_surveillance.sh). Les réglages ntfy
viennent de /etc/astroplan/alerts.json s'il existe, sinon des clés server/topic/token.
    surveillance.py            vérifie et prévient
    surveillance.py --dry-run  vérifie et affiche, sans rien envoyer
    surveillance.py --test     envoie une notification d'essai
"""
import json
import os
import shutil
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

CONF = os.environ.get("SURVEILLANCE_CONF", "/etc/surveillance.json")
ETAT = os.environ.get("SURVEILLANCE_ETAT", "/var/lib/surveillance/etat.json")
ARGS = set(sys.argv[1:])
RAPPEL_H = 24
ECHECS_AVANT_ALERTE = 2          # un site doit échouer deux fois de suite (évite les fausses alertes)


def charger_conf():
    with open(CONF, encoding="utf-8") as f:
        conf = json.load(f)
    src = conf.get("ntfy_depuis", "/etc/astroplan/alerts.json")
    if not conf.get("topic") and os.path.exists(src):
        with open(src, encoding="utf-8") as f:
            a = json.load(f)
        conf.setdefault("server", a.get("server", "https://ntfy.sh"))
        conf["topic"], conf["token"] = a.get("topic"), a.get("token", "")
    conf.setdefault("server", "https://ntfy.sh")
    conf.setdefault("nom", socket.gethostname())
    return conf


# ------------------------------------------------------------------ vérifications
class SansRedirection(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def verifier_url(u):
    url, codes = u["url"], u.get("codes", [200])
    req = urllib.request.Request(url, headers={"User-Agent": "surveillance"}, method="GET")
    try:
        with urllib.request.build_opener(SansRedirection).open(req, timeout=20) as r:
            code = r.status
    except urllib.error.HTTPError as e:
        code = e.code
    except (urllib.error.URLError, OSError) as e:
        return f"{url} injoignable ({getattr(e, 'reason', e)})"
    return None if code in codes else f"{url} répond {code}"


def jours_certificat(hote):
    ctx = ssl.create_default_context()
    with socket.create_connection((hote, 443), timeout=15) as s:
        with ctx.wrap_socket(s, server_hostname=hote) as t:
            fin = t.getpeercert()["notAfter"]
    return (datetime.strptime(fin, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
            - datetime.now(timezone.utc)).total_seconds() / 86400


def systemd(unite):
    if not shutil.which("systemctl"):
        return {"ActiveState": "inconnu", "Result": "pas de systemd"}
    out = subprocess.run(["systemctl", "show", unite, "-p", "ActiveState", "-p", "Result",
                          "-p", "ExecMainExitTimestamp", "-p", "LoadState"],
                         capture_output=True, text=True, timeout=20).stdout
    return dict(l.split("=", 1) for l in out.strip().splitlines() if "=" in l)


def date_systemd(v):
    # « Tue 2026-11-03 04:00:12 CET » : on lit la date et l'heure, le fuseau est celui du serveur
    try:
        return datetime.strptime(" ".join(v.split()[1:3]), "%Y-%m-%d %H:%M:%S").timestamp()
    except (ValueError, IndexError):
        return None


def problemes(conf):
    p = {}
    for u in conf.get("urls", []):
        e = verifier_url(u)
        if e:
            p["url:" + u["url"]] = e
    for h in conf.get("certificats", []):
        try:
            j = jours_certificat(h)
            if j < conf.get("jours_certificat", 14):
                p["cert:" + h] = f"certificat de {h} : expire dans {j:.0f} jour(s) (le renouvellement automatique a-t-il échoué ?)"
        except (OSError, ssl.SSLError, ValueError, KeyError) as e:
            p["cert:" + h] = f"certificat de {h} illisible ({e})"
    for d in conf.get("disques", ["/"]):
        if not os.path.exists(d):
            continue
        u = shutil.disk_usage(d)
        pc = 100 * u.used / u.total
        if pc >= conf.get("seuil_disque", 90):
            p["disque:" + d] = f"disque {d} plein à {pc:.0f} % ({u.free / 1e9:.1f} Go libres)"
    for s in conf.get("services", []):
        i = systemd(s)
        if i.get("LoadState") == "not-found":
            p["service:" + s] = f"service {s} introuvable"
        elif i.get("ActiveState") not in ("active", "reloading"):
            p["service:" + s] = f"service {s} arrêté ({i.get('ActiveState')}, {i.get('Result')})"
    for s in conf.get("sauvegardes", []):            # services lancés par un minuteur
        unite, max_h = (s["service"], s.get("max_heures", 30)) if isinstance(s, dict) else (s, 30)
        i = systemd(unite)
        t = date_systemd(i.get("ExecMainExitTimestamp", ""))
        if i.get("Result") not in (None, "success"):
            p["sauve:" + unite] = f"sauvegarde {unite} en échec ({i.get('Result')}) : journalctl -u {unite}"
        elif t is None or time.time() - t > max_h * 3600:
            age = f"{(time.time() - t) / 3600:.0f} h" if t else "jamais"
            p["sauve:" + unite] = f"sauvegarde {unite} : dernière il y a {age}"
    return p


# ------------------------------------------------------------------ notifications
def envoyer(conf, titre, texte, tags, priorite=4):
    if not conf.get("topic"):
        print("pas de sujet ntfy : rien d'envoyé", file=sys.stderr)
        return
    msg = {"topic": conf["topic"], "title": titre, "message": texte, "tags": tags, "priority": priorite}
    hdr = {"Content-Type": "application/json", "User-Agent": "surveillance"}
    if conf.get("token"):
        hdr["Authorization"] = f"Bearer {conf['token']}"
    req = urllib.request.Request(conf["server"].rstrip("/") + "/", data=json.dumps(msg).encode("utf-8"),
                                 headers=hdr, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        r.read()


def main():
    conf = charger_conf()
    if "--test" in ARGS:
        envoyer(conf, f"{conf['nom']} : surveillance active", "Notification d'essai : tout fonctionne.", ["white_check_mark"], 3)
        print("notification d'essai envoyée")
        return
    trouve = problemes(conf)
    try:
        with open(ETAT, encoding="utf-8") as f:
            etat = json.load(f)
    except (OSError, ValueError):
        etat = {}
    maintenant = time.time()
    nouveaux, regles = [], []
    for k, texte in trouve.items():
        e = etat.get(k, {"echecs": 0, "signale": 0})
        e["echecs"] += 1
        e["texte"] = texte
        seuil = ECHECS_AVANT_ALERTE if k.startswith("url:") else 1
        if e["echecs"] >= seuil and (not e["signale"] or maintenant - e["signale"] > RAPPEL_H * 3600):
            nouveaux.append(texte)
            e["signale"] = maintenant
        etat[k] = e
    for k in list(etat):
        if k not in trouve:
            if etat[k].get("signale"):
                regles.append(etat[k]["texte"])
            del etat[k]
    if "--dry-run" in ARGS:
        print("problèmes :", json.dumps(trouve, ensure_ascii=False, indent=1) if trouve else "aucun")
        return
    if nouveaux:
        envoyer(conf, f"{conf['nom']} : {len(nouveaux)} problème(s)", "\n".join("• " + t for t in nouveaux), ["warning"], 4)
    if regles:
        envoyer(conf, f"{conf['nom']} : réglé", "\n".join("✓ " + t for t in regles), ["white_check_mark"], 3)
    os.makedirs(os.path.dirname(ETAT), exist_ok=True)
    tmp = ETAT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(etat, f, ensure_ascii=False)
    os.replace(tmp, ETAT)


if __name__ == "__main__":
    main()
