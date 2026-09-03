from ccai import testbase

from ccai.restclient.base.restclientgenerator import literal_text


def test_markdown_escapes_are_unwrapped():
    """
        Markdown-escaped punctuation in an OpenAPI description becomes plain punctuation.
    """
    found = literal_text(r"short\_description and **display\_name** or \[link\]")
    testbase.assert_equal(found, "short_description and **display_name** or [link]")
    return


def test_other_backslashes_are_doubled():
    """
        A backslash that is not a markdown escape survives as a literal backslash.
    """
    found = literal_text(r"path C:\temp\new")
    testbase.assert_equal(found, r"path C:\\temp\\new")
    return


def test_result_compiles_as_a_docstring_without_warnings():
    """
        The sanitized text is valid inside a generated docstring under -W error.
    """
    import warnings

    text = literal_text(r"ISSUE\_TEMPLATE, PULL\_REQUEST\_TEMPLATE and C:\new")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        compile('"""' + text + '"""', "<generated>", "exec")
    return


def test_empty_and_missing_text():
    """
        Missing descriptions produce an empty string rather than failing.
    """
    testbase.assert_equal(literal_text(""), "")
    testbase.assert_equal(literal_text(None), "")
    return
