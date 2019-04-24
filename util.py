from data import Event, EventPart, RegistrationPartStati
from typing import Iterable, Union


def get_registrations(event: Event, parts: Iterable[EventPart] = None, stati: Iterable[RegistrationPartStati] = None,
                      list_consent_only: bool = False, minors_only: bool = False):
    if parts is None:
        parts = event.parts
    if stati is None:
        stati = [RegistrationPartStati.participant]

    result = [r for r in event.registrations if any(r.parts[part].status in stati for part in parts)]

    if list_consent_only:
        result = [r for r in result if r.list_consent]

    if minors_only:
        result = [r for r in result if r.age_class.is_minor]

    return result


def get_tracks(event: Event, parts: Iterable[EventPart] = None):
    if parts is None:
        parts = event.parts

    result = [t for t in event.tracks if t.part in parts]

    return result


def get_parts_without_tracks(event: Event, parts: Iterable[EventPart] = None):
    if parts is None:
        parts = event.parts

    result = [p for p in parts if not p.tracks]

    return result


def get_nametag_courses(registration, tracks, merge=True, second_always_right=False):
    """Get the courses to be printed on the nametag from a list of the event tracks and the registration

    :param merge: Merge equal courses of the first and second track
    :param second_always_right: Return a None value to push the second course to the right, if the participant is
        not present in the first track's part
    :returns The reduced list of courses and a flag to indicate if the courses have been merged
    :rtype ([courses], bool)
    """
    courses = []
    for t in tracks:
        reg_track = registration.tracks[t]
        if reg_track.registration_part.status.is_present:
            courses.append(registration.tracks[t].course)
        elif second_always_right:
            courses.append(None)

    if merge:
        if len(courses) > 1 and courses[0] is courses[1]:
            return courses[0], True
        else:
            return courses, False
    else:
        return courses, False
