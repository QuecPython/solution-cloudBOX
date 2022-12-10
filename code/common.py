"""
公共功能

Logger :日志输出
Abstract:抽象父类
Lock: 互斥锁
ConfigStoreManager:文件系统管理
"""

import _thread
import utime
import usys
import ql_fs
from usr import EventMesh

DEBUG = 0
INFO = 1
WARNING = 2
ERROR = 3
CRITICAL = 4
DESC = {
    DEBUG: "DEBUG",
    INFO: "INFO",
    WARNING: "WARNING",
    ERROR: "ERROR",
    CRITICAL: "CRITICAL",
}

def log(obj, level, *message, local_only=False, return_only=False, timeout=None):
    if level < obj._level:
        return
    name = obj.name
    level = DESC[level]
    if hasattr(utime, "strftime"):
        print("[{}]".format(utime.strftime("%Y-%m-%d %H:%M:%S")), "[{}]".format(name),
              "[{}]".format(level), *message)
    else:
        t = utime.localtime()
        print("[{}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}]".format(*t), "[{}]".format(name),
              "[{}]".format(level), *message)
    if return_only:
        return

class Logger(object):
    def __init__(self, name):
        self.name = name
        self._level = DEBUG

    def set_level(self, level):
        if level > CRITICAL or level < DEBUG:
            raise Exception("日志级别错误")
        self._level = level

    def critical(self, *message, local_only=True):
        log(self, CRITICAL, *message, local_only=local_only, timeout=None)

    def error(self, *message, exc=None, local_only=True):
        log(self, ERROR, *message, local_only=local_only, timeout=None)
        if exc is not None and isinstance(exc, Exception):
            usys.print_exception(exc)

    def warn(self, *message, local_only=True):
        log(self, WARNING, *message, local_only=local_only, timeout=None)

    def info(self, *message, local_only=True):
        log(self, INFO, *message, local_only=local_only, timeout=20)

    def debug(self, *message, local_only=True):
        log(self, DEBUG, *message, local_only=local_only, timeout=5)

    def asyncLog(self, level, *message, timeout=True):
        pass

def get_logger(name):
    return Logger(name)

class Abstract(object):
    def post_processor_after_instantiation(self, *args, **kwargs):
        """实例化后调用"""
        pass

    def post_processor_before_initialization(self, *args, **kwargs):
        """初始化之前调用"""
        pass

    def initialization(self, *args, **kwargs):
        """初始化load"""
        pass

    def post_processor_after_initialization(self, *args, **kwargs):
        """初始化之后调用"""
        pass

class Lock(object):

    def __init__(self):
        self.lock = _thread.allocate_lock()

    def __enter__(self, *args, **kwargs):
        self.lock.acquire()

    def __exit__(self, *args, **kwargs):
        self.lock.release()

class ConfigStoreManager(Abstract):
    def __init__(self):
        self.file_name = "/usr/conf_store.json"
        self.lock = Lock()
        self.map = dict(
            vol_num=3,
            sn = "",
            barcode = "",
            version = "V1.0.0",
            flag =  "0"
        )

    def post_processor_after_initialization(self):
        if ql_fs.path_exists(self.file_name):
            file_map = ql_fs.read_json(self.file_name)
            for k in self.map.keys():
                if k not in file_map:
                    file_map.update({k: self.map.get(k)})
            self.__store(msg=file_map)
            self.map = file_map
        else:
            self.__store()
        EventMesh.subscribe("persistent_config_get", self.__read)
        EventMesh.subscribe("persistent_config_store", self.__store)

    def __read(self, event, msg):
        with self.lock:
            return self.map.get(msg)

    def __store(self, event=None, msg=None):
        if msg is None:
            msg = dict()
        with self.lock:
            self.map.update(msg)
            ql_fs.touch(self.file_name, self.map)