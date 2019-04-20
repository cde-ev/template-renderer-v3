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
import enum
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
        RenderTask('tnlist.tex', 'tnlist', {}, True),
        RenderTask('tnlist_blackboard.tex', 'tnlist_blackboard', {}, True),
        RenderTask('tnlist_orga.tex', 'tnlist_orga', {}, True),
    ]

    return tasks


@target_function
def tnlists_per_part(event: Event, config, output_dir, match):
    """Render the participant lists individually for each part."""

    tasks = []

    for part in event.parts:
        tasks.append(RenderTask('tnlist.tex', 'tnlist_{}'.format(part.id),
                                {'parts': [part]}, True))
        tasks.append(RenderTask('tnlist_blackboard.tex', 'tnlist_blackboard_{}'.format(part.id),
                                {'parts': [part]}, True))
        tasks.append(RenderTask('tnlist_orga.tex', 'tnlist_orga_{}'.format(part.id),
                                {'parts': [part]}, True))

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

    def get_courses(registration, tracks, force_merge=False):
        """Get the courses to be printed on the nametag from a list of the event tracks and the registration

        :param force_merge: Merge equal courses, even if the config doesn't say so
        :returns The reduced list of courses and a flag to indicate if the courses have been merged
        :rtype ([courses], bool)
        """
        courses = []
        for t in tracks:
            reg_track = registration.tracks[t]
            if reg_track.registration_part.status.is_present:
                courses.append(registration.tracks[t].course)
            elif config['nametags']['second_track_always_right']:
                courses.append(None)

        if config['nametags']['merge_courses'] or force_merge:
            if len(courses) > 1 and courses[0] is courses[1]:
                return courses[0], True
            else:
                return courses, False
        else:
            return courses, False

    meals = get_meals(config, event.registrations)

    if config['nametags'].getboolean('per_part', fallback=(len(event.parts) > 2 or len(event.tracks) > 2)):
        return [RenderTask('nametags.tex',
                           'nametags_{}'.format(part.id),
                           {'registration_blocks': [("age u{}".format(name), ps) for name, ps in r_blocks],
                            'part': part,
                            'meals': meals,
                            'get_courses': get_courses},
                           False)
                for part in event.parts]
    else:
        return RenderTask('nametags.tex',
                          'nametags',
                          {'registration_blocks': [("age u{}".format(name), ps) for name, ps in r_blocks],
                           'meals': meals,
                           'get_courses': get_courses},
                          False),


class Meals(enum.IntEnum):
    meat = 0
    vegetarian = 1
    vegan = 2
    special = 3
    halfmeat1 = 4
    halfmeat2 = 5


def get_meals(config, registrations):
    """
    Helper function for parsing the desired meal of a participant from its datafields.
    :param config: The Config data
    :param registrations: The list of all registrations of the event
    :type registrations: [data.Registration]
    :return: A dict, mapping registrations to a meal type from the Meals enum.
    :rtype: Dict[data.Registration, Meals]
    """
    meal_field = config.get('data', 'meal_field', fallback=None)
    halfmeat_group_field = config.get('data', 'halfmeat_group_field', fallback=None)
    if not meal_field:
        return {r: None
                for r in registrations}

    meal_map = {alias: Meals(i)
                for i, alias in enumerate(config['data']['meal_values'].split(','))}

    result = {}
    for r in registrations:
        meal = meal_map.get(r.fields.get(meal_field, ''), None)
        if meal == Meals.halfmeat1 and halfmeat_group_field and bool(r.fields.get(halfmeat_group_field, None)):
            meal = Meals.halfmeat2
        result[r] = meal

    print(list(result.values()))
    return result

