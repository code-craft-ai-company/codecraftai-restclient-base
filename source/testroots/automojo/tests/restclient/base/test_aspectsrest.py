import logging

import testbase

from automojo.restclient.base.aspectsrest import (
    ActionPattern,
    AspectsRest,
    DEFAULT_ALLOWED_CONNECTION_EXCEPTIONS,
    DEFAULT_ALLOWED_ERROR_CODES,
    DEFAULT_COMPLETION_INTERVAL,
    DEFAULT_COMPLETION_TIMEOUT,
    DEFAULT_CONNECTION_TIMEOUT,
    DEFAULT_INACTIVITY_TIMEOUT,
    DEFAULT_LOGGING_PATTERN,
    DEFAULT_MONITOR_DELAY,
    DEFAULT_MUST_CONNECT,
    DEFAULT_RETRY_LOGGING_INTERVAL,
)


def test_aspectsrest_defaults_match_constants():
    aspects = AspectsRest()

    testbase.assert_equal(aspects.action_pattern, ActionPattern.SINGLE_CALL)
    testbase.assert_equal(aspects.completion_timeout, DEFAULT_COMPLETION_TIMEOUT)
    testbase.assert_equal(aspects.completion_interval, DEFAULT_COMPLETION_INTERVAL)
    testbase.assert_equal(aspects.connection_timeout, DEFAULT_CONNECTION_TIMEOUT)
    testbase.assert_equal(aspects.inactivity_timeout, DEFAULT_INACTIVITY_TIMEOUT)
    testbase.assert_equal(aspects.monitor_delay, DEFAULT_MONITOR_DELAY)
    testbase.assert_equal(aspects.logging_pattern, DEFAULT_LOGGING_PATTERN)
    testbase.assert_equal(aspects.retry_logging_interval, DEFAULT_RETRY_LOGGING_INTERVAL)
    testbase.assert_equal(aspects.allowed_error_codes, DEFAULT_ALLOWED_ERROR_CODES)
    testbase.assert_equal(aspects.allowed_connection_exceptions, DEFAULT_ALLOWED_CONNECTION_EXCEPTIONS)
    testbase.assert_equal(aspects.must_connect, DEFAULT_MUST_CONNECT)
    testbase.assert_equal(aspects.logger, None)
    testbase.assert_equal(aspects.session, None)
    return


def test_aspectsrest_converts_allowed_values_to_tuples():
    logger = logging.getLogger("test")
    aspects = AspectsRest(
        allowed_error_codes=[401, 403],
        allowed_connection_exceptions=[TimeoutError],
        logger=logger,
    )

    testbase.assert_equal(aspects.allowed_error_codes, (401, 403))
    testbase.assert_equal(aspects.allowed_connection_exceptions, (TimeoutError,))
    testbase.assert_equal(aspects.logger, logger)
    return


def test_aspectsrest_disallows_attribute_changes():
    aspects = AspectsRest()

    error = None
    try:
        aspects.connection_timeout = 5
    except AttributeError as err:
        error = err

    testbase.assert_equal(error is not None, True)
    return
