"""

  `Bloom SQL Date and Time Fields`
--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--·--
   The MIT License (MIT) © 2015 Jared Lunde
   http://github.com/jaredlunde/bloom-orm

"""
import copy

from psycopg2.extensions import *

from dateutil import parser as dateparser
import arrow

from bloom.etc import operators
from bloom.etc.types import *
from bloom.expressions import *
from bloom.fields import Field


__all__ = ('TimeLogic', 'DateLogic', 'DateTimeLogic', 'Time', 'Date',
           'Timestamp', 'TimestampTZ', 'TimeTZ')


class TimeLogic(BaseNumericLogic):

    def interval(self, length, alias=None):
        return Expression(_empty, 'interval', length, alias=alias)

    def last(self, length):
        right = Expression(
            self.now(), operators.SUB, self.interval(length)).group()
        return Expression(self, operators.GE, right)

    def age(self, *args, alias=None):
        """ :see::meth:Functions.age """
        return Functions.age(self, *args, alias=alias)

    @staticmethod
    def clock_timestamp(alias=None):
        return Functions.clock_timestamp(alias=alias)

    @staticmethod
    def current_time(precision=None, alias=None):
        return Expression(_empty, "current_time", _empty, alias=alias)

    @staticmethod
    def current_timestamp(alias=None):
        return Expression(_empty, "current_timestamp", _empty, alias=alias)

    @staticmethod
    def localtime(alias=None):
        return Expression(_empty, "localtime", _empty, alias=alias)

    @staticmethod
    def localtimestamp(alias=None):
        return Expression(_empty, "localtimestamp", _empty, alias=alias)

    @staticmethod
    def transaction_timestamp(alias=None):
        return Functions.transaction_timestamp(alias=alias)

    @staticmethod
    def now(alias=None):
        return Function("now", alias=alias)

    def isfinite(self, **kwargs):
        """ isfinite(timestamp '2001-02-16 21:28:30') """
        return Functions.isfinite(self, **kwargs)


class DateLogic(BaseNumericLogic):

    def interval(self, length, alias=None):
        return Expression(_empty, 'interval', length)

    def last(self, length):
        interval = Expression(
            self.now(), operators.SUB, self.interval(length)).group()
        return Expression(self, operators.GE, interval)

    def age(self, *args, alias=None):
        """ :see::meth:Functions.age """
        return Functions.age(self, *args, alias=alias)

    def current_date(self, alias=None):
        return Expression(_empty, 'current_date', _empty, alias=alias)

    def date_part(self, text, **kwargs):
        """ :see::meth:Functions.date_part """
        return Functions.date_part(text, self, **kwargs)

    def date_trunc(self, text, **kwargs):
        """ :see::meth:Functions.date_trunc """
        return Functions.date_trunc(text, self, **kwargs)

    def extract(self, text, **kwargs):
        """ :see::meth:Functions.extract """
        return Functions.extract(text, self, **kwargs)

    def justify_days(self, *args, **kwargs):
        """ :see::meth:Functions.justify_days """
        return Functions.justify_days(self, *args, **kwargs)

    def justify_interval(self, *args, **kwargs):
        """ :see::meth:Functions.justify_interval """
        return Functions.justify_interval(self, *args, **kwargs)

    def timeofday(self, alias=None):
        """ :see::meth:Functions.timeofday """
        return Functions.timeofday(alias=alias)


class DateTimeLogic(DateLogic, TimeLogic):
    pass


class _DateFields(Field):
    __slots__ = ('_arrow',)

    def __init__(self, *args, **kwargs):
        self._arrow = None
        super().__init__(*args, **kwargs)

    def humanize(self, *args, **kwargs):
        """ :see::meth:arrow.Arrow.humanize """
        return self._arrow.humanize(*args, **kwargs)

    @property
    def validation_value(self):
        if isinstance(self.value, arrow.Arrow):
            return self._arrow.datetime
        else:
            return self.value if self.value is not self.empty else None

    @property
    def arrow(self):
        """ Read-only access to the local :class:arrow.Arrow instance """
        return self._arrow

    @property
    def since_epoch(self):
        return self._arrow.timestamp

    @property
    def microsecond(self):
        return self._arrow.datetime.microsecond

    @property
    def second(self):
        return self._arrow.datetime.second

    @property
    def minute(self):
        return self._arrow.datetime.minute

    @property
    def hour(self):
        return self._arrow.datetime.hour

    @property
    def day(self):
        return self._arrow.datetime.day

    @property
    def month(self):
        return self._arrow.datetime.month

    @property
    def year(self):
        return self._arrow.datetime.year

    @property
    def tzinfo(self):
        return self._arrow.datetime.tzinfo

    @property
    def timezone(self):
        return self._arrow.datetime.tzname()

    def replace(self, *args, **kwargs):
        """ Replaces the current value with the specified :mod: arrow options
            :see::meth:arrow.Arrow.replace
        """
        return self.__call__(self._arrow.replace(*args, **kwargs))

    def fromdate(self, *args, **kwargs):
        """ Sets the value of the field from a date object using :mod:arrow

            :see::meth:arrow.Arrow.fromdate
        """
        return self.__call__(self._arrow.fromdate(*args, **kwargs))

    def fromdatetime(self, *args, **kwargs):
        """ Sets the value of the field from a datetime object using :mod:arrow

            :see::meth:arrow.Arrow.fromdatetime
        """
        return self.__call__(self._arrow.fromdatetime(*args, **kwargs))

    def fromtimestamp(self, *args, **kwargs):
        """ Sets the value of the field from a timestamp using :mod:arrow

            :see::meth:arrow.Arrow.fromtimestamp
        """
        self.__call__(self._arrow.fromtimestamp(*args, **kwargs))

    def isocalendar(self, *args, **kwargs):
        """ :see::meth:arrow.Arrow.isocalendar """
        return self._arrow.isocalendar(*args, **kwargs)

    def isoformat(self, *args, **kwargs):
        """ :see::meth:arrow.Arrow.isoformat """
        return self._arrow.isoformat(*args, **kwargs)

    def isoweekday(self, *args, **kwargs):
        """ :see::meth:arrow.Arrow.isoweekday """
        return self._arrow.isoweekday(*args, **kwargs)

    def toordinal(self, *args, **kwargs):
        """ :see::meth:arrow.Arrow.toordinal """
        return self._arrow.toordinal(*args, **kwargs)

    def for_json(self, *args, **kwargs):
        """ :see::meth:arrow.Arrow.for_json """
        return self._arrow.for_json(*args, **kwargs)

    def utcoffset(self, *args, **kwargs):
        """ :see::meth:arrow.Arrow.utcoffset """
        return self._arrow.utcoffset(*args, **kwargs)


class _TimeFields(_DateFields):
    __slots__ = ('_arrow',)

    def to(self, *args, **kwargs):
        """ Replaces the current value with a value reflecting the new
            timezone.

            :see::meth:arrow.Arrow.to
        """
        return self.__call__(self._arrow.to(*args, **kwargs))

    def utctimetuple(self, *args, **kwargs):
        """ :see::meth:arrow.Arrow.utctimetuple """
        return self._arrow.utctimetuple(*args, **kwargs)

    def timetz(self, *args, **kwargs):
        """ :see::meth:arrow.Arrow.timetz """
        return self._arrow.timetz(*args, **kwargs)

    def time(self, *args, **kwargs):
        """ :see::meth:arrow.Arrow.time """
        return self._arrow.time(*args, **kwargs)


class ArrowTime(arrow.Arrow):
    @staticmethod
    def to_db(val):
        return adapt(val.time()).getquoted().replace(b'timetz', b'time')


class ArrowTimeTZ(ArrowTime):
    @staticmethod
    def to_db(val):
        return adapt(val.time()).getquoted()


class ArrowDate(ArrowTime):
    @staticmethod
    def to_db(val):
        return adapt(val.date()).getquoted()


class ArrowTimestamp(ArrowTime):
    @staticmethod
    def to_db(val):
        return adapt(val.datetime).getquoted().replace(
            b'timestamptz', b'timestamp')


class ArrowTimestampTZ(ArrowTime):
    @staticmethod
    def to_db(val):
        return adapt(val.datetime).getquoted()


register_adapter(ArrowTime, ArrowTime.to_db)
register_adapter(ArrowTimeTZ, ArrowTimeTZ.to_db)
register_adapter(ArrowDate, ArrowDate.to_db)
register_adapter(ArrowTimestamp, ArrowTimestamp.to_db)
register_adapter(ArrowTimestampTZ, ArrowTimestampTZ.to_db)


def _get_arrow(typ, value):
    return typ.fromdatetime(arrow.get(value))


class Time(_TimeFields, TimeLogic, DateLogic):
    """ Field object for the PostgreSQL field type |TIME|. """
    __slots__ = (
        'field_name', 'primary', 'unique', 'index', 'not_null', 'value',
        'validation', 'validation_error', '_alias', 'default', '_arrow',
        'table')
    sqltype = TIME
    _arrow_type = ArrowTime

    def __init__(self, *args, **kwargs):
        """ `Time`
            :see::meth:Field.__init__
        """
        super().__init__(*args, **kwargs)

    def __call__(self, value=Field.empty):
        if value is not Field.empty:
            if isinstance(value, (Expression, Function, Clause)):
                self._arrow = None
                self._set_value(value)
                return self.value
            elif not isinstance(value, arrow.Arrow):
                if isinstance(value, str):
                    value = dateparser.parse(value)
                self._arrow = _get_arrow(self._arrow_type, value)
            else:
                self._arrow = value
            self._set_value(self._arrow)
        return self.value

    def copy(self, *args, **kwargs):
        cls = self._copy(*args, **kwargs)
        cls._arrow = copy.copy(self._arrow)
        return cls

    __copy__ = copy


class TimeTZ(Time):
    """ Field object for the PostgreSQL field type |TIMETZ|. """
    __slots__ = (
        'field_name', 'primary', 'unique', 'index', 'not_null', 'value',
        'validation', 'validation_error', '_alias', 'default', '_arrow',
        'table')
    sqltype = TIMETZ
    _arrow_type = ArrowTimeTZ

    def __init__(self, *args, **kwargs):
        """ `Time WITH timezone`
            :see::meth:Field.__init__
        """
        super().__init__(*args, **kwargs)


class Date(_DateFields, DateLogic):
    """ - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        Field object for the PostgreSQL field type |DATE|.
    """
    __slots__ = (
        'field_name', 'primary', 'unique', 'index', 'not_null', 'value',
        'validation', 'validation_error', '_alias', 'default', '_arrow',
        'table')
    sqltype = DATE
    _arrow_type = ArrowDate

    def __init__(self, value=Field.empty, **kwargs):
        """ `Date`
            :see::meth:Field.__init__
        """
        self._arrow = None
        super().__init__(value=value, **kwargs)

    __call__ = Time.__call__

    def copy(self, *args, **kwargs):
        cls = self._copy(*args, **kwargs)
        cls._arrow = copy.copy(self._arrow)
        return cls

    __copy__ = copy


class Timestamp(Time):
    """ - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        Field object for the PostgreSQL field type |TIMESTAMP|.
    """
    __slots__ = (
        'field_name', 'primary', 'unique', 'index', 'not_null', 'value',
        'validation', 'validation_error', '_alias', 'default', '_arrow',
        'table')
    sqltype = TIMESTAMP
    _arrow_type = ArrowTimestamp

    def __init__(self, value=Field.empty, **kwargs):
        """ `Timestamp`
            :see::meth:Field.__init__
        """
        super().__init__(value=value, **kwargs)


class TimestampTZ(Time):
    """ - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        Field object for the PostgreSQL field type |TIMESTAMPTZ|.
    """
    __slots__ = (
        'field_name', 'primary', 'unique', 'index', 'not_null', 'value',
        'validation', 'validation_error', '_alias', 'default', '_arrow',
        'table')
    sqltype = TIMESTAMPTZ
    _arrow_type = ArrowTimestampTZ

    def __init__(self, value=Field.empty, **kwargs):
        """ `Timestamp WITH timezone`
            :see::meth:Field.__init__
        """
        super().__init__(value=value, **kwargs)
