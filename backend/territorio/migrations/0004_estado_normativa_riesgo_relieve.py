import django.contrib.gis.db.models.fields
import django.contrib.postgres.indexes
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("territorio", "0003_martin_mvt_function"),
    ]

    operations = [
        migrations.AddField(
            model_name="parcela",
            name="elevacion_media_m",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="parcela",
            name="pendiente_media_pct",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="parcela",
            name="exposicion_aspecto",
            field=models.CharField(blank=True, db_default="", default="", max_length=16),
        ),
        migrations.AddField(
            model_name="parcela",
            name="fuente_relieve",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="parcelas_relieve",
                to="territorio.fuentedato",
            ),
        ),
        migrations.AddField(
            model_name="parcela",
            name="fecha_corte_relieve",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="parcela",
            name="confianza_relieve",
            field=models.CharField(
                blank=True,
                choices=[("alta", "Alta"), ("media", "Media"), ("referencial", "Referencial")],
                db_default="",
                default="",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="TerrenoFiscal",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("codigo_bn", models.CharField(max_length=64)),
                ("institucion", models.CharField(max_length=150)),
                ("tipo", models.CharField(max_length=80)),
                (
                    "geom",
                    django.contrib.gis.db.models.fields.MultiPolygonField(
                        spatial_index=False, srid=4326
                    ),
                ),
                ("superficie_m2", models.DecimalField(decimal_places=2, max_digits=14)),
                ("fecha_corte", models.DateField()),
                (
                    "confianza",
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
                (
                    "comuna",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="terrenos_fiscales",
                        to="territorio.comuna",
                    ),
                ),
                (
                    "fuente",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="terrenos_fiscales",
                        to="territorio.fuentedato",
                    ),
                ),
            ],
            options={
                "db_table": "terreno_fiscal",
            },
        ),
        migrations.CreateModel(
            name="CapaNormativa",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("instrumento", models.CharField(max_length=80)),
                ("codigo_zona", models.CharField(max_length=40)),
                ("codigo_poligono", models.CharField(default="", max_length=64)),
                ("nombre_zona", models.CharField(blank=True, default="", max_length=150)),
                ("usos_permitidos", models.JSONField(default=list)),
                ("parametros_urbanisticos", models.JSONField(default=dict)),
                (
                    "geom",
                    django.contrib.gis.db.models.fields.MultiPolygonField(
                        spatial_index=False, srid=4326
                    ),
                ),
                ("fecha_corte", models.DateField()),
                (
                    "confianza",
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
                (
                    "comuna",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="capas_normativas",
                        to="territorio.comuna",
                    ),
                ),
                (
                    "fuente",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="capas_normativas",
                        to="territorio.fuentedato",
                    ),
                ),
            ],
            options={
                "db_table": "capa_normativa",
            },
        ),
        migrations.CreateModel(
            name="CapaRiesgo",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("codigo_evento", models.CharField(max_length=64)),
                (
                    "tipo",
                    models.CharField(
                        choices=[
                            ("inundacion", "Inundación"),
                            ("tsunami", "Tsunami"),
                            ("remocion_masa", "Remoción en masa"),
                            ("incendio", "Incendio forestal"),
                            ("sismicidad", "Sismicidad"),
                            ("otro", "Otro"),
                        ],
                        max_length=30,
                    ),
                ),
                (
                    "nivel",
                    models.CharField(
                        choices=[
                            ("alto", "Alto"),
                            ("medio", "Medio"),
                            ("bajo", "Bajo"),
                            ("restriccion", "Área de restricción"),
                        ],
                        max_length=20,
                    ),
                ),
                ("descripcion", models.CharField(blank=True, default="", max_length=240)),
                (
                    "geom",
                    django.contrib.gis.db.models.fields.MultiPolygonField(
                        spatial_index=False, srid=4326
                    ),
                ),
                ("fecha_corte", models.DateField()),
                (
                    "confianza",
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
                (
                    "fuente",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="capas_riesgo",
                        to="territorio.fuentedato",
                    ),
                ),
            ],
            options={
                "db_table": "capa_riesgo",
            },
        ),
        migrations.AddIndex(
            model_name="terrenofiscal",
            index=django.contrib.postgres.indexes.GistIndex(
                fields=["geom"], name="idx_fiscal_geom_gist"
            ),
        ),
        migrations.AddIndex(
            model_name="terrenofiscal",
            index=models.Index(fields=["comuna", "tipo"], name="idx_fiscal_comuna_tipo"),
        ),
        migrations.AddConstraint(
            model_name="terrenofiscal",
            constraint=models.UniqueConstraint(
                fields=("codigo_bn", "vigente_desde"), name="uq_fiscal_codigo_vigencia"
            ),
        ),
        migrations.AddIndex(
            model_name="capanormativa",
            index=django.contrib.postgres.indexes.GistIndex(
                fields=["geom"], name="idx_normativa_geom_gist"
            ),
        ),
        migrations.AddIndex(
            model_name="capanormativa",
            index=models.Index(
                fields=["comuna", "instrumento", "codigo_zona"],
                name="idx_norm_com_inst_zona",
            ),
        ),
        migrations.AddConstraint(
            model_name="capanormativa",
            constraint=models.UniqueConstraint(
                fields=("comuna", "instrumento", "codigo_zona", "codigo_poligono", "vigente_desde"),
                name="uq_normativa_zona_vigencia",
            ),
        ),
        migrations.AddIndex(
            model_name="capariesgo",
            index=django.contrib.postgres.indexes.GistIndex(
                fields=["geom"], name="idx_riesgo_geom_gist"
            ),
        ),
        migrations.AddIndex(
            model_name="capariesgo",
            index=models.Index(fields=["tipo", "nivel"], name="idx_riesgo_tipo_nivel"),
        ),
        migrations.AddConstraint(
            model_name="capariesgo",
            constraint=models.UniqueConstraint(
                fields=("tipo", "codigo_evento"), name="uq_riesgo_tipo_codigo"
            ),
        ),
    ]
