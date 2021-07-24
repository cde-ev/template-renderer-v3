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
import operator
import pathlib
import re
import csv
from typing import List, Tuple, Iterable, Dict, Any, Optional
import configparser

import util
from globals import target_function
from render import RenderTask
from data import Event, EventPart, RegistrationPartStati, CourseTrackStati, Lodgement, Registration, Course, \
    EventTrack, LodgementGroup


@target_function
def tnletters(event: Event, _config, output_dir: pathlib.Path, match):
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
    with open(output_dir / 'tnletter_mailmerge.csv', 'w') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["persona.forename", "persona.family_name", "persona.username", "attachment"])
        for r in participants:
            writer.writerow([r.name.salutation,
                             r.name.family_name,
                             r.email,
                             output_dir.resolve() / f"tnletter_{r.id}.pdf"])

    return [RenderTask('tnletter.tex', 'tnletter_{}'.format(r.id), {'registration': r}, False)
            for r in participants if r.is_present]


@target_function
def tnlists(event: Event, config, _output_dir, _match):
    """Render the participant lists (one with, one without course, one for the orgas, one for the blackboard)"""

    participants = util.get_active_registrations(event, include_guests=config.getboolean('tnlist', 'show_guests'))
    participants_lc = util.get_active_registrations(event, include_guests=config.getboolean('tnlist', 'show_guests'),
                                                    list_consent_only=True)
    participants_orga = util.get_active_registrations(event,
                                                      include_guests=config.getboolean('tnlist', 'show_guests_orga'))

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
def tnlists_per_part(event: Event, config, _output_dir, _match):
    """Render the participant lists (one with, one without course, one for the orgas, one for the blackboard)
    individually for each part."""

    tasks = []
    part_suffixes = util.generate_part_jobnames(event)

    for part in event.parts:
        participants = util.get_active_registrations(event, parts=(part,),
                                                     include_guests=config.getboolean('tnlist', 'show_guests'))
        participants_lc = util.get_active_registrations(event, parts=(part,),
                                                        include_guests=config.getboolean('tnlist', 'show_guests'),
                                                        list_consent_only=True)
        participants_orga = util.get_active_registrations(
            event, parts=(part,), include_guests=config.getboolean('tnlist', 'show_guests_orga'))

        tasks.append(RenderTask('tnlist.tex', 'tnlist_{}'.format(part_suffixes[part]),
                                {'registrations': participants_lc, 'parts': [part], 'tracks': part.tracks,
                                 'title_suffix': " ({})".format(part.title)},
                                True))
        tasks.append(RenderTask('tnlist_blackboard.tex', 'tnlist_blackboard_{}'.format(part_suffixes[part]),
                                {'registrations': participants, 'parts': [part], 'tracks': part.tracks,
                                 'title_suffix': " ({})".format(part.title)},
                                True))
        tasks.append(RenderTask('tnlist_orga.tex', 'tnlist_orga_{}'.format(part_suffixes[part]),
                                {'registrations': participants_orga, 'parts': [part], 'tracks': part.tracks,
                                 'title_suffix': " ({})".format(part.title)},
                                True))

    return tasks


@target_function
def minor_checklists(event: Event, _config, _output_idr, _match):
    """Render a list of all minors with columns to check their presence every evening (one document per event part)"""
    part_suffixes = util.generate_part_jobnames(event)

    return [
        RenderTask('tnlist_minors.tex', 'tnlist_minors_{}'.format(part_suffixes[part]),
                   {'part': part,
                    'registrations': util.get_active_registrations(
                        event, parts=(part,), include_guests=True, minors_only=True)},
                   True)
        for part in event.parts
    ]


@target_function
def tnlists_cl(event: Event, _config, _output_dir, _match):
    """Render participant listings of individual courses and rooms (course rooms + lodgements)

    Course rooms and lodgements are combined by their name.
    """
    targets = []
    part_suffixes = util.generate_part_jobnames(event)

    # Inhabitant and course-attendee listings for each room for each part
    for part in event.parts:
        # We need to build the rooms_by_name dict new for every part, as the rooms are dependent on the course_rooms of
        # the courses taking place in that part.
        rooms_by_name = {l.title: (l, []) for l in event.lodgements}\
            # type: Dict[str, Tuple[Optional[Lodgement], List[Tuple[Course, List[EventTrack]]]]]
        for c in event.courses:
            course_room = c.fields.get(event.course_room_field, None)  # type: Any
            course_tracks = [t for t in part.tracks if c.tracks[t].status == CourseTrackStati.active]
            if course_room and course_tracks:
                if course_room in rooms_by_name:
                    rooms_by_name[course_room][1].append((c, course_tracks))
                else:
                    rooms_by_name[course_room] = (None, [(c, course_tracks)])

        targets.append(RenderTask('room_lists.tex',
                                  'room_list_{}'.format(part_suffixes[part]),
                                  {'part': part,
                                   'rooms': sorted([(t, l, cs) for t, (l, cs) in rooms_by_name.items()],
                                                   key=operator.itemgetter(0))},
                                  True))

    # Attendee-listing for course instructors
    targets.append(RenderTask('tnlist_kl.tex', 'tnlist_kl', {}, True))

    return targets


@target_function
def courselist(_event: Event, _config, _output_dir, _match):
    """Render the courselists"""

    return [RenderTask('courselist.tex', 'courselist', {}, True)]


@target_function
def nametags(event: Event, config, _output_dir, _match):
    """Render nametags."""
    per_part = config['nametags'].getboolean('per_part', fallback=(len(event.parts) > 2 or len(event.tracks) > 2))

    meals = get_meals(config, event.registrations)

    if per_part:
        part_suffixes = util.generate_part_jobnames(event)
        return [RenderTask('nametags.tex',
                           'nametags_{}'.format(part_suffixes[part]),
                           {'registration_groups': group_participants(
                               event, config, (p for p in event.registrations if p.parts[part].status.is_present),
                               part),
                            'part': part,
                            'meals': meals},
                           False)
                for part in event.parts]
    else:
        return RenderTask('nametags.tex',
                          'nametags',
                          {'registration_groups': group_participants(
                               event, config, (p for p in event.registrations if p.is_present), event.parts[0]),
                           'meals': meals},
                          False),


class Meals(enum.IntEnum):
    meat = 0
    vegetarian = 1
    vegan = 2
    special = 3
    halfmeat1 = 4
    halfmeat2 = 5


def group_participants(event: Event, config: configparser.ConfigParser, participants: Iterable[Registration],
                       part: EventPart)\
        -> List[Tuple[str, List[Registration]]]:
    """ Helper function for grouping the participants by age and lodgement for different nametag colors.

    First, tries to assign, each participant to one of the config.nametags.age_groups. If not possible, tries to assign
    them to one of the config.nametags.lodgement_groups. If not possible assignes them to the 'others' group.

    :param config: The Config data
    :param participants: A list of participants to group
    :param part: The event part to consider for grouping by lodgement
    :return: List of groups as tuple of group name and list of participants
    :rtype: [(str, [Registration])]
    """
    age_groups = [(int(x), [])
                  for x in config.get('nametags', 'age_groups', fallback="").split(',')]\
        # type: List[Tuple[int, List[Registration]]]
    lodgement_groups = [(lg, [])
                        for lg in event.lodgement_groups]  # type: List[Tuple[LodgementGroup, List[Registration]]]
    others = []
    for p in participants:
        for max_age, l in age_groups:
            if p.age < max_age:
                l.append(p)
                break
        else:
            for lg, ps in lodgement_groups:
                if p.parts[part].lodgement and p.parts[part].lodgement.group is lg:
                    ps.append(p)
                    break
            else:
                others.append(p)
    return ([("age u{}".format(name), ps) for name, ps in age_groups]
            + [(lg.title, ps) for lg, ps in lodgement_groups]
            + [('others', others)])


def get_meals(config: configparser.ConfigParser, registrations: Iterable[Registration])\
        -> Dict[Registration, Optional[Meals]]:
    """
    Helper function for parsing the desired meal of a participant from its datafields.
    :param config: The Config data
    :param registrations: The list of all registrations of the event
    :type registrations: [data.Registration]
    :return: A dict, mapping registrations to a meal type from the Meals enum.
    """
    meal_field = config.get('data', 'meal_field', fallback=None)
    halfmeat_group_field = config.get('data', 'halfmeat_group_field', fallback=None)
    if not meal_field:
        return {r: None
                for r in registrations}

    meal_map = {alias: Meals(i)
                for i, alias in enumerate(config['data']['meal_values'].split(','))}  # type: Dict[Any, Meals]

    result = {}
    for r in registrations:
        meal = meal_map.get(r.fields.get(meal_field, ''), None)
        if meal == Meals.halfmeat1 and halfmeat_group_field and bool(r.fields.get(halfmeat_group_field, None)):
            meal = Meals.halfmeat2
        result[r] = meal

    return result
