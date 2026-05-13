import json
from decimal import Decimal
from django.contrib import admin
from django.db.models import Sum, Count, Q, F
from django.utils import timezone
from django.utils.html import format_html

from apiManager.cockfightManager.serializers import CockfightMatchSerializer
from cockfightManager.utils import broadcast_manual_match_update
from .models import (
    Zone, CockfightMatch, MatchPremiumHighlights,
    CockfightMatchBet, LiveSession, OddsConfig
)
from base.admin import MediaDeleteMixin, MediaUpdateMixin, media_preview

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


# ============================
# Zone Admin
# ============================
@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    icon_name = 'golf_course'
    list_display = ('name', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('name',)
    ordering = ('name',)
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ('Zone Information', {
            'fields': (('name', 'is_active'),),
        }),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        try:
            broadcast_manual_match_update()
        except Exception:
            import logging
            logging.exception("Failed to broadcast WebSocket update")

    def has_delete_permission(self, request, obj=...):
        return False


# ============================
# Premium Highlights Inline
# ============================
class MatchPremiumHighlightsInline(admin.TabularInline):
    model = MatchPremiumHighlights
    extra = 1
    fields = ('title', 'video', 'video_preview')
    readonly_fields = ('id', 'video_preview')

    def video_preview(self, obj):
        if obj.video:
            return format_html(
                '<video width="200" controls><source src="{}" type="video/mp4">'
                'Your browser does not support the video tag.</video>',
                obj.video.url
            )
        return "No video"
    video_preview.short_description = "Preview"


# ============================
# Quick Settle Actions
# ============================
def _settle_match(modeladmin, request, queryset, win_team, label):
    if queryset.count() != 1:
        modeladmin.message_user(request, "Select exactly one match.", level='warning')
        return
    match = queryset.first()
    if match.isWinnerDeclared or match.processed:
        modeladmin.message_user(request, "Match already settled.", level='error')
        return
    match.isBettingEnabled = False
    match.winTeam = win_team
    match.isWinnerDeclared = True
    match.save()
    broadcast_manual_match_update()
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "match_result",
        {"type": "send_match_result", "result_type": "manual_match_result",
         "data": CockfightMatchSerializer(match).data}
    )
    modeladmin.message_user(request, f"{label} — payouts processing.", level='success')


@admin.action(description="Declare Winner")
def declare_winner(modeladmin, request, queryset):
    if queryset.count() != 1:
        modeladmin.message_user(request, "Select exactly one match.", level='warning')
        return
    match = queryset.first()
    if match.isWinnerDeclared:
        modeladmin.message_user(request, "Winner already declared.", level='info')
        return
    if match.processed:
        modeladmin.message_user(request, "Already processed.", level='error')
        return
    if match.isBettingEnabled:
        modeladmin.message_user(request, "Disable betting first.", level='error')
        return
    if match.winTeam not in [1, 2, 3, 4]:
        modeladmin.message_user(request, "Set winTeam (1-4) first.", level='error')
        return
    match.isWinnerDeclared = True
    match.save()
    broadcast_manual_match_update()
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "match_result",
        {"type": "send_match_result", "result_type": "manual_match_result",
         "data": CockfightMatchSerializer(match).data}
    )
    modeladmin.message_user(request, "Winner declared.", level='success')


@admin.action(description="Quick Settle: Team A Wins")
def settle_team_a_wins(modeladmin, request, queryset):
    _settle_match(modeladmin, request, queryset, 1,
                  f"Team A ({queryset.first().teamAName}) wins!")


@admin.action(description="Quick Settle: Team B Wins")
def settle_team_b_wins(modeladmin, request, queryset):
    _settle_match(modeladmin, request, queryset, 2,
                  f"Team B ({queryset.first().teamBName}) wins!")


@admin.action(description="Quick Settle: Draw")
def settle_draw(modeladmin, request, queryset):
    _settle_match(modeladmin, request, queryset, 3, "Draw declared!")


@admin.action(description="Quick Settle: Cancel & Refund All")
def settle_cancelled(modeladmin, request, queryset):
    _settle_match(modeladmin, request, queryset, 4, "Match cancelled! All bets refunded.")


# ============================
# CockfightMatch Admin
# ============================
@admin.register(CockfightMatch)
class CockfightMatchAdmin(MediaUpdateMixin, MediaDeleteMixin, admin.ModelAdmin):
    icon_name = 'live_tv'
    list_display = (
        'title', 'zone', 'match_mode', 'isLive', 'isBettingEnabled',
        'winner_display', 'total_bets_display', 'pl_display',
        'recording_display', 'team_1_Preview', 'team_2_Preview',
    )
    list_filter = ('zone', 'match_mode', 'isWinnerDeclared', 'isLive', 'processed')
    search_fields = ('title',)
    ordering = ('-created_at',)
    readonly_fields = (
        'created_at', 'updated_at', 'oddsSnapshot',
        'bettingOpenedAt', 'bettingClosedAt',
        'recordingFile', 'recordingStatus', 'screenshotFile',
        'match_stats_display',
    )
    list_editable = ['isLive', 'isBettingEnabled']
    inlines = [MatchPremiumHighlightsInline]
    autocomplete_fields = ['zone']
    actions = [declare_winner, settle_team_a_wins, settle_team_b_wins, settle_draw, settle_cancelled]
    media_fields = ['promoVideo', 'teamAIcon', 'teamBIcon']
    list_per_page = 15

    def get_fieldsets(self, request, obj=None):
        mode = obj.match_mode if obj else 'manual'

        base_fields = (
            ('Match Details', {
                'fields': (
                    ('zone', 'title', 'match_mode'),
                    ('isLive', 'isBettingEnabled', 'winTeam'),
                    ('teamAName', 'teamBName'),
                    ('teamAIcon', 'teamBIcon'),
                ),
            }),
            ('Odds / Thresholds', {
                'fields': (
                    ('minThresholdTeamA', 'maxThresholdTeamA'),
                    ('minThresholdTeamB', 'maxThresholdTeamB'),
                    ('minThresholdTeamDraw', 'maxThresholdTeamDraw'),
                ),
            }),
        )

        if mode == 'prerecorded':
            extra = (
                ('Pre-Recorded Video', {
                    'fields': (
                        ('matchVideo',),
                        ('scheduledStart', 'bettingDurationMinutes'),
                        ('bettingOpensAt',),
                    ),
                }),
            )
        elif mode == 'live_rtmp':
            extra = (
                ('Live Stream', {
                    'fields': (
                        ('live_session', 'match_number_in_session'),
                        ('youtubeLiveLink',),
                    ),
                }),
            )
        else:
            extra = (
                ('Stream / Video', {
                    'fields': (
                        ('youtubeLiveLink', 'promoVideo'),
                        ('liveDate',),
                    ),
                }),
            )

        stats = (
            ('Match Stats & Recording', {
                'fields': (
                    'match_stats_display',
                    ('oddsSnapshot',),
                    ('bettingOpenedAt', 'bettingClosedAt'),
                    ('recordingFile', 'recordingStatus', 'screenshotFile'),
                ),
                'classes': ('collapse',),
            }),
        )

        return base_fields + extra + stats

    # --- Display helpers ---
    def team_1_Preview(self, obj):
        return media_preview(obj.teamAIcon)
    team_1_Preview.short_description = "A"

    def team_2_Preview(self, obj):
        return media_preview(obj.teamBIcon)
    team_2_Preview.short_description = "B"

    def winner_display(self, obj):
        labels = {0: '-', 1: obj.teamAName, 2: obj.teamBName, 3: 'Draw', 4: 'Cancelled'}
        colors = {0: 'gray', 1: '#c0392b', 2: '#2980b9', 3: '#f39c12', 4: '#7f8c8d'}
        label = labels.get(obj.winTeam, '-')
        color = colors.get(obj.winTeam, 'gray')
        return format_html('<span style="color:{};font-weight:bold">{}</span>', color, label)
    winner_display.short_description = "Winner"

    def _get_match_bet_stats(self, obj):
        bets = CockfightMatchBet.objects.filter(matchType='M', matchId=str(obj.pk))
        stats = bets.aggregate(
            total_count=Count('id'),
            total_amount=Sum('amount'),
            team_a_amount=Sum('amount', filter=Q(betTeam=1)),
            team_b_amount=Sum('amount', filter=Q(betTeam=2)),
            draw_amount=Sum('amount', filter=Q(betTeam=3)),
            team_a_count=Count('id', filter=Q(betTeam=1)),
            team_b_count=Count('id', filter=Q(betTeam=2)),
            draw_count=Count('id', filter=Q(betTeam=3)),
        )
        return stats

    def total_bets_display(self, obj):
        stats = self._get_match_bet_stats(obj)
        count = stats['total_count'] or 0
        amount = stats['total_amount'] or 0
        if count == 0:
            return '-'
        return format_html('<b>{}</b> bets<br/>Rs.{}', count, f'{amount:,}')
    total_bets_display.short_description = "Bets"

    def pl_display(self, obj):
        if obj.winTeam == 0:
            return '-'
        stats = self._get_match_bet_stats(obj)
        total_in = stats['total_amount'] or 0
        if total_in == 0:
            return '-'

        # Calculate payouts
        bets = CockfightMatchBet.objects.filter(matchType='M', matchId=str(obj.pk))
        if obj.winTeam in [1, 2, 3]:
            winning_bets = bets.filter(betTeam=obj.winTeam)
            total_payout = sum(b.amount + (b.amount * b.betRatio) for b in winning_bets)
        elif obj.winTeam == 4:
            total_payout = total_in  # refunded
        else:
            total_payout = 0

        pl = Decimal(total_in) - Decimal(str(total_payout))
        color = 'green' if pl >= 0 else 'red'
        sign = '+' if pl >= 0 else ''
        return format_html(
            '<span style="color:{};font-weight:bold">{}Rs.{}</span>',
            color, sign, f'{pl:,.2f}'
        )
    pl_display.short_description = "P/L"

    def recording_display(self, obj):
        status = obj.recordingStatus
        if status == 'none':
            return '-'
        colors = {'recording': 'orange', 'completed': 'green', 'failed': 'red'}
        icons = {'recording': '🔴', 'completed': '📹', 'failed': '❌'}
        parts = []
        parts.append(format_html(
            '<span style="color:{}">{} {}</span>',
            colors.get(status, 'gray'), icons.get(status, ''), status.title()
        ))
        if obj.screenshotFile:
            parts.append(format_html(
                ' <a href="/media/{}" target="_blank">📷</a>', obj.screenshotFile
            ))
        return format_html(''.join(str(p) for p in parts))
    recording_display.short_description = "Recording"

    def match_stats_display(self, obj):
        stats = self._get_match_bet_stats(obj)
        total = stats['total_count'] or 0
        if total == 0:
            return format_html('<em>No bets placed</em>')

        team_a_amt = stats['team_a_amount'] or 0
        team_b_amt = stats['team_b_amount'] or 0
        draw_amt = stats['draw_amount'] or 0
        team_a_cnt = stats['team_a_count'] or 0
        team_b_cnt = stats['team_b_count'] or 0
        draw_cnt = stats['draw_count'] or 0
        total_amt = stats['total_amount'] or 0

        return format_html(
            '<div style="background:#f8f9fa;padding:12px;border-radius:6px;font-size:13px">'
            '<table style="width:100%;border-collapse:collapse">'
            '<tr style="border-bottom:1px solid #ddd">'
            '<th style="text-align:left;padding:4px 8px">Team</th>'
            '<th style="text-align:right;padding:4px 8px">Bets</th>'
            '<th style="text-align:right;padding:4px 8px">Amount</th>'
            '</tr>'
            '<tr><td style="padding:4px 8px;color:#c0392b"><b>{} (A)</b></td>'
            '<td style="text-align:right;padding:4px 8px">{}</td>'
            '<td style="text-align:right;padding:4px 8px">Rs.{}</td></tr>'
            '<tr><td style="padding:4px 8px;color:#2980b9"><b>{} (B)</b></td>'
            '<td style="text-align:right;padding:4px 8px">{}</td>'
            '<td style="text-align:right;padding:4px 8px">Rs.{}</td></tr>'
            '<tr><td style="padding:4px 8px;color:#f39c12"><b>Draw</b></td>'
            '<td style="text-align:right;padding:4px 8px">{}</td>'
            '<td style="text-align:right;padding:4px 8px">Rs.{}</td></tr>'
            '<tr style="border-top:2px solid #333"><td style="padding:4px 8px"><b>Total</b></td>'
            '<td style="text-align:right;padding:4px 8px"><b>{}</b></td>'
            '<td style="text-align:right;padding:4px 8px"><b>Rs.{}</b></td></tr>'
            '</table></div>',
            obj.teamAName, team_a_cnt, f'{team_a_amt:,}',
            obj.teamBName, team_b_cnt, f'{team_b_amt:,}',
            draw_cnt, f'{draw_amt:,}',
            total, f'{total_amt:,}',
        )
    match_stats_display.short_description = "Bet Statistics"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        isWinnerDeclared = request.GET.get('isWinnerDeclared__exact')
        if isWinnerDeclared:
            return qs.filter(isWinnerDeclared=isWinnerDeclared)
        return qs.filter(isWinnerDeclared=False)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        try:
            broadcast_manual_match_update()
        except Exception:
            import logging
            logging.exception("Failed to broadcast WebSocket update")

    def has_delete_permission(self, request, obj=...):
        return False


# ============================
# LiveSession Admin
# ============================
@admin.register(LiveSession)
class LiveSessionAdmin(admin.ModelAdmin):
    icon_name = 'videocam'
    list_display = ('title', 'zone', 'stream_key_display', 'is_active',
                    'rtmp_url_display', 'match_count', 'started_at', 'created_at')
    list_filter = ('is_active', 'zone')
    search_fields = ('title', 'stream_key')
    readonly_fields = ('stream_key', 'rtmp_url_display', 'hls_url_display',
                       'created_at', 'recordingFile', 'recordingStatus')
    ordering = ('-created_at',)

    fieldsets = (
        ('Session Info', {
            'fields': (
                ('zone', 'title'),
                ('is_active',),
            ),
        }),
        ('Stream URLs (copy to OBS)', {
            'fields': (
                ('stream_key',),
                ('rtmp_url_display',),
                ('hls_url_display',),
            ),
        }),
        ('Timing', {
            'fields': (('started_at', 'ended_at'),),
        }),
        ('Recording', {
            'fields': (('recordingFile', 'recordingStatus'),),
            'classes': ('collapse',),
        }),
    )

    def stream_key_display(self, obj):
        return format_html(
            '<code style="background:#f0f0f0;padding:2px 6px;border-radius:3px">{}</code>',
            obj.stream_key[:12] + '...'
        )
    stream_key_display.short_description = "Key"

    def rtmp_url_display(self, obj):
        url = obj.rtmp_url
        return format_html(
            '<div style="background:#1a1a2e;color:#00ff88;padding:8px 12px;'
            'border-radius:4px;font-family:monospace;font-size:13px;'
            'user-select:all;cursor:text">{}</div>'
            '<p style="color:#666;font-size:11px;margin-top:4px">'
            'Copy this URL into OBS > Settings > Stream > Server</p>',
            url
        )
    rtmp_url_display.short_description = "RTMP URL (for OBS)"

    def hls_url_display(self, obj):
        url = obj.hls_url
        return format_html(
            '<div style="background:#f8f9fa;padding:8px 12px;border-radius:4px;'
            'font-family:monospace;font-size:13px;user-select:all">{}</div>'
            '<p style="color:#666;font-size:11px;margin-top:4px">'
            'Users watch via this HLS URL</p>',
            url
        )
    hls_url_display.short_description = "HLS Playback URL"

    def match_count(self, obj):
        count = CockfightMatch.objects.filter(live_session=obj).count()
        return count
    match_count.short_description = "Matches"

    def save_model(self, request, obj, form, change):
        if not obj.stream_key:
            import uuid
            obj.stream_key = uuid.uuid4().hex[:16]
        if obj.is_active and not obj.started_at:
            obj.started_at = timezone.now()
        elif not obj.is_active and obj.started_at and not obj.ended_at:
            obj.ended_at = timezone.now()
        super().save_model(request, obj, form, change)


# ============================
# CockfightMatchBet Admin
# ============================
class BetTeamFilter(admin.SimpleListFilter):
    title = 'Bet On'
    parameter_name = 'betTeam'
    def lookups(self, request, model_admin):
        return ((1, 'Meron (Team A)'), (2, 'Wala (Team B)'), (3, 'Draw'))
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(betTeam=int(self.value()))

class WinStatusFilter(admin.SimpleListFilter):
    title = 'Result'
    parameter_name = 'matchWinStatus'
    def lookups(self, request, model_admin):
        return ((0, 'Pending'), (1, 'Won'), (2, 'Lost'), (3, 'Cancelled'))
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(matchWinStatus=int(self.value()))

@admin.register(CockfightMatchBet)
class CockfightMatchBetAdmin(admin.ModelAdmin):
    icon_name = 'receipt'
    list_display = ['transactionHash', 'customer', 'match_game_info', 'matchType',
                    'betTeam_display', 'amount', 'betRatio', 'win_status_display', 'createdDate']
    list_filter = ['matchType', WinStatusFilter, BetTeamFilter]
    search_fields = ['customer__email', 'customer__username', 'customer__phoneNumber',
                     'matchId', 'transactionHash']
    list_per_page = 25
    readonly_fields = ['transactionHash', 'id', 'matchId', 'matchType', 'customer',
                       'betTeam', 'amount', 'betRatio', 'matchWinStatus', 'createdDate', 'updatedDate']
    list_display_links = None
    actions = ['export_bets_csv']

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

    def match_game_info(self, obj):
        if obj.matchType == 'M':
            try:
                match = CockfightMatch.objects.filter(id=obj.matchId).first()
                if match:
                    zone_name = match.zone.name if match.zone else 'Unknown'
                    return f"{zone_name} - Match #{obj.matchId}"
            except Exception:
                pass
        elif obj.matchType == 'A':
            from cockfightManager.models import CockfightAutoMatch
            try:
                match = CockfightAutoMatch.objects.filter(id=obj.matchId).first()
                if match:
                    return f"China - #{match.matchNumber or obj.matchId}"
            except Exception:
                pass
        return f"Match #{obj.matchId}"
    match_game_info.short_description = "Game / Match"

    def betTeam_display(self, obj):
        teams = {1: 'Meron', 2: 'Wala', 3: 'Draw'}
        return teams.get(obj.betTeam, str(obj.betTeam))
    betTeam_display.short_description = "Bet On"

    def win_status_display(self, obj):
        statuses = {0: ('Pending', 'orange'), 1: ('Won', 'green'), 2: ('Lost', 'red'),
                    3: ('Cancelled', 'gray')}
        label, color = statuses.get(obj.matchWinStatus, ('Unknown', 'black'))
        return format_html('<span style="color:{};font-weight:bold;">{}</span>', color, label)
    win_status_display.short_description = "Result"

    @admin.action(description="Download as CSV")
    def export_bets_csv(self, request, queryset):
        import csv
        from django.http import HttpResponse
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="bet_history_{timezone.now().strftime("%Y%m%d_%H%M")}.csv"'
        writer = csv.writer(response)
        writer.writerow(['Hash', 'Customer', 'Phone', 'Match ID', 'Type', 'Bet On', 'Amount', 'Ratio', 'Result', 'Date'])
        teams = {1: 'Team A', 2: 'Team B', 3: 'Draw'}
        statuses = {0: 'Pending', 1: 'Won', 2: 'Lost', 3: 'Cancelled'}
        for bet in queryset.select_related('customer'):
            writer.writerow([
                bet.transactionHash or '-',
                bet.customer.email if bet.customer else '-',
                bet.customer.phoneNumber if bet.customer else '-',
                bet.matchId,
                bet.get_matchType_display(),
                teams.get(bet.betTeam, str(bet.betTeam)),
                bet.amount,
                bet.betRatio,
                statuses.get(bet.matchWinStatus, 'Unknown'),
                bet.createdDate.strftime('%Y-%m-%d %H:%M') if bet.createdDate else '-'
            ])
        return response


# China Market Admin
from cockfightManager.china_market_admin import ChinaMarketAdmin  # noqa


# ============================
# Odds Configuration Admin
# ============================
@admin.register(OddsConfig)
class OddsConfigAdmin(admin.ModelAdmin):
    icon_name = 'trending_up'

    list_display = ('odds_system_display', 'current_odds_display', 'win_stats_display', 'last_recalculated')

    fieldsets = (
        ('Active Odds System', {
            'fields': ('odds_system',),
            'description': '<div style="background:#1a1a2e;border:1px solid #d4a843;border-radius:8px;padding:16px;margin-bottom:16px;color:#eee;">'
                '<h3 style="color:#d4a843;margin-top:0;">Choose Your Odds System</h3>'
                '<p>Select which system controls Meron/Wala/Draw ratios for China Market (Auto) matches. Only ONE system is active at a time.</p>'
                '</div>',
        }),
        ('Option 1: Manual Odds', {
            'fields': (
                ('manual_meron_min', 'manual_meron_max'),
                ('manual_wala_min', 'manual_wala_max'),
                ('manual_draw_min', 'manual_draw_max'),
            ),
            'classes': ('collapse',),
            'description': '<div style="background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:16px;margin-bottom:8px;color:#c9d1d9;">'
                '<h4 style="color:#d4a843;margin-top:0;">Manual Odds — You Set Everything</h4>'
                '<p><b>How it works:</b> You manually set the min/max ratio for each team. Users pick a ratio within your range.</p>'
                '<p><b>Example:</b><br>'
                'You set Meron: 0.50x - 0.85x<br>'
                'You set Wala: 0.60x - 0.95x<br>'
                'User picks Meron at 0.75x, bets 1000<br>'
                'If Meron wins: user gets 1000 + 750 = 1750 back<br>'
                'If Wala wins: user loses 1000</p>'
                '<p><b>When to use:</b> When you want full control over the odds.</p>'
                '<p style="color:#ffa500;">Warning: If you set Wala max at 0.95x but Wala wins 55%+ of the time, the house loses money!</p>'
                '</div>',
        }),
        ('Option 2: Dynamic Win-Rate Odds', {
            'fields': (
                'dynamic_lookback',
                'dynamic_house_edge',
                ('dynamic_min_ratio', 'dynamic_max_ratio'),
                ('dynamic_draw_min', 'dynamic_draw_max'),
            ),
            'classes': ('collapse',),
            'description': '<div style="background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:16px;margin-bottom:8px;color:#c9d1d9;">'
                '<h4 style="color:#d4a843;margin-top:0;">Dynamic Win-Rate Odds — Auto-Adjusts After Every Match</h4>'
                '<p><b>How it works:</b> System analyzes last N matches, calculates win%, and sets odds to guarantee your house edge.</p>'
                '<p><b>Formula:</b> max_ratio = (1 / win_rate) x (1 - house_edge) - 1</p>'
                '<p><b>Example with 5% house edge, last 50 matches:</b><br>'
                'Meron wins 44%: max_ratio = (1/0.44) x 0.95 - 1 = 1.16x<br>'
                'Wala wins 52%: max_ratio = (1/0.52) x 0.95 - 1 = 0.83x<br>'
                'User bets 1000 on Wala at 0.83x:<br>'
                '- Win (52%): gets 1830 back (830 profit)<br>'
                '- Lose (48%): loses 1000<br>'
                '- Expected return: 52% x 1.83 = 0.95 (House keeps 5%)</p>'
                '<p style="color:#22c55e;">RECOMMENDED — Set it and forget it. Guaranteed profit in the long run.</p>'
                '</div>',
        }),
        ('Option 3: Pool-Based (Parimutuel) Odds', {
            'fields': (
                'pool_house_cut',
                ('pool_draw_min', 'pool_draw_max'),
            ),
            'classes': ('collapse',),
            'description': '<div style="background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:16px;margin-bottom:8px;color:#c9d1d9;">'
                '<h4 style="color:#d4a843;margin-top:0;">Pool-Based (Parimutuel) — Like Horse Racing</h4>'
                '<p><b>How it works:</b> All bets go into a pool. Odds are based on how much is bet on each side. More bets on one team = lower odds.</p>'
                '<p><b>Formula:</b> odds = (total_pool / team_pool) x (1 - house_cut) - 1</p>'
                '<p><b>Example with 5% house cut:</b><br>'
                'Total bets: 100,000<br>'
                'Meron bets: 60,000 (60%)<br>'
                'Wala bets: 40,000 (40%)<br>'
                'Meron odds: (100000/60000) x 0.95 - 1 = 0.58x<br>'
                'Wala odds: (100000/40000) x 0.95 - 1 = 1.38x<br>'
                'If Wala wins: Wala bettors share 95,000. House keeps 5,000.</p>'
                '<p><b>Key:</b> Odds change in REAL-TIME as users bet! House ALWAYS keeps its cut.</p>'
                '</div>',
        }),
        ('Option 4: Fixed Rebalance Odds', {
            'fields': (
                ('rebalance_interval', 'rebalance_lookback'),
                'rebalance_house_edge',
                ('rebalance_min_ratio', 'rebalance_max_ratio'),
                ('rebalance_draw_min', 'rebalance_draw_max'),
            ),
            'classes': ('collapse',),
            'description': '<div style="background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:16px;margin-bottom:8px;color:#c9d1d9;">'
                '<h4 style="color:#d4a843;margin-top:0;">Fixed Rebalance — Auto-Adjusts Every N Matches</h4>'
                '<p><b>How it works:</b> Same formula as Dynamic, but only recalculates every N matches. More stable odds for users.</p>'
                '<p><b>Example (interval=10, lookback=20, edge=5%):</b><br>'
                'After every 10 matches, checks last 20 results:<br>'
                'Matches 1-10: Meron=6 Wala=4 -> Meron max=0.58x Wala max=1.38x<br>'
                'Matches 11-20 (rebalance): Meron=8 Wala=10 Draw=2 -> Meron max=1.37x Wala max=0.90x<br>'
                'Between rebalances, odds stay fixed.</p>'
                '<p style="color:#a855f7;">Tip: Use interval=10-20, lookback=20-50 for best stability.</p>'
                '</div>',
        }),
        ('Current Computed Odds & Stats', {
            'fields': (
                ('current_meron_min', 'current_meron_max'),
                ('current_wala_min', 'current_wala_max'),
                ('current_draw_min', 'current_draw_max'),
                ('meron_win_pct', 'wala_win_pct', 'draw_pct'),
                'matches_since_rebalance',
                'last_recalculated',
            ),
            'description': '<div style="background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:16px;margin-bottom:8px;color:#c9d1d9;">'
                '<h4 style="color:#d4a843;margin-top:0;">Live Odds and Statistics</h4>'
                '<p>These values are automatically computed by the active system. For Manual mode, the manual values above are used directly.</p>'
                '</div>',
        }),
    )

    def odds_system_display(self, obj):
        colors = {'manual': '#fbbf24', 'dynamic': '#22c55e', 'pool': '#3b82f6', 'rebalance': '#a855f7'}
        color = colors.get(obj.odds_system, '#888')
        return format_html('<span style="color:{};font-weight:700;">{}</span>', color, obj.get_odds_system_display())
    odds_system_display.short_description = 'Active System'

    def current_odds_display(self, obj):
        if obj.odds_system == 'manual':
            m_min, m_max = obj.manual_meron_min, obj.manual_meron_max
            w_min, w_max = obj.manual_wala_min, obj.manual_wala_max
        else:
            m_min, m_max = obj.current_meron_min, obj.current_meron_max
            w_min, w_max = obj.current_wala_min, obj.current_wala_max
        return format_html(
            '<span style="color:#ef4444;">Meron: {}x-{}x</span> | '
            '<span style="color:#3b82f6;">Wala: {}x-{}x</span>',
            m_min, m_max, w_min, w_max
        )
    current_odds_display.short_description = 'Current Odds'

    def win_stats_display(self, obj):
        if obj.meron_win_pct or obj.wala_win_pct:
            return format_html(
                '<span style="color:#ef4444;">M: {}%</span> / '
                '<span style="color:#3b82f6;">W: {}%</span> / '
                '<span style="color:#a855f7;">D: {}%</span>',
                obj.meron_win_pct, obj.wala_win_pct, obj.draw_pct
            )
        return format_html('<span style="color:#888;">No data yet</span>')
    win_stats_display.short_description = 'Win Rates'

    def has_add_permission(self, request):
        return not OddsConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        if not OddsConfig.objects.exists():
            OddsConfig.objects.create()
        obj = OddsConfig.objects.first()
        from django.shortcuts import redirect
        return redirect(f'/cockfightManager/oddsconfig/{obj.pk}/change/')
