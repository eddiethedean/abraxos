"""Sphinx configuration for the installed version of Abraxos."""

from importlib.metadata import version as package_version

project = 'Abraxos'
copyright = '2024–2026, Odos Matthews'
author = 'Odos Matthews'
release = package_version('abraxos')
version = release

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.doctest',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
]
autosummary_generate = True
autodoc_typehints = 'description'
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']
templates_path = ['_templates']

html_theme = 'furo'
html_title = f'{project} {release}'
html_static_path = ['_static']
html_css_files = ['abraxos.css']
html_theme_options = {
    'light_css_variables': {
        'color-background-primary': '#fcfdfb',
        'color-background-secondary': '#f2f6f2',
        'color-background-hover': '#e6efe9',
        'color-background-hover--transparent': '#e6efe900',
        'color-background-border': '#d7e3da',
        'color-foreground-primary': '#192c23',
        'color-foreground-secondary': '#41584b',
        'color-foreground-muted': '#566f61',
        'color-brand-primary': '#195b43',
        'color-brand-content': '#144a36',
        'color-brand-visited': '#514779',
        'color-link-underline': '#8eac9e',
        'color-highlight-on-target': '#e4f2e9',
        'color-highlighted-background': '#dceee3',
        'color-sidebar-item-background--current': '#e6efe9',
        'color-api-background': '#eef4ef',
        'color-api-name': '#195b43',
        'color-api-pre-name': '#566f61',
        'color-ab-action-text': '#fff',
    },
    'dark_css_variables': {
        'color-background-primary': '#141e19',
        'color-background-secondary': '#1c2a22',
        'color-background-hover': '#263b30',
        'color-background-hover--transparent': '#263b3000',
        'color-background-border': '#385044',
        'color-foreground-primary': '#e4eee7',
        'color-foreground-secondary': '#bbd0c3',
        'color-foreground-muted': '#a0b8a9',
        'color-brand-primary': '#a0e3c2',
        'color-brand-content': '#baf0d5',
        'color-brand-visited': '#d5c2f0',
        'color-link-underline': '#668f79',
        'color-highlight-on-target': '#253e32',
        'color-highlighted-background': '#2a4637',
        'color-sidebar-item-background--current': '#263b30',
        'color-api-background': '#1c2a22',
        'color-api-name': '#a0e3c2',
        'color-api-pre-name': '#a0b8a9',
        'color-ab-action-text': '#142d22',
    },
}
