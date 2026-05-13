"""Add performance index to DicePlayMatch for recent results query."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dicePlayManager", "0005_provably_fair_game_engine"),
    ]

    operations = [
        # DicePlayMatch: match_type + isWinnerDeclared + updated_at DESC
        # Eliminates full table scan on recent results query (was scanning 1144 rows)
        migrations.AddIndex(
            model_name="diceplaymatch",
            index=models.Index(
                fields=["match_type", "isWinnerDeclared", "-updated_at"],
                name="dice_match_type_winner_idx",
            ),
        ),
    ]
