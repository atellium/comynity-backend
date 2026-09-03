from django.db import models

from core.utils import generate_unique_slug


class TimestampedModel(models.Model):
    """Add creation and modification timestamps to a model."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SEOModel(models.Model):
    """Add optional search-engine metadata to a model."""

    seo_title = models.CharField(max_length=255, blank=True)
    seo_description = models.TextField(blank=True)
    seo_keywords = models.CharField(max_length=500, blank=True)

    class Meta:
        abstract = True


class AutoSlugModel(models.Model):
    """Generate a unique slug from a configurable model field."""

    slug = models.SlugField(max_length=255, unique=True, blank=True)
    slug_source_field = "name"
    slug_fallback = "item"

    class Meta:
        abstract = True

    def get_slug_source(self):
        return getattr(self, self.slug_source_field)

    def save(self, *args, **kwargs):
        generated_slug = not self.slug
        if generated_slug:
            self.slug = generate_unique_slug(
                self,
                self.get_slug_source(),
                fallback=self.slug_fallback,
                using=kwargs.get("using"),
            )

        update_fields = kwargs.get("update_fields")
        if generated_slug and update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {"slug"}

        return super().save(*args, **kwargs)
