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


class TipoRiesgo(models.TextChoices):
    INUNDACION = "inundacion", "Inundación"
    TSUNAMI = "tsunami", "Tsunami"
    REMOCION_MASA = "remocion_masa", "Remoción en masa"
    INCENDIO = "incendio", "Incendio forestal"
    SISMICIDAD = "sismicidad", "Sismicidad"
    OTRO = "otro", "Otro"


class NivelRiesgo(models.TextChoices):
    ALTO = "alto", "Alto"
    MEDIO = "medio", "Medio"
    BAJO = "bajo", "Bajo"
    RESTRICCION = "restriccion", "Área de restricción"


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
    elevacion_media_m = models.FloatField(null=True, blank=True)
    pendiente_media_pct = models.FloatField(null=True, blank=True)
    exposicion_aspecto = models.CharField(max_length=16, blank=True, default="", db_default="")
    fuente_relieve = models.ForeignKey(
        FuenteDato,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="parcelas_relieve",
    )
    fecha_corte_relieve = models.DateField(null=True, blank=True)
    confianza_relieve = models.CharField(
        max_length=20,
        choices=NivelConfianza.choices,
        blank=True,
        default="",
        db_default="",
    )
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


class TerrenoFiscal(models.Model):
    """Catastro de propiedad fiscal (Bienes Nacionales / SERVIU / Fisco) en EPSG:4326."""

    codigo_bn = models.CharField(max_length=64)
    comuna = models.ForeignKey(
        Comuna,
        on_delete=models.PROTECT,
        related_name="terrenos_fiscales",
        null=True,
        blank=True,
    )
    institucion = models.CharField(max_length=150)
    tipo = models.CharField(max_length=80)
    geom = models.MultiPolygonField(srid=4326, spatial_index=False)
    superficie_m2 = models.DecimalField(max_digits=14, decimal_places=2)
    fuente = models.ForeignKey(
        FuenteDato, on_delete=models.PROTECT, related_name="terrenos_fiscales"
    )
    fecha_corte = models.DateField()
    confianza = models.CharField(
        max_length=20,
        choices=NivelConfianza.choices,
        default=NivelConfianza.REFERENCIAL,
    )
    vigente_desde = models.DateField()
    vigente_hasta = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "terreno_fiscal"
        constraints = [
            models.UniqueConstraint(
                fields=["codigo_bn", "vigente_desde"],
                name="uq_fiscal_codigo_vigencia",
            )
        ]
        indexes = [
            GistIndex(fields=["geom"], name="idx_fiscal_geom_gist"),
            models.Index(fields=["comuna", "tipo"], name="idx_fiscal_comuna_tipo"),
        ]

    def __str__(self) -> str:
        return f"{self.codigo_bn} ({self.institucion})"


class CapaNormativa(models.Model):
    """Zonificación y parámetros urbanísticos (PRC / PRI / PRMS) en EPSG:4326."""

    comuna = models.ForeignKey(
        Comuna, on_delete=models.PROTECT, related_name="capas_normativas"
    )
    instrumento = models.CharField(max_length=80)
    codigo_zona = models.CharField(max_length=40)
    codigo_poligono = models.CharField(max_length=64, default="")
    nombre_zona = models.CharField(max_length=150, blank=True, default="")
    usos_permitidos = models.JSONField(default=list)
    parametros_urbanisticos = models.JSONField(default=dict)
    geom = models.MultiPolygonField(srid=4326, spatial_index=False)
    fuente = models.ForeignKey(
        FuenteDato, on_delete=models.PROTECT, related_name="capas_normativas"
    )
    fecha_corte = models.DateField()
    confianza = models.CharField(
        max_length=20,
        choices=NivelConfianza.choices,
        default=NivelConfianza.REFERENCIAL,
    )
    vigente_desde = models.DateField()
    vigente_hasta = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "capa_normativa"
        constraints = [
            models.UniqueConstraint(
                fields=["comuna", "instrumento", "codigo_zona", "codigo_poligono", "vigente_desde"],
                name="uq_normativa_zona_vigencia",
            )
        ]
        indexes = [
            GistIndex(fields=["geom"], name="idx_normativa_geom_gist"),
            models.Index(
                fields=["comuna", "instrumento", "codigo_zona"],
                name="idx_norm_com_inst_zona",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.instrumento} - {self.codigo_zona}"


class CapaRiesgo(models.Model):
    """Capas de amenazas naturales y restricciones ambientales en EPSG:4326."""

    codigo_evento = models.CharField(max_length=64)
    tipo = models.CharField(max_length=30, choices=TipoRiesgo.choices)
    nivel = models.CharField(max_length=20, choices=NivelRiesgo.choices)
    descripcion = models.CharField(max_length=240, blank=True, default="")
    geom = models.MultiPolygonField(srid=4326, spatial_index=False)
    fuente = models.ForeignKey(FuenteDato, on_delete=models.PROTECT, related_name="capas_riesgo")
    fecha_corte = models.DateField()
    confianza = models.CharField(
        max_length=20,
        choices=NivelConfianza.choices,
        default=NivelConfianza.REFERENCIAL,
    )

    class Meta:
        db_table = "capa_riesgo"
        constraints = [
            models.UniqueConstraint(
                fields=["tipo", "codigo_evento"],
                name="uq_riesgo_tipo_codigo",
            )
        ]
        indexes = [
            GistIndex(fields=["geom"], name="idx_riesgo_geom_gist"),
            models.Index(fields=["tipo", "nivel"], name="idx_riesgo_tipo_nivel"),
        ]

    def __str__(self) -> str:
        return f"{self.tipo} ({self.nivel})"
