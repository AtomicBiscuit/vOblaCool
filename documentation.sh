#!/usr/bin/env sh

m2r README.md --overwrite
sphinx-build -M  html docs/source docs/build/
rm README.rst
