#!/usr/bin/env python3
import argparse
import configparser
import importlib.util
import multiprocessing
import os
import concurrent.futures
import sys
import traceback

import pytz


# define some static paths
THIS_DIR = os.path.abspath(os.path.dirname(__file__))
DEFAULT_DIR = os.path.join(THIS_DIR, 'default')

# Make sure the additional modules are found
sys.path.insert(0, THIS_DIR)

import render
import data
import globals
import util


# Some info for cli argument defaults
default_threads = max(1, multiprocessing.cpu_count() - 1)
default_output_dir = os.path.join(os.path.dirname(__file__), 'output')

# parse CLI arguments
parser = argparse.ArgumentParser(description='Template renderer for CdE Events')
parser.add_argument('targets', metavar='TARGETS', type=str, nargs='*',
                    help='Specifies which templates to render.')
parser.add_argument('-c', '--custom-dir', default=os.path.join(THIS_DIR, 'custom'),
                    help="Path of custom directory to find config file, templates and assets. Defaults to the `custom` "
                         "directory in the script's directory.")
parser.add_argument('-i', '--input', default="partial_export_event.json",
                    help="Path of the input file, exported from the CdEdb. Typically xxx_partial_export_event.json.")
parser.add_argument('-o', '--output', default=os.path.join(THIS_DIR, 'output'),
                    help="Path of the output directory. Defaults to the `output` directory in the script's directory. "
                         "The directory must exist.")
parser.add_argument('-j', '--max-threads', type=int, default=default_threads,
                    help='Maximum number of concurrent template renderings and LuaLaTeX compile processes. '
                         'Defaults to {} on your system.'.format(default_threads))
parser.add_argument('-m', '--match', type=str, default=None,
                    help='A string or regex to be passed to the tasks to match subtasks against. E.g. for '
                         'tnletters only letters with recipients\' name matching to the given string are compiled.')
parser.add_argument('-n', '--no-cleanup', action='store_const', const=True, default=False,
                    help='Don\'t delete rendered template and LaTeX auxiliary files after compilation.')
args = parser.parse_args()


# Read config (default config and -- if available -- custom config)
config = configparser.ConfigParser()
with open(os.path.join(DEFAULT_DIR, 'config.ini')) as f:
    config.read_file(f)
config.read((os.path.join(args.custom_dir, 'config.ini'),))

# Initialize lists of template and asset directories
template_dirs = [os.path.join(DEFAULT_DIR, 'templates')]
custom_template_dir = os.path.join(args.custom_dir, 'templates')
if os.path.isdir(custom_template_dir):
    template_dirs.insert(0, custom_template_dir)
asset_dirs = [os.path.join(DEFAULT_DIR, 'assets')]
custom_asset_dir = os.path.join(args.custom_dir, 'assets')
if os.path.isdir(custom_asset_dir):
    asset_dirs.insert(0, os.path.abspath(custom_asset_dir))

# Import targets specifications
import default.targets  # type: ignore
custom_targets_file = os.path.join(args.custom_dir, 'targets.py')
if os.path.isfile(custom_targets_file):
    spec = importlib.util.spec_from_file_location("custom.targets", custom_targets_file)
    foo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(foo)  # type: ignore

# read input json file
event = data.load_input_file(args.input)

# Construct Jinja environment
timezone = pytz.timezone(config.get('data', 'timezone'))
jinja_env = render.get_latex_jinja_env(template_dirs, asset_dirs, timezone)
jinja_env.globals['CONFIG'] = config
jinja_env.globals['EVENT'] = event
jinja_env.globals['ENUMS'] = {e.__name__: e for e in data.ALL_ENUMS}
jinja_env.globals['UTIL'] = util


# if no targets are given, show help output
if not args.targets:
    if globals.TARGETS:
        max_name_length = max(len(name) for name in globals.TARGETS)
        print("No targets given. Please specify one or more of the following targets:\n")
        for target_name, target_fn in globals.TARGETS.items():
            # TODO use shutil.get_terminal_size and textwrap.fill and some fancy logic to adapt docstrings to terminal
            print("{:{}}".format(target_name + ':', max_name_length+2), end='')
            if target_fn.__doc__:
                print(('\n' + ' ' * (max_name_length+2))
                      .join(l.strip() for l in target_fn.__doc__.strip().splitlines()))
            print()
    else:
        print("No targets are available. This script is pretty useless. Take a look at the documentation,"
              " to see, how targets can be added")
    sys.exit(1)


# Some global variables for the rendering threads
count_tasks = 0
count_failures = 0
futures = []
shutter = render.ScheduleShutter()

with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_threads) as executor:
    # Issue all render tasks to executor
    for target in args.targets:
        if target not in globals.TARGETS.keys():
            print("Target '{}' is unknown".format(target))
            continue
        render_tasks = globals.TARGETS[target](event, config, args.output, args.match)
        for task in render_tasks:
            future = executor.submit(shutter.wrap(render.render_template),
                                     task, output_dir=args.output, cleanup=not args.no_cleanup, jinja_env=jinja_env)
            futures.append(future)
        count_tasks += len(render_tasks)

    print("Starting {} Tasks, {} at a time ...".format(count_tasks, args.max_threads))

    # Wait for all futures (render tasks) to complete
    try:
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                if not result:
                    count_failures += 1
            except Exception as exc:
                count_failures += 1
                traceback.print_exception(type(exc), exc, exc.__traceback__)
    except (KeyboardInterrupt, SystemExit):
        shutter.shutdown = True
        print("Waiting for running compile tasks to be finished ...")
        executor.shutdown()
        print("All pending compile tasks have been cancelled. Stopping.")
        sys.exit(1)

print("Finished all tasks.")
if count_failures > 0:
    print("{} of {} render tasks failed. See above exceptions or LuaLaTeX log files\n"
          "for more information".format(count_failures, count_tasks))
    sys.exit(1)
