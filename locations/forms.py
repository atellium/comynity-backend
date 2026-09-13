from django import forms
from django.contrib.gis.geos import Point

from locations.models import Locality


class LocalityAdminForm(forms.ModelForm):
    latitude = forms.DecimalField(
        required=False,
        min_value=-90,
        max_value=90,
        max_digits=12,
        decimal_places=9,
    )
    longitude = forms.DecimalField(
        required=False,
        min_value=-180,
        max_value=180,
        max_digits=12,
        decimal_places=9,
    )

    class Meta:
        model = Locality
        fields = ("name", "slug", "city", "aliases", "latitude", "longitude")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.center:
            self.fields["latitude"].initial = self.instance.center.y
            self.fields["longitude"].initial = self.instance.center.x

    def clean(self):
        cleaned_data = super().clean()
        latitude = cleaned_data.get("latitude")
        longitude = cleaned_data.get("longitude")

        if (latitude is None) != (longitude is None):
            raise forms.ValidationError(
                "Latitude and longitude must either both be provided or both be empty."
            )
        return cleaned_data

    def save(self, commit=True):
        locality = super().save(commit=False)
        latitude = self.cleaned_data.get("latitude")
        longitude = self.cleaned_data.get("longitude")
        locality.center = (
            Point(float(longitude), float(latitude), srid=4326)
            if latitude is not None and longitude is not None
            else None
        )

        if commit:
            locality.save()
            self.save_m2m()
        return locality
