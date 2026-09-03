from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from categories.cache import invalidate_category_cache
from categories.models import BusinessCategory, ProductCategory


def _invalidate_after_commit():
    transaction.on_commit(invalidate_category_cache)


@receiver(post_save, sender=BusinessCategory)
def category_saved(**kwargs):
    _invalidate_after_commit()


@receiver(post_delete, sender=BusinessCategory)
def category_deleted(**kwargs):
    _invalidate_after_commit()


@receiver(post_save, sender=ProductCategory)
def product_category_saved(**kwargs):
    _invalidate_after_commit()


@receiver(post_delete, sender=ProductCategory)
def product_category_deleted(**kwargs):
    _invalidate_after_commit()
