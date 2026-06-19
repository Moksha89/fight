"""Add performance index to CockfightAutoMatch for recent results query."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cockfightManager", "0006_odds_system"),
    ]

    operations = [
        # CockfightAutoMatch: processed + id DESC
        # Improves recent processed results query (reverse ID scan)
        migrations.AddIndex(
            model_name="cockfightautomatch",
            index=models.Index(
                fields=["processed", "-id"],
                name="cf_auto_processed_id_idx",
            ),
        ),
    ]
