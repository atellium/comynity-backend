from rest_framework import serializers

from locations.models import City, Locality


class NearestLocalityRequestSerializer(serializers.Serializer):
    lat = serializers.FloatField(min_value=-90, max_value=90)
    lng = serializers.FloatField(min_value=-180, max_value=180)


class LocalitySearchQuerySerializer(serializers.Serializer):
    query = serializers.CharField(max_length=100, trim_whitespace=True, allow_blank=False)


class CityListQuerySerializer(serializers.Serializer):
    search = serializers.CharField(
        required=False,
        max_length=100,
        trim_whitespace=True,
        allow_blank=False,
    )


class CitySerializer(serializers.ModelSerializer):
    state = serializers.SerializerMethodField()

    class Meta:
        model = City
        fields = ("id", "name", "slug", "tier", "state")

    def get_state(self, obj):
        return {
            "id": obj.state_id,
            "name": obj.state.name,
            "slug": obj.state.slug,
            "code": obj.state.code,
        }


class LocalitySerializer(serializers.ModelSerializer):
    city = serializers.CharField(source="city.name", read_only=True)
    city_slug = serializers.CharField(source="city.slug", read_only=True)
    latitude = serializers.FloatField(read_only=True)
    longitude = serializers.FloatField(read_only=True)

    class Meta:
        model = Locality
        fields = (
            "id",
            "name",
            "slug",
            "city",
            "city_slug",
            "latitude",
            "longitude",
        )
