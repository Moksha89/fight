from django.contrib import admin
from django.utils.html import format_html
from base.admin import MediaDeleteMixin, MediaUpdateMixin, media_preview
from .models import Board, DicePlayMatch, DicePlayMatchBet
from apiManager.dicePlayManager.serializers import DicePlayMatchSerializer
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


@admin.register(Board)
class BoardAdmin(admin.ModelAdmin):
    icon_name = "dashboard"
    list_display = ("name", "board_type_display", "is_active", "virtual_betting_seconds", "virtual_shuffle_seconds", "virtual_result_seconds", "created_at")
    list_filter = ("is_active", "is_virtual")
    search_fields = ("name",)
    ordering = ("name",)
    readonly_fields = ("created_at", "updated_at")
    list_editable = ["is_active"]
    fieldsets = (
        ("Board Information", {"fields": (("name", "is_active"),)}),
        ("Virtual Mode", {"fields": (
            ("is_virtual",),
            ("virtual_betting_seconds", "virtual_shuffle_seconds", "virtual_result_seconds"),
        ), "description": "Enable virtual mode for server-side auto-roll dice rounds. Timing: betting → shuffle → result → repeat."}),
    )

    def board_type_display(self, obj):
        if obj.is_virtual:
            return format_html('<span style="color:#4caf50;font-weight:bold;">VIRTUAL</span>')
        return format_html('<span style="color:#2196f3;font-weight:bold;">LIVE</span>')
    board_type_display.short_description = "Type"

    def has_delete_permission(self, request, obj=None):
        return False


def _check_rolls_sum(match):
    total = (
        match.total1Rolled + match.total2Rolled + match.total3Rolled
        + match.total4Rolled + match.total5Rolled + match.total6Rolled
    )
    return total == 6


@admin.action(description="Declare winner")
def declare_winner(modeladmin, request, queryset):
    if queryset.count() != 1:
        modeladmin.message_user(request, "Please select exactly one match to declare winner.", level="warning")
        return
    match = queryset.first()
    if match.isWinnerDeclared:
        modeladmin.message_user(request, "Winner already declared for this match.", level="info")
        return
    if match.processed:
        modeladmin.message_user(request, "Match already processed.", level="error")
        return
    if match.isBettingEnabled:
        modeladmin.message_user(request, "Disable betting first before declaring winner.", level="error")
        return
    if not _check_rolls_sum(match):
        modeladmin.message_user(request, "Sum of total1Rolled..total6Rolled must be 6 before declaring winner.", level="error")
        return
    match.isWinnerDeclared = True
    match.save()
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "dice_match_result",
        {
            "type": "send_dice_match_result",
            "result_type": "dice_match_result",
            "data": DicePlayMatchSerializer(match).data,
        },
    )
    modeladmin.message_user(request, "Winner declared and payouts triggered.", level="success")


@admin.action(description="Roll dice (virtual match)")
def roll_virtual_dice(modeladmin, request, queryset):
    """Trigger auto-roll for a virtual match."""
    if queryset.count() != 1:
        modeladmin.message_user(request, "Please select exactly one match.", level="warning")
        return
    match = queryset.first()
    if match.match_type != "V":
        modeladmin.message_user(request, "This is not a virtual match. Use 'Declare winner' for live matches.", level="error")
        return
    if match.isWinnerDeclared:
        modeladmin.message_user(request, "Match already settled.", level="info")
        return
    from .tasks import auto_roll_virtual_match
    auto_roll_virtual_match.delay(match.id)
    modeladmin.message_user(request, "Dice rolling... Result will appear shortly.", level="success")


@admin.action(description="Start next virtual round")
def start_next_virtual_round(modeladmin, request, queryset):
    """Create a new virtual round on the selected match's board."""
    if queryset.count() != 1:
        modeladmin.message_user(request, "Please select exactly one match.", level="warning")
        return
    match = queryset.first()
    board = match.board
    active = DicePlayMatch.objects.filter(board=board, isWinnerDeclared=False).exists()
    if active:
        modeladmin.message_user(request, "Board already has an active match.", level="error")
        return
    from .tasks import create_next_virtual_round
    create_next_virtual_round.delay(board.id)
    modeladmin.message_user(request, f"Starting next virtual round on {board.name}...", level="success")


@admin.register(DicePlayMatch)
class DicePlayMatchAdmin(MediaUpdateMixin, MediaDeleteMixin, admin.ModelAdmin):
    icon_name = "casino"
    list_display = (
        "title",
        "board",
        "match_type_display",
        "virtual_phase_display",
        "daily_match_number",
        "isLive",
        "isBettingEnabled",
        "isWinnerDeclared",
        "dice_result_display",
        "game_hash_short",
        "created_at",
    )
    list_filter = ("board", "match_type", "isWinnerDeclared", "isLive", "virtual_phase", "match_date")
    search_fields = ("title", "game_hash")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at", "dice_result_json", "processed", "game_hash", "daily_match_number", "match_date", "virtual_phase", "phase_started_at")
    list_editable = ["isLive", "isBettingEnabled"]
    autocomplete_fields = ["board"]
    actions = [declare_winner, roll_virtual_dice, start_next_virtual_round]
    media_fields = ["promoVideo"]
    list_per_page = 15

    def match_type_display(self, obj):
        if obj.match_type == "V":
            return format_html('<span style="color:#4caf50;font-weight:bold;">VIRTUAL</span>')
        return format_html('<span style="color:#2196f3;font-weight:bold;">LIVE</span>')
    match_type_display.short_description = "Mode"

    def virtual_phase_display(self, obj):
        colors = {"betting": "#4caf50", "shuffling": "#ff9800", "result": "#2196f3", "done": "#666"}
        color = colors.get(obj.virtual_phase, "#666")
        return format_html('<span style="color:{};font-weight:bold;">{}</span>', color, obj.virtual_phase.upper())
    virtual_phase_display.short_description = "Phase"

    def game_hash_short(self, obj):
        if obj.game_hash:
            return format_html('<code style="font-size:11px;">{}</code>', obj.game_hash[:12] + '...')
        return "-"
    game_hash_short.short_description = "Hash"

    def dice_result_display(self, obj):
        if obj.dice_result_json:
            dice = obj.dice_result_json.split(",")
            faces = {"1": "\u2680", "2": "\u2681", "3": "\u2682", "4": "\u2683", "5": "\u2684", "6": "\u2685"}
            result = " ".join(faces.get(d.strip(), d) for d in dice)
            return format_html('<span style="font-size:18px;">{}</span>', result)
        return "-"
    dice_result_display.short_description = "Dice Result"

    def rolls_sum(self, obj):
        s = (
            obj.total1Rolled + obj.total2Rolled + obj.total3Rolled
            + obj.total4Rolled + obj.total5Rolled + obj.total6Rolled
        )
        return format_html("<strong>{}</strong> /6", s)
    rolls_sum.short_description = "Rolls"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.GET.get("isWinnerDeclared__exact"):
            return qs.filter(isWinnerDeclared=request.GET["isWinnerDeclared__exact"])
        return qs

    fieldsets = (
        (
            "Match Details",
            {
                "fields": (
                    ("board", "title", "match_type"),
                    ("isLive", "isBettingEnabled"),
                    ("liveDate",),
                ),
            },
        ),
        (
            "Virtual 24/7 Info",
            {
                "fields": (
                    ("game_hash", "daily_match_number", "match_date"),
                    ("virtual_phase", "phase_started_at"),
                ),
            },
        ),
        (
            "Stream (Live mode only)",
            {
                "fields": (("youtubeLiveLink", "promoVideo"),),
                "classes": ("collapse",),
            },
        ),
        (
            "Dice rolls (sum must be 6) - Live mode",
            {
                "fields": (
                    (
                        "total1Rolled", "total2Rolled", "total3Rolled",
                        "total4Rolled", "total5Rolled", "total6Rolled",
                    ),
                    "dice_result_json",
                ),
            },
        ),
    )

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if obj is None:
            return [fs for fs in fieldsets if fs[0] != "Dice rolls (sum must be 6) - Live mode"]
        return fieldsets

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DicePlayMatchBet)
class DicePlayMatchBetAdmin(admin.ModelAdmin):
    icon_name = "receipt"
    list_display = ("id", "match", "customer", "diceNumber", "amount", "matchWinStatus", "rolled_count", "createdDate")
    list_filter = ("matchWinStatus", "diceNumber")
    search_fields = ("customer__username", "customer__phone")
    ordering = ("-createdDate",)
    readonly_fields = ("match", "customer", "diceNumber", "amount", "matchWinStatus", "rolled_count", "createdDate", "updatedDate")
    list_per_page = 25

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
