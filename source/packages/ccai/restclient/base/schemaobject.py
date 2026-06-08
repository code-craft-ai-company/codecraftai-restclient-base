"""
    .. module:: schemaobject
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Base class for all generated schema types with Field descriptor support.
    
    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

from typing import Any, Dict, List, Optional, Type, TypeVar

from ccai.restclient.base.schemafield import Field


T = TypeVar('T', bound='SchemaObject')


class SchemaObjectMeta(type):
    """
        Metaclass for SchemaObject that collects Field descriptors.
    """
    
    def __new__(mcs, name, bases, namespace, **kwargs):
        # Collect all Field descriptors
        fields: Dict[str, Field] = {}
        
        for key, value in namespace.items():
            if isinstance(value, Field):
                fields[key] = value
        
        # Store field registry on the class
        namespace['_fields'] = fields
        
        # Create the class
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)
        
        return cls


class SchemaObject(metaclass=SchemaObjectMeta):
    """
        Base class for all generated schema types.
        
        Uses Field descriptors for declarative field definition.
        Provides serialization/deserialization support via to_dict and from_dict methods.
    """
    
    # Class-level registry (populated by metaclass)
    _fields: Dict[str, Field] = {}
    
    def __init__(self, **kwargs):
        """
            Initialize the schema object with provided keyword arguments.
            
            :param kwargs: Field values to set on the object
        """
        # Set all fields from kwargs
        for field_name, field_descriptor in self._fields.items():
            if field_name in kwargs:
                setattr(self, field_name, kwargs[field_name])
            elif field_descriptor.default is not None:
                setattr(self, field_name, field_descriptor.default)
            elif not field_descriptor.required:
                setattr(self, field_name, None)
            # Required fields without values will raise AttributeError when accessed
        
        # Allow extra fields for flexibility
        for key, value in kwargs.items():
            if key not in self._fields:
                setattr(self, key, value)
        return
    
    def to_dict(self) -> Dict[str, Any]:
        """
            Convert the object to a dictionary suitable for JSON serialization.
            
            :returns: Dictionary representation of the object
        """
        result: Dict[str, Any] = {}
        
        for field_name, field_descriptor in self._fields.items():
            value = getattr(self, field_name, None)
            
            if value is None:
                # Skip None values unless field is required
                if field_descriptor.required:
                    result[field_name] = None
                continue
            
            # Handle nested SchemaObjects
            if isinstance(value, SchemaObject):
                result[field_name] = value.to_dict()
            # Handle lists of SchemaObjects
            elif isinstance(value, list):
                result[field_name] = [
                    item.to_dict() if isinstance(item, SchemaObject) else item
                    for item in value
                ]
            # Handle dicts with SchemaObject values
            elif isinstance(value, dict):
                result[field_name] = {
                    k: v.to_dict() if isinstance(v, SchemaObject) else v
                    for k, v in value.items()
                }
            else:
                result[field_name] = value
        
        return result
    
    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """
            Create an instance from a dictionary.
            
            :param data: Dictionary with field values
            
            :returns: New instance of the schema object
        """
        if not isinstance(data, dict):
            # If data is not a dict, return as-is (might be primitive type)
            return data  # type: ignore
        
        # Create instance with the data
        instance = cls(**data)
        
        return instance
    
    def __repr__(self) -> str:
        """
            String representation of the object.
        """
        field_strs = []
        for field_name in self._fields.keys():
            value = getattr(self, field_name, None)
            if value is not None:
                field_strs.append(f"{field_name}={value!r}")
        
        return f"{self.__class__.__name__}({', '.join(field_strs)})"
    
    def __eq__(self, other: Any) -> bool:
        """
            Equality comparison based on field values.
        """
        if not isinstance(other, self.__class__):
            return False
        
        for field_name in self._fields.keys():
            if getattr(self, field_name, None) != getattr(other, field_name, None):
                return False
        
        return True
