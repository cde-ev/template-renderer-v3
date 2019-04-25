
# CdE Event Template Rendering System (Version 3)

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

### Prerequisites

You need the following software on your computer:

* Python 3.5 or higher with
    * jinja2
    * pytz

* A LaTeX installation with LuaLaTeX and
    * koma-script
    * colortbl
    * xcolor
    * longtable

* The *Linux Libertine* font for the default templates

`lualatex` must be available in the $PATH to be called by the Python script.

#### Setting up Prerequisites on Linux systems
… on Ubuntu & Debian:
```
$ sudo apt install python3 python3-jinja2 python3-tz fonts-linuxlibertine git \
                   texlive-latex-base texlive-latex-recommended texlive-latex-extra texlive-luatex
```

… on Arch Linux:
```
$ sudo pacman -S python python-jinja2 python-pytz texlive-core ttf-linux-libertine git
```


#### Setting up Prerequisites on Windows systems

* Download and run the "Windows x86-64 executable installer" of the latest Python 3 release from
  https://www.python.org/downloads/windows/
  * Select *Add Python 3.X to PATH* before installing
  * You may want to use the *Customize installation* menu to install Python for all users and disable unnecessary
    components. Only *pip* is required. In this case you should make sure that *Add Python to the Environment variables*
    is checked.
* Download and run the latest MiKTeX installer from https://miktex.org/download
* (Optional) if you want to install and update the template rendering scripts via Git, download and run the latest
  "64-bit Git for Windows Setup" from https://git-scm.com/download/win
  * It's recommended to "Use the Nano editor by default"
  * All other default settings are typically good
* Log off and on again, to make sure, your %PATH% is up to date
* Open a *Command Prompt* or *Git Bash* and run `pip install --user jinja2 pytz`
* Download the Linux Libertine font from https://sourceforge.net/projects/linuxlibertine/ extract and install it


### Installation

You can receive this template rendering script either by cloning the git repository or downloading and extracting the
zip file of the latest stable branch.

The zip file can be downloaded from https://tracker.cde-ev.de/gitea/orgas/cde_template_renderer_v3/archive/stable.zip

Alternatively, using Git, open up a terminal (on Windows preferably a *Git Bash*) and type:
```
$ git clone https://tracker.cde-ev.de/gitea/orgas/cde_template_renderer_v3.git
$ cd cde_template_renderer_v3/
$ git checkout stable
```

To upgrade to the latest stable version, open a terminal within the template renderer's directory and type:
```
$ git pull
```



## Usage

To render and compile PDF files, first download a full event export from the CdE Datenbank and store the file as
`export_event.json` in the template renderer's directory:
CdEDB → Events → EVENT'S NAME → Downloads → Full Event Export / JSON-File

**On Windows**, open up a Command Prompt (shift+rightclick on directory → Open command window here) or a Git Bash
(Rightclick on directory → Git Bash here) in the directory of the template renderer and run
```
> python main.py TARGETS
``` 
where `TARGETS` is a space-separated list of the targets you want to render and compile. You will be prompted to install
the required LaTeX packages on the first run with targets.

**On Linux**, open up a terminal in the template renderer's directory (rightclick → Open in Terminal, in most
environments) and run
```
$ ./main.py TARGETS
```

If you are not sure about the available targets and their names, run the Python script without any targets to get a list
of all targets with a description.


### Command line parameters

To get an overview over all available parameters, use
```
$ ./main.py --help
```

Most important parameters are
* `-i INPUT_FILE` to specify an other input file than `export_event.json`
* `-c CUSTOM_DIR` to specify a custom directory (see Customization) different from the `custom` folder

A call with parameters might look like the following example:
```
$ ./main.py -i export_event_2019-04-24.json -c pa19/ tnlists 
```

Since the custom directory allows to add additional target functions, it is useful to call the script with the `-c`
parameter but without targets, to get a full list of all available targets (default targets and custom targets). 



## Customization

There are four different ways to customize the rendered PDF files for a specific CdE event:

* changing configuration options
* overriding and adding asset files
* overriding templates
* overriding target functions

Additionally, you can add your own target functions and templates, along with assets and configuration options for them.

It's recommended to start customizing the default templates using the default configuration options. If this is not
sufficient for a certain template or use case (typically, the `tnletter.tex` template is such a case), take a look into
overriding some of the templates. The templates' structure is designed to allow overriding selected portions without
touching (or even understanding) the rest. At the same time, they profit from code reuse, so only few overrides are
required to effect the look of multiple documents.

If you want to add your own render targets and templates or do more sophisticated preprocessing of the rendered data
(e.g. filtering participants by certain criteria), you'll need to override target functions or add your own.



### Configuration Options 

Configuration options are read from two files using the Python `configparser` module: `default/config.ini` and the
`config.ini` in your custom directory, if present. Options in the custom `config.ini` override equally named options
in the same section of the `default/config.ini`.

**Don't change `default/config.ini`** to customize config options. Instead, create a `config.ini` in your custom 
directory and redefine the same option there with your custom value. This way, you can easily update the template
rendering systems later, including changes to the default configuration file, without need to merge the changes
manually. Additionally, you can apply version control (e.g. Git, SVN, Mercurial, …) to your custom directory to keep
track of changes to your customization independently from the development of the template rendering system. 

You can easily define your custom `config.ini` and use them for easy adjustment in your overriden or added templates
and target functions. Just specify your own configuration sections and options and they will be available in the
templates' `CONFIG` variable and the target functions' `config` parameter.  


### Assets

TODO overriding assets (no need to change default assets)

TODO adding your own assets


### Templates

TODO Jinja2 syntax (and reference)

TODO overriding templates (again: don't change default templates)

TODO template inheritance with blocks

TODO reusing blocks (incl. subblocks) with `<<< self.BLOCKNAME() >>>`

TODO our template inheritance structure

TODO accessing to EVENT and CONFIG data

TODO `-n` option for debugging templates


### Target Functions

TODO function signuature and registration

TODO custom targets and overriding (again: don't change default targets)

TODO access to EVENT and CONFIG data

TODO passing of template variables
 