"""Add provably fair fields, extended bet statuses, and game engine state tracking."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dicePlayManager', '0004_virtual_dice_24x7'),
    ]

    operations = [
        # Extend virtual_phase to support all game states
        migrations.AlterField(
            model_name='diceplaymatch',
            name='virtual_phase',
            field=models.CharField(
                choices=[
                    ('created', 'Created'),
                    ('betting', 'Betting Open'),
                    ('betting_closed', 'Betting Closed'),
                    ('shuffling', 'Dice Rolling'),
                    ('result', 'Result Reveal'),
                    ('settlement', 'Settlement'),
                    ('done', 'Completed'),
                    ('cancelled', 'Cancelled'),
                ],
                default='betting',
                help_text='Current phase of virtual match lifecycle',
                max_length=15,
            ),
        ),
        # Provably fair fields
        migrations.AddField(
            model_name='diceplaymatch',
            name='server_seed',
            field=models.CharField(blank=True, help_text='Secret server seed (revealed after round)', max_length=64, null=True),
        ),
        migrations.AddField(
            model_name='diceplaymatch',
            name='client_seed',
            field=models.CharField(blank=True, help_text='Public client seed', max_length=32, null=True),
        ),
        migrations.AddField(
            model_name='diceplaymatch',
            name='commitment_hash',
            field=models.CharField(blank=True, help_text='SHA256(server_seed) shown before round', max_length=64, null=True),
        ),
        migrations.AddField(
            model_name='diceplaymatch',
            name='nonce',
            field=models.PositiveIntegerField(default=0, help_text='Round nonce for provably fair'),
        ),
        migrations.AddField(
            model_name='diceplaymatch',
            name='server_seed_revealed',
            field=models.BooleanField(default=False, help_text='Whether server seed has been revealed'),
        ),
        # Settlement tracking
        migrations.AddField(
            model_name='diceplaymatch',
            name='settlement_id',
            field=models.CharField(blank=True, help_text='Unique settlement transaction ID', max_length=30, null=True),
        ),
        migrations.AddField(
            model_name='diceplaymatch',
            name='settled_at',
            field=models.DateTimeField(blank=True, help_text='When settlement completed', null=True),
        ),
        # Bet model extensions
        migrations.AddField(
            model_name='diceplaymatchbet',
            name='payout_amount',
            field=models.PositiveIntegerField(default=0, help_text='Actual payout credited'),
        ),
        migrations.AddField(
            model_name='diceplaymatchbet',
            name='settlement_id',
            field=models.CharField(blank=True, help_text='Settlement transaction ID', max_length=30, null=True),
        ),
        migrations.AlterField(
            model_name='diceplaymatchbet',
            name='matchWinStatus',
            field=models.PositiveSmallIntegerField(
                choices=[
                    (0, 'Pending'),
                    (1, 'Won'),
                    (2, 'Lost'),
                    (3, 'Accepted'),
                    (4, 'Cancelled'),
                    (5, 'Refunded'),
                    (6, 'Rejected'),
                ],
                db_index=True,
                default=0,
            ),
        ),
    ]
