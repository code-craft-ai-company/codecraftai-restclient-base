"""
    The canonical home of :class:`SchemaObject` is
    ``ccai.interfaces.schemaobject`` -- the declarative schema mechanism is a
    base-level interface so packages beneath the restclient family (e.g.
    codecraftai-configuration) can build schema types on it without a
    dependency cycle.  This module remains the spelling the restclient family
    imports.
"""

from ccai.interfaces.schemaobject import SchemaObject, SchemaObjectMeta
