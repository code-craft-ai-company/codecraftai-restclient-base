
"""
    .. module:: restclientbase
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: restclientbase module.
    
    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""


__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []


from typing import Dict, List, Optional, Union

import logging
import os
import time



from base64 import b64encode
from http import HTTPStatus

from requests import Session, Response, Request
from requests.adapters import HTTPAdapter

from ccai.errors.exceptions import HttpForbiddenError
from ccai.errors.raising import format_http_error_message, raise_for_http_status

from ccai.credentials.basecredential import BaseCredential
from ccai.credentials.basiccredential import BasicCredential

from ccai.restclient.base.aspectsrest import (
    ActionPattern, AspectsRest, LoggingPattern, DEFAULT_REST_ASPECTS
)


class RestClientBase:
    """
        The :class:`RestClientBase` object is a generic REST client base object that can be inherited from
        in order to implement a REST client that utilizes 'aspects' based APIs
    """

    AUTH_LEAF = ""

    # This code is for use with REST clients that can be used in both a production and test environment.
    # we must be able to make calls with SSL certificate verification turned off as some test environments
    # utilized self signed certificates.  Allowing the client to make calls with verify turned off is not a bug
    # its a feature.
    VERIFY_CERTIFICATE = True

    AUTHENTICATION_FAILURES = (HttpForbiddenError)

    def __init__(self, host: str, credential: BaseCredential, port: Optional[int] = None, scheme: Optional[str] = "https", headers: Optional[Dict[str, str]] = None, verify_certificate: Optional[bool] = None, aspects: AspectsRest = DEFAULT_REST_ASPECTS):
        """
            Initialize the REST client base.

            :param host: Hostname for the REST service.
            :param credential: Credential used for authentication.
            :param port: Optional port for the service.
            :param scheme: URL scheme, default is ``https``.
            :param verify_certificate: Optional flag to enable or disable TLS verification.
            :param aspects: Default REST aspects.

            :returns: None
        """

        self._host = host
        self._credential = credential
        self._headers = headers
        if self._headers is None:
            self._headers = {}
        if verify_certificate is None:
            self._verify_certificate = self.VERIFY_CERTIFICATE
        else:
            self._verify_certificate = verify_certificate
        self._aspects = aspects

        self._host_url = f"{scheme}://{self._host}"
        if port is not None:
            self._host_url = f"{self._host_url}:{port}"

        self._session: Session = None
        self._logger = logging.getLogger()
        return
    
    @property
    def aspects(self):
        """
            Default REST aspects for this client.

            :returns: The AspectsRest instance supplied at construction time.
        """
        return self._aspects
    
    @property
    def credential(self):
        """
            Credential object used for authentication with the REST service.

            :returns: The credential instance supplied at construction time.
        """
        return self._credential

    @property
    def headers(self):
        """
            Return the client level default headers that are passed for each API call.
        """
        return self._headers

    @property
    def host(self):
        """
            Hostname assigned to this REST client.

            :returns: The host string passed to the constructor.
        """
        return self._host
    

    def authenticate(self):
        """
            The `authenticate` method can be overloaded in order to modify the method of authentication
            for the rest client.  The current method of authentication is `Basic` authentication.
        """

        credential: BasicCredential = self._credential

        username = credential.username
        password = credential.password

        authbytes = f"{username}:{password}".encode("utf-8")
        passwd_encoded = b64encode(authbytes).decode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Basic {passwd_encoded}"
        }

        auth_leaf = self.AUTH_LEAF.rstrip("/")
        auth_url = f"{self._host_url}/{auth_leaf}"

        session = Session()
        session.verify = self._verify_certificate

        resp: Response = session.post(auth_url, headers=headers, verify=self._verify_certificate)
        if resp.status_code != HTTPStatus.OK:
            errmsg_lines = [
                f"Error attempting to authenticate on url={auth_url}.",
                f"STATUS: {resp.status_code}"
                "RESPONSE:",
                resp.content
            ]
            errmsg = os.linesep.join(errmsg_lines)
            raise HttpForbiddenError(errmsg)

        self._session = session

        return

    def perform_call(self, *, leaf: str, method: str, params: Union[Dict[str, str], None], body: Union[Dict[str, str], None],
                     exp_status: Union[int, List[int]], headers: Optional[Dict[str, str]] = None,
                     context_msg: Optional[str] = None, aspects: Union[AspectsRest, None]) -> Response:
        """
            Perform a REST call using the specified execution aspects.

            :param leaf: API leaf path.
            :param method: HTTP method name.
            :param params: Optional query parameters.
            :param body: Optional request body.
            :param exp_status: Expected HTTP status codes.
            :param headers: Optional request headers.
            :param context_msg: Optional context message for logging.
            :param aspects: Aspects controlling call behavior.

            :returns: The :class:`Response` object for the call.
        """
        
        if aspects is None:
            aspects = self._aspects

        response: Response = None

        action_pattern = aspects.action_pattern

        if action_pattern == ActionPattern.SINGLE_CALL:
            response = self._perform_single_call(leaf, method, params, body, exp_status, headers, context_msg, aspects)
        elif action_pattern == ActionPattern.SINGLE_CONNECTED_CALL:
            response = self._perform_single_connected_call(leaf, method, params, body, exp_status, headers, context_msg, aspects)
        elif action_pattern == ActionPattern.DO_UNTIL_CONNECTION_FAILURE:
            response = self._perform_call_until_connection_failure(leaf, method, params, body, exp_status, headers, context_msg, aspects)
        elif action_pattern == ActionPattern.DO_UNTIL_SUCCESS:
            response = self._perform_call_until_success(leaf, method, params, body, exp_status, headers, context_msg, aspects)
        elif action_pattern == ActionPattern.DO_WHILE_SUCCESS:
            response = self._perform_call_while_success(leaf, method, params, body, exp_status, headers, context_msg, aspects)
        else:
            errmsg = f"Unsupported action pattern '{action_pattern}'"
            raise RuntimeError(errmsg)

        return response


    def _format_call_url(self, leaf) -> str:
        """
            Compose the full request URL for an API leaf.

            :param leaf: API path segment to append to the host URL.

            :returns: Fully qualified URL for the call.
        """

        call_url = f"{self._host_url}{leaf}"

        return call_url


    def _get_session(self, aspects: AspectsRest) -> Session:
        """
            Retrieve or create the requests session for the given aspects.

            :param aspects: Execution aspects that may supply a pre-created session.

            :returns: :class:`Session` object for REST calls.
        """

        session = None

        if aspects.session is not None:
            session = aspects.session
        else:
            if self._session is None:
                self.authenticate()

            session = self._session

        return session


    def _perform_single_call(self, leaf: str, method: str, params: Union[Dict[str, str], None], body: Union[Dict[str, str], None],
                             exp_status: Union[int, List[int]], headers: Union[Dict[str, str], None],
                             context_msg: Union[str, None], aspects: AspectsRest) -> Response:
        """
            Performs a REST call using a newly authenticated session. Only a single attempt to make the call and provide
            the calling code with the result is made.  If the call does not succeed due to authentication failure this could
            be due to a credential timeout.  Make a single attempt to reauthenticate and then remake the call.

            :param leaf: API leaf path for the request.
            :param method: HTTP method to invoke.
            :param params: Query parameters for the request.
            :param body: Request body payload.
            :param exp_status: Expected HTTP status code(s).
            :param headers: Optional HTTP headers.
            :param context_msg: Context message for error reporting.
            :param aspects: Aspects controlling execution behaviour.

            :returns: The :class:`Response` object from the request.
        """

        # We need expected status in the form of a collection for our comparison
        if isinstance(exp_status, int):
            exp_status = [exp_status]

        call_url = self._format_call_url(leaf)

        logger = self._logger
        if aspects.logger is not None:
            logger = aspects.logger

        send_timeouts = (aspects.connection_timeout, aspects.inactivity_timeout)
        allowed_error_codes: List[int] = aspects.allowed_error_codes
        allowed_connection_exceptions: List[BaseException] = aspects.allowed_connection_exceptions

        auth_retry = False
        while True:

            try:
                session: Session = self._get_session(aspects)

                
                req = Request(method=method, url=call_url, headers=headers, params=params, data=body)
                prepared_req = session.prepare_request(req)
                
                resp :Response = session.send(prepared_req, timeout=send_timeouts, verify=self._verify_certificate)

            except self.AUTHENTICATION_FAILURES as autherr:
                if not auth_retry:
                    auth_retry = True
                    self._session = None
                else:
                    raise # we only make a single attempt to authenticate, bubble any additional failures

            else:
                break

        found_status = resp.status_code
        if found_status not in exp_status:
            resp_content = resp.content

            errmsg = format_http_error_message(found_status, resp_content, call_url, context=context_msg)
            logger.error(errmsg)

            raise_for_http_status(found_status, resp_content, call_url, context=context_msg)

        return resp
    

    def _perform_single_connected_call(self, leaf: str, method: str, params: Union[Dict[str, str], None], body: Union[Dict[str, str], None],
                                       exp_status: Union[int, List[int]], headers: Union[Dict[str, str], None],
                                       context_msg: Union[str, None], aspects: AspectsRest) -> Response:
        """
            Perform a single call using an existing connection.  This call will utilize aspect parameter such as connection timeout in its attempt
            to connect and only gives up if a constraint is exceeded.  Once it make a connection it makes a single attempt to perform the call on
            the API and if the call fails, it does not retry.

            :param leaf: API leaf path to call.
            :param method: HTTP method to use.
            :param params: Query parameters for the call.
            :param body: Body payload for the call.
            :param exp_status: Expected HTTP status code(s).
            :param headers: Optional HTTP headers.
            :param context_msg: Context message for error reporting.
            :param aspects: REST aspects controlling the call.

            :returns: Response returned from the request.
        """

        call_url = self._format_call_url(leaf)

        logger = self._logger
        if aspects.logger is not None:
            logger = aspects.logger

        send_timeouts = (aspects.connection_timeout, aspects.inactivity_timeout)
        completion_timeout: float = aspects.completion_timeout
        completion_interval: float = aspects.completion_interval
        monitor_delay: float = aspects.monitor_delay
        logging_pattern: LoggingPattern = aspects.logging_pattern
        retry_logging_interval: int = aspects.retry_logging_interval
        allowed_error_codes: List[int] = aspects.allowed_error_codes
        allowed_connection_exceptions: List[BaseException] = aspects.allowed_connection_exceptions
        must_connect: bool = aspects.must_connect

        # Attempt to establish a connection and make a single call.  We will
        # retry connecting until either a connection is made or the completion
        # timeout is exceeded.  Once connected, the call is executed only once.
        start_time = time.time()
        attempt = 0
        auth_retry = False
        while True:

            try:
                session: Session = self._get_session(aspects)

                req = Request(method=method, url=call_url, headers=headers,
                             params=params, data=body)
                prepared_req = session.prepare_request(req)

                resp: Response = session.send(
                    prepared_req, timeout=send_timeouts,
                    verify=self._verify_certificate
                )

            except self.AUTHENTICATION_FAILURES:
                if not auth_retry:
                    auth_retry = True
                    self._session = None
                    continue
                raise
            except Exception as exc:  # Connection failure
                if attempt % retry_logging_interval == 0:
                    dbg_msg = (
                        f"Connection attempt {attempt + 1} failed: {exc}"
                    )
                    logger.debug(dbg_msg)

                if time.time() - start_time >= completion_timeout:
                    raise TimeoutError(
                        f"Timeout attempting call on url={call_url}"
                    ) from exc

                time.sleep(completion_interval)
                attempt += 1
                continue

            else:
                break

        found_status = resp.status_code
        if isinstance(exp_status, int):
            exp_list = [exp_status]
        else:
            exp_list = exp_status

        if found_status not in exp_list:
            resp_content = resp.content
            errmsg = format_http_error_message(
                found_status, resp_content, call_url, context=context_msg
            )
            logger.error(errmsg)
            raise_for_http_status(
                found_status, resp_content, call_url, context=context_msg
            )

        return resp
    

    def _perform_call_until_connection_failure(self, leaf: str, method: str, params: Union[Dict[str, str], None], body: Union[Dict[str, str], None],
                                               exp_status: Union[int, List[int]], headers: Union[Dict[str, str], None],
                                               context_msg: Union[str, None], aspects: AspectsRest) -> Response:
        """
            Perform repeated calls until the connection fails by exceeding a constraint or until a completion timeout is reached.  If there is no connection
            failure prior to the completion timeout.  It will raise a TimeoutError

            :returns: The last response obtained before failure.
        """

        call_url = self._format_call_url(leaf)

        logger = self._logger
        if aspects.logger is not None:
            logger = aspects.logger

        send_timeouts = (aspects.connection_timeout, aspects.inactivity_timeout)
        completion_timeout: float = aspects.completion_timeout
        completion_interval: float = aspects.completion_interval
        monitor_delay: float = aspects.monitor_delay
        logging_pattern: LoggingPattern = aspects.logging_pattern
        retry_logging_interval: int = aspects.retry_logging_interval
        allowed_error_codes: List[int] = aspects.allowed_error_codes
        allowed_connection_exceptions: List[BaseException] = aspects.allowed_connection_exceptions
        must_connect: bool = aspects.must_connect

        # Repeatedly perform the call until we hit a connection failure or the
        # completion timeout expires.
        start_time = time.time()
        attempt = 0
        last_resp: Response = None
        auth_retry = False

        while True:
            try:
                session: Session = self._get_session(aspects)

                req = Request(method=method, url=call_url, headers=headers,
                             params=params, data=body)
                prepared_req = session.prepare_request(req)

                resp: Response = session.send(
                    prepared_req, timeout=send_timeouts,
                    verify=self._verify_certificate
                )
                last_resp = resp

            except self.AUTHENTICATION_FAILURES:
                if not auth_retry:
                    auth_retry = True
                    self._session = None
                    continue
                break
            except Exception as exc:
                # Any exception is treated as a connection failure
                if attempt % retry_logging_interval == 0:
                    dbg_msg = (
                        f"Connection failure after {attempt + 1} attempts: {exc}"
                    )
                    logger.debug(dbg_msg)
                break

            if time.time() - start_time >= completion_timeout:
                raise TimeoutError(
                    f"Timeout waiting for connection failure on url={call_url}"
                )

            time.sleep(completion_interval)
            attempt += 1

        return last_resp
    

    def _perform_call_until_success(self, leaf: str, method: str, params: Union[Dict[str, str], None], body: Union[Dict[str, str], None],
                                    exp_status: Union[int, List[int]], headers: Union[Dict[str, str], None],
                                    context_msg: Union[str, None], aspects: AspectsRest) -> Response:
        """
            Perform repeated calls until one succeeds.

            :returns: The successful response object.
        """

        call_url = self._format_call_url(leaf)

        logger = self._logger
        if aspects.logger is not None:
            logger = aspects.logger

        send_timeouts = (aspects.connection_timeout, aspects.inactivity_timeout)
        completion_timeout: float = aspects.completion_timeout
        completion_interval: float = aspects.completion_interval
        monitor_delay: float = aspects.monitor_delay
        logging_pattern: LoggingPattern = aspects.logging_pattern
        retry_logging_interval: int = aspects.retry_logging_interval
        allowed_error_codes: List[int] = aspects.allowed_error_codes
        allowed_connection_exceptions: List[BaseException] = aspects.allowed_connection_exceptions
        must_connect: bool = aspects.must_connect

        # Loop until we obtain a successful response or a timeout occurs.
        start_time = time.time()
        attempt = 0
        auth_retry = False

        while True:
            try:
                session: Session = self._get_session(aspects)

                req = Request(method=method, url=call_url, headers=headers,
                             params=params, data=body)
                prepared_req = session.prepare_request(req)

                resp: Response = session.send(
                    prepared_req, timeout=send_timeouts,
                    verify=self._verify_certificate
                )

            except self.AUTHENTICATION_FAILURES:
                if not auth_retry:
                    auth_retry = True
                    self._session = None
                    continue
                if must_connect:
                    raise
                resp = None
            except Exception as exc:
                if must_connect:
                    raise
                resp = None
                if attempt % retry_logging_interval == 0:
                    logger.debug(
                        f"Call attempt {attempt + 1} failed: {exc}"
                    )

            else:
                found_status = resp.status_code
                if isinstance(exp_status, int):
                    exp_list = [exp_status]
                else:
                    exp_list = exp_status

                if found_status in exp_list:
                    return resp

                if allowed_error_codes and found_status in allowed_error_codes:
                    resp = None
                else:
                    resp_content = resp.content
                    errmsg = format_http_error_message(
                        found_status, resp_content, call_url, context=context_msg
                    )
                    logger.error(errmsg)
                    raise_for_http_status(
                        found_status, resp_content, call_url, context=context_msg
                    )

            if time.time() - start_time >= completion_timeout:
                raise TimeoutError(
                    f"Timeout waiting for successful call on url={call_url}"
                )

            time.sleep(completion_interval)
            attempt += 1

    

    def _perform_call_while_success(self, leaf: str, method: str, params: Union[Dict[str, str], None], body: Union[Dict[str, str], None],
                                    exp_status: Union[int, List[int]], headers: Union[Dict[str, str], None],
                                    context_msg: Union[str, None], aspects: AspectsRest) -> Response:
        """
            Continue performing calls while each one succeeds.

            :returns: The last response object received.
        """

        call_url = self._format_call_url(leaf)

        logger = self._logger
        if aspects.logger is not None:
            logger = aspects.logger

        send_timeouts = (aspects.connection_timeout, aspects.inactivity_timeout)
        completion_timeout: float = aspects.completion_timeout
        completion_interval: float = aspects.completion_interval
        monitor_delay: float = aspects.monitor_delay
        logging_pattern: LoggingPattern = aspects.logging_pattern
        retry_logging_interval: int = aspects.retry_logging_interval
        allowed_error_codes: List[int] = aspects.allowed_error_codes
        allowed_connection_exceptions: List[BaseException] = aspects.allowed_connection_exceptions
        must_connect: bool = aspects.must_connect

        # Continue making calls while each call succeeds.  Stop when a call
        # fails or when the completion timeout is reached.
        start_time = time.time()
        attempt = 0
        last_resp: Response = None
        auth_retry = False

        while True:
            try:
                session: Session = self._get_session(aspects)

                req = Request(method=method, url=call_url, headers=headers,
                             params=params, data=body)
                prepared_req = session.prepare_request(req)

                resp: Response = session.send(
                    prepared_req, timeout=send_timeouts,
                    verify=self._verify_certificate
                )

            except self.AUTHENTICATION_FAILURES:
                if not auth_retry:
                    auth_retry = True
                    self._session = None
                    continue
                if must_connect:
                    raise
                break
            except Exception as exc:
                if must_connect:
                    raise
                if attempt % retry_logging_interval == 0:
                    logger.debug(
                        f"Call failed after {attempt + 1} attempts: {exc}"
                    )
                break
            else:
                last_resp = resp
                found_status = resp.status_code
                if isinstance(exp_status, int):
                    exp_list = [exp_status]
                else:
                    exp_list = exp_status

                if found_status not in exp_list:
                    if allowed_error_codes and found_status in allowed_error_codes:
                        break
                    resp_content = resp.content
                    errmsg = format_http_error_message(
                        found_status, resp_content, call_url, context=context_msg
                    )
                    logger.error(errmsg)
                    raise_for_http_status(
                        found_status, resp_content, call_url, context=context_msg
                    )

            if time.time() - start_time >= completion_timeout:
                raise TimeoutError(
                    f"Timeout waiting for call failure on url={call_url}"
                )

            time.sleep(completion_interval)
            attempt += 1

        return last_resp
    
