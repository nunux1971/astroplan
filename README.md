# AstroPlan

**Préparer une séance d'astrophotographie : quelle cible ce soir, avec quel instrument, quel filtre et quelles poses.**

AstroPlan est une page web autonome (un seul fichier HTML, aucun serveur applicatif). Pour la date et le lieu choisis, elle calcule la nuit noire, la position de la Lune et la hauteur de chaque objet, puis conseille le matériel le mieux adapté.

Elle complète [AstroCheck](https://github.com/nunux1971/astrocheck), qui trie et analyse les images après la séance.

## Ce qu'elle fait

- **Ce soir** : les meilleures cibles de la nuit, avec leur fenêtre au-dessus de la hauteur minimale, la gêne de la Lune et l'instrument conseillé. Filtres par type d'objet et par instrument.
- **Cible** : courbe de hauteur pendant la nuit, classement des instruments avec aperçu du cadrage, filtre, pose unitaire, temps total conseillé, retournement au méridien, rotation de champ du Dwarf 3, et une fiche de soirée à copier.
- **Meilleures nuits** : les 14 à 60 prochaines soirées pour une cible, selon la nuit noire et la Lune.
- **Matériel et lieu** : coordonnées, ciel (échelle de Bortle), turbulence, instruments emportés.
- **Mode rouge** pour garder la vision nocturne sur le terrain.

Les poses et temps totaux sont des ordres de grandeur pour le ciel indiqué. La météo n'est pas intégrée : un lien mène à Clear Outside pour le lieu.

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

## Modifier le matériel ou le catalogue

La page est assemblée à partir de `src/template.html` (interface, calculs, liste du matériel) et `src/catalog.json` (catalogue d'objets) :

```bash
python3 build.py      # régénère site/index.html
```

## Licences

Le code d'AstroPlan est distribué sous licence [GPL-2.0](LICENSE).

Le catalogue NGC/IC et Messier provient d'[OpenNGC](https://github.com/mattiaverga/OpenNGC) de Mattia Verga, sous licence [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Les coordonnées des nébuleuses Sharpless ajoutées sont approchées.
