from datetime import datetime
import platform


class Global(object):
    def get(self):
        raise NotImplementedError


class OsGlobal(object):
    def get(self):
        system = platform.system()
        if system == 'Linux':
            return 'linux'
        if system == 'Darwin':
            return 'mac'
        if system == 'Windows' or system.startswith('CYGWIN'):
            return 'win'
        return 'unknown'


class HourGlobal(object):
    def get(self):
        return datetime.now().hour


default_globals = dict(
    os=OsGlobal(),
    hour=HourGlobal(),
)
