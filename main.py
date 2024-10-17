import os
import psutil
from threading import Thread, Event
from time import sleep
from logger import logger, LOG_PID
from reporter import Reporter
from stray import SystemTray
from watcher import Watcher

LOG_PREFIX = f"{LOG_PID} {'watcher.py':<20}"

def is_watcher_already_running():
    current_process_id = os.getpid()    
    current_process = psutil.Process(current_process_id)
    current_process_description = Watcher.get_process_description(current_process)
    
    logger.debug(f'{LOG_PREFIX} current_process_id: {current_process_id}')
    logger.debug(f'{LOG_PREFIX} current_process: {current_process}')
    logger.debug(f'{LOG_PREFIX} current_process_description: {current_process_description}')
    
    already_running_counter = 0

    for process in psutil.process_iter(['pid', 'name', 'username']):
        try:
            if process.pid == current_process_id:
                continue
            
            process_description = Watcher.get_process_description(process)
            
            if current_process_description == process_description and current_process.username() == process.username():
                already_running_counter += 1
                logger.debug(f'{LOG_PREFIX} already_running_counter: {already_running_counter}')
                logger.debug(f'{LOG_PREFIX} process.pid: {process.pid}')
                logger.debug(f'{LOG_PREFIX} process: {process}')
                logger.debug(f'{LOG_PREFIX} process_description: {process_description}')
                if already_running_counter > 1:
                    logger.debug(f'{LOG_PREFIX} is_watcher_already_running(): True')
                    return True
                
        except: 
            continue

    logger.debug(f'{LOG_PREFIX} is_watcher_already_running(): False')
    return False

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
        logger.info(f'{LOG_PREFIX} Starting Threads')
        
        if restart_counter != 0:
            logger.warning(f'{LOG_PREFIX} restart_counter: {restart_counter}')
            
        stop_event, watcher, reporter, stray = run()
        
        logger.info(f'{LOG_PREFIX} Threads started')

        while watcher[1].is_alive() and reporter[1].is_alive() and stray[1].is_alive():
            sleep(1)

        logger.warning(f'{LOG_PREFIX} A thread stopped, restarting all threads')

        stop_event.set()

        watcher[1].join()
        logger.info(f'{LOG_PREFIX} Watcher thread stopped')
        
        reporter[1].join()
        logger.info(f'{LOG_PREFIX} Reporter thread stopped')
        
        stray[0].icon.stop()
        stray[1].join()
        logger.info(f'{LOG_PREFIX} System Tray thread stopped')

        sleep(2)
        restart_counter += 1

if __name__ == "__main__":
    logger.info(f'{LOG_PREFIX} Starting program with PID {os.getpid()}')
    if is_watcher_already_running():
        logger.info(f"{LOG_PREFIX} Watcher already running on user '{psutil.Process(os.getpid()).username()}'")
    else:
        infinity_run()