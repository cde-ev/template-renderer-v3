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

import util
from globals import target_function
from render import RenderTask
from data import Event, RegistrationPartStati


@target_function
def tnletters(event: Event, config, output_dir, match):
    """Render the "Teilnehmerbrief" for each participant.

    This target renders the tnletter.tex template once for every participant of the event. The `--match` parameter may
    be used to filter the registrations by name and only render some of their letters.

    The target function also creates an CSV file for use with Tunderbird Mailmerge in the output directory.
    """
    # Filter registrations
    participants = [r for r in event.registrations
                    if any(rp.status == RegistrationPartStati.participant for rp in r.parts.values())]
    if match is not None:
        regex = re.compile(match)
        participants = [r for r in participants
                        if regex.search("{} {}".format(r.name.given_names, r.name.family_name))]

    # Create MailMerge CSV file
    with open(os.path.join(output_dir, 'tnletter_mailmerge.csv'), 'w') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["persona.given_names", "persona.family_name", "persona.username", "attachment"])
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

    participants = util.get_active_registrations(event, include_guests=config['tnlist']['show_guests'])
    participants_lc = util.get_active_registrations(event, include_guests=config['tnlist']['show_guests'],
                                                    list_consent_only=True)
    participants_orga = util.get_active_registrations(event, include_guests=config['tnlist']['show_guests_orga'])

    tasks = [
        RenderTask('tnlist.tex', 'tnlist',
                   {'registrations': participants_lc, 'status_parts': [p for p in event.parts if not p.tracks],
                    'tracks': event.tracks},
                   True),
        RenderTask('tnlist.tex', 'tnlist_nocourse',
                   {'registrations': participants_lc, 'status_parts': event.parts if len(event.parts) > 1 else [],
                    'tracks': []},
                   True),
        RenderTask('tnlist_blackboard.tex', 'tnlist_blackboard',
                   {'registrations': participants, 'parts': event.parts, 'tracks': event.tracks},
                   True),
        RenderTask('tnlist_orga.tex', 'tnlist_orga',
                   {'registrations': participants_orga, 'parts': event.parts, 'tracks': event.tracks},
                   True),
    ]

    return tasks


@target_function
def tnlists_per_part(event: Event, config, output_dir, match):
    """Render the participant lists (one with, one without course, one for the orgas, one for the blackboard)
    individually for each part."""

    tasks = []

    for part in event.parts:
        participants = util.get_active_registrations(event, parts=(part,),
                                                     include_guests=config['tnlist']['show_guests'])
        participants_lc = util.get_active_registrations(event, parts=(part,),
                                                        include_guests=config['tnlist']['show_guests'],
                                                        list_consent_only=True)
        participants_orga = util.get_active_registrations(event, parts=(part,),
                                                          include_guests=config['tnlist']['show_guests_orga'])

        tasks.append(RenderTask('tnlist.tex', 'tnlist_{}'.format(part.id),
                                {'registrations': participants_lc, 'parts': [part], 'tracks': part.tracks,
                                 'title_suffix': " ({})".format(part.title)},
                                True))
        tasks.append(RenderTask('tnlist_blackboard.tex', 'tnlist_blackboard_{}'.format(part.id),
                                {'registrations': participants, 'parts': [part], 'tracks': part.tracks,
                                 'title_suffix': " ({})".format(part.title)},
                                True))
        tasks.append(RenderTask('tnlist_orga.tex', 'tnlist_orga_{}'.format(part.id),
                                {'registrations': participants_orga, 'parts': [part], 'tracks': part.tracks,
                                 'title_suffix': " ({})".format(part.title)},
                                True))

    return tasks


@target_function
def minor_checklist(event: Event, config, output_idr, match):
    """Render a list of all minors with columns to check their presence every evening"""

    return [RenderTask('tnlist_minors.tex', 'tnlist_minors', {}, True)]


@target_function
def minor_checklist_per_part(event: Event, config, output_idr, match):
    """Render a list of all minors for each part with columns to check their presence every evening"""

    tasks = []

    for part in event.parts:
        tasks.append(RenderTask('tnlist_minors.tex', 'tnlist_minors_{}'.format(part.id), {'parts': [part]}, True))

    return tasks


@target_function
def courselist(event: Event, config, output_dir, match):
    """Render the courselists"""

    return [RenderTask('courselist.tex', 'courselist', {}, True)]


@target_function
def nametags(event: Event, config, output_dir, match):
    """Render nametags."""
    per_part = config['nametags'].getboolean('per_part', fallback=(len(event.parts) > 2 or len(event.tracks) > 2))

    meals = get_meals(config, event.registrations)

    if per_part:
        return [RenderTask('nametags.tex',
                           'nametags_{}'.format(part.id),
                           {'registration_groups': group_participants(
                               config, (p for p in event.registrations if p.parts[part].status.is_present), part),
                            'part': part,
                            'meals': meals},
                           False)
                for part in event.parts]
    else:
        return RenderTask('nametags.tex',
                          'nametags',
                          {'registration_groups': group_participants(
                               config, (p for p in event.registrations if p.is_present), event.parts[0]),
                           'meals': meals},
                          False),


class Meals(enum.IntEnum):
    meat = 0
    vegetarian = 1
    vegan = 2
    special = 3
    halfmeat1 = 4
    halfmeat2 = 5


def group_participants(config, participants, part):
    """ Helper function for grouping the participants by age and lodgement for different nametag colors.

    First, tries to assign, each participant to one of the config.nametags.age_groups. If not possible, tries to assign
    them to one of the config.nametags.lodgement_groups. If not possible assignes them to the 'others' group.

    :param config: The Config data
    :param participants: A list of participants to group
    :return: List of groups as tuple of group name and list of participants
    :rtype: [(str, [data.Participant])]
    """
    age_groups = [(int(x), [])
                  for x in config.get('nametags', 'age_groups', fallback="").split(',')]
    lodgement_groups = [(re.compile(x.strip()), [])
                        for x in config.get('nametags', 'lodgement_groups', fallback="").split('\n')]
    others = []
    for p in participants:
        for max_age, l in age_groups:
            if p.age < max_age:
                l.append(p)
                break
        else:
            for regex, l in lodgement_groups:
                if p.parts[part].lodgement and regex.match(p.parts[part].lodgement.moniker):
                    l.append(p)
                    break
            else:
                others.append(p)
    return [("age u{}".format(name), ps) for name, ps in age_groups]\
           + [(regex.pattern, ps) for regex, ps in lodgement_groups]\
           + [('others', others)]


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

    return result

