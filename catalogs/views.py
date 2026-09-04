from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from django.db import transaction
from django.conf import settings
from botocore.exceptions import ClientError

from businesses.direct_uploads import new_upload_key, presign_upload, r2_client, storage_key

from businesses.services import get_business_for_update

from catalogs.serializers import (
    ProductCategorySerializer,
    ProductDetailSerializer,
    ProductListQuerySerializer,
    ProductListSerializer,
    CatalogWriteSerializer,
    CatalogCategoryListQuerySerializer,
    CatalogCategoryListSerializer,
    CatalogImageSerializer,
    CatalogGallerySyncSerializer,
    CatalogImageBulkUploadSerializer,
    CatalogImageWriteSerializer,
    CatalogImageUploadCreateSerializer,
    CatalogImageUploadSerializer,
)
from catalogs.models import CatalogImage, CatalogImageUpload
from catalogs.services import (
    get_public_business,
    get_public_product_by_slug,
    list_available_product_categories,
    list_public_products,
    paginate_products,
    get_catalog_for_owner,
    list_catalog_categories,
    paginate_catalog_categories,
)


@api_view(["GET"])
@permission_classes([AllowAny])
def catalog_category_list(request):
    query = CatalogCategoryListQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)
    filters = query.validated_data
    categories, pagination = paginate_catalog_categories(
        list_catalog_categories(filters), filters["page"], filters["page_size"]
    )
    return Response(
        {
            "pagination": pagination,
            "results": CatalogCategoryListSerializer(
                categories, many=True, context={"request": request}
            ).data,
        }
    )


def _owned_business(request, business_slug):
    business = get_business_for_update(business_slug)
    if business is None:
        raise NotFound("Business not found.")
    if business.owner_id != request.user.pk:
        raise PermissionDenied("You can only manage catalogs for your own business.")
    return business


def _owned_catalog(request, business_slug, catalog_slug):
    business = _owned_business(request, business_slug)
    catalog = get_catalog_for_owner(business, catalog_slug)
    if catalog is None:
        raise NotFound("Catalog not found.")
    return catalog


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def catalog_create(request, business_slug):
    business = _owned_business(request, business_slug)
    serializer = CatalogWriteSerializer(
        data=request.data,
        context={"request": request, "business": business},
    )
    serializer.is_valid(raise_exception=True)
    with transaction.atomic():
        catalog = serializer.save(business=business)
    return Response(
        {
            "result": CatalogWriteSerializer(
                catalog, context={"request": request, "business": business}
            ).data
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def catalog_manage(request, business_slug, catalog_slug):
    catalog = _owned_catalog(request, business_slug, catalog_slug)
    business = catalog.business

    if request.method == "DELETE":
        catalog.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = CatalogWriteSerializer(
        catalog,
        data=request.data,
        partial=True,
        context={"request": request, "business": business},
    )
    serializer.is_valid(raise_exception=True)
    with transaction.atomic():
        catalog = serializer.save()
    return Response(
        {
            "result": CatalogWriteSerializer(
                catalog, context={"request": request, "business": business}
            ).data
        }
    )


@api_view(["GET", "POST", "PATCH"])
@permission_classes([IsAuthenticated])
def catalog_image_create(request, business_slug, catalog_slug):
    catalog = _owned_catalog(request, business_slug, catalog_slug)

    if request.method == "GET":
        return Response(
            {
                "results": CatalogImageSerializer(
                    catalog.images.order_by("-is_primary", "sort_order", "created_at"),
                    many=True,
                    context={"request": request},
                ).data
            }
        )

    images = request.FILES.getlist("images")
    if not images:
        # Keep the original singular field compatible, including when repeated.
        images = request.FILES.getlist("image")

    sort_orders = []
    if hasattr(request.data, "getlist"):
        sort_orders = request.data.getlist("sort_orders")
        if not sort_orders:
            sort_orders = request.data.getlist("sort_orders[]")
    else:
        sort_orders = request.data.get("sort_orders", [])

    # Do not copy request.data here. QueryDict.copy() deep-copies temporary
    # uploaded files, whose BufferedRandom handles cannot be pickled.
    data = {
        "images": images,
        **{
            field: request.data[field]
            for field in ("alt_text", "is_primary", "is_active", "sort_order")
            if field in request.data
        },
    }
    if sort_orders:
        data["sort_orders"] = sort_orders

    if request.method == "PATCH":
        if hasattr(request.data, "getlist"):
            order = request.data.getlist("order")
            if not order:
                order = request.data.getlist("order[]")
        else:
            order = request.data.get("order", [])

        sync_serializer = CatalogGallerySyncSerializer(
            data={"images": images, "order": order}
        )
        sync_serializer.is_valid(raise_exception=True)
        sync_data = sync_serializer.validated_data
        new_images = sync_data.get("images", [])
        parsed_order = sync_data["parsed_order"]

        existing_images = {image.pk: image for image in catalog.images.all()}
        requested_existing_ids = {
            value for kind, value in parsed_order if kind == "existing"
        }
        missing_ids = requested_existing_ids - existing_images.keys()
        if missing_ids:
            raise NotFound(
                f"Catalog images not found: {', '.join(map(str, sorted(missing_ids)))}."
            )

        images_to_delete = [
            image
            for image_id, image in existing_images.items()
            if image_id not in requested_existing_ids
        ]

        with transaction.atomic():
            CatalogImage.objects.filter(catalog=catalog, is_primary=True).update(
                is_primary=False
            )
            for image in images_to_delete:
                stored_image = image.image
                image.delete()
                transaction.on_commit(
                    lambda stored_image=stored_image: stored_image.delete(save=False)
                )

            ordered_images = []
            for sort_order, (kind, value) in enumerate(parsed_order):
                if kind == "existing":
                    gallery_image = existing_images[value]
                    CatalogImage.objects.filter(pk=gallery_image.pk).update(
                        sort_order=sort_order,
                        is_primary=False,
                    )
                else:
                    gallery_image = CatalogImage.objects.create(
                        catalog=catalog,
                        image=new_images[value],
                        sort_order=sort_order,
                        is_primary=False,
                    )
                ordered_images.append(gallery_image)

            if ordered_images:
                CatalogImage.objects.filter(pk=ordered_images[0].pk).update(
                    is_primary=True
                )

        return Response(
            {
                "results": CatalogImageSerializer(
                    catalog.images.all(), many=True, context={"request": request}
                ).data
            }
        )

    data["is_primary"] = True
    data["sort_order"] = 0
    data.pop("sort_orders", None)
    serializer = CatalogImageBulkUploadSerializer(
        data=data,
        context={"request": request, "catalog": catalog},
    )
    serializer.is_valid(raise_exception=True)
    with transaction.atomic():
        images = serializer.save()
    return Response(
        {
            "results": CatalogImageSerializer(
                images, many=True, context={"request": request}
            ).data
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def catalog_image_upload_create(request, business_slug, catalog_slug):
    catalog = _owned_catalog(request, business_slug, catalog_slug)
    if not settings.R2_ENABLED:
        return Response({"detail": "Direct uploads require R2_ENABLED."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    serializer = CatalogImageUploadCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    content_type = serializer.validated_data["content_type"]
    object_key = new_upload_key(f"catalog-{catalog.pk}", content_type)
    upload = CatalogImageUpload.objects.create(catalog=catalog, object_key=object_key, content_type=content_type)
    return Response({"id": upload.pk, "upload_url": presign_upload(object_key, content_type), "content_type": content_type, "expires_in": 300}, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def catalog_image_upload_detail(request, business_slug, catalog_slug, upload_id):
    catalog = _owned_catalog(request, business_slug, catalog_slug)
    upload = CatalogImageUpload.objects.select_related("catalog_image").filter(pk=upload_id, catalog=catalog).first()
    if upload is None:
        raise NotFound("Product image upload not found.")
    return Response(CatalogImageUploadSerializer(upload, context={"request": request}).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def catalog_image_upload_complete(request, business_slug, catalog_slug, upload_id):
    catalog = _owned_catalog(request, business_slug, catalog_slug)
    upload = CatalogImageUpload.objects.filter(pk=upload_id, catalog=catalog).first()
    if upload is None:
        raise NotFound("Product image upload not found.")
    if upload.status != CatalogImageUpload.Status.PENDING:
        raise ValidationError({"detail": "This upload has already been finalized."})
    client = r2_client()
    try:
        metadata = client.head_object(Bucket=settings.R2_BUCKET_NAME, Key=storage_key(upload.object_key))
    except ClientError as exc:
        raise ValidationError({"detail": "The uploaded object was not found in R2."}) from exc
    if metadata["ContentLength"] > settings.MAX_IMAGE_UPLOAD_BYTES:
        client.delete_object(Bucket=settings.R2_BUCKET_NAME, Key=storage_key(upload.object_key))
        upload.status, upload.error = CatalogImageUpload.Status.FAILED, "Image file is too large."
        upload.save(update_fields=("status", "error", "updated_at"))
        raise ValidationError({"detail": upload.error})
    if metadata.get("ContentType") != upload.content_type:
        raise ValidationError({"detail": "Uploaded image content type does not match the request."})
    upload.status = CatalogImageUpload.Status.PROCESSING
    upload.save(update_fields=("status", "updated_at"))
    from catalogs.tasks import process_catalog_image_upload
    process_catalog_image_upload.delay(str(upload.pk))
    return Response(CatalogImageUploadSerializer(upload, context={"request": request}).data, status=status.HTTP_202_ACCEPTED)


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def catalog_image_manage(request, business_slug, catalog_slug, image_id):
    catalog = _owned_catalog(request, business_slug, catalog_slug)
    image = CatalogImage.objects.filter(pk=image_id, catalog=catalog).first()
    if image is None:
        raise NotFound("Catalog image not found.")

    if request.method == "DELETE":
        stored_image = image.image
        image.delete()
        stored_image.delete(save=False)
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = CatalogImageWriteSerializer(
        image,
        data=request.data,
        partial=True,
        context={"request": request, "catalog": catalog},
    )
    serializer.is_valid(raise_exception=True)
    with transaction.atomic():
        image = serializer.save()
    return Response(
        {
            "result": CatalogImageSerializer(
                image, context={"request": request}
            ).data
        }
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def business_product_list(request, slug):
    business = get_public_business(slug)
    if business is None:
        raise NotFound("Business not found.")

    query = ProductListQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)
    filters = query.validated_data
    products, pagination = paginate_products(
        list_public_products(business, filters),
        filters["page"],
        filters["page_size"],
    )
    return Response(
        {
            "business": {
                "id": business.pk,
                "name": business.name,
                "slug": business.slug,
            },
            "categories": ProductCategorySerializer(
                list_available_product_categories(business),
                many=True,
                context={"request": request},
            ).data,
            "pagination": pagination,
            "results": ProductListSerializer(
                products,
                many=True,
                context={"request": request},
            ).data,
        }
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def product_detail(request, slug):
    product = get_public_product_by_slug(slug)
    if product is None:
        raise NotFound("Product not found.")
    return Response(
        {
            "result": ProductDetailSerializer(
                product,
                context={"request": request},
            ).data
        }
    )
