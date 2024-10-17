from datetime import datetime, timedelta
from typing import Callable
from pynput import mouse, keyboard

from config import LOG_SENSOR_EVENTS, MOVE_INTERVAL, CLICK_INTERVAL, SCROLL_INTERVAL, PRESS_INTERVAL
from logger import logger, LOG_PID
from objects import SensorEvent, SensorCounters, SensorLast

LOG_PREFIX = f"{LOG_PID} {'sensor.py':<20}"
    
class Sensor():
    sensor_counter  = SensorCounters()
    sensor_last     = SensorLast()

    @classmethod
    def __log_counter_event(cls) -> None:
        if cls.sensor_counter.all % LOG_SENSOR_EVENTS == 0:
            logger.info(f'{LOG_PREFIX} The Sensor counted {cls.sensor_counter.all} events')

    @classmethod
    def __is_valid_mouse_event(cls, event: SensorEvent) -> bool:
        if cls.sensor_last.event == event:
            return False
        
        now = datetime.now()
        
        match event:
            case SensorEvent.MOUSE_MOVE:
                if (now - cls.sensor_last.move_time) < timedelta(seconds=MOVE_INTERVAL):
                    return False
                cls.sensor_last.move_time = now
            case SensorEvent.MOUSE_CLICK:
                if (now - cls.sensor_last.click_time) < timedelta(seconds=CLICK_INTERVAL):
                    return False
                cls.sensor_last.click_time = now
            case SensorEvent.MOUSE_SCROLL:
                if (now - cls.sensor_last.scroll_time) < timedelta(seconds=SCROLL_INTERVAL):
                    return False
                cls.sensor_last.scroll_time = now
            case _:
                return False

        cls.sensor_counter.mouse += 1
        cls.sensor_counter.all += 1
        cls.sensor_last.event = event
        
        return True
        
    @classmethod
    def __is_valid_keyboard_event(cls, key: keyboard.Key | keyboard.KeyCode | None) -> bool:
        if cls.sensor_last.pressed_key == key:
            return False
        
        now = datetime.now()
        
        if (now - cls.sensor_last.pressed_time) < timedelta(seconds=PRESS_INTERVAL):
            return False
        
        cls.sensor_counter.keyboard += 1
        cls.sensor_counter.all += 1
        cls.sensor_last.pressed_key = key
        cls.sensor_last.pressed_time = now
        
        return True
    
    @classmethod
    def __log_mouse_event(cls, event: SensorEvent) -> None:
        logger.debug(f'{LOG_PREFIX} {event.name} event')
        
        cls.__log_counter_event()
        
        if cls.sensor_counter.mouse % LOG_SENSOR_EVENTS == 0:
            logger.info(f'{LOG_PREFIX} The Sensor counted {cls.sensor_counter.mouse} mouse events')
                
    @classmethod
    def __log_keyboard_event(cls) -> None:        
        logger.debug(f'{LOG_PREFIX} KEYBOARD_PRESS event')
    
        cls.__log_counter_event()
    
        if cls.sensor_counter.keyboard % LOG_SENSOR_EVENTS == 0:
            logger.info(f'{LOG_PREFIX} The Sensor counted {cls.sensor_counter.keyboard} keyboard events')        
                    
    @classmethod
    def run(cls, callback: Callable[[SensorCounters, SensorEvent],  None], move_sensor: bool = True, click_sensor: bool = True, scroll_sensor: bool = True, press_sensor: bool = True) -> None:
        logger.debug(f'{LOG_PREFIX} Running Sensor')
        
        # Mouse events
        def __on_move(x: int, y: int) -> bool | None:
            if not cls.__is_valid_mouse_event(SensorEvent.MOUSE_MOVE):
                return None
            
            cls.__log_mouse_event(SensorEvent.MOUSE_MOVE)
            callback(cls.sensor_counter, SensorEvent.MOUSE_MOVE)

        def __on_click(x: int, y: int, button: mouse.Button, pressed: bool) -> bool | None:
            if not cls.__is_valid_mouse_event(SensorEvent.MOUSE_CLICK):
                return None
            
            cls.__log_mouse_event(SensorEvent.MOUSE_CLICK)
            callback(cls.sensor_counter, SensorEvent.MOUSE_CLICK)

        def __on_scroll(x: int, y: int, dx: int, dy: int) -> bool | None:
            if not cls.__is_valid_mouse_event(SensorEvent.MOUSE_SCROLL):
                return None
            
            cls.__log_mouse_event(SensorEvent.MOUSE_SCROLL)
            callback(cls.sensor_counter, SensorEvent.MOUSE_SCROLL)

        # Keyboard event
        def __on_press(key: keyboard.Key | keyboard.KeyCode | None) -> None:
            if not cls.__is_valid_keyboard_event(key):
                return None
            
            cls.__log_keyboard_event()
            callback(cls.sensor_counter, SensorEvent.KEYBOARD_PRESS)
            
        on_move = __on_move if move_sensor else None
        on_click = __on_click if click_sensor else None
        on_scroll = __on_scroll if scroll_sensor else None
        on_press = __on_press if press_sensor else None
        
        mouse_listener = mouse.Listener(on_move=on_move, on_click=on_click, on_scroll=on_scroll)
        keyboard_listener = keyboard.Listener(on_press=on_press)
        
        mouse_listener.start()
        keyboard_listener.start()