
# CdE event Template Rendering System (Version 3)

This repository contains a Python 3 script to render LaTeX based participant lists, course lists, nametags,
participation letters (“Teilnehmerbriefe”) and other documents, as well as a set of configurable LaTeX templates for
these documents.

The templates are rendered to TeX files using the Jinja2 template engine, and afterwards compiled with LuaLaTeX. A set
of Python functions creates the rendering tasks (including the selection of a template and calculation of additional
data) for different targets. The tasks are rendered and compiled in parallel to make use of multiprocessors for the
time-consuming LaTeX compilation. 

The default target functions, templates and configuration data can be extended and overridden to adapt the documents
to the needs of a specific CdE events.


## Setup

TODO prerequisites: LaTeX (LuaLaTeX + required packages)
TODO prerequisites: Python3 (+ required packages)

TODO cloning repository


## Usage

TODO


## Customization

### Configuration Options

TODO


### Templates

TODO Jinja2 syntax (and reference)

TODO template inheritance with blocks

TODO our template inheritance structure

TODO access to EVENT and CONFIG data


### Target Functions

TODO function signuature and registration

TODO custom targets and overriding

TODO access to EVENT and CONFIG data

TODO passing of template variables
 