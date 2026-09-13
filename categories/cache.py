import hashlib
from urllib.parse import urlencode
from uuid import uuid4

from django.core.cache import cache


CATEGORY_CACHE_GENERATION_KEY = "categories:cache-generation"
CATEGORY_CACHE_TIMEOUT = None


def _generation():
    generation = cache.get(CATEGORY_CACHE_GENERATION_KEY)
    if generation is None:
        generation = uuid4().hex
        cache.add(
            CATEGORY_CACHE_GENERATION_KEY,
            generation,
            timeout=CATEGORY_CACHE_TIMEOUT,
        )
        generation = cache.get(CATEGORY_CACHE_GENERATION_KEY) or generation
    return generation


def category_cache_key(name, query_params=None):
    key = f"categories:{_generation()}:{name}"
    if query_params:
        encoded = urlencode(sorted(query_params.lists()), doseq=True)
        key = f"{key}:{hashlib.sha256(encoded.encode()).hexdigest()}"
    return key


def invalidate_category_cache():
    old_generation = cache.get(CATEGORY_CACHE_GENERATION_KEY)
    cache.set(
        CATEGORY_CACHE_GENERATION_KEY,
        uuid4().hex,
        timeout=CATEGORY_CACHE_TIMEOUT,
    )
    if old_generation is not None and hasattr(cache, "delete_pattern"):
        cache.delete_pattern(f"categories:{old_generation}:*")
