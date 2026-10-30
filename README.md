# AstroPlan

**Préparer une séance d'astrophotographie : quelle cible ce soir, avec quel instrument, quel filtre et quelles poses.**

AstroPlan est une page web autonome (un seul fichier HTML, aucun serveur applicatif). Pour la date et le lieu choisis, elle calcule la nuit noire, la position de la Lune et la hauteur de chaque objet, puis conseille le matériel le mieux adapté.

Elle complète [AstroCheck](https://github.com/nunux1971/astrocheck), qui trie et analyse les images après la séance.

## Ce qu'elle fait

- **Système solaire** : Soleil, Lune, planètes et comètes brillantes comme cibles à part entière, avec un tableau en tête de « Ce soir » : fenêtre, hauteur, taille du disque, et conseils adaptés (vidéo et Barlow pour les planètes, mosaïque pour la Lune, empilement sur le noyau pour les comètes, **filtre solaire obligatoire** et avertissements pour le Soleil, image du jour du satellite SDO).
- **Alertes** : éclipses de Lune et de Soleil visibles d'ici (heures locales, pourcentage), **passages de l'ISS et de Tiangong** et leurs **transits devant le Soleil ou la Lune** (avec la distance à parcourir si la bande passe à côté), taches solaires et indice Kp (aurores), oppositions, élongations, rapprochements de planètes, la Lune près des planètes et des étoiles brillantes, étoiles filantes. Le bouton **Ajouter à mon agenda** télécharge un fichier `.ics` avec rappels pour le téléphone.
- **Ce soir** : les meilleures cibles de la nuit, avec leur fenêtre au-dessus de la hauteur minimale, la gêne de la Lune et l'instrument conseillé. Filtres par type d'objet et par instrument.
- **Carte du ciel** : le ciel vu en levant la tête à l'heure choisie (curseur sur toute la nuit), avec étoiles, constellations, Lune, horizon local et vos cibles ; zoom au doigt ou à la molette, et une touche sur une cible ouvre sa fiche.
- **Cible** : courbe de hauteur pendant la nuit, classement des instruments avec aperçu du cadrage, filtre, pose unitaire, temps total conseillé, retournement au méridien, rotation de champ du Dwarf 3, et une fiche de soirée à copier.
- **Meilleures nuits** : les 14 à 60 prochaines soirées pour une cible, selon la nuit noire et la Lune.
- **Aperçu dans l'instrument** : le champ de chaque instrument posé sur une image du ciel réel (relevés DSS2 et Mellinger, via NASA SkyView ou le CDS de Strasbourg), en vue large ou au format du capteur, avec la rotation du capteur réglable.
- **Météo** (Open-Meteo, 16 jours) : nuages bas, moyens et hauts, vent, et alerte de **buée** quand la température approche du point de rosée. Les nuages prévus entrent dans la note des meilleures nuits.
- **Journal** : le temps de pose déjà gardé par cible, d'après le journal écrit par AstroCheck, face au temps conseillé, avec le nombre de nuits restantes.
- **Matériel et lieu** : coordonnées, ciel (échelle de Bortle), turbulence, **horizon local** (hauteur des obstacles dans 16 directions), instruments emportés.
- **Mode rouge** pour garder la vision nocturne sur le terrain.
- **Français ou anglais** : la page suit la langue du téléphone, et le bouton FR / EN change de langue.

Les poses et temps totaux sont des ordres de grandeur pour le ciel indiqué. La météo et l'aperçu du ciel demandent que la page puisse joindre `api.open-meteo.com` et `skyview.gsfc.nasa.gov` (ou `alasky.cds.unistra.fr`) ; sans connexion, tout le reste fonctionne.

## Journal des séances

AstroCheck écrit `~/.config/astrocheck/journal.json` à chaque export (ou par Ctrl+J). Pour l'afficher dans AstroPlan, importez-le dans l'onglet Journal, ou posez-le à côté de la page sur le serveur :

```bash
scp ~/.config/astrocheck/journal.json serveur:/var/www/astroplan/site/journal.json
```

## Installation sur un serveur web (Debian + nginx)

```bash
sudo git clone https://github.com/nunux1971/astroplan /var/www/astroplan
```

Dans la configuration nginx du site, la racine est le dossier `site` :

```nginx
root /var/www/astroplan/site;
index index.html;
```

Mise à jour :

```bash
cd /var/www/astroplan && sudo git pull
```

On peut aussi simplement ouvrir `site/index.html` dans un navigateur, même sans connexion internet.

### Sur le téléphone ou la tablette

Ouvrez l'adresse du site dans Chrome, puis **Installer l'application** (bouton dans la page, ou menu ⋮ ▸ *Installer l'application*). AstroPlan s'ouvre alors en plein écran depuis son icône et **fonctionne hors ligne** une fois chargée une première fois avec du réseau. Elle se met à jour toute seule après un `git pull` sur le serveur. Le site doit être servi en HTTPS.

## Vos images AstroBin

AstroPlan peut afficher, sur la fiche de chaque cible, vos images publiques d'[AstroBin](https://www.astrobin.com), retrouvées grâce aux objets que la résolution astrométrique d'AstroBin a reconnus (ou au titre). Un petit script, sur le serveur, lit votre galerie par l'interface publique d'AstroBin (aucune clé d'API nécessaire) et écrit `site/astrobin.json`, que la page lit.

```bash
sudo python3 /var/www/astroplan/tools/astrobin_sync.py VOTRE_NOM_ASTROBIN --debug
```

Puis, pour une mise à jour chaque heure :

```bash
echo "17 * * * * root python3 /var/www/astroplan/tools/astrobin_sync.py VOTRE_NOM_ASTROBIN >/dev/null 2>&1" | sudo tee /etc/cron.d/astroplan-astrobin
```

## ISS, comètes, taches solaires (space.json)

Les orbites de l'ISS et de Tiangong (CelesTrak), des comètes (Minor Planet Center), le nombre de taches solaires et l'indice Kp (NOAA SWPC, ou SILSO en secours) sont récupérés par un script sur le serveur, qui écrit `site/space.json`. Sans ce fichier, éclipses, planètes, Lune, Soleil et événements fonctionnent quand même.

```bash
sudo python3 /var/www/astroplan/tools/space_sync.py --debug
```

Puis, toutes les six heures (les orbites de l'ISS vieillissent vite) :

```bash
echo "23 */6 * * * root python3 /var/www/astroplan/tools/space_sync.py >/dev/null 2>&1" | sudo tee /etc/cron.d/astroplan-space
```

## Alertes sur le téléphone (ntfy)

`tools/clear_night_alert.py` envoie une notification sur le téléphone, par l'application gratuite [ntfy](https://ntfy.sh) (Android : Play Store ou F-Droid ; aucun compte) :

- **nuit claire** : chaque après-midi, si la prévision Open-Meteo donne au moins 3 heures de nuit noire avec moins de 25 % de nuages, avec le créneau, la Lune, la buée et le vent ;
- **transit de l'ISS ou de Tiangong** devant le Soleil ou la Lune, visible d'ici ou à moins de 40 km, dans les 48 heures ;
- **orage géomagnétique** (indice Kp prévu de 7 ou plus) : aurore possible.

Installation sur le serveur :

```bash
sudo apt install python3-sgp4            # calcul des orbites, pour les transits
sudo mkdir -p /etc/astroplan
echo "{\"topic\": \"astroplan-$(openssl rand -hex 6)\"}" | sudo tee /etc/astroplan/alerts.json
sudo python3 /var/www/astroplan/tools/clear_night_alert.py --test
echo "41 7,16 * * * root python3 /var/www/astroplan/tools/clear_night_alert.py >/dev/null 2>&1" | sudo tee /etc/cron.d/astroplan-alertes
```

Dans l'application ntfy, abonnez-vous au sujet écrit dans `/etc/astroplan/alerts.json` (le nom fait office de mot de passe : gardez-le pour vous). Réglages possibles dans ce fichier : `max_cloud` (25), `min_hours` (3), `max_gust` (45), `lat`, `lon`, `site`, `server` et `token` pour un serveur ntfy personnel. `--dry-run` affiche le message sans l'envoyer.

## Modifier le matériel ou le catalogue

La page est assemblée à partir de `src/template.html` (interface, calculs, liste du matériel) et `src/catalog.json` (catalogue d'objets) :

```bash
python3 build.py      # régénère site/index.html
```

## Licences

Le code d'AstroPlan est distribué sous licence [GPL-2.0](LICENSE).

Prévisions météo : [Open-Meteo](https://open-meteo.com) (CC BY 4.0). Étoiles et constellations : [d3-celestial](https://github.com/ofrohn/d3-celestial) d'Olaf Frohn (licence BSD, voir `src/LICENSE-d3-celestial`). Images du ciel : [NASA SkyView](https://skyview.gsfc.nasa.gov) et [CDS, Strasbourg](https://alasky.cds.unistra.fr) (relevés DSS2 et Mellinger).

Soleil, Lune, planètes et éclipses : [Astronomy Engine](https://github.com/cosinekitty/astronomy) de Don Cross (MIT, `src/vendor/LICENSE-astronomy-engine.txt`). Satellites : [satellite.js](https://github.com/shashwatak/satellite-js) (MIT, `src/vendor/LICENSE-satellite-js.md`), regroupé par `tools/bundle_satellite.js` et vérifié sur les 130 000 cas de test SGP4 officiels. Orbites : [CelesTrak](https://celestrak.org) et [Minor Planet Center](https://minorplanetcenter.net). Taches et Kp : [NOAA SWPC](https://www.swpc.noaa.gov) et [SILSO](https://www.sidc.be/SILSO). Image du Soleil : [NASA SDO](https://sdo.gsfc.nasa.gov).

Le catalogue NGC/IC et Messier provient d'[OpenNGC](https://github.com/mattiaverga/OpenNGC) de Mattia Verga, sous licence [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Les coordonnées des nébuleuses Sharpless ajoutées sont approchées.

## English

AstroPlan is also available in English: the page follows the language of the phone or browser, and the **FR / EN** button in the header switches it by hand. It plans an astrophotography session for a chosen evening and site: tonight's best targets (deep sky, plus the Sun, Moon, planets and bright comets), an Alerts tab (eclipses, ISS and Tiangong passes and transits across the Sun or Moon, sunspots and aurora index, planetary events, meteor showers, with a calendar export), an interactive sky map, the best rig, filter, sub length and total time for each target, the best nights ahead (Moon and 16-day cloud forecast), a real-sky framing preview, a local horizon, and a progress log fed by [AstroCheck](https://github.com/nunux1971/astrocheck). It installs as an app on Android (Chrome ▸ *Install app*) and works offline once loaded.
