"""
This module defines the default targets. Each target is a function, that is called with the parsed event data and the
combined configuration (default + custom config.ini) and returns any number of RenderTasks. Each RenderTask will
be rendered with Jinja2 and compiled with LuaLaTeX, to result in a single PDF document. If multiple Tasks are present
-- either from different targets, specified by the user, or from a single target -- some of them are compiled in
parallel.

To add a function to the list of targets, the `@target_function` decorator from the `globals` module should be used.
A render task function must take exactly four positional parameters:
* The data.Event object with the CdE event's data
* A configparser object with the combined configuration data
* The path of the output directory. This may be used to add some auxiliary files to the directory
* A string taken from the `--match` command line argument. It may be used to filter the render tasks.

It must return an iterable of render.RenderTask tuples. The iterable may be empty, if only auxiliary files are
generated. Additionally it should contain a docstring according to PEP 257. It will be displayed as description of the
target to the user.
"""

import re
import csv
import os

from globals import target_function
from render import RenderTask
from data import Event


@target_function
def tnletters(event: Event, config, output_dir, match):
    """Render the "Teilnehmerbrief" for each participant.

    This target renders the tnletter.tex template once for every participant of the event. The `--match` parameter may
    be used to filter the registrations by name and only render some of their letters.
    """
    # Filter registrations
    if match is not None:
        regex = re.compile(match)
        participants = [r for r in event.registrations if regex.search("{} {}".format(r.name.given_names,
                                                                                       r.name.family_name))]
    else:
        participants = event.registrations

    # Create MailMerge CSV file
    with open(os.path.join(output_dir, 'tnletter_mailmerge.csv'), 'w') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["persona.given_names", "persona.familyname", "persona.username", "attachment"])
        for r in participants:
            writer.writerow([r.name.given_names,
                             r.name.family_name,
                             r.email,
                             os.path.join(os.path.realpath(output_dir), "tnletter_{}.pdf".format(r.id))])

    return [RenderTask('tnletter.tex', 'tnletter_{}'.format(r.id), {'registration': r}, False)
            for r in participants if r.is_present]


@target_function
def tnlists(event: Event, config, output_dir, match):
    """Render the participant lists (one with, one without course, one for the orgas, one for the blackboard)"""

    tasks = [
        RenderTask('tnlist.tex', 'tnlist', {'registrations': [p for p in event.registrations if p.list_consent]}, True),
        RenderTask('tnlist_blackboard.tex', 'tnlist_blackboard', {'registrations': event.registrations}, True),
        RenderTask('tnlist_orga.tex', 'tnlist_orga', {'registrations': event.registrations}, True),
    ]

    return tasks


@target_function
def tnlists_per_part(event: Event, config, output_dir, match):
    """Render the participant lists individually for each part."""

    tasks = []

    for part in event.parts:
        tasks.append(RenderTask('tnlist.tex', 'tnlist_{}'.format(part.id),
                                {'registrations': [p for p in event.registrations
                                                  if p.list_consent and p.parts[part].status.is_present]}, True))
        tasks.append(RenderTask('tnlist_blackboard.tex', 'tnlist_blackboard_{}'.format(part.id),
                                {'registrations': [p for p in event.registrations
                                                  if p.parts[part].status.is_present]}, True))
        tasks.append(RenderTask('tnlist_orga.tex', 'tnlist_orga_{}'.format(part.id),
                                {'registrations': [p for p in event.registrations
                                                  if p.parts[part].status.is_present]}, True))

    return tasks


@target_function
def courselist(event: Event, config, output_dir, match):
    """Render the courselists"""

    return [RenderTask('courselist.tex', 'courselist', {}, True)]


@target_function
def nametags(event: Event, config, output_dir, match):
    # TODO implement different grouping schemas (configurable via config)
    r_blocks = [(i, []) for i in [14, 16, 18, 22, 25, 30, 100]]
    for p in event.registrations:
        if p.is_present:
            for max_age, block in r_blocks:
                age = p.age
                if age < max_age:
                    block.append(p)
                    break

    return RenderTask('nametags.tex',
                      'nametags',
                      {'registration_blocks': [("age u{}".format(name), ps) for name, ps in r_blocks]},
                      False),
