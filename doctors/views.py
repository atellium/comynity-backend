from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from doctors.services import (
    BusinessNotFound,
    DoctorNotFound,
    DoctorSpecialtyNotFound,
    UnsupportedDoctorQueryParams,
    add_doctor_for_my_business,
    delete_doctor_for_my_business,
    get_doctor_detail,
    list_doctor_specialties,
    list_business_doctors,
    list_doctors,
    update_doctor_for_my_business,
)


@api_view(["GET"])
@permission_classes([AllowAny])
def doctor_list(request):
    try:
        return Response(list_doctors(query_params=request.query_params, request=request))
    except UnsupportedDoctorQueryParams as error:
        return Response(
            {"detail": str(error)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except DoctorSpecialtyNotFound as error:
        return Response({"detail": str(error)}, status=status.HTTP_404_NOT_FOUND)


@api_view(["GET"])
@permission_classes([AllowAny])
def doctor_specialty_list(request):
    try:
        return Response(
            list_doctor_specialties(
                query_params=request.query_params,
                request=request,
            )
        )
    except UnsupportedDoctorQueryParams as error:
        return Response(
            {"detail": str(error)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["GET"])
@permission_classes([AllowAny])
def business_doctor_list(request, business_slug):
    try:
        return Response(
            list_business_doctors(
                business_slug=business_slug,
                query_params=request.query_params,
                request=request,
            )
        )
    except UnsupportedDoctorQueryParams as error:
        return Response(
            {"detail": str(error)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except BusinessNotFound as error:
        return Response({"detail": str(error)}, status=status.HTTP_404_NOT_FOUND)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def my_business_doctor_list(request, business_id):
    try:
        return Response(
            add_doctor_for_my_business(
                business_id=business_id,
                data=request.data,
                request=request,
            ),
            status=status.HTTP_201_CREATED,
        )
    except BusinessNotFound as error:
        return Response({"detail": str(error)}, status=status.HTTP_404_NOT_FOUND)


@api_view(["PATCH", "PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def my_business_doctor_detail(request, business_id, doctor_id):
    try:
        if request.method == "DELETE":
            delete_doctor_for_my_business(
                business_id=business_id,
                doctor_id=doctor_id,
                request=request,
            )
            return Response(status=status.HTTP_204_NO_CONTENT)

        return Response(
            update_doctor_for_my_business(
                business_id=business_id,
                doctor_id=doctor_id,
                data=request.data,
                request=request,
                partial=request.method == "PATCH",
            )
        )
    except DoctorNotFound as error:
        return Response({"detail": str(error)}, status=status.HTTP_404_NOT_FOUND)


@api_view(["GET"])
@permission_classes([AllowAny])
def doctor_detail(request, slug):
    try:
        return Response(get_doctor_detail(slug=slug, request=request))
    except DoctorNotFound as error:
        return Response({"detail": str(error)}, status=status.HTTP_404_NOT_FOUND)
