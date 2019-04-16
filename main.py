import argparse
import configparser
import importlib.util
import multiprocessing
import os
import concurrent.futures
import sys
import traceback

# define some static paths
THIS_DIR = os.path.abspath(os.path.dirname(__file__))
DEFAULT_DIR = os.path.join(THIS_DIR, 'default')
OUTPUT_DIR = os.path.join(THIS_DIR, 'output')

# Make sure the additional modules are found
sys.path.insert(0, THIS_DIR)

import render
import data
import globals

# Some info for cli argument defaults
default_threads = multiprocessing.cpu_count() - 1
default_output_dir = os.path.join(os.path.dirname(__file__), 'output')

# parse CLI arguments
parser = argparse.ArgumentParser(description='Template renderer for CdE Events')
parser.add_argument('targets', metavar='TARGETS', type=str, nargs='+',
                    help='Specifies which templates to render.')
parser.add_argument('-c', '--custom-dir', default=os.path.join(THIS_DIR, 'custom'),
                    help="Path of custom directory to find config file, templates and assets.")
parser.add_argument('-i', '--input', default="export_event.json",
                    help="Path of custom directory to find config file, templates and assets.")
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
import default.targets
custom_targets_file = os.path.join(args.custom_dir, 'targets.py')
if os.path.isfile(custom_targets_file):
    spec = importlib.util.spec_from_file_location("custom.targets", custom_targets_file)
    foo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(foo)

# Construct Jinja environment
jinja_env = render.get_latex_jinja_env(template_dirs, asset_dirs)


# read input json file
event = data.load_input_file(args.input)


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
        render_tasks = globals.TARGETS[target](event, config, OUTPUT_DIR, args.match)
        for task in render_tasks:
            future = executor.submit(shutter.wrap(render.render_template),
                                     *task, cleanup=not args.no_cleanup, jinja_env=jinja_env)
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
