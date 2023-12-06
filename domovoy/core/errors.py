class DomovoyError(Exception):
    ...


class DomovoyAsyncError(DomovoyError):
    ...


class DomovoySchedulerError(DomovoyError):
    ...


class DomovoyUnknownPluginError(DomovoyError):
    ...


class DomovoyLogOnlyOnDebugWhenUncaughtError(Exception):
    ...
