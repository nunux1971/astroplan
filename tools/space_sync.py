#!/usr/bin/env python3
"""Met à jour site/space.json pour AstroPlan : orbites de l'ISS et de Tiangong (TLE),
comètes (Minor Planet Center), nombre de taches solaires et indice Kp prévu.

Usage :  python3 tools/space_sync.py [--debug]
Cron   :  23 */6 * * * root python3 /var/www/astroplan/tools/space_sync.py

Chaque source est indépendante : si l'une ne répond pas, la valeur précédente du fichier est gardée.
Aucune clé d'API n'est nécessaire.
"""
import datetime as dt
import json
import math
import os
import sys
import tempfile
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "site", "space.json")
DEBUG = "--debug" in sys.argv
UA = {"User-Agent": "AstroPlan/1.0 (planning page for amateur astronomy)"}

TLE_URL = "https://celestrak.org/NORAD/elements/gp.php?CATNR={}&FORMAT=tle"
SATS = {"ISS": 25544, "CSS": 48274}
COMETS_URL = "https://www.minorplanetcenter.net/iau/MPCORB/CometEls.txt"
SSN_URL = "https://services.swpc.noaa.gov/json/solar-cycle/swpc_observed_ssn.json"
SSN_FALLBACK = "https://www.sidc.be/SILSO/DATA/EISN/EISN_current.txt"
KP_URL = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json"


def log(*a):
    if DEBUG:
        print(*a, file=sys.stderr)


def get(url, timeout=40):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read().decode("utf-8", "replace")
    log(f"{url} : {len(data)} caractères")
    return data


def jd_from_date(y, m, d):
    """Jour julien d'une date (jour fractionnaire), calendrier grégorien."""
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    return math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1)) + d + b - 1524.5


def fetch_tle():
    out = {}
    for key, num in SATS.items():
        try:
            lines = [l.rstrip() for l in get(TLE_URL.format(num)).splitlines() if l.strip()]
            l1 = next(l for l in lines if l.startswith("1 "))
            l2 = next(l for l in lines if l.startswith("2 "))
            out[key] = [l1, l2]
        except Exception as e:  # noqa: BLE001
            print(f"TLE {key} : échec ({e})", file=sys.stderr)
    return out


def parse_comet(line, now_jd):
    """Une ligne de CometEls.txt (format à colonnes fixes du MPC) -> dict, ou None."""
    if len(line) < 100:
        return None
    # champs séparés par des blancs entre les colonnes 15 et 101 : plus robuste qu'un découpage exact
    t = line[14:101].split()
    if len(t) < 9:
        return None
    try:
        y, m, d = int(t[0]), int(t[1]), float(t[2])
        q, e, w, node, inc = (float(x) for x in t[3:8])
        rest = t[8:]
        if rest and len(rest[0]) == 8 and rest[0].isdigit():   # époque des éléments (AAAAMMJJ)
            rest = rest[1:]
        if not rest:
            return None
        H, G = float(rest[0]), float(rest[1]) if len(rest) > 1 else 4.0
    except ValueError:
        return None
    T = jd_from_date(y, m, d)
    name = line[101:158].strip()
    # comètes susceptibles d'être assez brillantes : périhélie à moins de deux ans,
    # et éclat optimiste au périhélie (à 1 UA de la Terre au mieux) sous la magnitude 15
    if abs(T - now_jd) > 730 or q > 6:
        return None
    if H + 2.5 * G * math.log10(max(q, 0.05)) > 15:
        return None
    return {"name": name, "q": q, "e": e, "w": w, "node": node, "i": inc, "T": round(T, 5), "H": H, "G": G}


def fetch_comets():
    now_jd = dt.datetime.now(dt.timezone.utc).timestamp() / 86400 + 2440587.5
    out = [c for c in (parse_comet(l, now_jd) for l in get(COMETS_URL, 90).splitlines()) if c]
    log(f"comètes gardées : {len(out)}")
    return out


def fetch_ssn():
    try:
        rows = json.loads(get(SSN_URL))
        rows = [r for r in rows if r.get("swpc_ssn") is not None]
        last = max(rows, key=lambda r: r.get("Obsdate", ""))
        return {"date": str(last["Obsdate"])[:10], "value": int(round(float(last["swpc_ssn"]))), "source": "SWPC"}
    except Exception as e:  # noqa: BLE001
        log(f"SWPC taches : {e}, essai SILSO")
    # SILSO : année mois jour date_décimale EISN écart nb_stations ...
    lines = [l.split() for l in get(SSN_FALLBACK).splitlines() if l.strip() and l[0].isdigit()]
    y, m, d, _, v = lines[-1][:5]
    return {"date": f"{int(y):04d}-{int(m):02d}-{int(d):02d}", "value": int(round(float(v))), "source": "SILSO"}


def fetch_kp():
    data = json.loads(get(KP_URL))
    out = []
    if data and isinstance(data[0], list):          # [["time_tag","kp","observed","noaa_scale"], [...], ...]
        head = data[0]
        it, ik = head.index("time_tag"), head.index("kp")
        for r in data[1:]:
            out.append([str(r[it]).replace("T", " ")[:16], float(r[ik])])
    else:                                            # [{"time_tag": ..., "kp": ...}, ...]
        for r in data:
            out.append([str(r.get("time_tag", "")).replace("T", " ")[:16], float(r.get("kp", r.get("Kp", 0)))])
    return out


def main():
    try:
        with open(OUT, encoding="utf-8") as f:
            space = json.load(f)
    except Exception:  # noqa: BLE001
        space = {}
    ok = []
    tle = fetch_tle()
    if tle:
        space["tle"] = {**space.get("tle", {}), **tle}
        ok.append(f"TLE {', '.join(tle)}")
    for key, fn in (("comets", fetch_comets), ("ssn", fetch_ssn), ("kp", fetch_kp)):
        try:
            space[key] = fn()
            ok.append(key)
        except Exception as e:  # noqa: BLE001
            print(f"{key} : échec ({e}), ancienne valeur gardée", file=sys.stderr)
    space["updated"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(OUT), prefix=".space-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(space, f, ensure_ascii=False, separators=(",", ":"))
    os.chmod(tmp, 0o644)
    os.replace(tmp, OUT)
    print(f"space.json écrit : {', '.join(ok) or 'rien de neuf'}"
          f" ({len(space.get('comets', []))} comètes, taches {space.get('ssn', {}).get('value', '?')})")


if __name__ == "__main__":
    main()
