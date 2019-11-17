import enum
import functools
import itertools
import json
import datetime
from typing import List, Dict, Tuple, Any, Optional, Iterable

MINIMUM_EXPORT_VERSION = 4
MAXIMUM_EXPORT_VERSION = 6


def load_input_file(filename: str):
    with open(filename, encoding='utf-8') as f:
        data = json.load(f)

    event = Event.from_json(data)
    print("Parsed event data with {} registrations, {} courses and {} lodgements in {} event parts and {} course "
          "tracks."
          .format(len(event.registrations), len(event.courses), len(event.lodgements), len(event.parts),
                  len(event.tracks)))
    return event


def parse_date(value: str) -> datetime.date:
    return datetime.datetime.strptime(value, "%Y-%m-%d").date()


def parse_datetime(value: str) -> datetime.datetime:
    return datetime.datetime.strptime(value.replace(':', ''), "%Y-%m-%dT%H%M%S%z")


def calculate_age(reference: datetime.date, born: datetime.date) -> int:
    """Calculate age on a reference date based on birthday.

    Source: https://stackoverflow.com/a/9754466
    """
    return reference.year - born.year - ((reference.month, reference.day) < (born.month, born.day))


def registration_sort_key(r: 'Registration'):
    """ Sort key function for registrations. Should be used whenever sorting a list of registrations"""
    return r.name.given_names, r.name.family_name


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

    @property
    def is_involved(self):
        """Any status which warrants further attention by the orgas.

        :rtype: bool
        """
        return self in (RegistrationPartStati.applied,
                        RegistrationPartStati.participant,
                        RegistrationPartStati.waitlist,
                        RegistrationPartStati.guest,)

    @property
    def is_present(self):
        return self in (RegistrationPartStati.participant,
                        RegistrationPartStati.guest,)


class CourseTrackStati(enum.IntEnum):
    """Spec for field status of CourseTracks"""
    not_offered = -1  #:
    cancelled = 1  #:
    active = 2

    @property
    def is_active(self):
        return self == CourseTrackStati.active


class FieldDatatypes(enum.IntEnum):
    """Spec for the datatypes available as custom data fields.
    From Cdedb v2: cdedb.database.constants"""
    str = 1  #:
    bool = 2  #:
    int = 3  #:
    float = 4  #:
    date = 5  #:
    datetime = 6  #:


class AgeClasses(enum.IntEnum):
    """Abstraction for encapsulating properties like legal status changing with
    age.

    If there is any need for additional detail in differentiating this
    can be centrally added here.
    """
    full = 1  #: at least 18 years old
    u18 = 2  #: between 16 and 18 years old
    u16 = 3  #: between 14 and 16 years old
    u14 = 4  #: less than 14 years old

    @property
    def is_minor(self) -> bool:
        """Checks whether a legal guardian is required.

        :rtype: bool
        """
        return self in {AgeClasses.u14, AgeClasses.u16, AgeClasses.u18}


ALL_ENUMS = (Genders, RegistrationPartStati, CourseTrackStati, FieldDatatypes, AgeClasses)


class Event:
    def __init__(self):
        self.title = ""  # type: str
        self.shortname = ""  # type: str
        self.parts = []  # type: List[EventPart]
        self.tracks = []  # type: List[EventTrack]

        self.registrations = []  # type: List[Registration]
        self.courses = []  # type: List[Course]
        self.lodgements = []  # type: List[Lodgement]

        self.course_room_field = None

        self.timestamp = datetime.datetime.now()

    @property
    def begin(self) -> datetime.date:
        return self.parts[0].begin

    @property
    def end(self) -> datetime.date:
        return max(p.end for p in self.parts)

    @property
    def days(self) -> List[datetime.date]:
        # Silencing of mypy false-positive required (https://github.com/python/mypy/issues/4150)
        return sorted(functools.reduce(lambda a, b: a | b,  # type: ignore
                                       (set(p.days) for p in self.parts)))

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> 'Event':
        if 'kind' not in data or data['kind'] != "partial":
            raise ValueError("This script requires a 'Partial Export' from the CdEDB!")
        if not MINIMUM_EXPORT_VERSION <= data['CDEDB_EXPORT_EVENT_VERSION'] <= MINIMUM_EXPORT_VERSION:
            raise ValueError("This script requires a 'Partial Export' with versio number in [{},{}]!"
                             .format(MINIMUM_EXPORT_VERSION, MAXIMUM_EXPORT_VERSION))

        event = cls()

        event_data = data['event']
        event.title = event_data['title']
        event.shortname = event_data['shortname']
        event.timestamp = datetime.datetime.strptime(data['timestamp'].replace(':', ''), "%Y-%m-%dT%H%M%S.%f%z")
        event.course_room_field = event_data['course_room_field']

        # Parse parts and tracks
        event.parts = [EventPart.from_json(part_id, part_data)
                       for part_id, part_data in data['event']['parts'].items()]
        event.parts.sort(key=(lambda p: p.begin))
        parts_by_id = {p.id: p for p in event.parts}
        event.tracks = list(itertools.chain.from_iterable(p.tracks for p in event.parts))
        event.tracks.sort(key=(lambda t: t.sortkey))
        tracks_by_id = {t.id: t for t in event.tracks}

        # Get field definitions
        field_types = {field_name: FieldDatatypes(field_data['kind'])
                       for field_name, field_data in event_data['fields'].items()}

        # Parse courses and course_segments
        event.courses = [Course.from_json(course_id, course_data, field_types, tracks_by_id)
                         for course_id, course_data in data['courses'].items()]
        max_course_nr_len = max(len(c.nr) if c.nr else 0
                                for c in event.courses)
        event.courses.sort(key=(lambda c: c.nr.rjust(max_course_nr_len, '\0')))
        courses_by_id = {c.id: c for c in event.courses}

        # Parse lodgements
        event.lodgements = [Lodgement.from_json(lodgement_id, lodgement_data, field_types, event.parts)
                            for lodgement_id, lodgement_data in data['lodgements'].items()]
        event.lodgements.sort(key=(lambda l: l.moniker))
        lodgements_by_id = {l.id: l for l in event.lodgements}

        # Parse registrations
        event_begin = event.begin
        event.registrations = sorted((Registration.from_json(reg_id, reg_data, field_types, event_begin, parts_by_id,
                                                             tracks_by_id, courses_by_id, lodgements_by_id)
                                      for reg_id, reg_data in data['registrations'].items()),
                                     key=registration_sort_key)

        # Add registrations to the relevant lodgements and courses
        # This done after sorting of Registrations
        for registration in event.registrations:
            registration.tracks = {t: pt for t, pt in registration.tracks.items()
                                   if t.part in registration.parts}
            for part, registration_part in registration.parts.items():
                if registration_part.lodgement:
                    registration_part.lodgement.parts[part].inhabitants.append(
                        (registration, registration_part.campingmat))
            for track, registration_track in registration.tracks.items():
                if registration_track.course and track in registration_track.course.tracks:
                    registration_track.course.tracks[track].attendees.append(
                        (registration, registration_track.instructor))

        return event


class EventPart:
    def __init__(self):
        self.id = 0  # type: int
        self.title = ""  # type: str
        self.shortname = ""  # type: str
        self.begin = datetime.date.today()  # type: datetime.date
        self.end = datetime.date.today()  # type: datetime.date

        self.tracks = []  # type: List[EventTrack]

    @property
    def days(self) -> Iterable[datetime.date]:
        d = self.begin
        while d <= self.end:
            yield d
            d += datetime.timedelta(days=1)

    @classmethod
    def from_json(cls, part_id: int, data: Dict[str, Any]) -> 'EventPart':
        part = cls()
        part.id = int(part_id)
        part.title = data['title']
        part.shortname = data['shortname']
        part.begin = parse_date(data['part_begin'])
        part.end = parse_date(data['part_end'])
        part.tracks = [EventTrack.from_json(ti, td, part) for ti, td in data['tracks'].items()]
        part.tracks.sort(key=(lambda t: t.sortkey))
        return part


class EventTrack:
    def __init__(self):
        self.id = 0  # type: int
        self.part = None  # type: EventPart

        self.title = ""  # type: str
        self.shortname = ""  # type: str
        self.sortkey = 0  # type: int
        self.num_choices = 0  # type: int

    @classmethod
    def from_json(cls, track_id: int, data: Dict[str, Any], part: EventPart) -> 'EventTrack':
        track = cls()
        track.id = int(track_id)
        track.title = data['title']
        track.shortname = data['shortname']
        track.sortkey = data['sortkey']
        track.num_choices = data['num_choices']
        track.part = part
        part.tracks.append(track)
        return track


class Course:
    def __init__(self):
        self.id = 0  # type: int
        self.nr = ""  # type: str
        self.title = ""  # type: str
        self.shortname = ""  # type: str
        self.fields = {}  # type: Dict[str, object]
        self.tracks = {}  # type: Dict[EventTrack, CourseTrack]

    @property
    def instructors(self) -> List['Registration']:
        # Silencing of mypy false-positive required (https://github.com/python/mypy/issues/4150)
        return sorted(functools.reduce(lambda x, y: x | y,  # type: ignore
                                       (set(t.instructors) for t in self.tracks.values())),
                      key=registration_sort_key)

    @property
    def is_active(self):
        return any(t.status.is_active for t in self.tracks.values())

    @classmethod
    def from_json(cls, course_id: int, data: Dict[str, Any], field_types: Dict[str, FieldDatatypes],
                  event_tracks: Dict[int, EventTrack]) -> 'Course':
        course = cls()
        course.id = int(course_id)
        course.title = data['title']
        course.shortname = data['shortname']
        course.nr = data['nr'] if data['nr'] else ""
        for field, value in data['fields'].items():
            if field not in field_types:
                continue
            if field_types[field] == FieldDatatypes.datetime and value is not None:
                value = parse_datetime(value)
            elif field_types[field] == FieldDatatypes.date and value is not None:
                value = parse_date(value)
            course.fields[field] = value
        # Add CourseTracks
        course.tracks = {event_tracks[int(ti)]: CourseTrack.from_json(td, course, event_tracks[int(ti)])
                         for ti, td in data['segments'].items()}
        for track in event_tracks.values():
            if track not in course.tracks:
                course_track = CourseTrack()
                course_track.track = track
                course_track.course = course
                course.tracks[track] = course_track
        return course


class CourseTrack:
    def __init__(self):
        self.track = None  # type: EventTrack
        self.course = None  # type: Course
        self.status = CourseTrackStati.not_offered  # type: CourseTrackStati
        self.attendees = []  # type: [Tuple[Registration, bool]]

    @property
    def regular_attendees(self) -> List['Registration']:
        return [p for p, instructor in self.attendees if not instructor]

    @property
    def instructors(self) -> List['Registration']:
        return [p for p, instructor in self.attendees if instructor]

    @classmethod
    def from_json(cls, data: Dict[str, Any], course: Course, track: EventTrack) -> 'CourseTrack':
        course_track = cls()
        course_track.track = track
        course_track.course = course
        course_track.status = CourseTrackStati.active if data else CourseTrackStati.cancelled
        return course_track


class Lodgement:
    def __init__(self):
        self.id = 0  # type: int
        self.moniker = ""  # type: str
        self.fields = {}  # type: Dict[str, object]
        self.parts = {}  # type: Dict[EventPart, LodgementPart]

    @classmethod
    def from_json(cls, lodgement_id: int, data: Dict[str, Any], field_types: Dict[str, FieldDatatypes],
                  event_parts: List[EventPart]) -> 'Lodgement':
        lodgement = cls()
        lodgement.id = int(lodgement_id)
        lodgement.moniker = data['moniker']
        for field, value in data['fields'].items():
            if field not in field_types:
                continue
            if field_types[field] == FieldDatatypes.datetime and value is not None:
                value = parse_datetime(value)
            elif field_types[field] == FieldDatatypes.date and value is not None:
                value = parse_date(value)
            lodgement.fields[field] = value
        for part in event_parts:
            lodgement_part = LodgementPart()
            lodgement_part.part = part
            lodgement_part.lodgement = lodgement
            lodgement.parts[part] = lodgement_part
        return lodgement


class LodgementPart:
    def __init__(self):
        self.part = None  # type: EventPart
        self.lodgement = None  # type: Lodgement
        self.inhabitants = []  # type: List[Tuple[Registration, bool]]

    @property
    def regular_inhabitants(self) -> List['Registration']:
        return [p for p, campingmat in self.inhabitants if not campingmat]

    @property
    def campingmat_inhabitants(self) -> List['Registration']:
        return [p for p, campingmat in self.inhabitants if campingmat]


class Registration:
    def __init__(self):
        self.id = 0  # type: int
        self.cdedbid = 0  # type: int
        self.name = Name()  # type: Name
        self.gender = Genders.not_specified  # type: Genders
        self.birthday = datetime.datetime.today()  # type: datetime.date
        self.age = 0  # type: int
        self.email = ""  # type: str
        self.telephone = ""  # type: str
        self.mobile = ""  # type: str
        self.address = Address()  # type: Address

        self.list_consent = False  # type: bool
        self.tracks = {}  # type: Dict[EventTrack, RegistrationTrack]
        self.parts = {}  # type: Dict[EventPart, RegistrationPart]
        self.fields = {}  # type: Dict[str, object]

    @property
    def is_present(self) -> bool:
        return any(p.status.is_present for p in self.parts.values())

    @property
    def is_participant(self) -> bool:
        return any(p.status == RegistrationPartStati.participant for p in self.parts.values())

    @property
    def age_class(self) -> AgeClasses:
        if self.age >= 18:
            return AgeClasses.full
        if self.age >= 16:
            return AgeClasses.u18
        if self.age >= 14:
            return AgeClasses.u16
        return AgeClasses.u14

    @classmethod
    def from_json(cls, reg_id: str, data: Dict, field_types: Dict[str, FieldDatatypes], event_begin: datetime.date,
                  event_parts: Dict[int, EventPart], event_tracks: Dict[int, EventTrack], courses: Dict[int, Course],
                  lodgements: Dict[int, Lodgement]) -> 'Registration':
        registration = cls()
        registration.id = int(reg_id)
        registration.cdedbid = data['persona']['id']
        registration.name = Name.from_json_persona(data['persona'])
        registration.gender = Genders(data['persona']['gender'])
        registration.birthday = parse_date(data['persona']['birthday'])
        registration.age = calculate_age(event_begin, registration.birthday)
        registration.email = data['persona']['username']
        registration.telephone = data['persona']['telephone']
        registration.mobile = data['persona']['mobile']
        registration.address = Address.from_json_persona(data['persona'])
        registration.list_consent = data['list_consent']

        for field, value in data['fields'].items():
            if field not in field_types:
                continue
            if field_types[field] == FieldDatatypes.datetime and value is not None:
                value = parse_datetime(value)
            elif field_types[field] == FieldDatatypes.date and value is not None:
                value = parse_date(value)
            registration.fields[field] = value

        registration.parts = {event_parts[int(pi)]: RegistrationPart.from_json(pd, registration,
                                                                               event_parts[int(pi)], lodgements)
                              for pi, pd in data['parts'].items()}
        registration.tracks = {event_tracks[int(ti)]: RegistrationTrack.from_json(td, registration,
                                                                                  event_tracks[int(ti)], courses)
                               for ti, td in data['tracks'].items()}
        for part in event_parts.values():
            if part not in registration.parts:
                registration_part = RegistrationPart()
                registration_part.registration = registration
                registration_part.part = part
                registration.parts[part] = registration_part
            for track in part.tracks:
                if track not in registration.tracks:
                    registration_track = RegistrationTrack()
                    registration_track.registration = registration
                    registration_track.choices = [None] * track.num_choices
                    registration_track.track = track
                    registration_track.registration_part = registration.parts[part]
                    registration.tracks[track] = registration_track

        return registration


class Name:
    def __init__(self):
        self.title = ""  # type: str
        self.given_names = ""  # type: str
        self.family_name = ""  # type: str
        self.name_supplement = ""  # type: str
        self.display_name = ""  # type: str

    @property
    def fullname(self) -> str:
        return ((self.title + " ") if self.title else "") \
               + self.given_names + " " + self.family_name \
               + ((" " + self.name_supplement) if self.name_supplement else "")

    @classmethod
    def from_json_persona(cls, data: Dict[str, Any]) -> 'Name':
        name = cls()
        name.title = data['title']
        name.given_names = data['given_names']
        name.family_name = data['family_name']
        name.name_supplement = data['name_supplement']
        name.display_name = data['display_name']
        return name


class Address:
    def __init__(self):
        self.address = ""  # type: str
        self.address_supplement = ""  # type: str
        self.postal_code = ""  # type: str
        self.location = ""  # type: str
        self.country = ""  # type: str

    @property
    def full_address(self) -> str:
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
    def from_json_persona(cls, data: Dict[str, Any]) -> 'Address':
        address = cls()
        address.address = data['address']
        address.address_supplement = data['address_supplement']
        address.postal_code = data['postal_code']
        address.location = data['location']
        address.country = data['country']
        return address


class RegistrationPart:
    def __init__(self):
        self.part = None  # type: EventPart
        self.registration = None  # type: Registration
        self.status = RegistrationPartStati.not_applied  # type: RegistrationPartStati
        self.lodgement = None  # type: Lodgement
        self.campingmat = False  # type: bool

    @classmethod
    def from_json(cls, data: Dict[str, Any], registration: Registration, part: EventPart,
                  lodgements: Dict[int, Lodgement]) -> 'RegistrationPart':
        rpart = cls()
        rpart.registration = registration
        rpart.part = part
        rpart.status = RegistrationPartStati(data['status'])
        if data['lodgement_id']:
            rpart.lodgement = lodgements[data['lodgement_id']]
        rpart.campingmat = data['is_reserve']
        # Adding the registration to the lodgement's registration list is done later, to ensure the order
        return rpart


class RegistrationTrack:
    def __init__(self):
        self.track = None  # type: EventTrack
        self.registration = None  # type: Registration
        self.registration_part = None  # type: RegistrationPart
        self.course = None  # type: Course
        self.offered_course = None  # type: Course
        self.choices = []  # type: List[Optional[Course]]

    @property
    def instructor(self) -> bool:
        return self.offered_course is not None and self.offered_course == self.course

    @classmethod
    def from_json(cls, data: Dict[str, Any], registration: Registration, track: EventTrack,
                  courses: Dict[int, Course]) -> 'RegistrationTrack':
        rtrack = cls()
        rtrack.registration = registration
        rtrack.track = track
        if data['course_id']:
            rtrack.course = courses[data['course_id']]
        if data['course_instructor']:
            rtrack.offered_course = courses[data['course_instructor']]
        rtrack.choices = [courses[choice] for choice in data['choices']]
        rtrack.registration_part = registration.parts[track.part]
        # Adding the registration to the courses' attendee list ist done later, to ensure the correct order
        return rtrack
