import django.contrib.gis.db.models.fields
import django.contrib.postgres.indexes
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.RunSQL(
            sql="CREATE EXTENSION IF NOT EXISTS postgis;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.CreateModel(
            name="Comuna",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("codigo_ine", models.CharField(max_length=10, unique=True)),
                ("nombre", models.CharField(max_length=120)),
                ("region_id", models.SmallIntegerField()),
                (
                    "geom",
                    django.contrib.gis.db.models.fields.MultiPolygonField(
                        blank=True, null=True, spatial_index=False, srid=4326
                    ),
                ),
            ],
            options={
                "db_table": "comuna",
            },
        ),
        migrations.CreateModel(
            name="FuenteDato",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("nombre", models.CharField(max_length=150)),
                ("origen", models.CharField(max_length=50)),
                ("url", models.URLField(blank=True, default="")),
                ("licencia", models.CharField(max_length=120)),
                ("fecha_corte", models.DateField()),
                ("fecha_descarga", models.DateTimeField(auto_now_add=True)),
                ("hash_archivo", models.CharField(db_index=True, max_length=64)),
                ("version_etl", models.CharField(max_length=40)),
                ("filas_leidas", models.IntegerField(default=0)),
                (
                    "confianza_defecto",
                    models.CharField(
                        choices=[
                            ("alta", "Alta"),
                            ("media", "Media"),
                            ("referencial", "Referencial"),
                        ],
                        default="referencial",
                        max_length=20,
                    ),
                ),
            ],
            options={
                "db_table": "fuente_dato",
            },
        ),
        migrations.CreateModel(
            name="Parcela",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("rol", models.CharField(max_length=32)),
                ("region_id", models.SmallIntegerField()),
                (
                    "geom",
                    django.contrib.gis.db.models.fields.MultiPolygonField(
                        spatial_index=False, srid=4326
                    ),
                ),
                ("superficie_m2", models.DecimalField(decimal_places=2, max_digits=14)),
                (
                    "superficie_declarada",
                    models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
                ),
                ("diferencia_superficie_pct", models.FloatField(blank=True, null=True)),
                ("destino", models.CharField(blank=True, default="", max_length=80)),
                (
                    "serie",
                    models.CharField(
                        choices=[
                            ("agricola", "Agrícola"),
                            ("no_agricola", "No agrícola"),
                            ("desconocida", "Desconocida"),
                        ],
                        default="desconocida",
                        max_length=20,
                    ),
                ),
                ("avaluo_fiscal", models.BigIntegerField(blank=True, null=True)),
                ("fecha_corte", models.DateField()),
                (
                    "confianza_geom",
                    models.CharField(
                        choices=[
                            ("alta", "Alta"),
                            ("media", "Media"),
                            ("referencial", "Referencial"),
                        ],
                        default="referencial",
                        max_length=20,
                    ),
                ),
                ("vigente_desde", models.DateField()),
                ("vigente_hasta", models.DateField(blank=True, null=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                (
                    "comuna",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="parcelas",
                        to="territorio.comuna",
                    ),
                ),
                (
                    "fuente",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="parcelas",
                        to="territorio.fuentedato",
                    ),
                ),
            ],
            options={
                "db_table": "parcela",
            },
        ),
        migrations.CreateModel(
            name="AliasRol",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("rol_anterior", models.CharField(max_length=32)),
                ("rol_actual", models.CharField(max_length=32)),
                (
                    "motivo",
                    models.CharField(
                        choices=[
                            ("fusion", "Fusión"),
                            ("subdivision", "Subdivisión"),
                            ("rectificacion", "Rectificación"),
                        ],
                        max_length=30,
                    ),
                ),
                ("fecha_cambio", models.DateField()),
                (
                    "comuna",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="alias_roles",
                        to="territorio.comuna",
                    ),
                ),
                (
                    "fuente",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="alias_roles",
                        to="territorio.fuentedato",
                    ),
                ),
            ],
            options={
                "db_table": "parcela_alias_rol",
            },
        ),
        migrations.AddIndex(
            model_name="comuna",
            index=models.Index(fields=["region_id"], name="idx_comuna_region"),
        ),
        migrations.AddIndex(
            model_name="comuna",
            index=django.contrib.postgres.indexes.GistIndex(
                fields=["geom"], name="idx_comuna_geom_gist"
            ),
        ),
        migrations.AddConstraint(
            model_name="fuentedato",
            constraint=models.UniqueConstraint(
                fields=("nombre", "hash_archivo", "version_etl"),
                name="uq_fuente_nombre_hash_version",
            ),
        ),
        migrations.AddIndex(
            model_name="parcela",
            index=django.contrib.postgres.indexes.GistIndex(
                fields=["geom"], name="idx_parcela_geom_gist"
            ),
        ),
        migrations.AddIndex(
            model_name="parcela",
            index=models.Index(
                fields=["region_id", "comuna", "rol"], name="idx_parcela_reg_com_rol"
            ),
        ),
        migrations.AddIndex(
            model_name="parcela",
            index=models.Index(fields=["comuna", "rol"], name="idx_parcela_comuna_rol"),
        ),
        migrations.AddConstraint(
            model_name="parcela",
            constraint=models.UniqueConstraint(
                fields=("comuna", "rol", "vigente_desde"),
                name="uq_parcela_comuna_rol_vigencia",
            ),
        ),
        migrations.AddIndex(
            model_name="aliasrol",
            index=models.Index(fields=["comuna", "rol_anterior"], name="idx_alias_rol_anterior"),
        ),
        migrations.AddIndex(
            model_name="aliasrol",
            index=models.Index(fields=["comuna", "rol_actual"], name="idx_alias_rol_actual"),
        ),
        migrations.AddConstraint(
            model_name="aliasrol",
            constraint=models.UniqueConstraint(
                fields=("comuna", "rol_anterior", "rol_actual", "fecha_cambio"),
                name="uq_alias_rol_cambio",
            ),
        ),
    ]
