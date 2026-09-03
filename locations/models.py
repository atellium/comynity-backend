from django.contrib.gis.db import models as gis_models
from django.core.validators import RegexValidator
from django.db import models


state_code_validator = RegexValidator(
    regex=r"^[A-Z]{2}$",
    message="Enter a two-letter uppercase state code.",
)


class State(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    code = models.CharField(
        max_length=2,
        unique=True,
        validators=[state_code_validator],
    )

    class Meta:
        ordering = ("name",)
        indexes = [
            models.Index(fields=["name"]),
        ]

    def __str__(self):
        return self.name


class City(models.Model):
    class CityTier(models.IntegerChoices):
        TIER_1 = 1, "Tier 1"
        TIER_2 = 2, "Tier 2"
        TIER_3 = 3, "Tier 3"
        TIER_4 = 4, "Tier 4"

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)

    state = models.ForeignKey(
        State,
        on_delete=models.PROTECT,
        related_name="cities",
    )

    tier = models.PositiveSmallIntegerField(
        choices=CityTier.choices,
        default=CityTier.TIER_2,
    )

    class Meta:
        ordering = ("name",)
        verbose_name_plural = "Cities"

        constraints = [
            models.UniqueConstraint(
                fields=["state", "slug"],
                name="unique_city_slug_per_state",
            ),
        ]

        indexes = [
            models.Index(fields=["state", "name"]),
            models.Index(fields=["state", "slug"]),
            models.Index(fields=["tier"]),
        ]

    def __str__(self):
        return f"{self.name}, {self.state.name}"


class Locality(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)

    city = models.ForeignKey(
        City,
        on_delete=models.PROTECT,
        related_name="localities",
    )

    aliases = models.CharField(
        max_length=300,
        blank=True,
        default="",
        help_text="Comma-separated alternate names/search terms.",
    )

    center = gis_models.PointField(
        geography=True,
        srid=4326,
        null=True,
        blank=True,
        spatial_index=True,
        help_text="Representative point (longitude, latitude).",
    )

    @property
    def latitude(self):
        return self.center.y if self.center else None

    @property
    def longitude(self):
        return self.center.x if self.center else None

    class Meta:
        ordering = ("name",)
        verbose_name_plural = "Localities"

        constraints = [
            models.UniqueConstraint(
                fields=["city", "slug"],
                name="unique_locality_slug_per_city",
            ),
        ]

        indexes = [
            models.Index(fields=["city", "name"]),
            models.Index(fields=["city", "slug"]),
        ]

    def __str__(self):
        return f"{self.name}, {self.city.name}"