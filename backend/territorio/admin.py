from django.contrib.gis import admin

from .models import (
    AliasRol,
    CapaNormativa,
    CapaRiesgo,
    CeldaH3,
    Comuna,
    FuenteDato,
    Parcela,
    TerrenoFiscal,
    Transaccion,
)

admin.site.register(Comuna, admin.GISModelAdmin)
admin.site.register(FuenteDato)
admin.site.register(Parcela, admin.GISModelAdmin)
admin.site.register(AliasRol)
admin.site.register(TerrenoFiscal, admin.GISModelAdmin)
admin.site.register(CapaNormativa, admin.GISModelAdmin)
admin.site.register(CapaRiesgo, admin.GISModelAdmin)
admin.site.register(Transaccion)
admin.site.register(CeldaH3, admin.GISModelAdmin)
