"""
    .. module:: pagedlist
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Container for paginated list responses with navigation support.
    
    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

from __future__ import annotations

from typing import Any, Dict, Generic, List, Optional, TypeVar
from dataclasses import dataclass
import re


T = TypeVar('T')


@dataclass
class LinkInfo:
    """
        Parsed pagination link information from Link header.
    """
    url: str
    rel: str
    page: Optional[int] = None


class PagedList(Generic[T]):
    """
        Container for paginated list responses.
        
        Provides typed access to list items plus pagination metadata
        from the Link header and response data.
    """
    
    def __init__(self, items: List[T], headers: Dict[str, Any], response_data: Any = None):
        """
            Initialize a PagedList.
            
            :param items: The list of typed items
            :param headers: HTTP response headers (for Link header)
            :param response_data: Raw response data for extracting pagination hints
        """
        self._items = items
        self._headers = headers
        self._response_data = response_data
        self._links: Optional[Dict[str, LinkInfo]] = None
        return
    
    @property
    def items(self) -> List[T]:
        """
            Get the list of typed items.
        """
        return self._items
    
    def __iter__(self):
        """
            Allow iteration over items directly.
        """
        return iter(self._items)
    
    def __len__(self) -> int:
        """
            Get the count of items in this page.
        """
        return len(self._items)
    
    def __getitem__(self, index):
        """
            Allow indexing into items.
        """
        return self._items[index]
    
    @property
    def links(self) -> Dict[str, LinkInfo]:
        """
            Get pagination links from Link header.
        """
        if self._links is None:
            self._links = self._parse_link_header()
        return self._links
    
    @property
    def has_next(self) -> bool:
        """
            Returns True if there is a next page.
        """
        return 'next' in self.links
    
    @property
    def has_prev(self) -> bool:
        """
            Returns True if there is a previous page.
        """
        return 'prev' in self.links
    
    @property
    def next_page(self) -> Optional[int]:
        """
            Get the next page number if available.
        """
        next_link = self.links.get('next')
        return next_link.page if next_link else None
    
    @property
    def prev_page(self) -> Optional[int]:
        """
            Get the previous page number if available.
        """
        prev_link = self.links.get('prev')
        return prev_link.page if prev_link else None
    
    @property
    def first_page(self) -> Optional[int]:
        """
            Get the first page number if available.
        """
        first_link = self.links.get('first')
        return first_link.page if first_link else None
    
    @property
    def last_page(self) -> Optional[int]:
        """
            Get the last page number if available.
        """
        last_link = self.links.get('last')
        return last_link.page if last_link else None
    
    def _parse_link_header(self) -> Dict[str, LinkInfo]:
        """
            Parse the Link header for pagination information.
            
            :returns: Dictionary mapping rel types (next, prev, first, last) to LinkInfo
        """
        link_header = self._headers.get('Link', self._headers.get('link', ''))
        if not link_header:
            return {}
        
        links: Dict[str, LinkInfo] = {}
        
        # Link header format: <url>; rel="next", <url>; rel="prev"
        parts = link_header.split(',')
        for part in parts:
            part = part.strip()
            match = re.match(r'<([^>]+)>;\s*rel="([^"]+)"', part)
            if match:
                url = match.group(1)
                rel = match.group(2)
                
                # Try to extract page number from URL
                page_match = re.search(r'[?&]page=(\d+)', url)
                page = int(page_match.group(1)) if page_match else None
                
                links[rel] = LinkInfo(url=url, rel=rel, page=page)
        
        return links
