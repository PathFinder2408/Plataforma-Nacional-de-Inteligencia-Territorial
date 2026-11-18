import redis
from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.urls import include, path


def health_view(_request):
    """Verifica conectividad con PostGIS y Redis."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1;")
    client = redis.from_url(settings.REDIS_URL)
    client.ping()
    return JsonResponse({"status": "ok", "db": "postgis", "cache": "redis"})


urlpatterns = [
    path("health/", health_view, name="health"),
    path("api/v1/", include("territorio.urls")),
]
