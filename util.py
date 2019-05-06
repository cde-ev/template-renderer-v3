from data import Event, EventPart, RegistrationPartStati
from typing import Iterable, Union


def get_active_registrations(event: Event, parts: Iterable[EventPart] = None, include_guests: bool = False,
                             list_consent_only: bool = False, minors_only: bool = False):
    """
    Construct a list of all active participants of an event, possibly filtered by active parts, list_consent and age.

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
        if len(courses) > 1 and courses[0] is courses[1] and courses[0] is not None:
            return [courses[0]], True
        else:
            return courses, False
    else:
        return courses, False
