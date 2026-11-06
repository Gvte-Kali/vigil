# Construire la documentation

Le site utilise Jekyll et Just the Docs (version fixée dans `_config.yml`).
Prérequis : Ruby, Bundler et les outils de compilation des gems natives.

Depuis `docs/` :

```bash
bundle install
bundle exec jekyll build --strict_front_matter
bundle exec jekyll serve --baseurl /vigil
```

Ouvrir `http://127.0.0.1:4000/vigil/`. Vérifier la navigation, la recherche et le
rendu sur mobile avant de publier. Ne pas ajouter `_site/`, `.jekyll-cache/`,
`.bundle/` ou `vendor/` au dépôt.

La publication GitHub Pages conserve la source `docs/`. La palette Graphite est
chargée par `_sass/color_schemes/graphite.scss`. Le README de chaque rubrique
conserve son adresse pour préserver les liens existants.
