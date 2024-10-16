import ctypes
import psutil
import win32api
from datetime import datetime, timedelta
from threading import Event
from time import sleep

from config import ACTIVE_TIMEOUT, SENSORS, WATCHER_INTERVAL
from logger import logger, LOG_PID
from objects import SensorEvent, SensorCounters, WatcherApp, WatcherData, EventsQueue
from sensor import Sensor

LOG_PREFIX = f"{LOG_PID} {'watcher.py':<20}"

class Watcher():
    def __init__(self, stop_event: Event) -> None:
        logger.debug(f'{LOG_PREFIX} Instantiating Watcher')
        
        self.stop_event = stop_event
        
        self.user32_dll = ctypes.windll.user32
        
        self.data = WatcherData(self.get_active_window_process().username())
        
        self.events_queue = EventsQueue()
        
    def __sensor_callback(self, sensor_counters: SensorCounters, sensor_event: SensorEvent) -> None:
        now = datetime.now()
        
        self.data.sensor_counters = sensor_counters
        self.data.last_active_time = now
        
        if not self.data.is_active:
            self.data.is_active = True
            self.events_queue.activity.append((self.data.is_active, now))
            
            logger.info(f'{LOG_PREFIX} Activity detected')
            
        self.events_queue.sensor.append((sensor_event, datetime.now()))
        
    def get_active_window_process(self) -> psutil.Process:
        hwnd = self.user32_dll.GetForegroundWindow()
        pid = ctypes.c_ulong()

        self.user32_dll.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

        return psutil.Process(pid.value)
         
    @classmethod
    def get_process_description(cls, process: psutil.Process) -> str:
        if process.pid == 0:
            return ""
        
        try:
            file_path = process.exe()
            lang, codepage = win32api.GetFileVersionInfo(file_path, '\\VarFileInfo\\Translation')[0] # type: ignore
            description_key = f'\\StringFileInfo\\{lang:04x}{codepage:04x}\\FileDescription'

            description = win32api.GetFileVersionInfo(file_path, description_key)
            return str(description) if description else process.name()

        except:
            return process.name()
    
    def __run(self):
        logger.debug(f'{LOG_PREFIX} Running Watcher')
        Sensor.run(self.__sensor_callback, SENSORS[0], SENSORS[1], SENSORS[2], SENSORS[3])
        
        while not self.stop_event.is_set():
            sleep(WATCHER_INTERVAL)
            
            active_window_process = self.get_active_window_process()
            active_window_description = self.get_process_description(active_window_process)
                
            if active_window_description == 'System Idle Process':
                continue
                
            if active_window_description not in self.data.apps:
                self.data.apps[active_window_description] = WatcherApp(active_window_description)
                
            now = datetime.now()
            
            delta_time = now - self.data.last_time
            delta_active_time = now - self.data.last_active_time
            
            self.data.screen_time += delta_time
            self.data.apps[active_window_description].screen_time += delta_time
            
            if active_window_description != self.data.last_app:
                logger.debug(f'{LOG_PREFIX} {active_window_description}')
                self.events_queue.app.append((self.data.apps[active_window_description].name, now))
            
            if self.data.is_active and delta_active_time > timedelta(seconds=ACTIVE_TIMEOUT):
                self.data.is_active = False
                self.events_queue.activity.append((self.data.is_active, now))
                
                logger.info(f'{LOG_PREFIX} Inactivity detected')
                
            if self.data.is_active:
                self.data.active_time += delta_time
                self.data.apps[active_window_description].active_time += delta_time
                
            self.data.last_time = now
            self.data.last_app = active_window_description
            
    def run(self):
        try:
            self.__run()
        except Exception:
            logger.exception(f'{LOG_PREFIX} Exception on running ↴')
            self.stop_event.set()