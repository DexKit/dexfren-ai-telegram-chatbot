from functools import lru_cache
from typing import List, Dict, Any
import time

class KnowledgeCache:
    def __init__(self, cache_size: int = 100, cache_ttl: int = 3600):
        """
        Initialize the cache manager
        :param cache_size: Maximum cache size
        :param cache_ttl: Cache time-to-live in seconds (default 1 hour)
        """
        self.cache_ttl = cache_ttl
        self._setup_cache(cache_size)

    def _setup_cache(self, cache_size: int):
        """Configures the cache decorator with the specified size"""
        @lru_cache(maxsize=cache_size)
        def cached_query(query: str, k: int) -> tuple:
            return self.current_time, self._query_function(query, k)
        
        self._cached_query = cached_query
        self.current_time = time.time()
        self._query_function = None

    def set_query_function(self, query_function):
        """Sets the query function that will be cached"""
        self._query_function = query_function

    def query(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        """
        Performs a cached query
        :param query: Query to perform
        :param k: Number of results to return
        :return: List of results
        """
        if not self._query_function:
            raise ValueError("Query function not set")

        timestamp, results = self._cached_query(query, k)
        
        if time.time() - timestamp > self.cache_ttl:
            self._cached_query.cache_clear()
            self.current_time = time.time()
            timestamp, results = self._cached_query(query, k)
            
        return results

    def clear(self):
        """Clears the cache"""
        self._cached_query.cache_clear()
        self.current_time = time.time()

    def info(self) -> Dict[str, Any]:
        """Returns information about the cache state"""
        cache_info = self._cached_query.cache_info()
        return {
            'hits': cache_info.hits,
            'misses': cache_info.misses,
            'maxsize': cache_info.maxsize,
            'currsize': cache_info.currsize
        } 