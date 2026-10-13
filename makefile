# Convenience wrapper: rebuild all lectures listed in _lamd/lectures.csv.
# Requires LaMD tools on PATH (prefer $HOME/lawrennd/lamd/.venv/bin).

.PHONY: all lectures site

all: lectures

lectures:
	cd _lamd && ./compile.sh

site:
	bundle exec jekyll build
