from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from locations.models import City, Locality
from locations.serializers import (
    CityListQuerySerializer,
    CitySerializer,
    LocalitySearchQuerySerializer,
    LocalitySerializer,
    NearestLocalityRequestSerializer,
)
from locations.services import find_nearest_locality


@api_view(["GET"])
@permission_classes([AllowAny])
def city_list(request):
    query_serializer = CityListQuerySerializer(data=request.query_params)
    query_serializer.is_valid(raise_exception=True)

    cities = City.objects.select_related("state")
    search = query_serializer.validated_data.get("search")
    if search:
        cities = cities.filter(name__icontains=search)

    return Response(CitySerializer(cities.order_by("name", "pk"), many=True).data)


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def nearest_locality(request):
    serializer = NearestLocalityRequestSerializer(
        data=request.query_params if request.method == "GET" else request.data
    )
    serializer.is_valid(raise_exception=True)

    locality = find_nearest_locality(**serializer.validated_data)
    if locality is None:
        return Response(
            {"detail": "No locality with coordinates was found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response(LocalitySerializer(locality).data)


@api_view(["GET"])
@permission_classes([AllowAny])
def search_localities(request):
    query_serializer = LocalitySearchQuerySerializer(data=request.query_params)
    query_serializer.is_valid(raise_exception=True)

    localities = (
        Locality.objects.filter(
            name__istartswith=query_serializer.validated_data["query"]
        )
        .select_related("city")
        .order_by("name", "pk")
    )
    return Response(LocalitySerializer(localities, many=True).data)
