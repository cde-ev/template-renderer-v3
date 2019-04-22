from data import Event, EventPart, RegistrationPartStati
from typing import Iterable, Union
from datetime import timedelta


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


def get_tracks(event: Event, parts:Iterable[EventPart] = None):

    if parts is None:
        parts = event.parts

    result = [t for t in event.tracks if t.part in parts]

    return result


def get_days(foo: Union[Event, EventPart]):

    delta = foo.end - foo.begin

    return delta.days


def get_total_days(event: Event):

    return sum(get_days(part) for part in event.parts)


def get_date(foo: Union[Event, EventPart], days=0):

    date = foo.begin + timedelta(days=days)

    return date.strftime("%d.%m.")