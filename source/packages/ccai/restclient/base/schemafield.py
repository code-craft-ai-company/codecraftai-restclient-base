"""
    .. module:: schemafield
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Field descriptor for declarative schema object definitions.
    
    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

from typing import Any, Optional, TypeVar, get_type_hints


T = TypeVar('T')


class Field:
    """
        Descriptor for schema object fields, similar to SQLAlchemy Column.
        
        Provides declarative field definition with type, required status, and metadata.
    """
    
    def __init__(self, 
                 field_type: Any,
                 *,
                 required: bool = False,
                 description: Optional[str] = None,
                 default: Optional[Any] = None):
        """
            Initialize a field descriptor.
            
            :param field_type: The Python type of the field (int, str, List[X], etc.)
            :param required: Whether this field is required
            :param description: Optional description from OpenAPI schema
            :param default: Default value if not required
        """
        self.field_type = field_type
        self.required = required
        self.description = description
        self.default = default
        self.name: Optional[str] = None  # Set by SchemaObject metaclass
        return
    
    def __set_name__(self, owner, name):
        """
            Called when the descriptor is assigned to a class attribute.
            
            :param owner: The class that owns this descriptor
            :param name: The attribute name
        """
        self.name = name
        return
    
    def __get__(self, obj, objtype=None):
        """
            Get the field value from an instance.
            
            :param obj: The instance (None if accessing from class)
            :param objtype: The class type
            
            :returns: Field value or self if accessed from class
        """
        if obj is None:
            # Accessing from class, return descriptor
            return self
        
        # Get from instance __dict__
        return obj.__dict__.get(self.name, self.default)
    
    def __set__(self, obj, value):
        """
            Set the field value on an instance.
            
            :param obj: The instance
            :param value: The value to set
        """
        obj.__dict__[self.name] = value
        return
    
    def __repr__(self) -> str:
        """
            String representation of the field.
        """
        req_str = "required" if self.required else "optional"
        if isinstance(self.field_type, str):
            type_name = self.field_type
        else:
            type_name = getattr(self.field_type, "__name__", str(self.field_type))
        return f"Field({type_name}, {req_str})"
