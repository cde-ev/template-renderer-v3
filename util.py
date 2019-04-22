from data import Event, EventPart, RegistrationPartStati
from typing import Iterable


def get_registrations(event: Event, parts: Iterable[EventPart] = None, stati: Iterable[RegistrationPartStati] = None,
                      list_consent_only: bool = False):

    if parts is None:
        parts = event.parts
    if stati is None:
        stati = [RegistrationPartStati.participant]

    result = [r for r in event.registrations if any(r.parts[part].status in stati for part in parts)]

    if list_consent_only:
        result = [r for r in result if r.list_consent]

    return result


def get_tracks(event: Event, parts:Iterable[EventPart] = None):

    if parts is None:
        parts = event.parts

    result = [t for t in event.tracks if t.part in parts]

    return result
