from django.db import models
from django.utils.text import slugify


def generate_unique_slug(
    instance: models.Model,
    value: str,
    *,
    slug_field: str = "slug",
    fallback: str = "item",
    using: str | None = None,
) -> str:
    """Return a slug that is unique for an instance's model.

    Conflicting slugs receive an incrementing suffix (for example, ``shop-2``).
    The current instance is excluded when updating an existing object.
    """
    field = instance._meta.get_field(slug_field)
    max_length = field.max_length
    base_slug = slugify(value) or slugify(fallback) or "item"
    base_slug = base_slug[:max_length].strip("-") or "item"[:max_length]

    queryset = type(instance)._default_manager.using(using or instance._state.db).all()
    if instance.pk is not None:
        queryset = queryset.exclude(pk=instance.pk)

    candidate = base_slug
    counter = 2
    while queryset.filter(**{slug_field: candidate}).exists():
        suffix = f"-{counter}"
        candidate = f"{base_slug[:max_length - len(suffix)].rstrip('-')}{suffix}"
        counter += 1

    return candidate
