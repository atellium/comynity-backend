# Businesses API

## List businesses

`GET /api/businesses/`

Returns grouped business records with pagination metadata. No full next or previous URLs are exposed.

### Query parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `search` | string | - | Searches name, description, address, and locality. |
| `category` | slug | - | Category slug. |
| `city` | slug | - | City slug. |
| `locality` | string | - | Case-insensitive exact locality name. |
| `lat` | number | - | User latitude. Must be supplied with `lng`; nearby results are sorted by distance. |
| `lng` | number | - | User longitude. Must be supplied with `lat`. |
| `is_active` | boolean | - | Filter by active state. |
| `is_verified` | boolean | - | Filter by verification state. |
| `open_now` | boolean | - | `true` returns currently open businesses; `false` returns businesses not currently open. Businesses that hide their status are always included. |
| `publication_status` | string | - | `draft`, `pending`, `published`, `rejected`, or `suspended`. |
| `status` | string | - | Alias for `publication_status`; conflicting values are rejected. |
| `established_year_min` | integer | - | Minimum establishment year, starting at 1800. |
| `established_year_max` | integer | - | Maximum establishment year. |
| `sort_by` | string | `name` | `name`, `established_year`, `published_at`, `created_at`, or `updated_at`. |
| `sort_order` | string | `asc` | `asc` or `desc`. |
| `page` | integer | `1` | Page number starting at 1. |
| `page_size` | integer | `20` | Results per page, from 1 to 100. |

Example:

```http
GET /api/businesses/?city=kolkata&category=grocery-stores&open_now=true&lat=22.5726&lng=88.3639&is_active=true&publication_status=published&page=1&page_size=20
```

### Response

```json
{
  "pagination": {"page": 1, "page_size": 20, "total_pages": 5, "total_items": 100, "has_next": true, "has_previous": false},
  "category": {"name": "Grocery Store", "display_name": "Grocery", "label": "Grocery Stores"},
  "results": [
    {
      "id": "1464372a-2e6b-45fb-98bd-3fd5a1256a84",
      "name": "Royal Grocery Store",
      "slug": "royal-grocery-store-001",
      "established_year": 2012,
      "is_active": true,
      "publication_status": "published",
      "last_updated": "2026-08-15T01:00:00Z",
      "categories": [{"id": 7, "name": "Grocery Store", "slug": "grocery-stores", "display_name": "Grocery Store"}],
      "media": {"thumbnail": null},
      "location": {
        "address": "215, Patuli Main Road",
        "landmark": "Beside SBI",
        "locality": "Patuli",
        "city": {"id": 7, "name": "Kolkata", "state_id": 4, "state": "West Bengal"},
        "postal_code": "700147",
        "coordinates": {"latitude": 22.53607946, "longitude": 88.466492547, "distance_km": 11.311}
      },
      "contact": {
        "phone": "+917000007919",
        "whatsapp": "+917000007919",
        "alternate_numbers": ["+917003967419"],
        "email": "business001@example.com",
        "website": "",
        "social_urls": {"instagram": "https://instagram.com/royalgrocerystore001"}
      },
      "business_hours_status": {
        "status": "closing_soon",
        "next_closing_time": "2026-08-15T23:00:00+05:30",
        "remark": "Open until 11 PM"
      },
      "publication": {"status": "published", "is_active": true, "is_verified": false, "published_at": "2025-11-08T01:30:00Z"},
      "seo": {"title": "", "description": "", "keywords": ""},
      "metadata": {"created_at": "2026-08-15T01:00:00Z", "updated_at": "2026-08-15T01:00:00Z"}
    }
  ]
}
```

Invalid filters return HTTP `400` with field-keyed errors.

`category` contains the selected category metadata when the `category` slug filter is supplied; otherwise it is `null`.

`business_hours_status.status` is `open`, `closing_soon`, or `closed`. `closing_soon` means the current slot ends in less than 60 minutes. `next_closing_time` is an ISO-8601 timestamp only for `closing_soon`; it is `null` for `open` and `closed`. The `remark` describes the relevant transition, such as `Open until 11 PM`, `Opens tomorrow at 10 AM`, or `Hours unavailable`.

The `open_now` filter always includes businesses with `display_business_status=false`, regardless of their actual opening state, so filtering cannot reveal a status they chose to hide.

Every list and detail representation includes the boolean
`display_business_status` key. When it is `false`, `business_hours_status` is
`null`. When a business disables `display_full_address`, the exact `address`,
`landmark`, `postal_code`, and coordinate values are `null`; locality and city
remain available.

When `lat` and `lng` are present, the API uses the PostGIS geography field and
its spatial index to filter businesses within `radius_km` (25 km by default),
calculate exact distances, and order by `distance_km`. `sort_order=desc`
reverses distance ordering.

## Retrieve a business by slug

`GET /api/businesses/{slug}/`

Returns one business under `result`, using the same grouped keys as the list API. The detail representation additionally includes `description` and the full weekly `business_hours` schedule.

Example:

```http
GET /api/businesses/royal-grocery-store-001/
```

The schedule contains every weekday as a key and that day's ordered opening slots as an array:

```json
{
  "business_hours": {
    "monday": [{"opens_at": "09:00:00", "closes_at": "18:00:00"}],
    "tuesday": [{"opens_at": "09:00:00", "closes_at": "18:00:00"}],
    "wednesday": [{"opens_at": "09:00:00", "closes_at": "18:00:00"}],
    "thursday": [{"opens_at": "09:00:00", "closes_at": "18:00:00"}],
    "friday": [{"opens_at": "09:00:00", "closes_at": "18:00:00"}],
    "saturday": [],
    "sunday": []
  }
}
```

Businesses without configured hours still return all seven weekday keys with empty arrays.

Unknown slugs return HTTP `404` with `{"detail": "Business not found."}`.

## Retrieve or update an owned business

`GET /api/businesses/mine/{slug}/`

`PATCH /api/businesses/mine/{slug}/`

Authentication is required and only the business owner may access this endpoint.
The owner response uses the same grouped representation as the public detail,
but never masks address or coordinate data. It also includes `owner_id`, numeric
city/state IDs, `location.display_full_address`, and both visibility settings
under `visibility`.

`PATCH` partially updates the business. `PUT` is not supported. Omitted fields
remain unchanged, and the response returns the complete owner representation.
The public `GET /api/businesses/{slug}/` endpoint is read-only.

Owner-editable fields include business information, handle, categories, location, contact details, media, `is_active`, visibility preferences, and SEO metadata. Publication status, verification state, ownership, slug, and system metadata cannot be changed through this endpoint.

For example, an owner can enable or disable their business with:

```json
{"is_active": true}
```

## Add or update business hours

`PATCH /api/businesses/{slug}/hours/`

Authentication is required, and only the business owner can update the schedule.
The submitted schedule replaces all existing business-hour slots atomically. Send
an empty `business_hours` array to clear the schedule. Weekdays use integers from
Monday (`0`) through Sunday (`6`); slots for the same day cannot overlap, and
`closes_at` must be later than `opens_at`.

Example request:

```json
{
  "business_hours": [
    {
      "days": [0, 1, 2, 3, 4],
      "opens_at": "09:00",
      "closes_at": "17:00"
    }
  ]
}
```

The response contains the saved slots, including their generated IDs:

```json
{
  "result": {
    "business_hours": [
      {
        "id": "<uuid>",
        "days": [0, 1, 2, 3, 4],
        "opens_at": "09:00:00",
        "closes_at": "17:00:00"
      }
    ]
  }
}
```


# Business Holiday

POST /api/businesses/{slug}/holidays/
PATCH /api/businesses/{slug}/holidays/{holiday_id}/
DELETE /api/businesses/{slug}/holidays/{holiday_id}/
