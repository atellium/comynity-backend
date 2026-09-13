from django.db import IntegrityError, transaction
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone

from bookmarks.models import SavedItem
from bookmarks.serializers import SavedItemListSerializer, SavedItemSerializer
from bookmarks.services import resolve_saved_items


def _get_owned_saved_item(request, object_id):
    saved_item = SavedItem.objects.filter(
        object_id=object_id,
        user=request.user,
    ).first()
    if saved_item is None:
        raise NotFound("Saved item not found.")
    return saved_item


def _save(serializer, **kwargs):
    try:
        with transaction.atomic():
            return serializer.save(**kwargs)
    except IntegrityError:
        raise serializers.ValidationError(
            {"non_field_errors": ["This item is already saved."]}
        )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def saved_item_create(request):
    if request.method == "GET":
        saved_items = SavedItem.objects.filter(user=request.user).order_by(
            "-created_at"
        )
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(saved_items, request)
        serializer = SavedItemListSerializer(
            page,
            many=True,
            context={
                "request": request,
                "now": timezone.now(),
                "resolved_items": resolve_saved_items(page),
            },
        )
        return paginator.get_paginated_response(serializer.data)

    serializer = SavedItemSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    saved_item = _save(serializer, user=request.user)
    return Response(
        {"result": SavedItemSerializer(saved_item).data},
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def saved_item_detail(request, object_id):
    saved_item = _get_owned_saved_item(request, object_id)

    if request.method == "GET":
        return Response({"result": SavedItemSerializer(saved_item).data})

    if request.method == "DELETE":
        saved_item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = SavedItemSerializer(
        saved_item,
        data=request.data,
        partial=True,
        context={"request": request},
    )
    serializer.is_valid(raise_exception=True)
    saved_item = _save(serializer)
    return Response({"result": SavedItemSerializer(saved_item).data})
