import enum
import functools
import json
import datetime
from typing import List, Dict, Set, Tuple


def load_input_file(filename):
    with open(filename, encoding='utf-8') as f:
        data = json.load(f)

    event = Event.from_json(data)
    print("Parsed event data with {} registrations, {} courses and {} lodgements in {} event parts and {} course tracks."
          .format(len(event.registrations), len(event.courses), len(event.lodgements), len(event.parts),
                  len(event.tracks)))
    return event


def parse_date(value):
    return datetime.datetime.strptime(value, "%Y-%m-%d").date()


def parse_datetime(value):
    return datetime.datetime.strptime(value.replace(':', ''), "%Y-%m-%dT%H%M%S%z")


def calculate_age(reference, born):
    """Calculate age on a reference date based on birthday.

    Source: https://stackoverflow.com/a/9754466
    """
    return reference.year - born.year - ((reference.month, reference.day) < (born.month, born.day))


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

    def is_involved(self):
        """Any status which warrants further attention by the orgas.

        :rtype: bool
        """
        return self in (RegistrationPartStati.applied,
                        RegistrationPartStati.participant,
                        RegistrationPartStati.waitlist,
                        RegistrationPartStati.guest,)

    def is_present(self):
        return self in (RegistrationPartStati.participant,
                        RegistrationPartStati.guest,)


class CourseTrackStati(enum.IntEnum):
    """Spec for field status of CourseTracks"""
    not_offered = -1  #:
    cancelled = 1  #:
    active = 2

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
    def is_minor(self):
        """Checks whether a legal guardian is required.

        :rtype: bool
        """
        return self in {AgeClasses.u14, AgeClasses.u16, AgeClasses.u18}


class Event:
    def __init__(self):
        self.title = ""  # type: str
        self.shortname = ""  # type: str
        self.parts = []  # type: List[EventPart]
        self.tracks = []  # type: List[EventTrack]

        self.registrations = []  # type: List[Registration]
        self.courses = []  # type: List[Course]
        self.lodgements = []  # type: List[Lodgement]

        self.timestamp = datetime.datetime.now()

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
        event.timestamp = datetime.datetime.strptime(data['timestamp'].replace(':', ''), "%Y-%m-%dT%H%M%S.%f%z")

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
        event.courses = sorted((Course.from_json(course_data, field_types)
                                for course_data in data['event.courses'].values()),
                               key=(lambda c: c.nr.rjust(max_course_nr_len, '\0')))
        courses_by_id = {c.id: c for c in event.courses}

        for ct_data in data['event.course_segments'].values():
            # CourseTracks are automatically added to the courses' `tracks` dict
            CourseTrack.from_json(ct_data, tracks_by_id, courses_by_id)

        # Add missing (non-offered) course_tracks
        for course in event.courses:
            for track in event.tracks:
                if track not in course.tracks:
                    course_track = CourseTrack()
                    course_track.track = track
                    course_track.course = course
                    course.tracks[track] = course_track

        # Parse lodgements
        event.lodgements = [Lodgement.from_json(lodgement_data, field_types, event.parts)
                            for lodgement_data in data['event.lodgements'].values()]
        event.lodgements.sort(key=(lambda l: l.moniker))
        lodgements_by_id = {l.id: l for l in event.lodgements}

        # Parse registrations
        event_begin = event.begin
        event.registrations = sorted((Registration.from_json(reg_data, data['core.personas'], field_types, event_begin)
                                      for reg_data in data['event.registrations'].values()),
                                     key=(lambda r: (r.name.given_names, r.name.family_name)))
        registrations_by_id = {p.id: p for p in event.registrations}

        # Parse registration parts and tracks
        for rp_data in data['event.registration_parts'].values():
            # RegistrationParts are automatically added to the Registrations' `parts` dicts
            RegistrationPart.from_json(rp_data, parts_by_id, registrations_by_id, lodgements_by_id)
        for rt_data in data['event.registration_tracks'].values():
            # RegistrationTracks are automatically added to the Registrations' `tracks` dicts
            # Filtering of tracks by active parts is done in the following for-loop
            RegistrationTrack.from_json(rt_data, tracks_by_id, registrations_by_id, courses_by_id)

        # Add missing registration parts and tracks
        for registration in event.registrations:
            for part in event.parts:
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

        # Parse course choices
        for choice_data in data['event.course_choices'].values():
            track = tracks_by_id[choice_data['track_id']]
            rank = choice_data['rank']
            if rank < track.num_choices:
                registration = registrations_by_id[choice_data['registration_id']]
                registration.tracks[track].choices[rank] = courses_by_id[choice_data['course_id']]

        # Add registrations to the relevant lodgements and courses
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

    @classmethod
    def from_json(cls, data):
        part = cls()
        part.id = data['id']
        part.title = data['title']
        part.shortname = data['shortname']
        part.begin = parse_date(data['part_begin'])
        part.end = parse_date(data['part_end'])
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
    def from_json(cls, data, parts_by_id):
        track = cls()
        track.id = data['id']
        track.title = data['title']
        track.shortname = data['shortname']
        track.sortkey = data['sortkey']
        track.num_choices = data['num_choices']
        part = parts_by_id.get(data['part_id'], None)
        if part:
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
    def instructors(self):
        return sorted(functools.reduce(lambda x, y: x | y,
                                       (set(t.instructors) for t in self.tracks.values())),
                      key=lambda r: (r.name.given_names, r.name.family_name))

    @property
    def is_active(self):
        return any(t.status.is_active() for t in self.tracks.values())

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
            if field_types[field] == FieldDatatypes.datetime and value is not None:
                value = parse_datetime(value)
            elif field_types[field] == FieldDatatypes.date and value is not None:
                value = parse_date(value)
            course.fields[field] = value
        return course


class CourseTrack:
    def __init__(self):
        self.track = None  # type: EventTrack
        self.course = None  # type: Course
        self.status = CourseTrackStati.not_offered  # type: CourseTrackStati
        self.attendees = []  # type: [Tuple[Registration, bool]]

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
        course_track.status = CourseTrackStati.active if data['is_active'] else CourseTrackStati.cancelled
        # Appending the course to track.courses is done later on to ensure the correct order
        course_track.course.tracks[course_track.track] = course_track
        return course_track


class Lodgement:
    def __init__(self):
        self.id = 0  # type: int
        self.moniker = ""  # type: str
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
    def regular_inhabitants(self):
        return [p for p, campingmat in self.inhabitants if not campingmat]

    @property
    def campingmat_inhabitants(self):
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
    def is_present(self):
        return any(p.status.is_present() for p in self.parts.values())

    @property
    def age_class(self):
        if self.age >= 18:
            return AgeClasses.full
        if self.age >= 16:
            return AgeClasses.u18
        if self.age >= 14:
            return AgeClasses.u16
        return AgeClasses.u14

    @classmethod
    def from_json(cls, data, persona_datasets, field_types, event_begin):
        registration = cls()
        registration.id = data['id']
        persona_data = persona_datasets[str(data['persona_id'])]
        registration.cdedbid = persona_data['id']
        registration.name = Name.from_json_persona(persona_data)
        registration.gender = Genders(persona_data['gender'])
        registration.birthday = parse_date(persona_data['birthday'])
        registration.age = calculate_age(event_begin, registration.birthday)
        registration.email = persona_data['username']
        registration.telephone = persona_data['telephone']
        registration.mobile = persona_data['mobile']
        registration.address = Address.from_json_persona(persona_data)
        registration.list_consent = data['list_consent']

        for field, value in data['fields'].items():
            if field not in field_types:
                continue
            if field_types[field] == FieldDatatypes.datetime and value is not None:
                value = parse_datetime(value)
            elif field_types[field] == FieldDatatypes.date and value is not None:
                value = parse_date(value)
            registration.fields[field] = value

        return registration


class Name:
    def __init__(self):
        self.title = ""  # type: str
        self.given_names = ""  # type: str
        self.family_name = ""  # type: str
        self.name_supplement = ""  # type: str
        self.display_name = ""  # type: str

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
        self.address = ""  # type: str
        self.address_supplement = ""  # type: str
        self.postal_code = ""  # type: str
        self.location = ""  # type: str
        self.country = ""  # type: str

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


class RegistrationPart:
    def __init__(self):
        self.part = None  # type: EventPart
        self.registration = None  # type: Registration
        self.status = RegistrationPartStati.not_applied  # type: RegistrationPartStati
        self.lodgement = None  # type: Lodgement
        self.campingmat = False  # type: bool

    @classmethod
    def from_json(cls, data, event_parts, registrations, lodgements):
        rpart = cls()
        rpart.registration = registrations[data['registration_id']]
        rpart.part = event_parts[data['part_id']]
        rpart.status = RegistrationPartStati(data['status'])
        if data['lodgement_id']:
            rpart.lodgement = lodgements[data['lodgement_id']]
        rpart.campingmat = data['is_reserve']
        rpart.registration.parts[rpart.part] = rpart
        # Adding the registration to the lodgement's registration list ist done later, to ensure the order
        return rpart


class RegistrationTrack:
    def __init__(self):
        self.track = None  # type: EventTrack
        self.registration = None  # type: Registration
        self.registration_part = None  # type: RegistrationPart
        self.course = None  # type: Course
        self.instructor = False  # type: bool
        self.choices = []  # type: List[Course]

    @classmethod
    def from_json(cls, data, event_tracks, registrations, courses):
        rtrack = cls()
        rtrack.registration = registrations[data['registration_id']]
        rtrack.track = event_tracks[data['track_id']]
        if data['course_id']:
            rtrack.course = courses[data['course_id']]
            if data['course_instructor'] and data['course_instructor'] == data['course_id']:
                rtrack.instructor = True
        rtrack.choices = [None] * rtrack.track.num_choices
        rtrack.registration_part = rtrack.registration.parts[rtrack.track.part]
        rtrack.registration.tracks[rtrack.track] = rtrack
        # Adding the registration to the courses' attendee list ist done later, to ensure the correct order
        return rtrack
