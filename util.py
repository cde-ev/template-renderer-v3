from data import (Event, EventPart, EventTrack, Registration, Course, registration_sort_key,
                  CourseTrackStati, RegistrationPartStati)
from typing import Iterable, Union, Dict, Tuple, List, Optional


def get_active_registrations(event: Event, parts: Iterable[EventPart] = None, include_guests: bool = False,
                             list_consent_only: bool = False, minors_only: bool = False):
    """
    Construct a list of all active participants of an event, possibly filtered by active parts, list_consent and age.

    :param event: The Event data
    :param parts: The event parts to check the registration for activity. If not given, all event parts are considered
    :param include_guests: If true, `RegistrationPartStati.guest` is considered as acitve. Otherwise only `participant`.
    :param list_consent_only: If true, only registrations with list_consent == True are returned
    :param minors_only: If true, only minors are returned
    :rtype: List[data.Registration]
    """
    if parts is None:
        parts = event.parts
    active_stati = [RegistrationPartStati.participant]
    if include_guests:
        active_stati.append(RegistrationPartStati.guest)

    return [r
            for r in event.registrations
            if any(r.parts[part].status in active_stati for part in parts)
                and (not list_consent_only or r.list_consent)
                and (not minors_only or r.age_class.is_minor)]


def get_nametag_courses(registration: Registration, tracks: Iterable[EventTrack], merge=True,
                        second_always_right=False) -> Tuple[List[Optional[Course]], bool, bool]:
    """Get the courses to be printed on the nametag from a list of the event tracks and the registration

    :param registration: The registration to get its courses
    :param tracks: The list of event tracks to get the courses (e.g. only the tracks of one EventPart)
    :param merge: Merge equal courses of the first and second track
    :param second_always_right: Return a None value to push the second course to the right, if the participant is
        not present in the first track's part
    :returns The reduced list of courses, a flag to indicate if the courses have been merged and a flag to indicate
        if the persona attends at at least one course.
    """
    courses: List[Optional[Course]] = []
    for t in tracks:
        reg_track = registration.tracks[t]
        if reg_track.registration_part.status.is_present:
            courses.append(registration.tracks[t].course)
        elif second_always_right:
            courses.append(None)

    attends_any_course = any(course is not None for course in courses)

    if merge:
        if len(courses) > 1 and courses[0] is courses[1] and courses[0] is not None:
            return [courses[0]], True, attends_any_course
        else:
            return courses, False, attends_any_course
    else:
        return courses, False, attends_any_course


def gather_course_attendees(course: Course, part: EventPart = None)\
        -> Iterable[Tuple[Registration, Iterable[EventTrack]]]:
    """ Get a single list of all regular attendees (not instructors or guests) of a course (in all active tracks of the
    course)

    :param course: The course to gather its atttendees
    :param part: If given, only consider tracks in this part
    :return: A list of tuples, each representing a unique attendee of the course:
        (Registration: list of EventTracks, in which they attend the course)
    """
    regs: Dict[Registration, List[EventTrack]] = {}
    for event_track, course_track in course.tracks.items():
        if not part or event_track in part.tracks:
            for reg, instr in course_track.attendees:
                if (not instr and course_track.status == CourseTrackStati.active
                        and reg.tracks[event_track].registration_part.status == RegistrationPartStati.participant):
                    if reg in regs:
                        regs[reg].append(event_track)
                    else:
                        regs[reg] = [event_track]

    return [(r, regs[r]) for r in sorted(regs.keys(), key=registration_sort_key)]


def generate_part_jobnames(event: Event) -> Dict[EventPart, str]:
    """
    Helper function to generate a filename suffix for each event part to be used in jobnames.

    It uses sanitize_filename() to transform each part's shortname into a safe filename suffix. Afterwards, it appends
    the part's id to all ambiguous names, if any.
    :param event: The event to get the parts from
    :return: A dict mapping each event part object to its safe jobname suffix
    """
    result = {part: sanitize_filename(part.shortname)
              for part in event.parts}

    # Find ambiguous suffixes
    reverse_result: Dict[str, EventPart] = {}
    ambiguous_parts = set()
    for part, suffix in result.items():
        if suffix in reverse_result:
            ambiguous_parts.add(reverse_result[suffix])
            ambiguous_parts.add(part)
        reverse_result[suffix] = part

    # Add part id to parts with ambiguous suffix
    for part in ambiguous_parts:
        result[part] += '_{}'.format(part.id)

    return result


# According to https://en.wikipedia.org/wiki/Filename#Reserved_characters_and_words
# but we allow dots.
FILENAME_SANITIZE_MAP = str.maketrans({
    x: '_'
    for x in "/\\?%*:|\"<> "})

def sanitize_filename(name: str) -> str:
    """
    Helper function to sanitize filenames (strip forbidden and problematic characters).

    :param name: The unsafe name
    :return: A sanitized version of the name to be used as filename
    """
    return name.translate(FILENAME_SANITIZE_MAP)
