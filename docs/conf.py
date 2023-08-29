# This code is part of Qiskit.
#
# (C) Copyright IBM 2021, 2023.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

# pylint: disable=invalid-name
# Configuration file for the Sphinx documentation builder.
#
# This file does only contain a selection of the most common options. For a
# full list see the documentation:
# http://www.sphinx-doc.org/en/master/config

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
# import os
# import sys
# sys.path.insert(0, os.path.abspath('.'))

"""
Sphinx documentation builder
"""

import os
# Set env flag so that we can doc functions that may otherwise not be loaded
# see for example interactive visualizations in qiskit.visualization.
os.environ['QISKIT_DOCS'] = 'TRUE'

# -- Project information -----------------------------------------------------
project = 'Qiskit IBM Quantum Provider'
copyright = '2022, Qiskit Development Team'  # pylint: disable=redefined-builtin
author = 'Qiskit Development Team'

# The short X.Y version
version = ''
# The full version, including alpha/beta/rc tags
release = '0.7.1'

# -- General configuration ---------------------------------------------------

extensions = [
    'sphinx.ext.napoleon',
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.mathjax',
    'sphinx.ext.viewcode',
    'sphinx.ext.extlinks',
    'sphinx.ext.intersphinx',
    'jupyter_sphinx',
    'sphinx_autodoc_typehints',
    'reno.sphinxext',
    'nbsphinx',
    "qiskit_sphinx_theme",
]
templates_path = ['_templates']

intersphinx_mapping = {
    "qiskit": ("https://qiskit.org/documentation/", None),
}

nbsphinx_timeout = 300
nbsphinx_execute = "never"
nbsphinx_widgets_path = ''

nbsphinx_thumbnails = {"**": "_static/images/logo.png"}

nbsphinx_prolog = """
{% set docname = env.doc2path(env.docname, base=None) %}
.. only:: html

    .. role:: raw-html(raw)
        :format: html

    .. note::
        This page was generated from `docs/{{ docname }}`__.

        __"""

vers = release.split(".")
link_str = f" https://github.com/Qiskit/qiskit-ibm-provider/blob/stable/{vers[0]}.{vers[1]}/docs/"
nbsphinx_prolog += link_str + "{{ docname }}"

# -----------------------------------------------------------------------------
# Autosummary & autodoc
# -----------------------------------------------------------------------------

autosummary_generate = True

autodoc_default_options = {
    'inherited-members': None,
    'exclude-members': 'with_traceback'
}

autoclass_content = 'both'


# If true, figures, tables and code-blocks are automatically numbered if they
# have a caption.
numfig = True

# A dictionary mapping 'figure', 'table', 'code-block' and 'section' to
# strings that are used for format of figure numbers. As a special character,
# %s will be replaced to figure number.
numfig_format = {
    'table': 'Table %s'
}
# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#
# This is also used if you do content translation via gettext catalogs.
# Usually you set "language" from the command line for these cases.
language = 'en'

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["_build", "**.ipynb_checkpoints"]

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'colorful'

# A boolean that decides whether module names are prepended to all object names
# (for object types where a “module” of some kind is defined), e.g. for
# py:function directives.
add_module_names = False

# A list of prefixes that are ignored for sorting the Python module index
# (e.g., if this is set to ['foo.'], then foo.bar is shown under B, not F).
# This can be handy if you document a project that consists of a single
# package. Works only for the HTML builder currently.
modindex_common_prefix = ['qiskit.']

# -- Options for HTML output -------------------------------------------------

html_theme = "qiskit-ecosystem"
html_title = f"{project} {release}"

html_logo = "images/ibm-quantum-logo.png"

html_theme_options = {
    # Because this is an IBM-focused project, we use a blue color scheme.
    "light_css_variables": {
        "color-brand-primary": "var(--qiskit-color-blue)",
    },
}

html_last_updated_fmt = '%Y/%m/%d'

html_sourcelink_suffix = ''
