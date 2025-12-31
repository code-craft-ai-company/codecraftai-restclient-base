from typing import TYPE_CHECKING, Any, Dict, TypeVar

import weakref

if TYPE_CHECKING:
    from automojo.restclient.base.restclientbase import RestClientBase


T = TypeVar('T')


class RestApiGroup:
    """
        Base class for REST API operation groups.
    """

    def __init__(self, client: "RestClientBase"):
        self._client_ref = weakref.ref(client)
        return
    
    @property
    def client(self) -> "RestClientBase":
        return self._client_ref()
    
    def _parse_item(self, data: Dict[str, Any], item_type: type[T]) -> T:
        """
            Parse a dictionary into a SchemaObject instance.
            
            :param data: Raw dictionary data
            :param item_type: Target SchemaObject type
            
            :returns: Parsed SchemaObject instance
        """
        try:
            # Use from_dict if available (SchemaObject types)
            if hasattr(item_type, 'from_dict'):
                return item_type.from_dict(data)  # type: ignore
            else:
                return item_type(**data)  # type: ignore
        except Exception:
            # Fallback: return the raw dict if parsing fails
            return data  # type: ignore
