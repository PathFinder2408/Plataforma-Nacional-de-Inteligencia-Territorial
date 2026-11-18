from django.contrib.gis import admin

from .models import AliasRol, Comuna, FuenteDato, Parcela

admin.site.register(Comuna, admin.GISModelAdmin)
admin.site.register(FuenteDato)
admin.site.register(Parcela, admin.GISModelAdmin)
admin.site.register(AliasRol)
