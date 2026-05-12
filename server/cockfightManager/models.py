from decimal import Decimal
import hashlib
import uuid
from django.db import models
from utility.storageClasses import AzurePublicStorage
from django.conf import settings
from django.core.exceptions import ValidationError


class Zone(models.Model):
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name}"

    class Meta:
        verbose_name = "Zone"
        verbose_name_plural = "1. Zones"
        indexes = [
            models.Index(fields=['is_active']),
        ]
        ordering = ['name']


class LiveSession(models.Model):
    """Groups multiple live RTMP matches in one OBS streaming session."""
    zone = models.ForeignKey(Zone, on_delete=models.PROTECT)
    title = models.CharField(max_length=150, blank=True)
    stream_key = models.CharField(max_length=64, unique=True)
    is_active = models.BooleanField(default=False)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Recording
    recordingFile = models.CharField(max_length=255, null=True, blank=True)
    RECORDING_STATUS_CHOICES = [
        ('none', 'No Recording'),
        ('recording', 'Recording'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    recordingStatus = models.CharField(
        max_length=10, choices=RECORDING_STATUS_CHOICES, default='none')

    def __str__(self):
        return f"Session: {self.title or self.stream_key[:8]}"

    @property
    def rtmp_url(self):
        return f"rtmp://155.117.46.249:1935/live/{self.stream_key}"

    @property
    def hls_url(self):
        return f"http://155.117.46.249:8088/hls/{self.stream_key}.m3u8"

    def save(self, *args, **kwargs):
        if not self.stream_key:
            self.stream_key = uuid.uuid4().hex[:16]
        if not self.title:
            self.title = f"Live Session - {self.zone.name}"
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Live Session"
        verbose_name_plural = "Live Sessions"
        ordering = ['-created_at']


class CockfightMatch(models.Model):
    MATCH_MODE_CHOICES = [
        ('manual', 'Manual (Legacy)'),
        ('prerecorded', 'Pre-Recorded Video'),
        ('live_rtmp', 'Live RTMP Stream'),
    ]

    zone = models.ForeignKey(Zone, on_delete=models.PROTECT)
    title = models.CharField(max_length=100)
    match_mode = models.CharField(
        max_length=15, choices=MATCH_MODE_CHOICES, default='manual')
    liveDate = models.DateTimeField(null=True, blank=True)
    isLive = models.BooleanField(default=False)
    isBettingEnabled = models.BooleanField(default=False)
    youtubeLiveLink = models.CharField(max_length=100, null=True, blank=True)
    promoVideo = models.FileField(
        storage=AzurePublicStorage(), upload_to='cockfightMatchPromo/', null=True, blank=True)
    teamAName = models.CharField(max_length=15, default='Meron')
    teamBName = models.CharField(max_length=15, default='Wala')
    teamAIcon = models.FileField(
        storage=AzurePublicStorage(), upload_to='cockfightMatchIcons/', null=True, blank=True)
    teamBIcon = models.FileField(
        storage=AzurePublicStorage(), upload_to='cockfightMatchIcons/', null=True, blank=True)
    minThresholdTeamA = models.DecimalField(
        max_digits=3, decimal_places=2, null=True, blank=True, default=Decimal('0.75'))
    maxThresholdTeamA = models.DecimalField(
        max_digits=3, decimal_places=2, null=True, blank=True, default=Decimal('0.85'))
    minThresholdTeamB = models.DecimalField(
        max_digits=3, decimal_places=2, null=True, blank=True, default=Decimal('0.75'))
    maxThresholdTeamB = models.DecimalField(
        max_digits=3, decimal_places=2, null=True, blank=True, default=Decimal('0.85'))
    minThresholdTeamDraw = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True, default=Decimal('3.00'))
    maxThresholdTeamDraw = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True, default=Decimal('5.00'))
    winTeam = models.PositiveSmallIntegerField(default=0, blank=True)
    isWinnerDeclared = models.BooleanField(default=False)
    processed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # --- New fields for Pre-Recorded matches ---
    matchVideo = models.FileField(
        storage=AzurePublicStorage(), upload_to='cockfightMatchVideos/',
        null=True, blank=True, help_text="Pre-recorded match video file")
    scheduledStart = models.DateTimeField(
        null=True, blank=True,
        help_text="When the match video starts playing (betting closes)")
    bettingOpensAt = models.DateTimeField(
        null=True, blank=True,
        help_text="When betting opens (auto-set to 5 min before scheduledStart)")
    bettingDurationMinutes = models.PositiveSmallIntegerField(
        default=5, help_text="How many minutes before start to open betting")

    # --- New fields for Live RTMP matches ---
    live_session = models.ForeignKey(
        LiveSession, on_delete=models.SET_NULL, null=True, blank=True,
        help_text="Live session this match belongs to (for RTMP matches)")
    match_number_in_session = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Match number within the live session (like China Market)")

    # --- Recording & Screenshot (for both types) ---
    recordingFile = models.CharField(max_length=255, null=True, blank=True)
    RECORDING_STATUS_CHOICES = [
        ('none', 'No Recording'),
        ('recording', 'Recording'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    recordingStatus = models.CharField(
        max_length=10, choices=RECORDING_STATUS_CHOICES, default='none')
    screenshotFile = models.CharField(max_length=255, null=True, blank=True)

    # --- Odds Snapshot ---
    oddsSnapshot = models.TextField(
        null=True, blank=True,
        help_text="JSON snapshot of odds when match went live")

    # --- Timing ---
    bettingOpenedAt = models.DateTimeField(null=True, blank=True)
    bettingClosedAt = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Cockfight Match"
        verbose_name_plural = "2. Cockfight Matches"
        ordering = ['liveDate', '-created_at']
        indexes = [
            models.Index(fields=['zone', 'liveDate']),
            models.Index(fields=['isLive']),
            models.Index(fields=['isWinnerDeclared']),
            models.Index(fields=['processed']),
            models.Index(fields=['winTeam']),
            models.Index(fields=['match_mode']),
            models.Index(fields=['scheduledStart']),
        ]

    def __str__(self):
        mode_label = dict(self.MATCH_MODE_CHOICES).get(self.match_mode, '')
        return f"[{mode_label}] {self.title}"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_isBettingEnabled = self.isBettingEnabled
        self._original_winTeam = self.winTeam

    def clean(self):
        # 1. Only one active live match per zone (for manual and live_rtmp modes)
        if self.isLive and not self.isWinnerDeclared:
            conflicts = CockfightMatch.objects.filter(
                zone=self.zone,
                isLive=True,
                isWinnerDeclared=False
            ).exclude(id=self.id)
            if conflicts.exists():
                raise ValidationError(
                    "Only one live, undecided match is allowed per zone.")

        # 2. isBettingEnabled -> true requires isLive = true
        if not self._state.adding and self.isBettingEnabled and not self._original_isBettingEnabled:
            if not self.isLive:
                raise ValidationError(
                    "Betting can only be enabled on a live match.")

        # 3. winTeam from 0 -> 1-4 requires isLive = true
        if not self._state.adding and self._original_winTeam == 0 and self.winTeam in [1, 2, 3, 4]:
            if not self.isLive:
                raise ValidationError(
                    "Winner cannot be declared on a non-live match.")

        # 4. Pre-recorded match needs video and schedule
        if self.match_mode == 'prerecorded':
            if not self.matchVideo and self._state.adding:
                pass  # allow saving without video initially
            if self.scheduledStart and not self.bettingOpensAt:
                from django.utils import timezone
                from datetime import timedelta
                self.bettingOpensAt = self.scheduledStart - timedelta(
                    minutes=self.bettingDurationMinutes)

    def save(self, *args, **kwargs):
        self.full_clean()

        # Auto-calculate bettingOpensAt for pre-recorded matches
        if self.match_mode == 'prerecorded' and self.scheduledStart and not self.bettingOpensAt:
            from django.utils import timezone
            from datetime import timedelta
            self.bettingOpensAt = self.scheduledStart - timedelta(
                minutes=self.bettingDurationMinutes)

        # Snapshot odds when going live
        if self.isLive and not self.oddsSnapshot:
            import json
            self.oddsSnapshot = json.dumps({
                'teamA': {'min': str(self.minThresholdTeamA), 'max': str(self.maxThresholdTeamA)},
                'teamB': {'min': str(self.minThresholdTeamB), 'max': str(self.maxThresholdTeamB)},
                'draw': {'min': str(self.minThresholdTeamDraw), 'max': str(self.maxThresholdTeamDraw)},
            })

        # Track betting open/close times
        if self.isBettingEnabled and not self.bettingOpenedAt:
            from django.utils import timezone
            self.bettingOpenedAt = timezone.now()
        if not self.isBettingEnabled and self._original_isBettingEnabled and not self.bettingClosedAt:
            from django.utils import timezone
            self.bettingClosedAt = timezone.now()

        # Fetch old winTeam value only if this is an update
        if self.pk:
            old_instance = CockfightMatch.objects.filter(pk=self.pk).first()
            old_winDeclareStatus = old_instance.isWinnerDeclared
        else:
            old_winDeclareStatus = False

        super().save(*args, **kwargs)

        if (
            not self.processed and
            not old_winDeclareStatus and
            self.winTeam in [1, 2, 3, 4] and
            self.isWinnerDeclared
        ):
            from cockfightManager.tasks import process_cockfight_match_result

            MatchPremiumHighlights.objects.filter(match=self).delete()
            process_cockfight_match_result.delay(self.id, 'M')


class MatchPremiumHighlights(models.Model):
    match = models.ForeignKey(CockfightMatch, on_delete=models.CASCADE)
    title = models.CharField(max_length=100, unique=True)
    video = models.FileField(storage=AzurePublicStorage(),
                             upload_to='matchPremiumHighlights/',)

    def delete(self, *args, **kwargs):
        if self.video:
            self.video.delete(save=False)
        super().delete(*args, **kwargs)

    def save(self, *args, **kwargs):
        try:
            old_instance = MatchPremiumHighlights.objects.get(pk=self.pk)
            if old_instance.video and old_instance.video != self.video:
                old_instance.video.delete(save=False)
        except MatchPremiumHighlights.DoesNotExist:
            pass

        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Premium Highlight"
        verbose_name_plural = "Premium Highlights"


class AutoMatchPollingState(models.Model):
    runningAutoMatchId = models.PositiveBigIntegerField(null=True)
    runningMatchRefId = models.CharField(max_length=20, null=True, blank=True)
    matchNumber = models.CharField(max_length=5, null=True)
    isNewMatchUpdated = models.BooleanField(null=True, blank=True)
    isAcceptingBet = models.BooleanField(default=False)
    liveUrl = models.URLField(null=True)
    stampingUrl = models.URLField(null=True)
    pastMatchRefId = models.CharField(max_length=20, null=True, blank=True)


class CockfightAutoMatch(models.Model):
    matchTitle = models.CharField(max_length=120, null=True)
    referanceId = models.CharField(max_length=15, null=True)
    matchNumber = models.PositiveSmallIntegerField(null=True)
    winTeam = models.PositiveSmallIntegerField(default=0)
    createdDate = models.DateTimeField(auto_now_add=True)
    updatedDate = models.DateTimeField(auto_now=True)
    processed = models.BooleanField(default=False)

    # Video Recording
    recordingFile = models.CharField(max_length=255, null=True, blank=True)
    RECORDING_STATUS_CHOICES = [
        ('none', 'No Recording'),
        ('recording', 'Recording'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    recordingStatus = models.CharField(max_length=10, choices=RECORDING_STATUS_CHOICES, default='none')
    screenshotFile = models.CharField(max_length=255, null=True, blank=True)

    # Odds Snapshot (JSON string of odds at match creation)
    oddsSnapshot = models.TextField(null=True, blank=True)

    # Timing
    bettingOpenedAt = models.DateTimeField(null=True, blank=True)
    bettingClosedAt = models.DateTimeField(null=True, blank=True)

    # Live URL for this specific match
    liveUrl = models.URLField(max_length=500, null=True, blank=True)

    def __str__(self):
        return f"Auto Match {self.matchTitle or self.referanceId}"

    def save(self, *args, **kwargs):
        # Fetch old winTeam value only if this is an update
        if self.pk:
            old_instance = CockfightAutoMatch.objects.filter(
                pk=self.pk).first()
            old_win_team = old_instance.winTeam if old_instance else 0
        else:
            old_win_team = 0

        super().save(*args, **kwargs)

        if (
            not self.processed and
            old_win_team == 0 and
            self.winTeam in [1, 2, 3, 4]
        ):
            from cockfightManager.tasks import process_cockfight_match_result
            process_cockfight_match_result.delay(self.id, 'A')

    class Meta:
        ordering = ['-createdDate']
        indexes = [
            models.Index(fields=['processed']),
            models.Index(fields=['referanceId']),
        ]


class CockfightMatchBet(models.Model):
    MATCH_TYPE_CHOICE = [
        ('A', 'Auto Match'),
        ('M', 'Manual Match')
    ]
    transactionHash = models.CharField(
        max_length=64, unique=True, null=True, blank=True, db_index=True)
    matchId = models.CharField(
        max_length=25, db_index=True)
    matchType = models.CharField(
        max_length=1, choices=MATCH_TYPE_CHOICE, db_index=True)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, db_index=True)
    betTeam = models.PositiveSmallIntegerField(
        db_index=True)
    amount = models.PositiveSmallIntegerField()
    betRatio = models.DecimalField(max_digits=4, decimal_places=2)
    matchWinStatus = models.PositiveSmallIntegerField(
        default=0, db_index=True)
    createdDate = models.DateTimeField(
        auto_now_add=True, db_index=True)
    updatedDate = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.transactionHash:
            raw = f"{uuid.uuid4().hex}{self.matchId}{self.customer_id}{self.createdDate or ''}"
            self.transactionHash = hashlib.sha256(raw.encode()).hexdigest()[:16].upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Bet #{self.transactionHash or self.id}"

    class Meta:
        indexes = [
            models.Index(fields=['matchType', 'matchId']),
            models.Index(fields=['customer', 'matchWinStatus']),
            models.Index(fields=['matchType', 'matchId', 'betTeam']),
        ]


class OddsConfig(models.Model):
    ODDS_SYSTEM_CHOICES = [
        ('manual', 'Manual Odds'),
        ('dynamic', 'Dynamic Win-Rate Odds'),
        ('pool', 'Pool-Based (Parimutuel) Odds'),
        ('rebalance', 'Fixed Rebalance Odds'),
    ]

    odds_system = models.CharField(
        max_length=20, choices=ODDS_SYSTEM_CHOICES, default='manual',
        help_text='Which odds system is currently active for China Market (Auto) matches.')

    # Manual settings
    manual_meron_min = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.50'))
    manual_meron_max = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.95'))
    manual_wala_min = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.50'))
    manual_wala_max = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.95'))
    manual_draw_min = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('3.00'))
    manual_draw_max = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('10.00'))

    # Dynamic settings
    dynamic_lookback = models.PositiveIntegerField(default=50, help_text='Number of past matches to analyze')
    dynamic_house_edge = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal('0.05'), help_text='House edge e.g. 0.05 = 5%')
    dynamic_min_ratio = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.50'), help_text='Floor for Meron/Wala ratios')
    dynamic_max_ratio = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('1.50'), help_text='Cap for Meron/Wala ratios')
    dynamic_draw_min = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('3.00'))
    dynamic_draw_max = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('10.00'))

    # Pool-based settings
    pool_house_cut = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal('0.05'), help_text='House cut from total pool e.g. 0.05 = 5%')
    pool_draw_min = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('3.00'))
    pool_draw_max = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('10.00'))

    # Rebalance settings
    rebalance_interval = models.PositiveIntegerField(default=10, help_text='Recalculate every N matches')
    rebalance_lookback = models.PositiveIntegerField(default=20, help_text='Matches to look back')
    rebalance_house_edge = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal('0.05'), help_text='Target house edge')
    rebalance_min_ratio = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.50'))
    rebalance_max_ratio = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('1.20'))
    rebalance_draw_min = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('3.00'))
    rebalance_draw_max = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('10.00'))

    # Computed odds (updated by engine)
    current_meron_min = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.50'))
    current_meron_max = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.95'))
    current_wala_min = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.50'))
    current_wala_max = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.95'))
    current_draw_min = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('3.00'))
    current_draw_max = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('10.00'))

    # Stats
    last_recalculated = models.DateTimeField(null=True, blank=True)
    matches_since_rebalance = models.PositiveIntegerField(default=0)
    meron_win_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0'))
    wala_win_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0'))
    draw_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0'))
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Odds Config — {self.get_odds_system_display()}"

    class Meta:
        verbose_name = "Odds Configuration"
        verbose_name_plural = "5. Odds Configuration"
