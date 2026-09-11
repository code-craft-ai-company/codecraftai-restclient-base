"""
    .. module:: test_suite_floor
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: A floor on the number of tests the merge gate collects, so a
        discovery regression fails loudly instead of quietly running fewer
        tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""


__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []


import os

from ccai import testbase

from ccai.testbase.testcollector import TestCollector


# The include expression the merge gate passes to `testbase testing run`.
GATE_INCLUDE_EXPRESSION = "ccai.tests.restclient.base"

# The number of tests the gate collected when this floor was set.  Raise it
# when tests are added; never lower it without explaining why in the commit.
TEST_COUNT_FLOOR = 125


def _gate_test_root() -> str:
    """
        Resolves the ``--root`` the gate passes (``source/testroots/ccai``)
        from this module's location under it.
    """
    this_dir = os.path.dirname(os.path.abspath(__file__))
    restclient_dir = os.path.dirname(this_dir)
    tests_dir = os.path.dirname(restclient_dir)
    rtnval = os.path.dirname(tests_dir)
    return rtnval


def test_gate_collects_at_least_the_floor():
    """
        Mechanism: ``testbase testing run --root <root> --includes <expr>``
        builds a :class:`TestCollector` over the root and calls
        ``collect_references`` once per include expression; every module-level
        ``test_*`` function it finds becomes one reference.  This test drives
        the same collector with the same root and expression and counts the
        references, so a wrong include prefix, a module that stops importing,
        or a test file renamed out of the pattern lowers the count and fails
        here by name.  Import errors are asserted empty separately because
        the collector records them rather than raising.
    """
    root = _gate_test_root()

    collector = TestCollector(root, excludes=[], metafilters=[])
    collector.collect_references(GATE_INCLUDE_EXPRESSION)

    testbase.assert_equal(collector.import_errors, {})

    found = len(collector.references)
    if found < TEST_COUNT_FLOOR:
        errmsg_lines = [
            "The merge gate collects fewer tests than the recorded floor.",
            "ROOT: {}".format(root),
            "INCLUDE: {}".format(GATE_INCLUDE_EXPRESSION),
            "FLOOR: {}".format(TEST_COUNT_FLOOR),
            "FOUND: {}".format(found),
        ]
        errmsg = os.linesep.join(errmsg_lines)
        raise AssertionError(errmsg)

    return
