from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("territorio", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE EXTENSION IF NOT EXISTS pg_trgm;
            CREATE INDEX IF NOT EXISTS idx_parcela_rol_trgm
                ON parcela USING gin (rol gin_trgm_ops);
            CREATE INDEX IF NOT EXISTS idx_alias_rol_ant_trgm
                ON parcela_alias_rol USING gin (rol_anterior gin_trgm_ops);
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS idx_alias_rol_ant_trgm;
            DROP INDEX IF EXISTS idx_parcela_rol_trgm;
            """,
        ),
    ]
