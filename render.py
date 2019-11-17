import datetime
import functools
import re
import os
import subprocess
from typing import Iterable, Any, Optional

import jinja2


def escape_tex(value, linebreaks=False):
    """
    Escaping filter for the LaTeX Jinja2 environment.

    :param value: The raw string to be escaped for usage in TeX files
    :param linebreaks: If true, linebreaks are converted to TeX linebreaks ("\\")
    :return: The escaped string
    """
    if value is None:
        return ""
    latex_subs = [
        (re.compile(r'\\'), r'\\textbackslash'),
        (re.compile(r'([{}_#%&$])'), r'\\\1'),
        (re.compile(r'~'), r'\~{}'),
        (re.compile(r'\^'), r'\^{}'),
        (re.compile(r'"'), r"''"),
    ]
    if linebreaks:
        latex_subs.append((re.compile(r'\n'), r'\\\\'))

    res = str(value)
    for pattern, replacement in latex_subs:
        res = pattern.sub(replacement, res)
    return res


def filter_inverse_chunks(value: Iterable[Any], n=2):
    """
    A generator to be used as jinja filter that reverses chunks of n elements from the given iterator.
    The last element will be repeated to fill the last chunk if neccessary.

    :param value: Input iterator
    :param n: Chunk size
    """
    end = False
    iterator = iter(value)
    while not end:
        chunk = []
        for i in range(n):
            try:
                last = next(iterator)
            except StopIteration:
                end = True
                if i == 0:
                    break
            chunk.append(last)
        for i in reversed(chunk):
            yield i


def filter_date(value: Optional[datetime.date], format='%d.%m.%Y'):
    """
    A filter to format date values.

    :type value: datetime.date or None
    :param format: a format string for the strftime function
    """
    if value is None:
        return ''
    return value.strftime(format)


def filter_datetime(value: Optional[datetime.datetime], format='%d.%m.%Y~%H:%M', timezone=datetime.timezone.utc):
    """
    A filter to format date values.

    :type value: datetime.datetime or None
    :param format: a format string for the strftime function
    :param timezone: A timezone to convert the datetime object to before formatting
    """
    if value is None:
        return ''
    return value.astimezone(timezone).strftime(format)


def find_asset(name: str, asset_dirs: Iterable[str]):
    """
    Search the given asset directories for an asset with a given name and return its full path with '/' delimiters (to
    be used in TeX).

    :param name: The filename to search for. (May contain '/' to search in subdirectories.)
    :param asset_dirs: List of asset directories to search for the given asset name
    :type asset_dirs: [str]
    :rtype: str
    """
    for d in asset_dirs:
        fullname = os.path.join(d, name.replace('/', os.sep))
        if os.path.exists(fullname):
            return fullname.replace(os.sep, '/')
    return None


def get_latex_jinja_env(template_paths, asset_paths, timezone):
    """
    Factory function to construct the Jinja2 Environment object. It sets the template loader, the Jinja variable-,
    block- and comment delimiters, some additional options and the required filters and globals.

    :param template_paths: A list of directories to be passed to the jinja2.FileSystemLoader to search for templates
    :type template_paths: [str]
    :param asset_paths: A list of directories to be searched for assets, using the `find_asset` template function
    :type asset_paths: [str]
    :param timezone: The timezone to show timestamps in
    :type timezone: datetime.timezone
    :return: The configured Jinja2 Environment
    :rtype: jinja2.Environment
    """
    latex_jinja2_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(template_paths),
        block_start_string='<<%',
        block_end_string='%>>',
        variable_start_string='<<<',
        variable_end_string='>>>',
        comment_start_string='<<#',
        comment_end_string='#>>',
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=False,
        extensions=['jinja2.ext.do']
    )
    latex_jinja2_env.filters['e'] = escape_tex
    latex_jinja2_env.filters['inverse_chunks'] = filter_inverse_chunks
    latex_jinja2_env.filters['date'] = filter_date
    latex_jinja2_env.filters['datetime'] = functools.partial(filter_datetime, timezone=timezone)
    latex_jinja2_env.globals['now'] = datetime.datetime.now()
    latex_jinja2_env.globals['find_asset'] = functools.partial(find_asset, asset_dirs=asset_paths)

    return latex_jinja2_env


class ScheduleShutter:
    """
    A small helper class to cancel scheduled function executions by wrapping the functions.
    """
    def __init__(self):
        self.shutdown = False

    def wrap(self, fun):
        @functools.wraps(fun)
        def wrapped(*args, **kwargs):
            if self.shutdown:
                return
            return fun(*args, **kwargs)
        return wrapped


class RenderTask:
    def __init__(self, template_name: str, job_name: str, template_args=None, double_tex=False):
        self.template_name = template_name
        self.job_name = job_name
        self.template_args = template_args or {}
        self.double_tex = double_tex


def render_template(task, output_dir, jinja_env, cleanup=True):
    """
    Helper method to do the Jinja template rendering and LuaLaTeX execution.

    :param task: A RenderJob tuple to define the job to be done. It contains the following fields:
        template_name: filename of the Jinja template to render and compile
        job_name: TeX jobname, defines filename of the output files
        template_args: dict of arguments to be passed to the template
        double_tex: if True, execute LuaLaTeX twice to allow building of links, tocs, longtables etc.
    :type task: RenderTask
    :param output_dir: Output directory. Absolute or relative path from working directory.
    :type output_dir: str
    :param jinja_env: The jinja Environment to use for template rendering
    :param cleanup:
    :type cleanup: bool
    :return: True if rendering was successful
    :rtype: bool
    """
    # Get template
    template = jinja_env.get_template(task.template_name)

    # render template
    outfile_name = task.job_name + '.tex'
    with open(os.path.join(output_dir, outfile_name), 'w', encoding='utf-8') as outfile:
        outfile.write(template.render(**task.template_args))

    # Execute LuaLaTeX once
    print('Compiling {}{} ...'.format(task.job_name, " once" if task.double_tex else ""))
    process = subprocess.Popen(['lualatex', '--interaction=batchmode', outfile_name],
                               stdin=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL,
                               cwd=output_dir)
    process.wait()
    rc = process.returncode
    success = True
    if rc != 0:
        print("Compiling '{}' failed.{}".format(task.job_name, " (run 1)" if task.double_tex else ""))
        success = False

    # Execute LuaLaTeX second time
    if success and task.double_tex:
        print('Compiling {} a second time ...'.format(task.job_name))
        process = subprocess.Popen(['lualatex', '--interaction=batchmode', outfile_name],
                                   stdin=subprocess.DEVNULL,
                                   stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL,
                                   cwd=output_dir)
        process.wait()
        rc = process.returncode
        if rc != 0:
            print("Compiling '{}' failed. (run 2)")
            success = False

    # Clean up
    if cleanup and success:
        exp = re.compile(r'^{}\.(.+)$'.format(re.escape(task.job_name)))
        for f in os.listdir(output_dir):
            match = re.match(exp, f)
            if match and match.group(1) not in ('pdf',):
                os.remove(os.path.join(output_dir, f))

    return success
