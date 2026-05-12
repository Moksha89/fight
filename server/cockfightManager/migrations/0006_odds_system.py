from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cockfightManager', '0005_manual_match_enhancements'),
    ]

    operations = [
        migrations.CreateModel(
            name='OddsConfig',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('odds_system', models.CharField(
                    max_length=20,
                    choices=[
                        ('manual', 'Manual Odds'),
                        ('dynamic', 'Dynamic Win-Rate Odds'),
                        ('pool', 'Pool-Based (Parimutuel) Odds'),
                        ('rebalance', 'Fixed Rebalance Odds'),
                    ],
                    default='manual',
                    help_text='Which odds system is currently active for China Market (Auto) matches.'
                )),
                # Manual settings (used by manual mode)
                ('manual_meron_min', models.DecimalField(max_digits=5, decimal_places=2, default=0.50)),
                ('manual_meron_max', models.DecimalField(max_digits=5, decimal_places=2, default=0.95)),
                ('manual_wala_min', models.DecimalField(max_digits=5, decimal_places=2, default=0.50)),
                ('manual_wala_max', models.DecimalField(max_digits=5, decimal_places=2, default=0.95)),
                ('manual_draw_min', models.DecimalField(max_digits=5, decimal_places=2, default=3.00)),
                ('manual_draw_max', models.DecimalField(max_digits=5, decimal_places=2, default=10.00)),

                # Dynamic settings
                ('dynamic_lookback', models.PositiveIntegerField(default=50, help_text='Number of past matches to analyze for win rates')),
                ('dynamic_house_edge', models.DecimalField(max_digits=4, decimal_places=2, default=0.05, help_text='House edge (e.g. 0.05 = 5%)')),
                ('dynamic_min_ratio', models.DecimalField(max_digits=5, decimal_places=2, default=0.50, help_text='Floor for Meron/Wala ratios')),
                ('dynamic_max_ratio', models.DecimalField(max_digits=5, decimal_places=2, default=1.50, help_text='Cap for Meron/Wala ratios')),
                ('dynamic_draw_min', models.DecimalField(max_digits=5, decimal_places=2, default=3.00)),
                ('dynamic_draw_max', models.DecimalField(max_digits=5, decimal_places=2, default=10.00)),

                # Pool-based settings
                ('pool_house_cut', models.DecimalField(max_digits=4, decimal_places=2, default=0.05, help_text='House cut from total pool (e.g. 0.05 = 5%)')),
                ('pool_draw_min', models.DecimalField(max_digits=5, decimal_places=2, default=3.00)),
                ('pool_draw_max', models.DecimalField(max_digits=5, decimal_places=2, default=10.00)),

                # Rebalance settings
                ('rebalance_interval', models.PositiveIntegerField(default=10, help_text='Recalculate odds every N matches')),
                ('rebalance_lookback', models.PositiveIntegerField(default=20, help_text='Number of matches to look back')),
                ('rebalance_house_edge', models.DecimalField(max_digits=4, decimal_places=2, default=0.05, help_text='Target house edge')),
                ('rebalance_min_ratio', models.DecimalField(max_digits=5, decimal_places=2, default=0.50)),
                ('rebalance_max_ratio', models.DecimalField(max_digits=5, decimal_places=2, default=1.20)),
                ('rebalance_draw_min', models.DecimalField(max_digits=5, decimal_places=2, default=3.00)),
                ('rebalance_draw_max', models.DecimalField(max_digits=5, decimal_places=2, default=10.00)),

                # Computed odds (used by all auto systems - updated by tasks)
                ('current_meron_min', models.DecimalField(max_digits=5, decimal_places=2, default=0.50)),
                ('current_meron_max', models.DecimalField(max_digits=5, decimal_places=2, default=0.95)),
                ('current_wala_min', models.DecimalField(max_digits=5, decimal_places=2, default=0.50)),
                ('current_wala_max', models.DecimalField(max_digits=5, decimal_places=2, default=0.95)),
                ('current_draw_min', models.DecimalField(max_digits=5, decimal_places=2, default=3.00)),
                ('current_draw_max', models.DecimalField(max_digits=5, decimal_places=2, default=10.00)),

                # Stats
                ('last_recalculated', models.DateTimeField(null=True, blank=True)),
                ('matches_since_rebalance', models.PositiveIntegerField(default=0)),
                ('meron_win_pct', models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text='Current Meron win %')),
                ('wala_win_pct', models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text='Current Wala win %')),
                ('draw_pct', models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text='Current Draw %')),

                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Odds Configuration',
                'verbose_name_plural': '5. Odds Configuration',
            },
        ),
    ]
