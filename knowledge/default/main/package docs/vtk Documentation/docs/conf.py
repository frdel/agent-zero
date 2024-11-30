# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import vtk_documentation

# We add the base directory of the repository to allow resolve relative
# references between markdown files
# sys.path.insert(0, os.path.abspath('../../'))

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information


project = "VTK"
copyright = "2023, VTK Developers"
author = "VTK Developers"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

# Define the canonical URL if you are using a custom domain on Read the Docs
import os
html_baseurl = os.environ.get("READTHEDOCS_CANONICAL_URL", "")

# Tell Jinja2 templates the build is running on Read the Docs
if os.environ.get("READTHEDOCS", "") == "True":
    if "html_context" not in globals():
        html_context = {}
    html_context["READTHEDOCS"] = True

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "myst_parser",
    "sphinx.ext.todo",
    "sphinx_copybutton",  # add copy button to snippets
    "sphinx_design",  # enables tabs, and other web components
    "autodoc2",  # generate native python documentation for vtkmodules
    "sphinxcontrib.moderncmakedomain",  # generate cmake documentation
]

autodoc2_packages = [
    "../../Wrapping/Python/vtkmodules/",
]
autodoc2_render_plugin = "myst"
autodoc2_output_dir = "./api/python"
autodoc2_index_template = None  # skip ./api/python/index.rst generation
vtk_documentation.add_init_file("../../Wrapping/Python/vtkmodules/__init__.py")


myst_enable_extensions = [
    "linkify",  # convert bare links to hyperlinks
    "substitution",
    "colon_fence",  # recommended to use with sphinx_design
]
# create anchors up to 7 level deep
myst_heading_anchors = 7

# myst_all_links_external = True
# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["_build", ".venv", "Thumbs.db", ".DS_Store", "README.md"]

todo_include_todos = True

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
html_logo = "../../vtkLogo.ico"
html_favicon = "../../Utilities/Doxygen/vtk_favicon.png"
html_theme = "furo"

copybutton_prompt_text = r"\$ | C\:\> |>>> "  # strip prompt text on copy
copybutton_prompt_is_regexp = True
copybutton_only_copy_prompt_lines = False


# -- Custom markdown generation ------------------------------------------------
ignore_list = [
    "Wrapping/Tools",  # we handle these separately
    "Examples",  # we don't want these to appear
    "ThirdParty",
]
module_list = vtk_documentation.gather_module_documentation(
    "../../",
    "./modules/vtk-modules",
    custom_paths=[],
    ignore_list=ignore_list,
)


# some files require more complex substitutions
for entry in vtk_documentation.MANUAL_SUBSTITUTIONS:
    vtk_documentation.copy_with_substitutions(**entry)

myst_substitutions = {
    "module_table": vtk_documentation.create_module_table(module_list),
    "release_index": vtk_documentation.create_release_index("./release_details/"),
    "supported_data_formats_list": vtk_documentation.create_supported_formats_list(
        "./supported_data_formats.yaml"
    ),
}
