#!/bin/bash
# Installe la surveillance sur un serveur :
#   sudo bash installer_surveillance.sh s1     (musique, Jellyfin)
#   sudo bash installer_surveillance.sh s2     (ericastro.fr, AstroPlan)
# Vérification toutes les 10 minutes ; notifications par ntfy.
set -euo pipefail
PROFIL="${1:-}"
ICI="$(cd "$(dirname "$0")" && pwd)"
CONF=/etc/surveillance.json

case "$PROFIL" in
  s2) cat > /tmp/surveillance.json <<'EOF'
{
  "nom": "Serveur 2 (ericastro.fr)",
  "urls": [
    {"url": "https://ericastro.fr/sante/", "codes": [200]},
    {"url": "https://plan.ericastro.fr/", "codes": [200, 302]},
    {"url": "https://musiques.ericcioli.fr/", "codes": [200, 301, 302]}
  ],
  "certificats": ["ericastro.fr", "plan.ericastro.fr"],
  "disques": ["/", "/backup"],
  "seuil_disque": 90,
  "services": ["nginx.service", "ericastro.service", "postgresql.service"],
  "sauvegardes": [{"service": "backup-s2.service", "max_heures": 30}]
}
EOF
  ;;
  s1) cat > /tmp/surveillance.json <<'EOF'
{
  "nom": "Serveur 1 (musique)",
  "urls": [
    {"url": "https://musiques.ericcioli.fr/", "codes": [200, 301, 302]},
    {"url": "https://ericastro.fr/sante/", "codes": [200]}
  ],
  "certificats": ["musiques.ericcioli.fr"],
  "disques": ["/", "/backup", "/var/music"],
  "seuil_disque": 90,
  "services": ["nginx.service", "docker.service"],
  "sauvegardes": [{"service": "backup-jellyfin.service", "max_heures": 30}]
}
EOF
  ;;
  *) echo "Usage : sudo bash $0 s1|s2" >&2; exit 1 ;;
esac

install -m 755 "$ICI/surveillance.py" /usr/local/bin/surveillance.py
if [ -f "$CONF" ]; then
  echo "$CONF existe déjà : gardé tel quel (le nouveau modèle est dans /tmp/surveillance.json)."
else
  install -m 600 /tmp/surveillance.json "$CONF"
fi
rm -f /tmp/surveillance.json
if [ ! -f /etc/astroplan/alerts.json ] && ! grep -q '"topic"' "$CONF"; then
  echo "Pas de /etc/astroplan/alerts.json ici : collez le sujet ntfy (le même que pour les alertes d'AstroPlan), puis Entrée."
  read -r -s SUJET
  python3 - "$CONF" "$SUJET" <<'EOF'
import json, sys
c = json.load(open(sys.argv[1])); c["topic"] = sys.argv[2].strip(); c["server"] = "https://ntfy.sh"
json.dump(c, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
EOF
fi

cat > /etc/systemd/system/surveillance.service <<'EOF'
[Unit]
Description=Surveillance du serveur (notifications ntfy)
After=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /usr/local/bin/surveillance.py
EOF
cat > /etc/systemd/system/surveillance.timer <<'EOF'
[Unit]
Description=Surveillance du serveur toutes les 10 minutes

[Timer]
OnBootSec=3min
OnUnitActiveSec=10min

[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now surveillance.timer
echo "Installé. État actuel :"
/usr/bin/python3 /usr/local/bin/surveillance.py --dry-run
