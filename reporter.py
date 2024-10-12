from bson.objectid import ObjectId
from datetime import datetime, date, time
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import ServerSelectionTimeoutError
from threading import Event
from time import sleep
from typing import Any, Dict

from config import MONGODB_URL, REPORTER_INTERVAL
from logger import logger
from objects import DatabaseCollections, EventsQueue, EventType, ReporterApp, ReporterData, ReporterUserData
from watcher import Watcher

LOG_PREFIX = "reporter.py"

class Reporter:
    def __init__(self, watcher: Watcher, stop_event: Event) -> None:
        logger.debug(f'{LOG_PREFIX:<20} Instantiating Reporter')
        
        self.watcher = watcher
        self.stop_event = stop_event
        
        self.mongodb: Database[Dict[str, Any]] = MongoClient(MONGODB_URL).get_database("watcher")
        
        self.events_queue = EventsQueue()
        self.last_save: datetime | None = None
        
        self.db = DatabaseCollections(
            self.mongodb.apps,
            self.mongodb.events,
            self.mongodb.reports,
            self.mongodb.users
        )
        
    def __get_or_create_user_id(self, username: str) -> ObjectId | None:
        user = self.db.users.find_one({"username": username})
        
        if user:
            return user.get('_id')
        else:
            new_user = {"username": username}
            result = self.db.users.insert_one(new_user)
            return result.inserted_id
        
    def __get_or_create_app_id(self, app_name: str) -> ObjectId | None:
        app: dict[str, ObjectId] | None = self.db.apps.find_one({"app": app_name})
        app_id: ObjectId | None
        
        if app:
            app_id = app.get('_id')
        else:
            new_app = {"app": app_name}
            result = self.db.apps.insert_one(new_app)
            app_id = result.inserted_id
                        
        if not app_id:
            return None
        
        self.data.apps[app_name] = ReporterApp(app_id, app_name)
        
        return app_id
        
    def __get_apps_db(self) -> dict[str, ReporterApp] | None:
        db_apps = self.db.apps.find()
        if not db_apps:
            return None
        
        apps: dict[str, ReporterApp] = dict()
        for app in db_apps:
            app_id: ObjectId | None = app.get('_id')
            app_name: str | None = app.get('app')
            
            if not app_name or not app_id:
                continue
            
            apps[app_name] = ReporterApp(app_id, app_name)
            
        return apps
 
    def __get_apps(self) -> dict[str, ReporterApp]:
        apps_db = self.__get_apps_db()
        apps: dict[str, ReporterApp] = dict()
        
        if not apps_db:
            logger.warning(f'{LOG_PREFIX:<20} Cannot get apps_db')
            logger.debug(f'{LOG_PREFIX:<20} apps_db: {apps_db}')
            return self.data.apps
            
        for app in apps_db.values():
            app_id = app.id
            app_name = app.name
            
            if not app_name:
                logger.warning(f'{LOG_PREFIX:<20} Cannot get app_name from apps_db')
                logger.debug(f'{LOG_PREFIX:<20} app_name: {app_name}')
                logger.debug(f'{LOG_PREFIX:<20} app: {app}')
                continue
            
            if not app_id:
                logger.warning(f'{LOG_PREFIX:<20} Cannot get app_id from apps_db')
                logger.debug(f'{LOG_PREFIX:<20} app_id: {app_id}')
                logger.debug(f'{LOG_PREFIX:<20} app: {app}')
                continue
            
            apps[app_name] = ReporterApp(app_id, app_name)
        
        return apps
           
    def __get_report_db(self, user_id: ObjectId) -> Dict[str, Any] | None:
        return self.db.reports.find_one({"date": datetime.combine(date.today(), time.min), "user": user_id})
        
    def __create_empty_report(self, user_id: ObjectId) -> ObjectId | None:    
        new_report: dict[str, Any] = {
            "date": datetime.combine(date.today(), time.min), 
            "user": user_id,
            "active_time": 0,
            "screen_time": 0,
            "sensor_counter": 0,
            "apps": {},
            "sessions": {},
        }
        result = self.db.reports.insert_one(new_report)
        return result.inserted_id

    def __log_active_time(self) -> None:
        hours = self.data.active_time // 3600
        minutes = (self.data.active_time % 3600) // 60
        seconds = self.data.active_time % 60
            
        logger.info(f'{LOG_PREFIX:<20} Active time: {hours:02d}:{minutes:02d}:{seconds:02d}')
        
    def __log_screen_time(self) -> None:
        hours = self.data.screen_time // 3600
        minutes = (self.data.screen_time % 3600) // 60
        seconds = self.data.screen_time % 60
            
        logger.info(f'{LOG_PREFIX:<20} Screen time: {hours:02d}:{minutes:02d}:{seconds:02d}')

    def __update_report_apps(self, report: dict[str, Any]) -> dict[str, Any]:
        for watcher_app in self.watcher.data.apps.values():
            app_id = self.data.apps.get(watcher_app.name)
            
            if not app_id:
                app_id = self.__get_or_create_app_id(watcher_app.name)
                
                if not app_id:
                    logger.warning(f'{LOG_PREFIX:<20} Cannot get app_id')
                    logger.debug(f'{LOG_PREFIX:<20} app_id: {app_id}')
                    continue
            
            if watcher_app.name not in report['apps']:
                report['apps'][watcher_app.name] = {'active_time': 0, 'screen_time': 0}
            
            report['apps'][watcher_app.name]['active_time'] += watcher_app.active_time.seconds - self.data.apps[watcher_app.name].active_time
            report['apps'][watcher_app.name]['screen_time'] += watcher_app.screen_time.seconds - self.data.apps[watcher_app.name].screen_time
            
            self.data.apps[watcher_app.name].active_time = watcher_app.active_time.seconds
            self.data.apps[watcher_app.name].screen_time = watcher_app.screen_time.seconds
            
        return report

    def __update_report_sessions(self, report: dict[str, Any], active_time_delta: int, screen_time_delta: int, sensor_counter_delta: int) -> dict[str, Any]:
        last_watch = self.watcher.data.last_time
        session_key = self.watcher.data.INIT_TIME.isoformat()
        
        for session in report['sessions']:
            session: datetime
            if session == session_key:
                report['sessions'][session_key]['last_watch'] = last_watch
                report['sessions'][session_key]['active_time'] += active_time_delta
                report['sessions'][session_key]['screen_time'] += screen_time_delta
                report['sessions'][session_key]['sensor_counter'] += sensor_counter_delta
                break
        else:
            report['sessions'][session_key] = {
                "init_watch": self.watcher.data.INIT_TIME,
                "last_watch": last_watch,
                "active_time": active_time_delta,
                "screen_time": screen_time_delta,
                "sensor_counter": sensor_counter_delta
            }
        
        return report

    def __update_report_total_deltas(self, report: dict[str, Any], active_time_delta: int, screen_time_delta: int, sensor_counter_delta: int) -> dict[str, Any]:
        report['active_time'] += active_time_delta
        report['screen_time'] += screen_time_delta
        report['sensor_counter'] += sensor_counter_delta
        
        return report

    def __get_report_total_deltas(self) -> tuple[int, int, int]:
        # active_time
        active_time_delta = self.watcher.data.active_time.seconds - self.data.active_time
        self.data.active_time = self.watcher.data.active_time.seconds
        
        # screen_time
        screen_time_delta = self.watcher.data.screen_time.seconds - self.data.screen_time
        self.data.screen_time = self.watcher.data.screen_time.seconds
        
        # sensor_counter
        sensor_counter_delta = self.watcher.data.sensor_counters.all - self.data.sensor_counters.all
        self.data.sensor_counters.all = self.watcher.data.sensor_counters.all
        
        return active_time_delta, screen_time_delta, sensor_counter_delta
    
    def __proccess_report(self, report: dict[str, Any]) -> dict[str, Any]:
        active_time_delta, screen_time_delta, sensor_counter_delta = self.__get_report_total_deltas()
        
        report = self.__update_report_apps(report)
        report = self.__update_report_sessions(report, active_time_delta, screen_time_delta, sensor_counter_delta)
        report = self.__update_report_total_deltas(report, active_time_delta, screen_time_delta, sensor_counter_delta)
            
        return report

    def __write_activity_events(self) -> None:
        while self.watcher.events_queue.activity:
            activity = self.watcher.events_queue.activity.popleft()
            self.events_queue.activity.append(activity)
            logger.debug(f'{LOG_PREFIX:<20} activity: {activity}')
            
        if not self.events_queue.activity:
            return
            
        documents: list[dict[str, Any]] = []
        activity_dict: dict[str, Any] = dict()
        for activity in self.events_queue.activity:
            activity_dict['active'] = activity[0]
            activity_dict['timestamp'] = activity[1]
            activity_dict['type'] = EventType.ACTIVITY.value
            activity_dict['user'] = self.data.user.id
            activity_dict['session'] = self.watcher.data.INIT_TIME.isoformat()
            
            documents.append(activity_dict)
            
        self.db.events.insert_many(documents)
        logger.success(f'{LOG_PREFIX:<20} The activity events have been saved in the database')
        
        self.events_queue.activity.clear()
        
    def __write_app_events(self) -> None:
        while self.watcher.events_queue.app:
            app = self.watcher.events_queue.app.popleft()
            self.events_queue.app.append(app)
            logger.debug(f'{LOG_PREFIX:<20} app: {app}')
            
        if not self.events_queue.app:
            return
            
        documents: list[dict[str, Any]] = []
        app_dict: dict[str, Any] = dict()
        for app in self.events_queue.app:
            app_dict['app'] = self.__get_or_create_app_id(app[0])
            app_dict['timestamp'] = app[1]
            app_dict['type'] = EventType.APP.value
            app_dict['user'] = self.data.user.id
            app_dict['session'] = self.watcher.data.INIT_TIME.isoformat()
            
            documents.append(app_dict)
            
        self.db.events.insert_many(documents)
        logger.success(f'{LOG_PREFIX:<20} The app events have been saved in the database')
        
        self.events_queue.app.clear()

    def __write_sensor_events(self) -> None:
        while self.watcher.events_queue.sensor:
            sensor = self.watcher.events_queue.sensor.popleft()
            self.events_queue.sensor.append(sensor)
            logger.debug(f'{LOG_PREFIX:<20} sensor: {sensor}')
            
        if not self.events_queue.sensor:
            return

        documents: list[dict[str, Any]] = []
        sensor_dict: dict[str, Any] = dict()
        for sensor in self.events_queue.sensor:
            sensor_dict['sensor'] = sensor[0].value
            sensor_dict['timestamp'] = sensor[1]
            sensor_dict['type'] = EventType.SENSOR.value
            sensor_dict['user'] = self.data.user.id
            sensor_dict['session'] = self.watcher.data.INIT_TIME.isoformat()

            documents.append(sensor_dict)

        self.db.events.insert_many(documents)
        logger.success(f'{LOG_PREFIX:<20} The sensor events have been saved in the database')
        
        self.events_queue.sensor.clear()

    def __write_report(self, report: dict[str, Any], report_id: ObjectId) -> None:
        update_one = self.db.reports.update_one(filter={'_id': report_id}, update={'$set': report}, upsert=True)

        if update_one.modified_count == 0:
            logger.warning(f'{LOG_PREFIX:<20} The report data were not saved in the database: no document modified')
            logger.debug(f'{LOG_PREFIX:<20} update_one.matched_count: {update_one.matched_count}')
            logger.debug(f'{LOG_PREFIX:<20} update_one.modified_count: {update_one.modified_count}')
            return None

        self.last_save = datetime.now()
        logger.success(f'{LOG_PREFIX:<20} The report data have been saved in the database')

    def __run(self) -> None:
        sleep(REPORTER_INTERVAL)
        report = self.__get_report_db(self.data.user.id)

        if not report:
            self.__create_empty_report(self.data.user.id)
            report = self.__get_report_db(self.data.user.id)

            if not report:
                logger.warning(f'{LOG_PREFIX:<20} Cannot get report')
                logger.debug(f'{LOG_PREFIX:<20} report: {report}')
                return None

        report_id: ObjectId | None = report.get('_id')

        if not report_id:
            logger.warning(f'{LOG_PREFIX:<20} Cannot get report_id')
            logger.debug(f'{LOG_PREFIX:<20} report_id: {report_id}')
            return None

        report = self.__proccess_report(report)

        self.__log_active_time()
        self.__log_screen_time()

        self.__write_report(report, report_id)
        self.__write_activity_events()
        self.__write_app_events()
        self.__write_sensor_events()

    def write_exception_event(self, restart_counter: int) -> None:
        document: dict[str, Any] = {
            'restarts': restart_counter,
            'timestamp': datetime.now(),
            'type': EventType.EXCEPTION.value,
            'user': self.data.user.id
        }
        self.db.events.insert_one(document)

    def run(self) -> None:
        logger.debug(f'{LOG_PREFIX:<20} Running Reporter')
        
        while not self.stop_event.is_set():
            try:
                username = self.watcher.data.USERNAME
                user_id = self.__get_or_create_user_id(username)
                
                if not user_id:
                    logger.warning(f'{LOG_PREFIX:<20} Cannot get user_id')
                    logger.debug(f'{LOG_PREFIX:<20} user_id: {user_id}')
                    raise Exception('Cannot get user_id')
                
                user = ReporterUserData(user_id, username)                
                self.data = ReporterData(user, self.__get_apps())
                
                while True:
                    self.__run()
            except ServerSelectionTimeoutError:
                logger.warning(f'{LOG_PREFIX:<20} The data were not saved in the database: database timeout')
            except Exception:
                logger.exception(f'{LOG_PREFIX:<20} Exception on running ↴')
                self.stop_event.set()