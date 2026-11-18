import django.contrib.gis.db.models.fields
import django.contrib.postgres.indexes
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("territorio", "0004_estado_normativa_riesgo_relieve"),
    ]

    operations = [
        migrations.CreateModel(
            name="Transaccion",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("codigo_f2890", models.CharField(max_length=64)),
                ("rol", models.CharField(max_length=32)),
                ("fecha", models.DateField()),
                ("monto_clp", models.BigIntegerField()),
                (
                    "superficie_m2",
                    models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
                ),
                (
                    "precio_m2_clp",
                    models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
                ),
                ("destino", models.CharField(blank=True, db_default="", default="", max_length=80)),
                ("h3_res8", models.CharField(blank=True, db_default="", default="", max_length=20)),
                ("fecha_corte", models.DateField()),
                (
                    "confianza",
                    models.CharField(
                        choices=[
                            ("alta", "Alta"),
                            ("media", "Media"),
                            ("referencial", "Referencial"),
                        ],
                        default="media",
                        max_length=20,
                    ),
                ),
                (
                    "comuna",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="transacciones",
                        to="territorio.comuna",
                    ),
                ),
                (
                    "fuente",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="transacciones",
                        to="territorio.fuentedato",
                    ),
                ),
                (
                    "parcela",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="transacciones",
                        to="territorio.parcela",
                    ),
                ),
            ],
            options={
                "db_table": "transaccion",
            },
        ),
        migrations.CreateModel(
            name="CeldaH3",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("h3_index", models.CharField(max_length=20, unique=True)),
                ("resolucion", models.SmallIntegerField()),
                (
                    "geom",
                    django.contrib.gis.db.models.fields.PolygonField(
                        spatial_index=False, srid=4326
                    ),
                ),
                ("cantidad_transacciones", models.IntegerField(db_default=0, default=0)),
                (
                    "precio_m2_mediana_clp",
                    models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
                ),
                (
                    "precio_m2_promedio_clp",
                    models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
                ),
                ("ratio_precio_avaluo", models.FloatField(blank=True, null=True)),
                ("tendencia_pct", models.FloatField(blank=True, null=True)),
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
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                (
                    "comuna",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="celdas_h3",
                        to="territorio.comuna",
                    ),
                ),
                (
                    "fuente",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="celdas_h3",
                        to="territorio.fuentedato",
                    ),
                ),
            ],
            options={
                "db_table": "celda_h3",
            },
        ),
        migrations.AddIndex(
            model_name="transaccion",
            index=django.contrib.postgres.indexes.BrinIndex(
                fields=["fecha"], name="idx_transaccion_fecha_brin"
            ),
        ),
        migrations.AddIndex(
            model_name="transaccion",
            index=models.Index(
                fields=["comuna", "rol", "fecha"], name="idx_trans_com_rol_fecha"
            ),
        ),
        migrations.AddIndex(
            model_name="transaccion",
            index=models.Index(fields=["h3_res8", "fecha"], name="idx_trans_h3_fecha"),
        ),
        migrations.AddConstraint(
            model_name="transaccion",
            constraint=models.UniqueConstraint(
                fields=("comuna", "codigo_f2890"), name="uq_transaccion_comuna_f2890"
            ),
        ),
        migrations.AddIndex(
            model_name="celdah3",
            index=django.contrib.postgres.indexes.GistIndex(
                fields=["geom"], name="idx_celda_h3_geom_gist"
            ),
        ),
        migrations.AddIndex(
            model_name="celdah3",
            index=models.Index(
                fields=["resolucion", "comuna"], name="idx_celda_h3_res_comuna"
            ),
        ),
    ]
