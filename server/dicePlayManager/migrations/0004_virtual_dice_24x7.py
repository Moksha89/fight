from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('dicePlayManager', '0003_virtual_dice_mode'),
    ]

    operations = [
        # Board: update default for virtual_betting_seconds, add new timing fields
        migrations.AlterField(
            model_name='board',
            name='virtual_betting_seconds',
            field=models.PositiveIntegerField(default=120, help_text='Seconds betting stays open for virtual rounds (default 2 min)'),
        ),
        migrations.AddField(
            model_name='board',
            name='virtual_shuffle_seconds',
            field=models.PositiveIntegerField(default=30, help_text='Seconds for dice shuffle animation phase'),
        ),
        migrations.AddField(
            model_name='board',
            name='virtual_result_seconds',
            field=models.PositiveIntegerField(default=12, help_text='Seconds to display result before next round'),
        ),
        # DicePlayMatch: add game_hash, daily numbering, phase tracking
        migrations.AddField(
            model_name='diceplaymatch',
            name='game_hash',
            field=models.CharField(blank=True, db_index=True, help_text='Unique SHA-256 hash for game verification', max_length=64, null=True),
        ),
        migrations.AddField(
            model_name='diceplaymatch',
            name='daily_match_number',
            field=models.PositiveIntegerField(default=0, help_text='Match number for the day (resets at 12:00 AM IST)'),
        ),
        migrations.AddField(
            model_name='diceplaymatch',
            name='match_date',
            field=models.DateField(blank=True, db_index=True, help_text='IST date this match belongs to', null=True),
        ),
        migrations.AddField(
            model_name='diceplaymatch',
            name='virtual_phase',
            field=models.CharField(choices=[('betting', 'Betting Open'), ('shuffling', 'Dice Shuffling'), ('result', 'Result Display'), ('done', 'Completed')], default='betting', help_text='Current phase of virtual match lifecycle', max_length=10),
        ),
        migrations.AddField(
            model_name='diceplaymatch',
            name='phase_started_at',
            field=models.DateTimeField(blank=True, help_text='When the current phase started', null=True),
        ),
        migrations.AddIndex(
            model_name='diceplaymatch',
            index=models.Index(fields=['match_date', 'daily_match_number'], name='diceplaymana_match_d_idx'),
        ),
    ]
