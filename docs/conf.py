# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
from pyheartlib import __version__

project = "pyheartlib"
copyright = "2023, devnums"
author = "devnums" 
version = __version__

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "myst_nb",
    "autoapi.extension",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
]
autoapi_dirs = ["../src"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "**/archs", "**/extra"]

autodoc_default_options = {
    'members': True,
    'undoc-members': False,
    'private-members': False,
    'special-members': False,
}

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "sphinx_rtd_theme"

# -- MyST-NB -------------------------------------------------
nb_execution_timeout = 180


# -- Custom code -----------------------------------------------------
print("\n***************\ndoc is running\n***************\n")
import shutil

files = [
    ["../examples/model/data_preparation.py", "examples/model/"],
    ["../examples/model/train.py", "examples/model/"],
    ["../examples/model/inference.py", "examples/model/"],
    ["../examples/model/result.txt", "examples/model/"],
    ["../examples/model/plots/mis.png", "examples/model/plots/mis.png"],
]
for f in files:
    shutil.copy(f[0], f[1])
