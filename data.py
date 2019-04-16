import datetime
import enum
import itertools
import json
import datetime


FIELD_KIND_MAP = {
    1: str,
    2: bool,
    3: int,
    4: float,
    5: datetime.date,
    6: datetime.datetime
}


def load_input_file(filename):
    with open(filename, encoding='utf-8') as f:
        data = json.load(f)

    return Event.from_json(data)


class Genders(enum.IntEnum):
    unknown = 0
    male = 1
    female = 2
    various = 3


class Event:
    def __init__(self):
        self.title = ""
        self.shortname = ""
        self.parts = []
        self.tracks = []

        self.participants = []
        self.courses = []
        self.lodgements = []

    @classmethod
    def from_json(cls, data):
        event = cls()

        event_data = data['event.events'][str(data['id'])]
        event.title = event_data['title']
        event.shortname = event_data['shortname']

        # Parse parts and tracks
        event.parts = sorted((EventPart.from_json(part_data) for part_data in data['event.event_parts'].values()),
                             key=lambda p: p.begin)
        parts_by_id = {p.id: p for p in event.parts}
        event.tracks = [EventTrack.from_json(part_data, parts_by_id)
                        for part_data in sorted(data['event.course_tracks'].values(),
                                                key=lambda pd: pd['sortkey'])]
        tracks_by_id = {p.id: p for p in event.tracks}

        # Get field definitions
        field_types = {field_data['field_name']: FIELD_KIND_MAP[field_data['kind']]
                       for field_data in data['event.field_definitions'].values()}

        # Parse courses and course_segments
        max_course_nr_len = max(len(cd['nr']) for cd in data['event.courses'].values()) if data['event.courses'] else 0
        event.courses = [Course.from_json(course_data, field_types)
                         for course_data in sorted(data['event.courses'].values(),
                                                   key=lambda cd: cd['nr'].rjust(max_course_nr_len, '\0'))]
        courses_by_id = {c.id: c for c in event.courses}
        course_track_by_ids = {}
        for ct_data in sorted(data['event.course_segments'].values(),
                              key=lambda ctd: (courses_by_id[ctd['course_id']].nr.rjust(max_course_nr_len, '\0'),
                                               tracks_by_id[ctd['track_id']].sortkey)):
            if not ct_data['is_active']:
                continue
            course_track = CourseTrack.insert_from_json(ct_data, tracks_by_id, courses_by_id)
            course_track_by_ids[(course_track.course.id, course_track.track.id)] = course_track

        # Parse lodgements
        event.lodgements = [Lodgement.from_json(lodgement_data, field_types)
                            for lodgement_data in sorted(data['event.lodgements'].values(),
                                                         key=lambda ld: ld['moniker'])]
        lodgment_parts_by_ids = {(lp.lodgement.id, lp.part.id): lp
                                 for lp in itertools.chain.from_iterable(l.parts for l in event.lodgements)}

        # TODO read registrations
        # TODO read registration-parts
        # TODO read registration-tracks
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
        self.tracks = []  # type: [CourseTrack]

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
            if field_types[field] == datetime.datetime:
                value = datetime.datetime.fromisoformat(value)
            elif field_types[field] == datetime.date:
                value = datetime.date.fromisoformat(value)
            course.fields[field] = value
        return course


class CourseTrack:
    def __init__(self):
        self.track = None
        self.course = None
        self.attendees = []

    @classmethod
    def insert_from_json(cls, data, tracks_by_id, courses_by_id):
        course_track = cls()
        course_track.track = tracks_by_id[data['track_id']]
        course_track.course = courses_by_id[data['course_id']]
        course_track.track.courses.append(course_track.course)
        course_track.course.tracks.append(course_track)
        return course_track


class Lodgement:
    def __init__(self):
        self.id = 0
        self.moniker = ''
        self.fields = {}  # type: Dict[str, object]
        self.parts = []  # type: [LodgementPart]

    @classmethod
    def from_json(cls, data, field_types, event_parts):
        lodgement = cls()
        lodgement.id = data['id']
        lodgement.moniker = data['moniker']
        for field, value in data['fields'].items():
            if field not in field_types:
                continue
            if field_types[field] == datetime.datetime:
                value = datetime.datetime.fromisoformat(value)
            elif field_types[field] == datetime.date:
                value = datetime.date.fromisoformat(value)
            lodgement.fields[field] = value
        for part in event_parts:
            lodgement_part = LodgementPart()
            lodgement_part.part = part
            lodgement_part.lodgement = lodgement
            lodgement.parts.append(lodgement_part)
        return lodgement


class LodgementPart:
    def __init__(self):
        self.part = None
        self.lodgement = None
        self.inhabitants = []


class Participant:
    def __init__(self):
        self.id = 0
        self.cdedbid = 0
        self.name = Name()
        self.display_name = ""
        self.gender = Genders.unknown
        self.birthday = datetime.datetime.today()
        self.email = ""
        self.telephone = ""
        self.mobile = ""
        self.address = None

        self.list_consent = False
        self.tracks = []
        self.parts = []
        self.fields = []

    @classmethod
    def from_json(cls, data, persona_data):
        # TODO
        pass


class Name:
    def __init__(self):
        self.title = ""
        self.given_names = ""
        self.family_name = ""
        self.name_supplement = ""

    @classmethod
    def from_json_persona(cls, data):
        name = cls()
        name.title = data['title']
        name.given_names = data['given_names']
        name.family_name = data['family_name']
        name.name_supplement = data['name_supplement']

    @property
    def fullname(self):
        return ((self.title + " ") if self.title else "") \
               + self.given_names + " " + self.family_name \
               + ((" " + self.name_supplement) if self.name_supplement else "")


class Address:
    def __init__(self):
        self.address = ""
        self.address_supplement = ""
        self.postal_code = ""
        self.location = ""
        self.country = ""

    @classmethod
    def from_json_persona(cls, data):
        address = cls()
        address.address = data['address']
        address.address_supplement = data['address_supplement']
        address.postal_code = data['postal_code']
        address.location = data['location']
        address.country = data['country']

    @property
    def full_address(self):
        res = self.address + "\n"
        if self.address_supplement:
            res += self.address_supplement + "\n"
        if self.postal_code:
            res += self.postal_code + " "
        res += self.location
        if self.country not in ("Germany", "Deutschland"):
            res += "\n" + self.country
        return res
