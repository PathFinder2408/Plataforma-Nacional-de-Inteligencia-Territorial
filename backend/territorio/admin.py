from django.contrib.gis import admin

from .models import AliasRol, CapaNormativa, CapaRiesgo, Comuna, FuenteDato, Parcela, TerrenoFiscal

admin.site.register(Comuna, admin.GISModelAdmin)
admin.site.register(FuenteDato)
admin.site.register(Parcela, admin.GISModelAdmin)
admin.site.register(AliasRol)
admin.site.register(TerrenoFiscal, admin.GISModelAdmin)
admin.site.register(CapaNormativa, admin.GISModelAdmin)
admin.site.register(CapaRiesgo, admin.GISModelAdmin)
