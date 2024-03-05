#!/usr/bin/env sh

# sudo rm -r /var/www/html/vOblaCoolDocs
# sudo cp -r ~/project/docs/build/html /var/www/html/vOblaCoolDocsvOblaCoolDocs
m2r readme.md --overwrite
sphinx-build -M  html docs/source docs/build/
rm readme.rst
