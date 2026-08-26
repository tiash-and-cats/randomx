import time
from decimal import Decimal

_HRS_IN_DAY = 24
_MINS_IN_HR = 60
_SECS_IN_MIN = 60

_SECS_IN_HR = _MINS_IN_HR * _SECS_IN_MIN
_SECS_IN_DAY = _HRS_IN_DAY * _SECS_IN_HR

class Duration:
    def __init__(self, seconds=Decimal("0"), *, minutes=0, hours=0, days=0):
        self._tsdiff = Decimal(seconds)
        self._tsdiff += minutes * _SECS_IN_MIN
        self._tsdiff += hours * _SECS_IN_HR
        self._tsdiff += days * _SECS_IN_DAY

    def _calc(self):
        days, seconds = divmod(self._tsdiff, _SECS_IN_DAY)
        hours, seconds = divmod(seconds, _SECS_IN_HR)
        minutes, seconds = divmod(seconds, _SECS_IN_MIN)
        return days, hours, minutes, seconds
    
    @property
    def days(self):
        return self._calc()[0]
    
    @property
    def hours(self):
        return self._calc()[1]
    
    @property
    def minutes(self):
        return self._calc()[2]
    
    @property
    def seconds(self):
        return self._calc()[3]

    def __repr__(self):
        days, hours, minutes, seconds = self._calc()
        return type(self).__name__ + \
            f"({days=}, {hours=}, {minutes=}, {seconds=})"
    
    def __add__(self, other):
        return Duration(self._tsdiff + other._tsdiff)
    
    def __sub__(self, other):
        return Duration(self._tsdiff - other._tsdiff)
    
    def __str__(self):
        days, hours, minutes, seconds = self._calc()
        
        s = []
        if days:
            s.append(f"{days}d")
        if hours:
            s.append(f"{hours}h")
        if minutes:
            s.append(f"{minutes}m")
        if seconds:
            s.append(f"{seconds:.0f}s")
        
        return " ".join(s)
#
class Timestamp(Duration):
    @classmethod
    def now(cls):
        return cls(time.time())
    
    def __str__(self):
        return "timestamp: " + super().__str__()