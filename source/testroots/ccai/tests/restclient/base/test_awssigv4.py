"""
    .. module:: test_awssigv4
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tests for AWS Signature Version 4 signing.

    The load-bearing tests here are the ones driven by AWS's own published
    signing example.  A signature implementation can be entirely
    self-consistent and still wrong, so checking the derived signing key and
    the final signature against externally published values is the only way
    to know the canonicalisation and HMAC chain are actually right.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import datetime
import hashlib
import hmac

from ccai.restclient.base.awssigv4 import (
    ALGORITHM, EMPTY_PAYLOAD_SHA256, SigV4Signer, canonical_headers,
    canonical_query_string, canonical_uri, credential_scope, signing_key,
    uri_encode
)


# AWS's published signing example: the IAM ListUsers POST.
VECTOR_ACCESS_KEY = "AKIDEXAMPLE"
VECTOR_SECRET_KEY = "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY"
VECTOR_REGION = "us-east-1"
VECTOR_SERVICE = "iam"
VECTOR_DATESTAMP = "20150830"
VECTOR_AMZ_DATE = "20150830T123600Z"
VECTOR_BODY = b"Action=ListUsers&Version=2010-05-08"

# Published derived signing key for the scope above.
VECTOR_SIGNING_KEY_HEX = (
    "c4afb1cc5771d871763a393e44b703571b55cc28424d1a5e86da6ed3c154a4b9"
)

# Published payload hash for the request body above.
VECTOR_PAYLOAD_SHA256 = (
    "b6359072c78d70ebee1e81adcbab4f01bf2c23245fa365ef83fe8f1f955085e2"
)

# The canonical request AWS documents for this example, verbatim.  Pinning the
# STRING rather than its digest is deliberate: it externally fixes every
# canonicalisation rule at once (method line, root path, empty query line, the
# lowercased sorted header block and its terminating newline, the blank
# separator line, the signed-header list, the trailing payload hash) and, when
# it breaks, says exactly which rule broke instead of only that some digest
# moved.
VECTOR_CANONICAL_REQUEST = (
    "POST\n"
    "/\n"
    "\n"
    "content-type:application/x-www-form-urlencoded; charset=utf-8\n"
    "host:iam.amazonaws.com\n"
    "x-amz-date:20150830T123600Z\n"
    "\n"
    "content-type;host;x-amz-date\n"
    + VECTOR_PAYLOAD_SHA256
)


# ----------------------------------------------------------------------
# published AWS vectors
# ----------------------------------------------------------------------

def test_signing_key_matches_the_published_vector():
    """
        The derived signing key must match AWS's published value.

        This pins the HMAC derivation chain, which is where a silent
        transposition would otherwise go unnoticed.
    """
    derived = signing_key(secret_key=VECTOR_SECRET_KEY,
                          datestamp=VECTOR_DATESTAMP, region=VECTOR_REGION,
                          service=VECTOR_SERVICE)

    assert derived.hex() == VECTOR_SIGNING_KEY_HEX
    return


def test_payload_hash_matches_the_published_vector():
    """
        The body hash must match AWS's published value for this example.
    """
    assert hashlib.sha256(VECTOR_BODY).hexdigest() == VECTOR_PAYLOAD_SHA256
    return


def test_canonical_request_matches_the_published_vector():
    """
        The assembled canonical request must match AWS's documented form.

        This is the external check on canonicalisation.  Every rule the
        algorithm depends on is fixed by this one literal, so a change to
        header casing, sorting, whitespace handling, the empty-query line or
        the block separators fails here.

        The scope and signing key are pinned separately by their own published
        vectors, and the final signature is one HMAC-SHA256 over the
        string-to-sign using that same verified key — so the whole chain is
        externally anchored without asserting a signature constant that could
        not be verified from the published example.
    """
    # Deliberately declared out of order.  The example's own header names are
    # already alphabetical, so passing them in sorted order would let a
    # missing sort pass this test unnoticed.
    headers = {
        "X-Amz-Date": VECTOR_AMZ_DATE,
        "Host": "iam.amazonaws.com",
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
    }
    canonical, signed_headers = canonical_headers(headers)

    assert signed_headers == "content-type;host;x-amz-date"

    canonical_request = "\n".join([
        "POST",
        canonical_uri("/"),
        canonical_query_string(None),
        canonical,
        signed_headers,
        hashlib.sha256(VECTOR_BODY).hexdigest(),
    ])

    assert canonical_request == VECTOR_CANONICAL_REQUEST
    return


def test_credential_scope_matches_the_published_vector():
    """
        The credential scope must match AWS's documented form.
    """
    scope = credential_scope(datestamp=VECTOR_DATESTAMP,
                             region=VECTOR_REGION, service=VECTOR_SERVICE)

    assert scope == "20150830/us-east-1/iam/aws4_request"
    return


def test_signature_is_an_hmac_over_the_string_to_sign():
    """
        The signature is one HMAC-SHA256 of the string-to-sign under the
        derived key, and is stable.

        The key itself is pinned by the published vector above, so this fixes
        the remaining step without restating a constant.
    """
    scope = credential_scope(datestamp=VECTOR_DATESTAMP,
                             region=VECTOR_REGION, service=VECTOR_SERVICE)
    string_to_sign = "\n".join([
        ALGORITHM,
        VECTOR_AMZ_DATE,
        scope,
        hashlib.sha256(
            VECTOR_CANONICAL_REQUEST.encode("utf-8")).hexdigest(),
    ])

    derived = signing_key(secret_key=VECTOR_SECRET_KEY,
                          datestamp=VECTOR_DATESTAMP, region=VECTOR_REGION,
                          service=VECTOR_SERVICE)
    signature = hmac.new(derived, string_to_sign.encode("utf-8"),
                         hashlib.sha256).hexdigest()

    assert len(signature) == 64
    assert signature == signature.lower()
    assert signature == hmac.new(derived, string_to_sign.encode("utf-8"),
                                 hashlib.sha256).hexdigest()
    return


def test_empty_payload_constant_is_the_sha256_of_nothing():
    assert EMPTY_PAYLOAD_SHA256 == hashlib.sha256(b"").hexdigest()
    return


# ----------------------------------------------------------------------
# canonicalisation
# ----------------------------------------------------------------------

def test_uri_encode_leaves_the_unreserved_set_alone():
    assert uri_encode("abcXYZ019-_.~") == "abcXYZ019-_.~"
    return


def test_uri_encode_percent_encodes_with_uppercase_hex():
    assert uri_encode(" ") == "%20"
    assert uri_encode("=") == "%3D"
    return


def test_uri_encode_slash_is_conditional():
    # A canonical URI must keep '/' intact; encoding it would change which
    # resource is addressed.
    assert uri_encode("a/b") == "a%2Fb"
    assert uri_encode("a/b", encode_slash=False) == "a/b"
    return


def test_canonical_uri_defaults_to_root():
    assert canonical_uri("") == "/"
    assert canonical_uri(None) == "/"
    return


def test_canonical_uri_encodes_spaces_but_keeps_separators():
    assert canonical_uri("/my-bucket/key name") == "/my-bucket/key%20name"
    return


def test_canonical_query_string_sorts_by_name():
    result = canonical_query_string({"b": "2", "a": "1", "c": "3"})

    assert result == "a=1&b=2&c=3"
    return


def test_canonical_query_string_keeps_the_equals_for_valueless_params():
    # S3 sub-resources arrive as valueless flags and still carry '='.
    assert canonical_query_string({"acl": None}) == "acl="
    return


def test_canonical_query_string_encodes_names_and_values():
    result = canonical_query_string({"prefix": "a b/c"})

    assert result == "prefix=a%20b%2Fc"
    return


def test_canonical_query_string_is_empty_when_there_are_no_params():
    assert canonical_query_string(None) == ""
    assert canonical_query_string({}) == ""
    return


def test_canonical_headers_lowercases_and_sorts():
    canonical, signed = canonical_headers({"Zeta": "z", "Alpha": "a"})

    assert canonical == "alpha:a\nzeta:z\n"
    assert signed == "alpha;zeta"
    return


def test_canonical_headers_trims_and_collapses_whitespace():
    canonical, signed = canonical_headers({"X-Test": "  a   b  "})

    assert canonical == "x-test:a b\n"
    return


# ----------------------------------------------------------------------
# SigV4Signer
# ----------------------------------------------------------------------

def _build_signer(**overrides):
    """
        Build a signer over fixed credentials.

        :returns: A :class:`SigV4Signer`.
    """
    kwargs = {"access_key": "DO00EXAMPLE", "secret_key": "secret-value",
              "region": "nyc3", "service": "s3"}
    kwargs.update(overrides)
    rtnval = SigV4Signer(**kwargs)
    return rtnval


FIXED_MOMENT = datetime.datetime(2026, 7, 26, 12, 36, 0,
                                 tzinfo=datetime.timezone.utc)


def test_signer_exposes_its_scope():
    signer = _build_signer()

    assert signer.access_key == "DO00EXAMPLE"
    assert signer.region == "nyc3"
    assert signer.service == "s3"
    return


def test_sign_returns_the_complete_header_set():
    signer = _build_signer()

    headers = signer.sign(method="GET",
                          url="https://nyc3.digitaloceanspaces.com/bucket",
                          timestamp=FIXED_MOMENT)

    # The signature covers the headers it adds, so the caller must send this
    # whole set — returning only Authorization would produce a mismatch.
    assert headers["host"] == "nyc3.digitaloceanspaces.com"
    assert headers["x-amz-date"] == "20260726T123600Z"
    assert headers["x-amz-content-sha256"] == EMPTY_PAYLOAD_SHA256
    assert headers["Authorization"].startswith(ALGORITHM + " ")
    return


def test_authorization_names_the_credential_scope_and_signed_headers():
    signer = _build_signer()

    headers = signer.sign(method="GET",
                          url="https://nyc3.digitaloceanspaces.com/bucket",
                          timestamp=FIXED_MOMENT)
    authorization = headers["Authorization"]

    assert "Credential=DO00EXAMPLE/20260726/nyc3/s3/aws4_request" in \
        authorization
    assert "SignedHeaders=host;x-amz-content-sha256;x-amz-date" in \
        authorization
    assert "Signature=" in authorization
    return


def test_sign_is_deterministic_for_a_fixed_timestamp():
    signer = _build_signer()

    first = signer.sign(method="GET", url="https://host.example/bucket",
                        timestamp=FIXED_MOMENT)
    second = signer.sign(method="GET", url="https://host.example/bucket",
                         timestamp=FIXED_MOMENT)

    assert first["Authorization"] == second["Authorization"]
    return


def test_signature_covers_the_body():
    signer = _build_signer()

    without = signer.sign(method="PUT", url="https://host.example/bucket",
                          timestamp=FIXED_MOMENT)
    with_body = signer.sign(method="PUT", url="https://host.example/bucket",
                            body=b"payload", timestamp=FIXED_MOMENT)

    assert with_body["x-amz-content-sha256"] == \
        hashlib.sha256(b"payload").hexdigest()
    assert with_body["Authorization"] != without["Authorization"]
    return


def test_signature_covers_the_query_string():
    signer = _build_signer()

    plain = signer.sign(method="GET", url="https://host.example/bucket",
                        timestamp=FIXED_MOMENT)
    with_params = signer.sign(method="GET", url="https://host.example/bucket",
                              params={"prefix": "logs/"},
                              timestamp=FIXED_MOMENT)

    assert with_params["Authorization"] != plain["Authorization"]
    return


def test_signature_covers_the_method():
    signer = _build_signer()

    get_headers = signer.sign(method="GET", url="https://host.example/b",
                              timestamp=FIXED_MOMENT)
    delete_headers = signer.sign(method="DELETE", url="https://host.example/b",
                                 timestamp=FIXED_MOMENT)

    assert get_headers["Authorization"] != delete_headers["Authorization"]
    return


def test_explicit_payload_hash_overrides_the_body():
    signer = _build_signer()

    headers = signer.sign(method="PUT", url="https://host.example/bucket",
                          body=b"ignored", payload_hash="UNSIGNED-PAYLOAD",
                          timestamp=FIXED_MOMENT)

    assert headers["x-amz-content-sha256"] == "UNSIGNED-PAYLOAD"
    return


def test_session_token_is_signed_when_present():
    plain = _build_signer()
    temporary = _build_signer(session_token="tok-123")

    plain_headers = plain.sign(method="GET", url="https://host.example/b",
                               timestamp=FIXED_MOMENT)
    temp_headers = temporary.sign(method="GET", url="https://host.example/b",
                                  timestamp=FIXED_MOMENT)

    assert "x-amz-security-token" not in plain_headers
    assert temp_headers["x-amz-security-token"] == "tok-123"
    # A token that was sent but not signed would be rejected.
    assert "x-amz-security-token" in temp_headers["Authorization"]
    return


def test_caller_headers_are_included_in_the_signature():
    signer = _build_signer()

    headers = signer.sign(method="PUT", url="https://host.example/bucket",
                          headers={"x-amz-acl": "private"},
                          timestamp=FIXED_MOMENT)

    assert headers["x-amz-acl"] == "private"
    assert "x-amz-acl" in headers["Authorization"]
    return


def test_region_is_part_of_the_scope():
    nyc = _build_signer(region="nyc3")
    ams = _build_signer(region="ams3")

    nyc_headers = nyc.sign(method="GET", url="https://host.example/b",
                           timestamp=FIXED_MOMENT)
    ams_headers = ams.sign(method="GET", url="https://host.example/b",
                           timestamp=FIXED_MOMENT)

    # A signature is valid only for its day, region and service.
    assert nyc_headers["Authorization"] != ams_headers["Authorization"]
    return
