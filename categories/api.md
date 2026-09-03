# Categories API

## List business categories

`GET /api/categories/business/`

Returns paginated business categories. Authentication is not required.

Query parameters:

- `search`: searches name, display name, label, slug, and aliases.
- `name`, `label`, `display_name`: case-insensitive partial filters.
- `slug`: exact slug filter.
- `is_active`, `is_featured`: boolean filters.
- `created_after`, `created_before`, `updated_after`, `updated_before`: ISO-8601 datetime filters.
- `sort_by`: `id`, `name`, `label`, `display_name`, `slug`, `sort_order`, `is_active`, `is_featured`, `created_at`, or `updated_at`.
- `sort_order`: `asc` or `desc`.
- `page`: page number, starting at 1.
- `page_size`: number of results from 1 to 100; defaults to 20.

Responses are cached only when `is_featured=true`. Each unique combination of
filters, sorting, and pagination has its own cache entry. Saving or deleting a
business category invalidates these cached responses.

## Search visible categories

`GET /api/categories/search/`

Returns active categories in configured display order.
