#!/usr/bin/env python3
"""Alertes d'AstroPlan sur le téléphone (application ntfy) :
- « nuit claire » quand la nuit qui vient s'annonce dégagée ;
- transit de l'ISS ou de Tiangong devant le Soleil ou la Lune à moins de 40 km, dans les 48 h
  (orbites lues dans site/space.json, paquet Debian python3-sgp4 nécessaire) ;
- orage géomagnétique fort (indice Kp prévu ≥ 7) : aurore possible.

Chaque lancement lit la prévision Open-Meteo pour le lieu, calcule la nuit noire (Soleil à plus
de 18° sous l'horizon) et la Lune, compte les heures sans nuages et, si la nuit est assez claire,
envoie une notification ntfy. Une seule alerte par nuit (sauf --force).

Usage :
  python3 tools/clear_night_alert.py --test     envoie une notification d'essai
  python3 tools/clear_night_alert.py --dry-run  affiche le message sans l'envoyer
  python3 tools/clear_night_alert.py            vérifie la nuit et prévient si elle est claire
Cron (7 h 41 et 16 h 41 ; la nuit claire n'est jugée que l'après-midi) :
  41 7,16 * * * root python3 /var/www/astroplan/tools/clear_night_alert.py

Réglages : /etc/astroplan/alerts.json (voir DEFAULTS ; seul « topic » est indispensable).
"""
import datetime as dt
import json
import math
import os
import sys
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

CONF = os.environ.get("ASTROPLAN_ALERTS", "/etc/astroplan/alerts.json")
STATE = os.environ.get("ASTROPLAN_ALERTS_STATE", "/var/lib/astroplan/clear_night_state.json")
DEFAULTS = {
    "topic": "",                       # nom du sujet ntfy : long et difficile à deviner
    "server": "https://ntfy.sh",
    "token": "",                       # jeton d'accès si votre serveur ntfy en demande un
    "lat": 43.4558, "lon": 5.0150, "site": "Saint-Mitre-les-Remparts", "tz": "Europe/Paris",
    "max_cloud": 25,                   # % de nuages au-delà duquel une heure ne compte pas
    "min_hours": 3,                    # heures claires de nuit noire nécessaires
    "max_gust": 45,                    # km/h : au-delà, l'alerte le signale
    "page": "https://astroplan.ericcioli.fr",
}
ARGS = set(sys.argv[1:])
SPACE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site", "space.json")
D2R, R2D = math.pi / 180, 180 / math.pi


# ------------------------------------------------------------------ Soleil et Lune (même modèle que la page)
def norm360(x):
    return x % 360


def jd_of(ts):
    return ts / 86400 + 2440587.5


def gmst(jd):
    T = (jd - 2451545) / 36525
    return norm360(280.46061837 + 360.98564736629 * (jd - 2451545) + 0.000387933 * T * T)


def altaz(ra, dec, jd, lat, lon):
    H = (gmst(jd) + lon - ra) * D2R
    d, f = dec * D2R, lat * D2R
    sa = math.sin(f) * math.sin(d) + math.cos(f) * math.cos(d) * math.cos(H)
    alt = math.asin(max(-1, min(1, sa)))
    az = math.atan2(-math.sin(H) * math.cos(d), math.cos(f) * math.sin(d) - math.sin(f) * math.cos(d) * math.cos(H))
    return alt * R2D, norm360(az * R2D)


def sun_pos(jd):
    n = jd - 2451545
    L = norm360(280.460 + 0.9856474 * n)
    g = norm360(357.528 + 0.9856003 * n) * D2R
    lam = (L + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g)) * D2R
    eps = (23.439 - 0.0000004 * n) * D2R
    return (norm360(math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam)) * R2D),
            math.asin(math.sin(eps) * math.sin(lam)) * R2D, lam * R2D)


def moon_pos(jd):   # méthode de P. Schlyter, perturbations principales
    d = jd - 2451543.5
    N = norm360(125.1228 - 0.0529538083 * d); i = 5.1454; w = norm360(318.0634 + 0.1643573223 * d)
    a = 60.2666; e = 0.0549; M = norm360(115.3654 + 13.0649929509 * d)
    E = M + R2D * e * math.sin(M * D2R) * (1 + e * math.cos(M * D2R))
    for _ in range(5):
        E = E - (E - R2D * e * math.sin(E * D2R) - M) / (1 - e * math.cos(E * D2R))
    xv = a * (math.cos(E * D2R) - e); yv = a * math.sqrt(1 - e * e) * math.sin(E * D2R)
    v = math.atan2(yv, xv) * R2D; r = math.hypot(xv, yv)
    vw, Nr, ir = (v + w) * D2R, N * D2R, i * D2R
    xh = r * (math.cos(Nr) * math.cos(vw) - math.sin(Nr) * math.sin(vw) * math.cos(ir))
    yh = r * (math.sin(Nr) * math.cos(vw) + math.cos(Nr) * math.sin(vw) * math.cos(ir))
    zh = r * math.sin(vw) * math.sin(ir)
    lon = math.atan2(yh, xh) * R2D; lat = math.atan2(zh, math.hypot(xh, yh)) * R2D
    Ms = norm360(356.0470 + 0.9856002585 * d); ws = 282.9404 + 4.70935e-5 * d
    Ls = Ms + ws; Lm = N + w + M; D = Lm - Ls; F = Lm - N
    s = lambda x: math.sin(x * D2R)
    lon += (-1.274 * s(M - 2 * D) + 0.658 * s(2 * D) - 0.186 * s(Ms) - 0.059 * s(2 * M - 2 * D) - 0.057 * s(M - 2 * D + Ms)
            + 0.053 * s(M + 2 * D) + 0.046 * s(2 * D - Ms) + 0.041 * s(M - Ms) - 0.035 * s(D) - 0.031 * s(M + Ms)
            - 0.015 * s(2 * F - 2 * D) + 0.011 * s(M - 4 * D))
    lat += -0.173 * s(F - 2 * D) - 0.055 * s(M - F - 2 * D) - 0.046 * s(M + F - 2 * D) + 0.033 * s(F + 2 * D) + 0.017 * s(2 * M + F)
    r += -0.58 * math.cos((M - 2 * D) * D2R) - 0.46 * math.cos(2 * D * D2R)
    ecl = (23.4393 - 3.563e-7 * d) * D2R; lo, la = lon * D2R, lat * D2R
    xe = math.cos(lo) * math.cos(la)
    ye = math.cos(ecl) * math.sin(lo) * math.cos(la) - math.sin(ecl) * math.sin(la)
    ze = math.sin(ecl) * math.sin(lo) * math.cos(la) + math.cos(ecl) * math.sin(la)
    return norm360(math.atan2(ye, xe) * R2D), math.atan2(ze, math.hypot(xe, ye)) * R2D, norm360(lon), lat, r


def moon_state(jd, lat0, lon0):
    ra, dec, mlon, mlat, r = moon_pos(jd)
    alt, _ = altaz(ra, dec, jd, lat0, lon0)
    alt -= R2D * math.asin(math.cos(alt * D2R) / r)            # parallaxe
    slon = sun_pos(jd)[2]
    elong = math.acos(math.cos(mlat * D2R) * math.cos((mlon - slon) * D2R)) * R2D
    return alt, (1 - math.cos(elong * D2R)) / 2, norm360(mlon - slon) < 180


# ------------------------------------------------------------------ la nuit
def night(conf, day):
    """Pas de 5 min de midi (jour donné) à midi le lendemain : hauteur du Soleil et de la Lune."""
    tz = ZoneInfo(conf["tz"])
    t0 = dt.datetime.combine(day, dt.time(12), tz).timestamp()
    steps = []
    for k in range(24 * 12 + 1):
        t = t0 + k * 300; jd = jd_of(t)
        sra, sdec, _ = sun_pos(jd)
        salt, _ = altaz(sra, sdec, jd, conf["lat"], conf["lon"])
        malt, illum, waxing = moon_state(jd, conf["lat"], conf["lon"])
        steps.append((t, salt, malt, illum, waxing))
    def cross(lim, down):
        for a, b in zip(steps, steps[1:]):
            if (a[1] > lim >= b[1]) if down else (a[1] <= lim < b[1]):
                return b[0]
        return None
    dark0, dark1, lim = cross(-18, True), cross(-18, False), -18
    if dark0 is None:                       # pas de nuit astronomique : nuit nautique
        dark0, dark1, lim = cross(-12, True), cross(-12, False), -12
    rise = next((b[0] for a, b in zip(steps, steps[1:]) if a[2] <= 0 < b[2]), None)
    sett = next((b[0] for a, b in zip(steps, steps[1:]) if a[2] > 0 >= b[2]), None)
    mid = steps[len(steps) // 2]
    return {"steps": steps, "dark0": dark0, "dark1": dark1, "lim": lim, "moon_rise": rise, "moon_set": sett,
            "illum": mid[3], "waxing": mid[4]}


def forecast(conf):
    q = urllib.parse.urlencode({
        "latitude": f"{conf['lat']:.4f}", "longitude": f"{conf['lon']:.4f}", "timeformat": "unixtime", "timezone": "auto",
        "forecast_days": 3,
        "hourly": "cloud_cover,cloud_cover_low,cloud_cover_mid,cloud_cover_high,temperature_2m,dew_point_2m,wind_gusts_10m"})
    req = urllib.request.Request(f"https://api.open-meteo.com/v1/forecast?{q}", headers={"User-Agent": "AstroPlan"})
    with urllib.request.urlopen(req, timeout=40) as r:
        h = json.load(r)["hourly"]
    return {t: {k: h[k][i] for k in h if k != "time"} for i, t in enumerate(h["time"])}


def assess(conf, n, wx):
    """Heures claires de nuit noire, meilleur créneau continu, buée, vent, Lune."""
    if not n["dark0"] or not n["dark1"]:
        return None
    hours = []
    t = math.ceil(n["dark0"] / 3600) * 3600
    while t < n["dark1"]:
        w = wx.get(int(t))
        if w and w.get("cloud_cover") is not None:
            hours.append((t, w))
        t += 3600
    if not hours:
        return None
    clear = [h for h in hours if h[1]["cloud_cover"] <= conf["max_cloud"]]
    best, cur = [], []
    for h in hours:                          # plus long créneau d'heures claires consécutives
        cur = cur + [h] if h[1]["cloud_cover"] <= conf["max_cloud"] else []
        if len(cur) > len(best):
            best = cur
    dew = next((t for t, w in hours if w["temperature_2m"] - w["dew_point_2m"] < 2.5), None)
    gust = max((w.get("wind_gusts_10m") or 0) for _, w in hours)
    moon_up = sum(1 for s in n["steps"] if best and best[0][0] <= s[0] <= best[-1][0] + 3600 and s[2] > 0) / 12
    return {"clear_h": len(clear), "best": best, "cloud": sum(w["cloud_cover"] for _, w in best) / len(best) if best else 100,
            "dew": dew, "gust": gust, "moon_up": moon_up, "n_hours": len(hours)}


def hm(ts, tz):
    return dt.datetime.fromtimestamp(ts, tz).strftime("%H:%M")


def message(conf, day, n, a, nxt):
    tz = ZoneInfo(conf["tz"])
    b0, b1 = max(a["best"][0][0], n["dark0"]), min(a["best"][-1][0] + 3600, n["dark1"])
    p = round(n["illum"] * 100)
    moon = "nouvelle Lune" if p < 3 else f"Lune {p} % {'croissante' if n['waxing'] else 'décroissante'}"
    if p >= 3:
        if a["moon_up"] < 0.25:
            moon += ", absente du créneau"
        else:
            bits = []
            if n["moon_rise"]:
                bits.append(f"lever {hm(n['moon_rise'], tz)}")
            if n["moon_set"]:
                bits.append(f"coucher {hm(n['moon_set'], tz)}")
            moon += f", levée {a['moon_up']:.0f} h pendant le créneau" + (f" ({', '.join(bits)})" if bits else "")
    lines = [f"Ciel dégagé de {hm(b0, tz)} à {hm(b1, tz)} ({(b1 - b0) / 3600:.0f} h, {a['cloud']:.0f} % de nuages)",
             f"Nuit noire {hm(n['dark0'], tz)} – {hm(n['dark1'], tz)}" + ("" if n["lim"] == -18 else " (nuit nautique)"),
             moon[0].upper() + moon[1:],
             f"Buée probable dès {hm(a['dew'], tz)} : résistances chauffantes" if a["dew"] else "Pas de buée prévue",
             f"Rafales jusqu'à {a['gust']:.0f} km/h" + (" : attention au vent" if a["gust"] >= conf["max_gust"] else "")]
    if nxt:
        lines.append(f"Demain soir aussi : {nxt['clear_h']} h claires prévues")
    title = f"Nuit claire ce soir à {conf['site']}" if day == dt.datetime.now(tz).date() else f"Nuit claire le {day.strftime('%d/%m')} à {conf['site']}"
    return title, "\n".join(lines)


def send(conf, title, body, tags=("star", "crescent_moon"), priority=3):
    # publication en JSON : titre et texte accentués passent sans encodage d'en-têtes
    msg = {"topic": conf["topic"], "title": title, "message": body, "tags": list(tags), "priority": priority, "click": conf["page"]}
    hdr = {"Content-Type": "application/json", "User-Agent": "AstroPlan"}
    if conf.get("token"):
        hdr["Authorization"] = f"Bearer {conf['token']}"
    req = urllib.request.Request(conf["server"].rstrip("/") + "/", data=json.dumps(msg).encode("utf-8"), headers=hdr, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        r.read()


# ------------------------------------------------------------------ transits de l'ISS et de Tiangong
SATS = {"ISS": "l'ISS", "CSS": "Tiangong"}


def observer_ecf(lat, lon, h=0.05):     # WGS72, comme SGP4
    a, f = 6378.135, 1 / 298.26
    e2 = f * (2 - f); la, lo = lat * D2R, lon * D2R
    N = a / math.sqrt(1 - e2 * math.sin(la) ** 2)
    return ((N + h) * math.cos(la) * math.cos(lo), (N + h) * math.cos(la) * math.sin(lo), (N * (1 - e2) + h) * math.sin(la))


def sat_look(sat, ts, conf, obs):
    """Hauteur, azimut (°) et distance (km) du satellite vus du lieu."""
    jd = jd_of(ts); jw = math.floor(jd - 0.5) + 0.5
    err, r, _ = sat.sgp4(jw, jd - jw)
    if err:
        return None
    g = gmst(jd) * D2R                                    # TEME -> repère terrestre
    x = r[0] * math.cos(g) + r[1] * math.sin(g); y = -r[0] * math.sin(g) + r[1] * math.cos(g); z = r[2]
    dx, dy, dz = x - obs[0], y - obs[1], z - obs[2]
    la, lo = conf["lat"] * D2R, conf["lon"] * D2R
    south = math.sin(la) * math.cos(lo) * dx + math.sin(la) * math.sin(lo) * dy - math.cos(la) * dz
    east = -math.sin(lo) * dx + math.cos(lo) * dy
    up = math.cos(la) * math.cos(lo) * dx + math.cos(la) * math.sin(lo) * dy + math.sin(la) * dz
    rng = math.sqrt(dx * dx + dy * dy + dz * dz)
    return math.asin(up / rng) * R2D, norm360((math.atan2(-east, south) + math.pi) * R2D), rng


def body_look(key, ts, conf):
    """Soleil ou Lune : hauteur, azimut, rayon apparent (°)."""
    jd = jd_of(ts)
    if key == "sun":
        ra, dec, _ = sun_pos(jd)
        alt, az = altaz(ra, dec, jd, conf["lat"], conf["lon"])
        return alt, az, 0.2666
    ra, dec, _, _, r = moon_pos(jd)
    alt, az = altaz(ra, dec, jd, conf["lat"], conf["lon"])
    alt -= R2D * math.asin(math.cos(alt * D2R) / r)
    return alt, az, math.atan(1737.4 / (r * 6378.14)) * R2D


def ang(a1, z1, a2, z2):
    c = math.sin(a1 * D2R) * math.sin(a2 * D2R) + math.cos(a1 * D2R) * math.cos(a2 * D2R) * math.cos((z1 - z2) * D2R)
    return math.acos(max(-1, min(1, c))) * R2D


def transits(conf, start, hours=48):
    """Transits à moins de 40 km du lieu dans les prochaines heures."""
    try:
        from sgp4.api import Satrec
        with open(SPACE, encoding="utf-8") as f:
            tle = json.load(f).get("tle", {})
    except (ImportError, FileNotFoundError, ValueError) as e:
        print(f"transits non vérifiés : {e}")
        return []
    obs, out = observer_ecf(conf["lat"], conf["lon"]), []
    for key, name in SATS.items():
        if key not in tle:
            continue
        sat = Satrec.twoline2rv(*tle[key][:2])
        look = lambda t: sat_look(sat, t, conf, obs)
        passes, rise, t, prev = [], None, start, look(start)
        while t < start + hours * 3600:                  # passages au-dessus de l'horizon (pas de 20 s)
            t += 20; cur = look(t)
            if cur and prev:
                if prev[0] <= 0 < cur[0]:
                    rise = t - 20
                if prev[0] > 0 >= cur[0] and rise:
                    passes.append((rise, t)); rise = None
            prev = cur
        for r0, r1 in passes:
            mid = (r0 + r1) / 2
            for bk in ("sun", "moon"):
                b0 = body_look(bk, mid, conf)
                if b0[0] < 2:
                    continue
                f = lambda x: (lambda l, b: ang(l[0], l[1], b[0], b[1]) if l else 180)(look(x), body_look(bk, x, conf))
                coarse = [(ang(l[0], l[1], b0[0], b0[1]), x) for x in range(int(r0), int(r1), 10) for l in [look(x)] if l]
                if not coarse or min(coarse)[0] > 8:
                    continue
                c0 = min(coarse)[1]
                best, bt = min((f(x), x) for x in range(int(max(r0, c0 - 90)), int(min(r1, c0 + 90)), 2))
                if best > 3:
                    continue
                a, b = bt - 2, bt + 2
                for _ in range(40):
                    m1, m2 = a + (b - a) / 3, b - (b - a) / 3
                    if f(m1) < f(m2):
                        b = m2
                    else:
                        a = m1
                tm = (a + b) / 2; l = look(tm); bb = body_look(bk, tm, conf); dsep = f(tm)
                l2 = look(tm + 1); speed = ang(l[0], l[1], l2[0], l2[1])
                off = max(0.0, dsep - bb[2]) * D2R * l[2] / max(0.2, math.sin(max(5, l[0]) * D2R))
                here = dsep < bb[2]
                if here or off <= 40:
                    out.append({"sat": name, "key": key, "body": bk, "t": tm, "here": here, "off": off, "el": l[0], "az": l[1],
                                "dur": 2 * math.sqrt(bb[2] ** 2 - dsep ** 2) / speed if here else 0})
    return sorted(out, key=lambda x: x["t"])


DIRS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSO", "SO", "OSO", "O", "ONO", "NO", "NNO"]


def transit_message(conf, x):
    tz = ZoneInfo(conf["tz"])
    when = dt.datetime.fromtimestamp(x["t"], tz)
    body = "le Soleil" if x["body"] == "sun" else "la Lune"
    title = f"Transit de {x['sat']} devant {body}" + (" visible d'ici" if x["here"] else f" à {x['off']:.0f} km")
    lines = [f"{when.strftime('%d/%m')} à {when.strftime('%H:%M:%S')}, hauteur {x['el']:.0f}° vers {DIRS[round(x['az'] / 22.5) % 16]}",
             f"Durée {x['dur']:.1f} s depuis {conf['site']}" if x["here"] else "La bande de visibilité passe à côté : il faut se déplacer.",
             "À confirmer la veille sur transit-finder.com."]
    if x["body"] == "sun":
        lines.append("Filtre solaire obligatoire.")
    return title, "\n".join(lines)


def kp_alert(conf):
    try:
        with open(SPACE, encoding="utf-8") as f:
            kp = json.load(f).get("kp", [])
    except (FileNotFoundError, ValueError):
        return None
    now = dt.datetime.now(dt.timezone.utc)
    soon = []
    for t, v in kp:
        try:
            ts = dt.datetime.fromisoformat(str(t).replace(" ", "T")[:16]).replace(tzinfo=dt.timezone.utc)
        except ValueError:
            continue
        if now - dt.timedelta(hours=3) <= ts <= now + dt.timedelta(hours=48):
            soon.append((float(v), ts))
    if not soon or max(soon)[0] < 7:
        return None
    v, ts = max(soon)
    when = ts.astimezone(ZoneInfo(conf["tz"])).strftime("%d/%m vers %H h")
    txt = ("Aurore possible sur l'horizon nord : grand champ, poses de 10 à 20 s." if v >= 8
           else "Aurore peu probable depuis le sud de la France, mais à surveiller.")
    return f"Orage géomagnétique : Kp {v:.0f} prévu", f"Maximum prévu le {when}.\n{txt}", ts.strftime("%Y-%m-%d")


def load_conf():
    conf = dict(DEFAULTS)
    try:
        with open(CONF, encoding="utf-8") as f:
            conf.update(json.load(f))
    except FileNotFoundError:
        pass
    return conf


def main():
    conf = load_conf()
    if not conf["topic"] and "--dry-run" not in ARGS:
        sys.exit(f"Aucun sujet ntfy : écrivez {{\"topic\": \"...\"}} dans {CONF} (voir le README).")
    if "--test" in ARGS:
        send(conf, "AstroPlan : notification d'essai", f"Les alertes « nuit claire » pour {conf['site']} arrivent bien sur ce téléphone.", tags=("white_check_mark",))
        print("notification d'essai envoyée")
        return
    tz = ZoneInfo(conf["tz"])
    now = dt.datetime.now(tz)
    try:
        with open(STATE, encoding="utf-8") as f:
            state = json.load(f)
    except (FileNotFoundError, ValueError):
        state = {}
    state.setdefault("transits", [])
    def notify(title, body, tags):
        if "--dry-run" in ARGS:
            print(title + "\n" + body)
        else:
            send(conf, title, body, tags=tags)
    # transits et aurores : à chaque lancement
    for x in transits(conf, now.timestamp()):
        tid = f"{x['key']}-{x['body']}-{round(x['t'] / 60)}"
        if tid in state["transits"] and "--force" not in ARGS:
            continue
        notify(*transit_message(conf, x), ("satellite", "sunny" if x["body"] == "sun" else "crescent_moon"))
        state["transits"] = (state["transits"] + [tid])[-50:]
    kp = kp_alert(conf)
    if kp and (state.get("kp") != kp[2] or "--force" in ARGS):
        notify(kp[0], kp[1], ("rotating_light",)); state["kp"] = kp[2]
    save_state(state)
    if now.hour < 12 and "--force" not in ARGS and "--dry-run" not in ARGS:
        return                               # la nuit claire se juge l'après-midi
    day = now.date() if now.hour >= 9 else now.date() - dt.timedelta(days=1)
    wx = forecast(conf)
    n = night(conf, day)
    a = assess(conf, n, wx)
    if not a:
        print("pas de prévision pour la nuit noire")
        return
    nxt_n = night(conf, day + dt.timedelta(days=1))
    nxt = assess(conf, nxt_n, wx)
    nxt = nxt if nxt and len(nxt["best"]) >= conf["min_hours"] else None
    ok = len(a["best"]) >= conf["min_hours"]
    print(f"{day} : {a['clear_h']}/{a['n_hours']} h claires, meilleur créneau {len(a['best'])} h -> {'alerte' if ok else 'rien'}")
    if not ok:
        return
    title, body = message(conf, day, n, a, nxt)
    if state.get("sent") == str(day) and "--force" not in ARGS and "--dry-run" not in ARGS:
        print("alerte déjà envoyée pour cette nuit")
        return
    notify(title, body, ("star", "crescent_moon"))
    if "--dry-run" not in ARGS:
        state["sent"] = str(day); save_state(state)
        print("alerte envoyée")


def save_state(state):
    if "--dry-run" in ARGS:
        return
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(state, f)


if __name__ == "__main__":
    main()
