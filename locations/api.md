# Locations API

## Import localities

Create or update all localities in a JSON file for one city:

```powershell
python manage.py import_localities --city-id 1 --file locations/data/localities.json
```

The file must contain a JSON array. Localities are matched by city and slug:

```json
[
  {
    "name": "Indiranagar",
    "slug": "indiranagar",
    "aliases": "Indira Nagar, HAL 2nd Stage",
    "latitude": 12.9784,
    "longitude": 77.6408
  },
  {
    "name": "Locality Without Coordinates",
    "slug": "locality-without-coordinates",
    "aliases": "",
    "latitude": null,
    "longitude": null
  }
]
```

`aliases`, `latitude`, and `longitude` may be omitted. Latitude and longitude
must either both be numbers or both be null/omitted. The import is atomic.

## List cities

`GET /api/locations/cities/`

The optional `search` parameter filters city names case-insensitively. For
example: `GET /api/locations/cities/?search=kata`.

```json
[
  {
    "id": 1,
    "name": "Kolkata",
    "slug": "kolkata",
    "tier": 1,
    "state": {
      "id": 1,
      "name": "West Bengal",
      "slug": "west-bengal",
      "code": "WB"
    }
  }
]
```

## Search localities

`GET /api/locations/search/?query=salt`

`query` is required, cannot be blank, and is matched case-insensitively against the beginning of locality names.

```json
[
  {"id": 1, "name": "Salt Lake", "slug": "salt-lake", "city": "Kolkata", "city_slug": "kolkata", "latitude": 22.5867, "longitude": 88.4171}
]
```

## Find nearest locality

`POST /api/locations/nearest/`

No authentication is required. Latitude must be between `-90` and `90`; longitude must be between `-180` and `180`.

```json
{"lat": 22.58, "lng": 88.41}
```

Success response:

```json
{"id": 1, "name": "Salt Lake", "slug": "salt-lake", "city": "Kolkata", "city_slug": "kolkata", "latitude": 22.5867, "longitude": 88.4171}
```

Returns HTTP `404` when no locality with coordinates exists.
