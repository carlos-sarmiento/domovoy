class DomovoyException(Exception):
    ...


class DomovoyAsyncException(DomovoyException):
    ...


class DomovoySchedulerException(DomovoyException):
    ...


class DomovoyUnknownPluginException(DomovoyException):
    ...


class DomovoyLogOnlyOnDebugWhenUncaughtException(Exception):
    ...
