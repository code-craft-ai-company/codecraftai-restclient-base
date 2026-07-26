"""
    .. module:: awssigv4
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: AWS Signature Version 4 request signing, in pure Python.

    SigV4 is the request-signing scheme used by AWS and by every
    S3-compatible object store that follows it — DigitalOcean Spaces, Linode
    Object Storage, Backblaze B2's S3 endpoint, MinIO.  It needs nothing but
    ``hmac`` and ``hashlib`` from the standard library: the signature is a
    chain of HMAC-SHA256 derivations over a canonicalised form of the
    request.

    This lives in ``restclient-base`` rather than in one provider's client
    because several providers need exactly the same algorithm, and a copy per
    provider would be a copy of the subtle parts too.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import datetime
import hashlib
import hmac
import urllib.parse

from typing import Dict, Mapping, Optional, Tuple


ALGORITHM = "AWS4-HMAC-SHA256"

TERMINATOR = "aws4_request"

# The SHA-256 of the empty string, which is the payload hash for every
# bodiless request.  Precomputed because it appears on nearly every call.
EMPTY_PAYLOAD_SHA256 = (
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
)

# S3 accepts this literal in place of a real body hash, telling the service
# the payload is not signed.  Useful for streaming uploads where the body
# cannot be hashed up front.
UNSIGNED_PAYLOAD = "UNSIGNED-PAYLOAD"


def _sha256_hex(data: bytes) -> str:
    """
        Return the lowercase hex SHA-256 of some bytes.

        :param data: The bytes to hash.

        :returns: The hex digest.
    """
    rtnval = hashlib.sha256(data).hexdigest()
    return rtnval


def _hmac_sha256(key: bytes, message: str) -> bytes:
    """
        Return the raw HMAC-SHA256 of a message under a key.

        :param key: The HMAC key.
        :param message: The message, encoded as UTF-8.

        :returns: The raw digest bytes.
    """
    rtnval = hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()
    return rtnval


def uri_encode(value: str, *, encode_slash: bool = True) -> str:
    """
        Percent-encode a string the way SigV4 canonicalisation requires.

        The unreserved set is ``A-Z a-z 0-9 - _ . ~``; everything else is
        percent-encoded with uppercase hex.  Path segments keep ``/``
        unencoded, which is why ``encode_slash`` exists — encoding it in a
        canonical URI would change the resource being addressed.

        :param value: The string to encode.
        :param encode_slash: Whether ``/`` is encoded.

        :returns: The encoded string.
    """
    safe = "-_.~"
    if encode_slash is False:
        safe = safe + "/"

    rtnval = urllib.parse.quote(value, safe=safe)
    return rtnval


def canonical_uri(path: str) -> str:
    """
        Build the canonical URI for a request path.

        :param path: The request path, e.g. ``/my-bucket/key name``.

        :returns: The canonical URI; ``/`` when the path is empty.
    """
    if path is None or len(path) == 0:
        rtnval = "/"
        return rtnval

    rtnval = uri_encode(path, encode_slash=False)
    return rtnval


def canonical_query_string(params: Optional[Mapping[str, object]]) -> str:
    """
        Build the canonical query string.

        Parameters are sorted by encoded name, then by encoded value, and a
        parameter with no value still carries its ``=``.

        :param params: The query parameters, or None.

        :returns: The canonical query string, empty when there are none.
    """
    if params is None or len(params) == 0:
        rtnval = ""
        return rtnval

    pairs = []
    for name, value in params.items():
        encoded_name = uri_encode(str(name))
        if value is None:
            encoded_value = ""
        else:
            encoded_value = uri_encode(str(value))
        pairs.append((encoded_name, encoded_value))

    pairs.sort()

    rtnval = "&".join(
        ["{}={}".format(name, value) for name, value in pairs])
    return rtnval


def canonical_headers(headers: Mapping[str, str]) -> Tuple[str, str]:
    """
        Build the canonical headers block and the signed-header list.

        Header names are lowercased, values have surrounding whitespace
        trimmed and internal runs collapsed, and the whole set is sorted by
        name.

        :param headers: The headers to sign.

        :returns: A ``(canonical_headers, signed_headers)`` pair.
    """
    normalized: Dict[str, str] = {}
    for name, value in headers.items():
        lowered = name.lower().strip()
        collapsed = " ".join(str(value).split())
        normalized[lowered] = collapsed

    names = sorted(normalized.keys())

    canonical = "".join(
        ["{}:{}\n".format(name, normalized[name]) for name in names])
    signed = ";".join(names)

    rtnval = (canonical, signed)
    return rtnval


def credential_scope(*, datestamp: str, region: str, service: str) -> str:
    """
        Build the credential scope a signature is bound to.

        :param datestamp: The ``YYYYMMDD`` date.
        :param region: The region name.
        :param service: The service name, e.g. ``s3``.

        :returns: The scope string.
    """
    rtnval = "{}/{}/{}/{}".format(datestamp, region, service, TERMINATOR)
    return rtnval


def signing_key(*, secret_key: str, datestamp: str, region: str,
                service: str) -> bytes:
    """
        Derive the signing key for a date, region and service.

        The key is a chain of HMACs starting from the secret, which is what
        makes a leaked signature useless outside its scope: it is valid only
        for that one day, region and service.

        :param secret_key: The secret access key.
        :param datestamp: The ``YYYYMMDD`` date.
        :param region: The region name.
        :param service: The service name.

        :returns: The derived signing key.
    """
    initial = ("AWS4" + secret_key).encode("utf-8")
    date_key = _hmac_sha256(initial, datestamp)
    region_key = _hmac_sha256(date_key, region)
    service_key = _hmac_sha256(region_key, service)
    rtnval = _hmac_sha256(service_key, TERMINATOR)
    return rtnval


class SigV4Signer:
    """
        Signs requests with AWS Signature Version 4.

        :ivar access_key: The access key id.
        :ivar region: The region the signature is scoped to.
        :ivar service: The service the signature is scoped to.
    """

    def __init__(self, *, access_key: str, secret_key: str, region: str,
                 service: str,
                 session_token: Optional[str] = None) -> None:
        """
            Construct a SigV4Signer.

            :param access_key: The access key id.
            :param secret_key: The secret access key.
            :param region: The region name, e.g. ``us-east-1`` or ``nyc3``.
            :param service: The service name, e.g. ``s3``.
            :param session_token: Optional session token, for temporary
                credentials.
        """
        self._access_key: str = access_key
        self._secret_key: str = secret_key
        self._region: str = region
        self._service: str = service
        self._session_token: Optional[str] = session_token
        return

    @property
    def access_key(self) -> str:
        """
            Return the access key id.

            :returns: The access key id.
        """
        rtnval = self._access_key
        return rtnval

    @property
    def region(self) -> str:
        """
            Return the region the signature is scoped to.

            :returns: The region name.
        """
        rtnval = self._region
        return rtnval

    @property
    def service(self) -> str:
        """
            Return the service the signature is scoped to.

            :returns: The service name.
        """
        rtnval = self._service
        return rtnval

    def sign(self, *, method: str, url: str,
             params: Optional[Mapping[str, object]] = None,
             headers: Optional[Mapping[str, str]] = None,
             body: Optional[bytes] = None,
             payload_hash: Optional[str] = None,
             timestamp: Optional[datetime.datetime] = None
             ) -> Dict[str, str]:
        """
            Compute the headers that authenticate one request.

            The returned mapping is the COMPLETE set of headers to send: the
            caller's own headers plus ``Host``, ``x-amz-date``,
            ``x-amz-content-sha256``, ``Authorization`` and, when temporary
            credentials are in use, ``x-amz-security-token``.  Returning the
            full set rather than just ``Authorization`` matters because the
            signature covers those added headers — sending a different set
            than was signed fails.

            :param method: The HTTP method.
            :param url: The absolute request URL.
            :param params: The query parameters, which must match what is
                actually sent.
            :param headers: Any caller headers to include in the signature.
            :param body: The request body, used to compute the payload hash.
            :param payload_hash: An explicit payload hash, overriding
                ``body`` — pass :data:`UNSIGNED_PAYLOAD` for a streamed body.
            :param timestamp: The signing time; defaults to now in UTC.
                Injectable so signatures are reproducible in tests.

            :returns: The headers to send.
        """
        moment = timestamp
        if moment is None:
            moment = datetime.datetime.now(datetime.timezone.utc)

        amz_date = moment.strftime("%Y%m%dT%H%M%SZ")
        datestamp = moment.strftime("%Y%m%d")

        parsed = urllib.parse.urlsplit(url)
        host = parsed.netloc

        effective_hash = payload_hash
        if effective_hash is None:
            payload = body
            if payload is None:
                effective_hash = EMPTY_PAYLOAD_SHA256
            else:
                effective_hash = _sha256_hex(payload)

        to_sign: Dict[str, str] = {}
        if headers is not None:
            for name, value in headers.items():
                to_sign[name] = value

        to_sign["host"] = host
        to_sign["x-amz-date"] = amz_date
        to_sign["x-amz-content-sha256"] = effective_hash
        if self._session_token is not None:
            to_sign["x-amz-security-token"] = self._session_token

        canonical, signed_headers = canonical_headers(to_sign)

        canonical_request = "\n".join([
            method.upper(),
            canonical_uri(parsed.path),
            canonical_query_string(params),
            canonical,
            signed_headers,
            effective_hash,
        ])

        scope = credential_scope(datestamp=datestamp, region=self._region,
                                 service=self._service)

        string_to_sign = "\n".join([
            ALGORITHM,
            amz_date,
            scope,
            _sha256_hex(canonical_request.encode("utf-8")),
        ])

        derived = signing_key(secret_key=self._secret_key,
                              datestamp=datestamp, region=self._region,
                              service=self._service)

        signature = hmac.new(derived, string_to_sign.encode("utf-8"),
                             hashlib.sha256).hexdigest()

        authorization = (
            "{} Credential={}/{}, SignedHeaders={}, Signature={}".format(
                ALGORITHM, self._access_key, scope, signed_headers,
                signature)
        )

        rtnval = dict(to_sign)
        rtnval["Authorization"] = authorization
        return rtnval
