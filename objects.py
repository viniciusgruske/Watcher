from bson.objectid import ObjectId
from collections import deque
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from pymongo.collection import Collection
from pynput import keyboard
from typing import Any, Dict
    
@dataclass
class DatabaseCollections():
    apps            : Collection[Dict[str, Any]]
    events          : Collection[Dict[str, Any]]
    reports         : Collection[Dict[str, Any]]
    users           : Collection[Dict[str, Any]]

class SensorEvent(Enum):
    MOUSE_MOVE      = 0
    MOUSE_CLICK     = 1
    MOUSE_SCROLL    = 2
    KEYBOARD_PRESS  = 3

@dataclass
class SensorCounters():
    all     : int = 0
    mouse   : int = 0
    keyboard: int = 0

@dataclass
class EventsQueue:
    activity    : deque[tuple[bool, datetime]]          = field(default_factory=deque)
    app         : deque[tuple[str, datetime]]           = field(default_factory=deque)
    sensor      : deque[tuple[SensorEvent, datetime]]   = field(default_factory=deque)
    
class EventType(Enum):
    ACTIVITY    = 0
    APP         = 1
    SENSOR      = 2
    EXCEPTION   = 3
    
@dataclass
class SensorLast():
    event       : SensorEvent | None                        = None
    move_time   : datetime                                  = field(default_factory=datetime.now)
    click_time  : datetime                                  = field(default_factory=datetime.now)
    scroll_time : datetime                                  = field(default_factory=datetime.now)
    pressed_key : keyboard.Key | keyboard.KeyCode | None    = None
    pressed_time: datetime                                  = field(default_factory=datetime.now)
        
@dataclass
class ReporterApp():
    id  : ObjectId
    name: str
    active_time: int = 0
    screen_time: int = 0

@dataclass    
class ReporterUserData():
    id  : ObjectId
    name: str
    
@dataclass    
class ReporterData():
    user            : ReporterUserData
    apps            : dict[str, ReporterApp]
    active_time     : int                       = 0
    screen_time     : int                       = 0
    sensor_counters : SensorCounters            = field(default_factory=SensorCounters)
    
@dataclass
class ReporterEvent():
    event       : dict[str, Any]
    timestamp   : datetime          = field(default_factory=datetime.now)
    
@dataclass
class WatcherApp():
    name        : str
    active_time : timedelta = field(default_factory=timedelta)
    screen_time : timedelta = field(default_factory=timedelta)
    
@dataclass
class WatcherData():
    USERNAME            : str
    today               : date                    = field(default_factory=lambda: datetime.now().date())
    INIT_TIME           : datetime                = field(default_factory=datetime.now)
    last_time           : datetime                = field(default_factory=datetime.now)
    last_active_time    : datetime                = field(default_factory=datetime.now)
    is_active           : bool                    = False
    active_time         : timedelta               = field(default_factory=timedelta)
    screen_time         : timedelta               = field(default_factory=timedelta)
    sensor_counters     : SensorCounters          = field(default_factory=SensorCounters)
    last_app            : str                     = ''
    apps                : dict[str, WatcherApp]   = field(default_factory=dict)