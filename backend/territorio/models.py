from django.contrib.gis.db import models
from django.contrib.postgres.indexes import GistIndex


class NivelConfianza(models.TextChoices):
    ALTA = "alta", "Alta"
    MEDIA = "media", "Media"
    REFERENCIAL = "referencial", "Referencial"


class SerieCatastral(models.TextChoices):
    AGRICOLA = "agricola", "Agrícola"
    NO_AGRICOLA = "no_agricola", "No agrícola"
    DESCONOCIDA = "desconocida", "Desconocida"


class MotivoAliasRol(models.TextChoices):
    FUSION = "fusion", "Fusión"
    SUBDIVISION = "subdivision", "Subdivisión"
    RECTIFICACION = "rectificacion", "Rectificación"


class Comuna(models.Model):
    """Unidad administrativa comunal con código INE y región para particionado futuro."""

    codigo_ine = models.CharField(max_length=10, unique=True)
    nombre = models.CharField(max_length=120)
    region_id = models.SmallIntegerField()
    geom = models.MultiPolygonField(srid=4326, null=True, blank=True, spatial_index=False)

    class Meta:
        db_table = "comuna"
        indexes = [
            models.Index(fields=["region_id"], name="idx_comuna_region"),
            GistIndex(fields=["geom"], name="idx_comuna_geom_gist"),
        ]

    def __str__(self) -> str:
        return f"{self.nombre} ({self.codigo_ine})"


class FuenteDato(models.Model):
    """Registro de linaje, licencia y hash por cada carga de datos."""

    nombre = models.CharField(max_length=150)
    origen = models.CharField(max_length=50)
    url = models.URLField(blank=True, default="")
    licencia = models.CharField(max_length=120)
    fecha_corte = models.DateField()
    fecha_descarga = models.DateTimeField(auto_now_add=True)
    hash_archivo = models.CharField(max_length=64, db_index=True)
    version_etl = models.CharField(max_length=40)
    filas_leidas = models.IntegerField(default=0)
    confianza_defecto = models.CharField(
        max_length=20,
        choices=NivelConfianza.choices,
        default=NivelConfianza.REFERENCIAL,
    )

    class Meta:
        db_table = "fuente_dato"
        constraints = [
            models.UniqueConstraint(
                fields=["nombre", "hash_archivo", "version_etl"],
                name="uq_fuente_nombre_hash_version",
            )
        ]

    def __str__(self) -> str:
        return f"{self.nombre} ({self.fecha_corte})"


class Parcela(models.Model):
    """Predio catastral en EPSG:4326 con clave natural (comuna, rol) y vigencia temporal."""

    rol = models.CharField(max_length=32)
    comuna = models.ForeignKey(Comuna, on_delete=models.PROTECT, related_name="parcelas")
    region_id = models.SmallIntegerField()
    geom = models.MultiPolygonField(srid=4326, spatial_index=False)
    superficie_m2 = models.DecimalField(max_digits=14, decimal_places=2)
    superficie_declarada = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    diferencia_superficie_pct = models.FloatField(null=True, blank=True)
    destino = models.CharField(max_length=80, blank=True, default="")
    serie = models.CharField(
        max_length=20,
        choices=SerieCatastral.choices,
        default=SerieCatastral.DESCONOCIDA,
    )
    avaluo_fiscal = models.BigIntegerField(null=True, blank=True)
    fuente = models.ForeignKey(FuenteDato, on_delete=models.PROTECT, related_name="parcelas")
    fecha_corte = models.DateField()
    confianza_geom = models.CharField(
        max_length=20,
        choices=NivelConfianza.choices,
        default=NivelConfianza.REFERENCIAL,
    )
    vigente_desde = models.DateField()
    vigente_hasta = models.DateField(null=True, blank=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "parcela"
        constraints = [
            models.UniqueConstraint(
                fields=["comuna", "rol", "vigente_desde"],
                name="uq_parcela_comuna_rol_vigencia",
            )
        ]
        indexes = [
            GistIndex(fields=["geom"], name="idx_parcela_geom_gist"),
            models.Index(fields=["region_id", "comuna", "rol"], name="idx_parcela_reg_com_rol"),
            models.Index(fields=["comuna", "rol"], name="idx_parcela_comuna_rol"),
        ]

    def __str__(self) -> str:
        return f"{self.comuna.codigo_ine}:{self.rol}"


class AliasRol(models.Model):
    """Trazabilidad de cambios de rol por fusiones, subdivisiones o rectificaciones."""

    comuna = models.ForeignKey(Comuna, on_delete=models.PROTECT, related_name="alias_roles")
    rol_anterior = models.CharField(max_length=32)
    rol_actual = models.CharField(max_length=32)
    motivo = models.CharField(max_length=30, choices=MotivoAliasRol.choices)
    fecha_cambio = models.DateField()
    fuente = models.ForeignKey(FuenteDato, on_delete=models.PROTECT, related_name="alias_roles")

    class Meta:
        db_table = "parcela_alias_rol"
        constraints = [
            models.UniqueConstraint(
                fields=["comuna", "rol_anterior", "rol_actual", "fecha_cambio"],
                name="uq_alias_rol_cambio",
            )
        ]
        indexes = [
            models.Index(fields=["comuna", "rol_anterior"], name="idx_alias_rol_anterior"),
            models.Index(fields=["comuna", "rol_actual"], name="idx_alias_rol_actual"),
        ]

    def __str__(self) -> str:
        return f"{self.rol_anterior} -> {self.rol_actual} ({self.motivo})"
