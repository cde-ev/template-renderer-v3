import datetime
import enum
import itertools
import json
import datetime
from typing import Dict


def load_input_file(filename):
    with open(filename, encoding='utf-8') as f:
        data = json.load(f)

    event = Event.from_json(data)
    print("Parsed event data with {} participants, {} courses and {} lodgements in {} event parts and {} course tracks."
          .format(len(event.participants), len(event.courses), len(event.lodgements), len(event.parts),
                  len(event.tracks)))
    return event


class Genders(enum.IntEnum):
    """Spec for field gender of core.personas.
    From Cdedb v2: cdedb.database.constants
    """
    female = 1  #:
    male = 2  #:
    #: this is a catch-all for complicated reality
    other = 10
    not_specified = 20  #:


class RegistrationPartStati(enum.IntEnum):
    """Spec for field status of event.registration_parts.
    From Cdedb v2: cdedb.database.constants"""
    not_applied = -1  #:
    applied = 1  #:
    participant = 2  #:
    waitlist = 3  #:
    guest = 4  #:
    cancelled = 5  #:
    rejected = 6  #:

    def is_present(self):
        return self in (RegistrationPartStati.participant,
                        RegistrationPartStati.guest,)


class FieldDatatypes(enum.IntEnum):
    """Spec for the datatypes available as custom data fields.
    From Cdedb v2: cdedb.database.constants"""
    str = 1  #:
    bool = 2  #:
    int = 3  #:
    float = 4  #:
    date = 5  #:
    datetime = 6  #:


class Event:
    def __init__(self):
        self.title = ""
        self.shortname = ""
        self.parts = []
        self.tracks = []

        self.participants = []
        self.courses = []
        self.lodgements = []

    @property
    def begin(self):
        if not self.parts:
            return None
        return self.parts[0].begin

    @property
    def end(self):
        if not self.parts:
            return None
        return max(p.end for p in self.parts)

    @classmethod
    def from_json(cls, data):
        event = cls()

        event_data = data['event.events'][str(data['id'])]
        event.title = event_data['title']
        event.shortname = event_data['shortname']

        # Parse parts and tracks
        event.parts = [EventPart.from_json(part_data)
                       for part_data in data['event.event_parts'].values()]
        event.parts.sort(key=(lambda p: p.begin))
        parts_by_id = {p.id: p for p in event.parts}
        event.tracks = [EventTrack.from_json(part_data, parts_by_id)
                        for part_data in data['event.course_tracks'].values()]
        event.tracks.sort(key=(lambda t: t.sortkey))
        tracks_by_id = {t.id: t for t in event.tracks}

        # Get field definitions
        field_types = {field_data['field_name']: FieldDatatypes(field_data['kind'])
                       for field_data in data['event.field_definitions'].values()}

        # Parse courses and course_segments
        max_course_nr_len = max(len(cd['nr']) for cd in data['event.courses'].values())
        # For now, the `courses` list includes all courses. Cancelled courses are filtered out later on.
        courses = sorted((Course.from_json(course_data, field_types)
                          for course_data in data['event.courses'].values()),
                         key=(lambda c: c.nr.rjust(max_course_nr_len, '\0')))
        courses_by_id = {c.id: c for c in courses}

        for ct_data in data['event.course_segments'].values():
            if ct_data['is_active']:
                # CourseTracks are automatically added to the courses' `tracks` dict
                CourseTrack.from_json(ct_data, tracks_by_id, courses_by_id)

        for course in courses:
            for track, course_track in course.tracks.items():
                track.courses.append(course)
        event.courses = [course for course in courses if course.tracks]

        # Parse lodgements
        event.lodgements = [Lodgement.from_json(lodgement_data, field_types, event.parts)
                            for lodgement_data in data['event.lodgements'].values()]
        event.lodgements.sort(key=(lambda l: l.moniker))
        lodgements_by_id = {l.id: l for l in event.lodgements}

        # Parse registrations
        # For now, the `participants` list includes all registrations. Inactive registrations are filtered later on.
        participants = sorted((Participant.from_json(reg_data, data['core.personas'], field_types)
                               for reg_data in data['event.registrations'].values()),
                              key=(lambda r: (r.name.given_names, r.name.family_name)))
        participants_by_id = {p.id: p for p in participants}

        # Parse registration parts and tracks
        for rp_data in data['event.registration_parts'].values():
            if RegistrationPartStati(rp_data['status']).is_present():
                # ParticipantParts are automatically added to the Participants' `parts` dicts
                ParticipantPart.from_json(rp_data, parts_by_id, participants_by_id, lodgements_by_id)
        for rt_data in data['event.registration_tracks'].values():
            # ParticipantTracks are automatically added to the Participants' `tracks` dicts
            # Filtering of tracks by active parts is done in the following for-loop
            ParticipantTrack.from_json(rt_data, tracks_by_id, participants_by_id, courses_by_id)

        # Filter participants' tracks by their active parts and add them to the relevant parts, lodgements and courses
        for participant in participants:
            participant.tracks = {t: pt for t, pt in participant.tracks.items()
                                  if t.part in participant.parts}
            for part, participant_part in participant.parts.items():
                part.participants.append(participant)
                if participant_part.lodgement:
                    participant_part.lodgement.parts[part].inhabitants.append(
                        (participant, participant_part.campingmat))
            for track, participant_track in participant.tracks.items():
                if participant_track.course:
                    participant_track.course.tracks[track].attendees.append(
                        (participant, participant_track.instructor))
        event.participants = [p for p in participants if p.parts]

        return event


class EventPart:
    def __init__(self):
        self.id = 0
        self.title = ''
        self.shortname = ''
        self.begin = datetime.date.today()
        self.end = datetime.date.today()

        self.tracks = []
        self.participants = []

    @classmethod
    def from_json(cls, data):
        part = cls()
        part.id = data['id']
        part.title = data['title']
        part.shortname = data['shortname']
        part.begin = data['part_begin']
        part.end = data['part_end']
        return part


class EventTrack:
    def __init__(self):
        self.id = 0
        self.part = None

        self.title = ''
        self.shortname = ''
        self.sortkey = 0
        self.courses = []

    @classmethod
    def from_json(cls, data, parts_by_id):
        track = cls()
        track.id = data['id']
        track.title = data['title']
        track.shortname = data['shortname']
        track.sortkey = data['sortkey']
        part = parts_by_id.get(data['part_id'], None)
        if part:
            track.part = part
            part.tracks.append(track)
        return track


class Course:
    def __init__(self):
        self.id = 0
        self.nr = ''
        self.title = ''
        self.shortname = ''
        self.fields = {}  # type: Dict[str, object]
        self.tracks = {}  # type: Dict[EventTrack, CourseTrack]

    @classmethod
    def from_json(cls, data, field_types):
        course = cls()
        course.id = data['id']
        course.title = data['title']
        course.shortname = data['shortname']
        course.nr = data['nr']
        for field, value in data['fields'].items():
            if field not in field_types:
                continue
            if field_types[field] == FieldDatatypes.datetime:
                value = datetime.datetime.fromisoformat(value)
            elif field_types[field] == FieldDatatypes.date:
                value = datetime.date.fromisoformat(value)
            course.fields[field] = value
        return course


class CourseTrack:
    def __init__(self):
        self.track = None  # type: EventTrack
        self.course = None  # type: Course
        self.active = False
        self.attendees = []  # type: [(Participant, bool)]

    @property
    def regular_attendees(self):
        return [p for p, instructor in self.attendees if not instructor]

    @property
    def instructors(self):
        return [p for p, instructor in self.attendees if instructor]

    @classmethod
    def from_json(cls, data, tracks_by_id, courses_by_id):
        course_track = cls()
        course_track.track = tracks_by_id[data['track_id']]
        course_track.course = courses_by_id[data['course_id']]
        course_track.active = data['is_active']
        # Appending the course to track.courses is done later on to ensure the correct order
        course_track.course.tracks[course_track.track] = course_track
        return course_track


class Lodgement:
    def __init__(self):
        self.id = 0
        self.moniker = ''
        self.fields = {}  # type: Dict[str, object]
        self.parts = {}  # type: Dict[EventPart, LodgementPart]

    @classmethod
    def from_json(cls, data, field_types, event_parts):
        lodgement = cls()
        lodgement.id = data['id']
        lodgement.moniker = data['moniker']
        for field, value in data['fields'].items():
            if field not in field_types:
                continue
            if field_types[field] == FieldDatatypes.datetime:
                value = datetime.datetime.fromisoformat(value)
            elif field_types[field] == FieldDatatypes.date:
                value = datetime.date.fromisoformat(value)
            lodgement.fields[field] = value
        for part in event_parts:
            lodgement_part = LodgementPart()
            lodgement_part.part = part
            lodgement_part.lodgement = lodgement
            lodgement.parts[part] = lodgement_part
        return lodgement


class LodgementPart:
    def __init__(self):
        self.part = None
        self.lodgement = None
        self.inhabitants = []  # type: [(Participant, bool)]

    @property
    def regular_inhabitants(self):
        return [p for p, campingmat in self.inhabitants if not campingmat]

    @property
    def campingmat_inhabitants(self):
        return [p for p, campingmat in self.inhabitants if campingmat]


class Participant:
    def __init__(self):
        self.id = 0
        self.cdedbid = 0
        self.name = Name()
        self.gender = Genders.not_specified
        self.birthday = datetime.datetime.today()
        self.email = ""
        self.telephone = ""
        self.mobile = ""
        self.address = Address()

        self.list_consent = False
        self.tracks = {}  # type: Dict[EventTrack, ParticipantTrack]
        self.parts = {}  # type: Dict[EventPart, ParticipantPart]
        self.fields = {}  # type: Dict[str, object]

    @classmethod
    def from_json(cls, data, persona_datasets, field_types):
        participant = cls()
        participant.id = data['id']
        persona_data = persona_datasets[str(data['persona_id'])]
        participant.cdedbid = persona_data['id']
        participant.name = Name.from_json_persona(persona_data)
        participant.gender = Genders(persona_data['gender'])
        participant.birthday = datetime.date.fromisoformat(persona_data['birthday'])
        participant.email = persona_data['username']
        participant.telephone = persona_data['telephone']
        participant.mobile = persona_data['mobile']
        participant.address = Address.from_json_persona(persona_data)

        for field, value in data['fields'].items():
            if field not in field_types:
                continue
            if field_types[field] == FieldDatatypes.datetime and value is not None:
                value = datetime.datetime.fromisoformat(value)
            elif field_types[field] == FieldDatatypes.date and value is not None:
                value = datetime.date.fromisoformat(value)
            participant.fields[field] = value

        return participant


class Name:
    def __init__(self):
        self.title = ""
        self.given_names = ""
        self.family_name = ""
        self.name_supplement = ""
        self.display_name = ""

    @property
    def fullname(self):
        return ((self.title + " ") if self.title else "") \
               + self.given_names + " " + self.family_name \
               + ((" " + self.name_supplement) if self.name_supplement else "")

    @classmethod
    def from_json_persona(cls, data):
        name = cls()
        name.title = data['title']
        name.given_names = data['given_names']
        name.family_name = data['family_name']
        name.name_supplement = data['name_supplement']
        name.display_name = data['display_name']
        return name


class Address:
    def __init__(self):
        self.address = ""
        self.address_supplement = ""
        self.postal_code = ""
        self.location = ""
        self.country = ""

    @property
    def full_address(self):
        res = self.address + "\n"
        if self.address_supplement:
            res += self.address_supplement + "\n"
        if self.postal_code:
            res += self.postal_code + " "
        res += self.location
        if self.country and self.country not in ("Germany", "Deutschland"):
            res += "\n" + self.country
        return res

    @classmethod
    def from_json_persona(cls, data):
        address = cls()
        address.address = data['address']
        address.address_supplement = data['address_supplement']
        address.postal_code = data['postal_code']
        address.location = data['location']
        address.country = data['country']
        return address


class ParticipantPart:
    def __init__(self):
        self.part = None  # type: EventPart
        self.participant = None  # type: Participant
        self.status = RegistrationPartStati.not_applied
        self.lodgement = None  # type: Lodgement
        self.campingmat = False

    @classmethod
    def from_json(cls, data, event_parts, participants, lodgements):
        ppart = cls()
        ppart.participant = participants[data['registration_id']]
        ppart.part = event_parts[data['part_id']]
        ppart.status = RegistrationPartStati(data['status'])
        if data['lodgement_id']:
            ppart.lodgement = lodgements[data['lodgement_id']]
        ppart.campingmat = data['is_reserve']
        ppart.participant.parts[ppart.part] = ppart
        # Adding the participant to the parts' and lodgement's participant list ist done later, to ensure the order
        return ppart


class ParticipantTrack:
    def __init__(self):
        self.track = None  # type: EventTrack
        self.participant = None  # type: Participant
        self.course = None  # type: Course
        self.instructor = False

    @classmethod
    def from_json(cls, data, event_tracks, participants, courses):
        ptrack = cls()
        ptrack.participant = participants[data['registration_id']]
        ptrack.track = event_tracks[data['track_id']]
        if data['course_id']:
            ptrack.course = courses[data['course_id']]
            if data['course_instructor'] and data['course_instructor'] == data['course_id']:
                ptrack.instructor = True
        ptrack.participant.tracks[ptrack.track] = ptrack
        # Adding the participant to the courses' attendee list ist done later, to ensure the correct order
        return ptrack
