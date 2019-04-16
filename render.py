import datetime
import functools
import re
import os
import subprocess

import jinja2


def escape_tex(value, linebreaks=False):
    """
    Escaping filter for the LaTeX Jinja2 environment.

    :param value: The raw string to be escaped for usage in TeX files
    :param linebreaks: If true, linebreaks are converted to TeX linebreaks ("\\")
    :return: The escaped string
    """
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


def filter_inverse_chunks(value, n=2):
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
            else:
                chunk.append(last)
        for i in reversed(chunk):
            yield i


def find_asset(name, asset_dirs):
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


def get_latex_jinja_env(template_paths, asset_paths):
    """
    Factory function to construct the Jinja2 Environment object. It sets the template loader, the Jinja variable-,
    block- and comment delimiters, some additional options and the required filters and globals.

    :param template_paths: A list of directories to be passed to the jinja2.FileSystemLoader to search for templates
    :type template_paths: [str]
    :param asset_paths: A list of directories to be searched for assets, using the `find_asset` template function
    :type asset_paths: [str]
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
        undefined=jinja2.StrictUndefined)
    latex_jinja2_env.filters['e'] = escape_tex
    latex_jinja2_env.filters['inverse_chunks'] = filter_inverse_chunks
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


def render_template(template_name, template_args, job_name, double_tex,
                    output_dir, jinja_env, cleanup=True):
    """
    Helper method to do the Jinja template rendering and LuaLaTeX execution.

    :param template_name: filename of the Jinja template to be rendered
    :type template_name: str
    :param template_args: Dict of arguments to be passed to the template
    :type template_args: dict
    :param job_name: LuaLaTeX jobname; specifies names of the output files
    :type job_name: str
    :param double_tex: Execute LuaLaTeX twice to allow building of links, tocs, longtables etc.
    :param output_dir: Output directory. Absolute or relative path from working directory.
    :type output_dir: str
    :param jinja_env: The jinja Environment to use for template rendering
    :param cleanup:
    :type cleanup: bool
    :return: True if rendering was successful
    :rtype: bool
    """
    # Get template
    template = jinja_env.get_template(template_name)

    # render template
    outfile_name = job_name + '.tex'
    with open(os.path.join(output_dir, outfile_name), 'w', encoding='utf-8') as outfile:
        outfile.write(template.render(**template_args))

    # Execute LuaLaTeX once
    print('Compiling {}{} ...'.format(job_name, " once" if double_tex else ""))
    process = subprocess.Popen(['lualatex', '--interaction=batchmode', outfile_name],
                               stdin=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL,
                               cwd=output_dir)
    process.wait()
    rc = process.returncode
    success = True
    if rc != 0:
        print("Compiling '{}' failed.{}".format(job_name, " (run 1)" if double_tex else ""))
        success = False

    # Execute LuaLaTeX second time
    if success and double_tex:
        print('Compiling {} a second time ...'.format(job_name))
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
        exp = re.compile(r'^{}\.(.+)$'.format(re.escape(job_name)))
        for f in os.listdir(output_dir):
            match = re.match(exp, f)
            if match and match.group(1) not in ('pdf', 'log', 'tex'):
                os.remove(os.path.join(output_dir, f))
            elif match and match.group(1) == 'log':
                if not os.path.exists(os.path.join(output_dir, 'log')):
                    os.mkdir(os.path.join(output_dir, 'log'))
                os.rename(os.path.join(output_dir, f), os.path.join(os.path.join(output_dir, 'log'), f))
            elif match and match.group(1) == 'tex':
                if not os.path.exists(os.path.join(output_dir, 'tex')):
                    os.mkdir(os.path.join(output_dir, 'tex'))
                os.rename(os.path.join(output_dir, f), os.path.join(os.path.join(output_dir, 'tex'), f))

    return success
