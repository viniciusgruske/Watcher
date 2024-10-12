import os
import sys
from datetime import datetime
from pystray import Icon, Menu, MenuItem # type: ignore
from PIL import Image
from threading import Event

from logger import logger, LOG_FILE
from reporter import Reporter
from watcher import Watcher

LOG_PREFIX = 'stray.py'


class SystemTray():
    def __init__(self, watcher: Watcher, reporter: Reporter, stop_event: Event) -> None:
        logger.debug(f'{LOG_PREFIX:<20} Instantiating SystemTray')
        
        self.watcher = watcher
        self.reporter = reporter
        self.stop_event = stop_event
        
        if getattr(sys, 'frozen', False):
            base_path = str(sys._MEIPASS) # type: ignore
        else:
            base_path = os.path.abspath(".")
            
        icon_image = Image.open(os.path.join(base_path, "images", "icon.png"))
        
        self.icon = Icon("Watcher", icon_image, "Watcher")
        
        self.menu = Menu(
            MenuItem(f"Tempo total ativo:", None, enabled=False),
            MenuItem(self.__get_total_active_time, None, enabled=False),
            MenuItem('', None, enabled=False),
            MenuItem(f"Tempo total de tela:", None, enabled=False),
            MenuItem(self.__get_total_screen_time, None, enabled=False),
            MenuItem('', None, enabled=False),
            MenuItem(f"Última sincronização:", None, enabled=False),
            MenuItem(self.__get_last_save, None, enabled=False),
            MenuItem('', None, enabled=False),
            MenuItem("Abrir arquivo de log", self.__open_log_file),
            MenuItem("Atualizar", self.__update_menu),
        )
        
        self.icon.menu = self.menu
        
    def __open_log_file(self) -> None:
        logger.info(f'{LOG_PREFIX:<20} Opening log file')
        os.startfile(LOG_FILE)
        
    def __update_menu(self) -> None:
        logger.info(f'{LOG_PREFIX:<20} Updating SystemTray')
        self.icon.update_menu()
    
    def __get_total_active_time(self, _: MenuItem) -> str:
        active_time = self.watcher.data.active_time.seconds
        
        active_hours = active_time // 3600
        active_minutes = (active_time % 3600) // 60
        active_seconds = active_time % 60
        
        return f"{active_hours:02d}h{active_minutes:02d}m{active_seconds:02d}s"
    
    def __get_total_screen_time(self, _: MenuItem) -> str:
        screen_time = self.watcher.data.screen_time.seconds
        
        screen_hours = screen_time // 3600
        screen_minutes = (screen_time % 3600) // 60
        screen_seconds = screen_time % 60
        
        return f"{screen_hours:02d}h{screen_minutes:02d}m{screen_seconds:02d}s"
    
    def __get_last_save(self, _: MenuItem) -> str:
        last_save = self.reporter.last_save
        
        if not last_save:
            return "Nunca sincronizado"
        
        time_since_last_save = (datetime.now() - last_save).seconds
        
        time_hours = time_since_last_save // 3600
        time_minutes = (time_since_last_save % 3600) // 60
        time_seconds = time_since_last_save % 60
        
        return f"{time_hours:02d}h{time_minutes:02d}m{time_seconds:02d}s"
                    
    def run(self) -> None:
        try:
            logger.debug(f'{LOG_PREFIX:<20} Running SystemTray')
            self.icon.run() # type: ignore
        except Exception as e:
            print('System Tray Exception')
            print(e)
            self.stop_event.set()
            self.icon.stop()