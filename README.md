# Gaussian Process Summer School lectures

Lecture site for the [Gaussian Process Summer School](https://gpss.cc), published at [mlatcl.github.io/gpss](https://mlatcl.github.io/gpss/).

Talk sources live in `_lamd/` and are compiled with [LaMD](https://github.com/lawrennd/lamd) (`maketalk`). Shared narrative and code includes come from [`lawrennd/snippets`](https://github.com/lawrennd/snippets) (see `snippetsdir` in `_lamd/_lamd.yml`). Generated lecture HTML, notebooks, and Reveal slides are committed under `_lectures/`, `_notebooks/`, and `slides/` for GitHub Pages (`gh-pages`).

## Local site preview

```bash
bundle install
bundle exec jekyll serve
# Visit http://localhost:4000/gpss/
```

## Rebuild a lecture

Requires a local LaMD install and paths in `_lamd/_lamd.yml` (`snippetsdir`, `bibdir`, `macrosdir`). Prefer the LaMD virtualenv on `PATH` so `mdfield` / `maketalk` resolve correctly:

```bash
export PATH="$HOME/lawrennd/lamd/.venv/bin:$PATH"
cd _lamd
maketalk deep-gps-I.md
maketalk deep-gps-II.md
# or: ./compile.sh   # rebuilds every stub in lectures.csv
```

## Notebook runtime dependencies

Deep GP notebooks install teaching helpers via LaMD `\installcode{}` cells, typically:

- `GPy`
- `PyDeepGP` (`import deepgp`)
- `mlai` (includes `mlai.deepgp_tutorial`: initialize, staged optimize, visualize, **visualize_pinball**)

Pinball and related Deep GP teaching methods live in [`lawrennd/mlai`](https://github.com/lawrennd/mlai), not in PyDeepGP itself; lecture setup monkey-patches them onto `deepgp.DeepGP`.

## Layout

| Path | Role |
|------|------|
| `_lamd/*.md` | Lecture sources |
| `_lamd/_lamd.yml` | LaMD paths and talk metadata |
| `_people/people.yml` | Speaker metadata for talks |
| `_lectures/` | Generated lecture HTML (Jekyll) |
| `_notebooks/` | Generated Jupyter notebooks |
| `slides/` | Reveal.js slides and `diagrams/` |
