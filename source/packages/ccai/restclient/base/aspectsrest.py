
"""
    .. module:: aspectsrest
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: aspectsrest module.
    
    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""


__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []


from typing import Optional, Tuple, Union

import logging

from enum import IntEnum

from requests import Session

from ccai.aspects.aspects import Aspects as AspectsBase

class ActionPattern(IntEnum):
    """
        An action pattern to use when using aspects to change the behavior of an API.
    """
    SINGLE_CALL = 0
    SINGLE_CONNECTED_CALL = 1
    DO_UNTIL_SUCCESS = 2
    DO_WHILE_SUCCESS = 3
    DO_UNTIL_CONNECTION_FAILURE = 4


class LoggingPattern:
    """
        A logging pattern to use when logging commands.
    """
    ALL_RESULTS = 0
    FAILURE_ONLY = 1
    SUCCESS_ONLY = 2


DEFAULT_COMPLETION_TIMEOUT = 600
DEFAULT_COMPLETION_INTERVAL = 10

DEFAULT_CONNECTION_TIMEOUT = 16
DEFAULT_CONNECTION_INTERVAL = 2
DEFAULT_ALLOWED_CONNECTION_EXCEPTIONS: Tuple[BaseException, ...] = ()

DEFAULT_INACTIVITY_TIMEOUT = 600
DEFAULT_INACTIVITY_INTERVAL = .5

DEFAULT_MONITOR_DELAY = 30

DEFAULT_RETRY_LOGGING_INTERVAL = 5

DEFAULT_LOGGING_PATTERN = LoggingPattern.ALL_RESULTS

DEFAULT_MUST_CONNECT = False

DEFAULT_ALLOWED_ERROR_CODES: Tuple[int, ...] = ()


class AspectsRest(AspectsBase):
    """
        Aspects container specialized for REST operations.
    """
    def __init__(self, *, action_pattern: ActionPattern = ActionPattern.SINGLE_CALL,
                completion_timeout: float = DEFAULT_COMPLETION_TIMEOUT,
                completion_interval: float = DEFAULT_COMPLETION_INTERVAL,
                connection_timeout: float = DEFAULT_CONNECTION_TIMEOUT,
                inactivity_timeout: float = DEFAULT_INACTIVITY_TIMEOUT,
                monitor_delay: float = DEFAULT_MONITOR_DELAY,
                logging_pattern: LoggingPattern = DEFAULT_LOGGING_PATTERN,
                retry_logging_interval: int = DEFAULT_RETRY_LOGGING_INTERVAL,
                allowed_error_codes: Tuple[int, ...] = DEFAULT_ALLOWED_ERROR_CODES,
                allowed_connection_exceptions: Tuple[BaseException, ...] = DEFAULT_ALLOWED_CONNECTION_EXCEPTIONS,
                must_connect: bool = DEFAULT_MUST_CONNECT,
                logger: Optional[logging.Logger]=None,
                session: Optional[Session] = None):
        """
            Initialize a set of REST call aspects.

            :param action_pattern: Default action pattern for calls.
            :param completion_timeout: Time in seconds to wait for completion.
            :param completion_interval: Polling interval when waiting.
            :param connection_timeout: Timeout for establishing connections.
            :param inactivity_timeout: Timeout for inactivity in seconds.
            :param monitor_delay: Delay before monitoring begins.
            :param logging_pattern: Pattern used for call logging.
            :param retry_logging_interval: Interval for retry log messages.
            :param allowed_error_codes: HTTP status codes considered success.
            :param allowed_connection_exceptions: Exceptions allowed during connect.
            :param must_connect: Whether a connection must be established.
            :param logger: Logger to use for messages.
            :param session: Requests session to reuse.
        """
        object.__setattr__(self, "__frozen__", False)
        
        super().__init__(completion_interval=completion_interval, completion_timeout=completion_timeout,
                         connection_timeout=connection_timeout)

        self.action_pattern=action_pattern
        self.inactivity_timeout=inactivity_timeout
        self.monitor_delay=monitor_delay
        self.logging_pattern=logging_pattern
        self.retry_logging_interval=retry_logging_interval
        self.allowed_error_codes=tuple(allowed_error_codes)
        self.allowed_connection_exceptions=tuple(allowed_connection_exceptions)
        self.must_connect=must_connect
        self.logger=logger
        self.session = session

        self.freeze()
        return



DEFAULT_REST_ASPECTS = AspectsRest()
