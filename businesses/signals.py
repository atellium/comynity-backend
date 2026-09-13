# from django.db.models.signals import post_save
# from django.dispatch import receiver

# from businesses.models import Business, BusinessProfile


# @receiver(post_save, sender=Business)
# def ensure_business_profile(sender, instance, **kwargs):
#     BusinessProfile.objects.get_or_create(business=instance)
