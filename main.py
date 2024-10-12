from threading import Thread, Event
from time import sleep
from logger import logger
from reporter import Reporter
from stray import SystemTray
from watcher import Watcher

LOG_PREFIX = "watcher.py"

def run():
    stop_event  = Event()

    watcher     = Watcher(stop_event)
    reporter    = Reporter(watcher, stop_event)
    stray       = SystemTray(watcher, reporter, stop_event)

    watcher_thread  = Thread(target=watcher.run)
    reporter_thread = Thread(target=reporter.run)
    stray_thread    = Thread(target=stray.run)

    watcher_thread.start()
    reporter_thread.start()
    stray_thread.start()

    return stop_event, (watcher, watcher_thread), (reporter, reporter_thread), (stray, stray_thread)

def infinity_run():
    restart_counter = 0
    while True:
        logger.info(f'{LOG_PREFIX:<20} Starting program')
        
        if restart_counter != 0:
            logger.warning(f'{LOG_PREFIX:<20} restart_counter: {restart_counter}')
            
        stop_event, watcher, reporter, stray = run()
        
        logger.info(f'{LOG_PREFIX:<20} Program started')

        while watcher[1].is_alive() and reporter[1].is_alive() and stray[1].is_alive():
            sleep(1)

        logger.warning(f'{LOG_PREFIX:<20} A thread stopped, restarting all threads')

        stop_event.set()

        watcher[1].join()
        logger.info(f'{LOG_PREFIX:<20} Watcher thread stopped')
        
        reporter[1].join()
        logger.info(f'{LOG_PREFIX:<20} Reporter thread stopped')
        
        stray[0].icon.stop()
        stray[1].join()
        logger.info(f'{LOG_PREFIX:<20} System Tray thread stopped')

        sleep(2)
        restart_counter += 1

if __name__ == "__main__":
    infinity_run()
