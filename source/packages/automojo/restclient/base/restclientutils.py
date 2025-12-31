
"""
    .. module:: restclientutils
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: restclientutils module.
    
    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""


__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Automation Mojo LLC"
__credits__ = []

import dataclasses
import urllib.parse

def normalize_query_arg_value(val) -> str:
    """
        Converts values to a normalized string that can be used to fill a query
        string.

        :param val: Value to normalize for use in a query string.

        :returns: Normalized string representation of ``val``.
    """

    norm_val = None

    if type(val) == int:
        norm_val = val
    else:
        norm_val = urllib.parse.quote(val)

    return norm_val


def convert_to_foundation_datatype(val) -> dict:
    """
        Helper function for converting a value to a dictionary.

        :param val: Value to convert.

        :returns: A dictionary or dictionary-compatible representation of ``val``.
    """

    dval = None

    if dataclasses.is_dataclass(val):
        dval = dataclasses.asdict(val)
    elif hasattr(val, "as_dict"):
        dval = val.as_dict()
    elif isinstance(val, str) or isinstance(val, int) or isinstance(val, dict):
        dval = val
    elif isinstance(val, list) or isinstance(val, tuple):
        dval = [ convert_to_foundation_datatype(item) for item in val ]
    else:
        errmsg = f"Unable to convert value of type='{type(val)}' to a dictionary."
        raise ValueError(errmsg)
    
    return dval
