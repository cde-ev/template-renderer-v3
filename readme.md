
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

* Python 3.6 or higher with
    * jinja2
    * pytz

* A LaTeX installation with LuaLaTeX and
    * koma-script
    * colortbl
    * xcolor
    * longtable
    * libertine (the *Linux Libertine* font) for the default templates

`lualatex` must be available in the $PATH to be called by the Python script.

#### Setting up Prerequisites on Linux systems
… on Ubuntu & Debian:
```
$ sudo apt install python3 python3-jinja2 python3-tz git \
                   texlive-latex-base texlive-latex-recommended texlive-latex-extra texlive-luatex texlive-fonts-extra \
                   texlive-lang-german
```

… on Arch Linux:
```
$ sudo pacman -S python python-jinja2 python-pytz texlive-core texlive-fontsextra git
```


If you're using Debian 9 (Stretch), you'll need to install the updated Jinja2 version from Debian Backports. See
https://backports.debian.org/ for instructions to add the backports package repository and run
`sudo apt install -t stretch-backports python3-jinja2`


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

To render and compile PDF files, first download a partial event export from the CdE Datenbank and store the file as
`partial_export_event.json` in the template renderer's directory:
CdEDB → Events → EVENT'S NAME → Downloads → Partial Event Export / JSON file

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
* `-i INPUT_FILE` to specify an other input file than `partial_export_event.json`
* `-c CUSTOM_DIR` to specify a custom directory (see Customization) different from the `custom` folder

A call with parameters might look like the following example:
```
$ ./main.py -i pa19_partial_export_event.json -c pa19/ tnlists
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
directory and redefine the same option there with a custom value. This way, you can easily update the template
rendering system later, including changes to the default configuration file, without need to merge the changes
manually. Additionally, you can apply version control (e.g. Git, SVN, Mercurial, …) to your custom directory to keep
track of changes to your customization independently from the development of the Template Rendering System. 

You can easily define your custom `config.ini` and use them for easy adjustment in your overriden or added templates
and target functions. Just specify your own configuration sections and options and they will be available in the
templates' `CONFIG` variable and the target functions' `config` parameter.  


### Assets

Asset files are typically graphics or fonts to be used within the templates. The default templates are shipped with
defaullt graphics, especially for the nametags. Additional graphics files can be included by config options (e.g. for
the event logo and course logos) or by overriding the templates. Assets are included into the templates using the
`find_asset()` template function. It searches for file with the requested name in the custom directory's `assets` folder
and – if no matching file has been found – in the `default/assets` folder.

This method allows to override default assets by creating an equally named file in the `assets/` folder in the custom
directory. Again, **don't change the contents of `defaults/assets/`**. Instead create an `assets/` folder in your
custom directory to override the default assets. 

Adding your own assets is just as easy: If you add them to your custom `assets/` folder, `find_asset()` will find them
by their filename and return the full path to be used in LaTeX. To use assets in subdirectories of the `assets/` folder,
pass the relative path of the asset file to `find_asset()`, using slashes (`/`) as path delimiter (even on Windows).


### Templates

The templates are rendered to TeX files by the Jinja2 template engine and afterwards compiled to PDF files by LuaLaTeX.
To avoid conflicts of the Jinja template syntax with TeX syntax (esp. considering curly brackets), we use a modified
Jinja environment with different delimiters:

|                | Default Jinja Syntax | Our Syntax           |
|----------------|----------------------|----------------------|
| Expressions    | `{{ expression }}`   | `<<< expression >>>` |
| Tags           | `{% tag %}`          | `<<% tag %>>`        |
| Comments       | `{# ... #}`          | `<<# ... #>>`        | 

This modification is consistent with the syntax of LaTeX templates in the CdE Datenbank source code.
Apart from that, the Jinja2 documentation applies to our templates: http://jinja.pocoo.org/docs/2.10/templates/

We use some global template variables, which are available in every template:

| Variable        | Type          | Description                                                |
|-----------------|---------------|------------------------------------------------------------|
| `EVENT`         | data.Event    | The full event data, as parsed from the CdEdb export file  |
| `CONFIG`        | ConfigParser  | The full configuration data from the `config.ini` files    |
| `UTIL`          | module        | The `util.py` module with some utilty functions            |
| `ENUMS`         | dict          | A dict of all enums defined in `data.py` to compare values |
| `now`           | datetime      | The timestamp of the starting of the script                |
| `find_asset`    | function      | Function to get full path of an asset by filename          |

Overriding templates works just like overriding assets: Just create a `templates/` folder in your custom directory and
place a file there, with the same name as the template to be overridden. Jinja will search this folder first for every
single template file to be loaded. Again, **don't change the default templates**. Instead copy the template to your
custom `templates/` directory and modify it there.

To allow reusing LaTeX code in different templates and overriding of specific portions of the templates, without copying
the whole template (which would make updates ineffective), we make heavy use of template inheritance and *blocks*.
In Jinja2, *Blocks* are placeholders with a default content, defined in a base template, which can be overriden by
sub-templates, *extending* this template.

The current inheritance tree of the default templates:
```
base.tex
├── lists.base.tex
│   ├─ courselist.tex
│   ├─ tnlist.tex
│   ├─ tnlist_blockboard.tex
│   ├─ tnlist_minors.tex
│   └─ tnlist_orga.tex
└── nametags.base.tex
    └─ nametags.tex
tnletter.base.tex
└── tnletter.tex
```
The primary purpose of `base.tex` and `lists.base.tex` is definition of common LaTeX code, used for all documents or
at least all lists. They may be overridden to change the overall look of the sub-templates. On the other hand,
`nametags.base.tex` and `tnletter.base.tex` contain the actual template code for the respective documents. They define
many *blocks*, which are **not** overridden by the default sub-templates. Since the sub-templates are used by the target
functions, this structure allows to override the sub-template to override only specific *blocks* of the base template. 


#### Additional Tricks

**Sub-Blocks:**
Sometimes *blocks* are nested within the base templates to allow redefinition of different sized parts of the code. For
example, the `nametags.base.tex` templates allows to override the nametags' rearside text (`block nametag_reartext`) or
the complete rearside (`block nametag_rearside`). When redefining/overriding a *block*, it es possible to use the
content of another *block*, including sub-blocks, as `<<< self.BLOCKNAME() >>>`. This way, it is possible to override a
*block* to rearrange its sub-blocks, but keep their individual default contents:
```
<<% block nametag_rearside %>>
    <<< self.nametag_rearlefticons >>>
    \hspace{\fill}
    <<< self.nametag_rearrighticons >>>
    
    
    \vspace{\fill}
    <<< self.nametag_reartext >>>
<<% endblock %>>
```


**No Cleanup:** By default, the `output/` directory is cleaned up after each successful rendering task. I.e. all files
with the jobname and an extension different from `.pdf` are deleted – including the generated `.tex` file and the
LuaLaTeX `.log`. The command line option `-n` of the Template Rendering System disables this cleanup, which is quite
helpful to debug the templates. 


### Target Functions

Target functions are defined in the `default/targets.py` and the `targets.py` file in the custom directory. They take
the event and configuration data and return a list of `RenderTask`s, each defining the template to be rendered, as set
of template variables and the output jobname. Target functions are registered in the list of available render targets,
using the `@globals.target_function` decorator. The function's name is used as identifier for the target; the function's
docstring (according to PEP 257) is used as description text in the command line user interface.

Each target function must have the following signature:
```python
@globals.target_function
def example_target(event: data.Event, config: ConfigParser, output_dir: str, match: str) -> [render.RenderTask]:
    ...
```
The `output_dir` parameter can be used to prepare the output directory for the render tasks. (e.g. creating an
additional file or subdirectory). The `match` parameter is optionally specified by the user (using the `-m` command line
parameter) and can be used to filter the objects (participants, courses, …) to be included when rendering the templates.

Each `RenderTask` takes four arguments to its constructor:
* `template_name`: filename of the template to be rendered
* `job_name`: LaTeX jobname, i.e. name of the output PDF file
* `template_args`: (optional) A dict of variables to be passed to the template
* `double_tex`: (optional) A boolean value. If true, LuaLaTeX is invoked twice to allow LaTeX macros to use the `.aux`
  file (e.g. references, longtables, …)

For some usecases it is required to create multiple `RenderTasks` for the same template, but with different jobnames and
template variables (e.g. the tnletter). 

Target functions in the custom `targets.py` override equally named default target functions. Thus, the custom
`targets.py` can be used to specify custom target functions and override default target functions. As for the
templates, please **don't change the `default/targets.py`**, but copy the target function to be changed to your custom
`targets.py` and modify it there. 
