from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('cockfightManager', '0004_add_recording_odds_fields'),
    ]

    operations = [
        # 1. Create LiveSession model
        migrations.CreateModel(
            name='LiveSession',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(blank=True, max_length=150)),
                ('stream_key', models.CharField(max_length=64, unique=True)),
                ('is_active', models.BooleanField(default=False)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('ended_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('recordingFile', models.CharField(blank=True, max_length=255, null=True)),
                ('recordingStatus', models.CharField(
                    choices=[('none', 'No Recording'), ('recording', 'Recording'),
                             ('completed', 'Completed'), ('failed', 'Failed')],
                    default='none', max_length=10)),
                ('zone', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='cockfightManager.zone')),
            ],
            options={
                'verbose_name': 'Live Session',
                'verbose_name_plural': 'Live Sessions',
                'ordering': ['-created_at'],
            },
        ),

        # 2. Add match_mode to CockfightMatch
        migrations.AddField(
            model_name='cockfightmatch',
            name='match_mode',
            field=models.CharField(
                choices=[('manual', 'Manual (Legacy)'), ('prerecorded', 'Pre-Recorded Video'),
                         ('live_rtmp', 'Live RTMP Stream')],
                default='manual', max_length=15),
        ),

        # 3. Pre-recorded match fields
        migrations.AddField(
            model_name='cockfightmatch',
            name='matchVideo',
            field=models.FileField(blank=True, null=True, upload_to='cockfightMatchVideos/',
                                   help_text='Pre-recorded match video file'),
        ),
        migrations.AddField(
            model_name='cockfightmatch',
            name='scheduledStart',
            field=models.DateTimeField(blank=True, null=True,
                                       help_text='When the match video starts playing (betting closes)'),
        ),
        migrations.AddField(
            model_name='cockfightmatch',
            name='bettingOpensAt',
            field=models.DateTimeField(blank=True, null=True,
                                       help_text='When betting opens (auto-set to 5 min before scheduledStart)'),
        ),
        migrations.AddField(
            model_name='cockfightmatch',
            name='bettingDurationMinutes',
            field=models.PositiveSmallIntegerField(default=5,
                                                    help_text='How many minutes before start to open betting'),
        ),

        # 4. Live RTMP fields
        migrations.AddField(
            model_name='cockfightmatch',
            name='live_session',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    to='cockfightManager.livesession',
                                    help_text='Live session this match belongs to (for RTMP matches)'),
        ),
        migrations.AddField(
            model_name='cockfightmatch',
            name='match_number_in_session',
            field=models.PositiveSmallIntegerField(blank=True, null=True,
                                                    help_text='Match number within the live session'),
        ),

        # 5. Recording fields
        migrations.AddField(
            model_name='cockfightmatch',
            name='recordingFile',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='cockfightmatch',
            name='recordingStatus',
            field=models.CharField(
                choices=[('none', 'No Recording'), ('recording', 'Recording'),
                         ('completed', 'Completed'), ('failed', 'Failed')],
                default='none', max_length=10),
        ),
        migrations.AddField(
            model_name='cockfightmatch',
            name='screenshotFile',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),

        # 6. Odds snapshot + timing
        migrations.AddField(
            model_name='cockfightmatch',
            name='oddsSnapshot',
            field=models.TextField(blank=True, null=True,
                                   help_text='JSON snapshot of odds when match went live'),
        ),
        migrations.AddField(
            model_name='cockfightmatch',
            name='bettingOpenedAt',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='cockfightmatch',
            name='bettingClosedAt',
            field=models.DateTimeField(blank=True, null=True),
        ),

        # 7. Add indexes
        migrations.AddIndex(
            model_name='cockfightmatch',
            index=models.Index(fields=['match_mode'], name='cockfightma_match_m_idx'),
        ),
        migrations.AddIndex(
            model_name='cockfightmatch',
            index=models.Index(fields=['scheduledStart'], name='cockfightma_schedu_idx'),
        ),
    ]
