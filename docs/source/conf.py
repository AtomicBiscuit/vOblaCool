import os
import sys

project = 'vOblaCool'
copyright = '2024, vOblaCool Team'
author = 'vOblaCool Team'
release = '1.0.0'

sys.path.insert(0, os.path.abspath('../../'))

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.intersphinx',
    'sphinx.ext.viewcode',
    'sphinx_rtd_theme',
    'sphinx_autodoc_typehints',
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

language = 'ru'

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']

intersphinx_mapping = {
    'python': ('https://docs.python.org', None),
    'telebot': (
        'https://pytba.readthedocs.io/en/latest/',
        None
    ),
    'requests': (
        'https://requests.readthedocs.io/en/latest/',
        None
    ),
    'putube': ('https://pytube.io/en/latest/', None),
    'pika': ('https://pika.readthedocs.io/en/stable/', None),
    'flask': ('https://flask.palletsprojects.com/en/latest/', None)
}

set_type_checking_flag = True
typehints_fully_qualified = True
always_document_param_types = True
typehints_document_rtype = True
