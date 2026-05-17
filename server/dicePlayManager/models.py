from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from utility.storageClasses import AzurePublicStorage


class Board(models.Model):
    """Board (like Zone in cockfight) - dice matches run per board."""
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)
    is_virtual = models.BooleanField(default=False, help_text="If True, this board runs virtual auto-roll rounds")
    virtual_betting_seconds = models.PositiveIntegerField(default=120, help_text="Seconds betting stays open for virtual rounds (default 2 min)")
    virtual_shuffle_seconds = models.PositiveIntegerField(default=30, help_text="Seconds for dice shuffle animation phase")
    virtual_result_seconds = models.PositiveIntegerField(default=12, help_text="Seconds to display result before next round")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        mode = "Virtual" if self.is_virtual else "Live"
        return f"{self.name} ({mode})"

    class Meta:
        verbose_name = "Board"
        verbose_name_plural = "1. Dice Boards"
        indexes = [models.Index(fields=['is_active'])]
        ordering = ['name']


MATCH_TYPE_CHOICES = (
    ("L", "Live (Manual)"),
    ("V", "Virtual (Auto-Roll)"),
)

VIRTUAL_PHASE_CHOICES = (
    ("created", "Created"),
    ("betting", "Betting Open"),
    ("betting_closed", "Betting Closed"),
    ("shuffling", "Dice Rolling"),
    ("result", "Result Reveal"),
    ("settlement", "Settlement"),
    ("done", "Completed"),
    ("cancelled", "Cancelled"),
)


class DicePlayMatch(models.Model):
    board = models.ForeignKey(Board, on_delete=models.PROTECT)
    title = models.CharField(max_length=100)
    match_type = models.CharField(max_length=1, choices=MATCH_TYPE_CHOICES, default="L")
    liveDate = models.DateTimeField(null=True, blank=True)
    isLive = models.BooleanField(default=False)
    isBettingEnabled = models.BooleanField(default=False)
    youtubeLiveLink = models.CharField(max_length=100, null=True, blank=True)
    promoVideo = models.FileField(
        storage=AzurePublicStorage(), upload_to='dicePlayMatchPromo/', null=True, blank=True
    )
    total1Rolled = models.PositiveSmallIntegerField(default=0)
    total2Rolled = models.PositiveSmallIntegerField(default=0)
    total3Rolled = models.PositiveSmallIntegerField(default=0)
    total4Rolled = models.PositiveSmallIntegerField(default=0)
    total5Rolled = models.PositiveSmallIntegerField(default=0)
    total6Rolled = models.PositiveSmallIntegerField(default=0)
    dice_result_json = models.CharField(max_length=50, null=True, blank=True, help_text="Individual dice results e.g. 3,3,3,3,5,1")
    isWinnerDeclared = models.BooleanField(default=False)
    processed = models.BooleanField(default=False)
    # New fields for 24/7 virtual dice
    game_hash = models.CharField(max_length=64, null=True, blank=True, db_index=True, help_text="Unique SHA-256 hash for game verification")
    daily_match_number = models.PositiveIntegerField(default=0, help_text="Match number for the day (resets at 12:00 AM IST)")
    match_date = models.DateField(null=True, blank=True, db_index=True, help_text="IST date this match belongs to")
    virtual_phase = models.CharField(max_length=15, choices=VIRTUAL_PHASE_CHOICES, default="betting", help_text="Current phase of virtual match lifecycle")
    phase_started_at = models.DateTimeField(null=True, blank=True, help_text="When the current phase started")
    # Provably fair fields
    server_seed = models.CharField(max_length=64, null=True, blank=True, help_text="Secret server seed (revealed after round)")
    client_seed = models.CharField(max_length=32, null=True, blank=True, help_text="Public client seed")
    commitment_hash = models.CharField(max_length=64, null=True, blank=True, help_text="SHA256(server_seed) shown before round")
    nonce = models.PositiveIntegerField(default=0, help_text="Round nonce for provably fair")
    server_seed_revealed = models.BooleanField(default=False, help_text="Whether server seed has been revealed")
    # Settlement tracking
    settlement_id = models.CharField(max_length=30, null=True, blank=True, help_text="Unique settlement transaction ID")
    settled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Dice Play Match"
        verbose_name_plural = "2. Dice Play Matches"
        ordering = ['liveDate', '-created_at']
        indexes = [
            models.Index(fields=['board', 'liveDate']),
            models.Index(fields=['isLive']),
            models.Index(fields=['isWinnerDeclared']),
            models.Index(fields=['processed']),
            models.Index(fields=['match_type']),
            models.Index(fields=['match_date', 'daily_match_number']),
            models.Index(fields=['match_type', 'isWinnerDeclared', '-updated_at']),
        ]

    def __str__(self):
        mode = "Virtual" if self.match_type == "V" else "Live"
        return f"Dice {self.title} ({mode})"

    def clean(self):
        if self.isLive and not self.isWinnerDeclared:
            conflicts = DicePlayMatch.objects.filter(
                board=self.board, isLive=True, isWinnerDeclared=False
            ).exclude(pk=self.pk)
            if conflicts.exists():
                raise ValidationError(
                    "Only one live, undecided match is allowed per board."
                )
        total = (
            self.total1Rolled + self.total2Rolled + self.total3Rolled
            + self.total4Rolled + self.total5Rolled + self.total6Rolled
        )
        if total > 0 and total != 6:
            raise ValidationError(
                "Sum of total1Rolled..total6Rolled must be 6 (exactly 6 dice)."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        old_win = False
        if self.pk:
            old = DicePlayMatch.objects.filter(pk=self.pk).first()
            if old:
                old_win = old.isWinnerDeclared
        super().save(*args, **kwargs)
        if not self.processed and not old_win and self.isWinnerDeclared:
            from dicePlayManager.tasks import process_dice_play_match_result
            process_dice_play_match_result.delay(self.id)


BET_STATUS_CHOICES = (
    (0, "Pending"),
    (1, "Won"),
    (2, "Lost"),
    (3, "Accepted"),
    (4, "Cancelled"),
    (5, "Refunded"),
    (6, "Rejected"),
)


class DicePlayMatchBet(models.Model):
    """Bet on a dice number (1-6) for a match; payout = bet + rolled_count * amount if die rolled >= 2."""
    match = models.ForeignKey(
        DicePlayMatch, on_delete=models.PROTECT, related_name='bets', db_index=True
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, db_index=True
    )
    diceNumber = models.PositiveSmallIntegerField(db_index=True)
    amount = models.PositiveIntegerField()
    matchWinStatus = models.PositiveSmallIntegerField(
        default=0, choices=BET_STATUS_CHOICES, db_index=True
    )  # 0=pending, 1=won, 2=lost, 3=accepted, 4=cancelled, 5=refunded, 6=rejected
    rolled_count = models.PositiveSmallIntegerField(default=0)
    payout_amount = models.PositiveIntegerField(default=0, help_text="Actual payout credited")
    settlement_id = models.CharField(max_length=30, null=True, blank=True, help_text="Settlement transaction ID")
    createdDate = models.DateTimeField(auto_now_add=True, db_index=True)
    updatedDate = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Dice Play Match Bet"
        verbose_name_plural = "3. Dice Play Match Bets"
        ordering = ['-createdDate']
        indexes = [
            models.Index(fields=['match', 'customer']),
            models.Index(fields=['customer', 'matchWinStatus']),
        ]

    def __str__(self):
        return f"Bet {self.amount} on {self.diceNumber} by {self.customer_id} (match {self.match_id})"
