"""
China Market Admin View - Custom admin page for managing auto cockfight matches.
Enhanced with video recording, odds snapshot, and detailed statistics.
"""

from django.contrib import admin
from django.urls import path
from django.http import JsonResponse, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.utils.html import format_html
from django.db.models import Sum, Count, Q, F, DecimalField
from django.db.models.functions import Coalesce
from decimal import Decimal
import json

from cockfightManager.models import CockfightAutoMatch, AutoMatchPollingState, CockfightMatchBet
from base.models import Setting


def is_china_market_enabled():
    """Check if China Market is enabled via DB Setting Y."""
    try:
        s = Setting.objects.get(action='Y')
        return s.actionValue.strip().upper() == 'Y'
    except Setting.DoesNotExist:
        return False


class ChinaMarketAdmin(admin.ModelAdmin):
    """Custom admin for China Market (Auto Match) management."""
    
    model = CockfightAutoMatch
    list_display = ['match_title_display', 'match_number_display', 'win_team_display',
                    'bets_by_team', 'total_amount', 'profit_loss', 'recording_display',
                    'odds_display', 'duration_display', 'processed', 'createdDate']
    list_filter = ['processed', 'winTeam', 'recordingStatus']
    search_fields = ['matchTitle', 'referanceId']
    list_per_page = 25
    readonly_fields = ['matchTitle', 'referanceId', 'matchNumber', 'createdDate', 'updatedDate']
    ordering = ['-createdDate']
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def match_title_display(self, obj):
        return obj.matchTitle or f"Match #{obj.referanceId}"
    match_title_display.short_description = "Match"
    
    def match_number_display(self, obj):
        return f"#{obj.matchNumber}" if obj.matchNumber else "-"
    match_number_display.short_description = "No."
    
    def win_team_display(self, obj):
        teams = {0: ('Pending', '#D97706'), 1: ('Meron', '#059669'), 2: ('Wala', '#C5930A'), 
                 3: ('Draw', '#2563EB'), 4: ('Cancelled', '#DC2626')}
        label, color = teams.get(obj.winTeam, ('Unknown', 'gray'))
        return format_html('<span style="color:{};font-weight:bold;">{}</span>', color, label)
    win_team_display.short_description = "Winner"
    
    def bets_by_team(self, obj):
        bets = CockfightMatchBet.objects.filter(matchType='A', matchId=str(obj.pk))
        team_a = bets.filter(betTeam=1).count()
        team_b = bets.filter(betTeam=2).count()
        draw = bets.filter(betTeam=3).count()
        total = team_a + team_b + draw
        if total == 0:
            return "0"
        return format_html(
            '<span title="A:{} B:{} D:{}">{} <small style="color:#666;">(A:{} B:{} D:{})</small></span>',
            team_a, team_b, draw, total, team_a, team_b, draw
        )
    bets_by_team.short_description = "Bets"
    
    def total_amount(self, obj):
        bets = CockfightMatchBet.objects.filter(matchType='A', matchId=str(obj.pk))
        total = bets.aggregate(total=Coalesce(Sum('amount'), 0))['total']
        if total == 0:
            return "₹0"
        # Per team breakdown
        amt_a = bets.filter(betTeam=1).aggregate(t=Coalesce(Sum('amount'), 0))['t']
        amt_b = bets.filter(betTeam=2).aggregate(t=Coalesce(Sum('amount'), 0))['t']
        amt_d = bets.filter(betTeam=3).aggregate(t=Coalesce(Sum('amount'), 0))['t']
        return format_html(
            '₹{} <small style="color:#666;">(A:₹{} B:₹{} D:₹{})</small>',
            f"{total:,}", f"{amt_a:,}", f"{amt_b:,}", f"{amt_d:,}"
        )
    total_amount.short_description = "Total Bet"
    
    def profit_loss(self, obj):
        if obj.winTeam == 0:
            return format_html('<span style="color:#D97706;">Pending</span>')
        if obj.winTeam == 4:
            return format_html('<span style="color:#666;">Cancelled (₹0)</span>')
        
        bets = CockfightMatchBet.objects.filter(matchType='A', matchId=str(obj.pk))
        total_bet_amount = bets.aggregate(total=Coalesce(Sum('amount'), 0))['total']
        
        winning_bets = bets.filter(betTeam=obj.winTeam)
        total_payout = Decimal('0')
        for bet in winning_bets:
            total_payout += Decimal(bet.amount) + (Decimal(bet.amount) * Decimal(str(bet.betRatio)))
        
        pl = Decimal(total_bet_amount) - total_payout
        if pl >= 0:
            return format_html('<span style="color:#059669;font-weight:bold;">+₹{}</span>', f"{pl:,.2f}")
        else:
            return format_html('<span style="color:#DC2626;font-weight:bold;">-₹{}</span>', f"{abs(pl):,.2f}")
    profit_loss.short_description = "P/L"
    
    def recording_display(self, obj):
        if obj.recordingStatus == 'completed' and obj.recordingFile:
            video_url = f'/media/{obj.recordingFile}'
            html = (
                '<a href="{}" target="_blank" style="color:#059669;text-decoration:none;font-weight:600;">'
                '&#9658; Video</a>'
            ).format(video_url)
            # Add screenshot link if available
            screenshot_file = getattr(obj, 'screenshotFile', None)
            if screenshot_file:
                screenshot_url = f'/media/{screenshot_file}'
                html += (
                    ' <a href="{}" target="_blank" style="color:#D97706;text-decoration:none;font-weight:600;margin-left:6px;">'
                    '&#128247; Shot</a>'
                ).format(screenshot_url)
            return format_html(html)
        elif obj.recordingStatus == 'recording':
            return format_html('<span style="color:#DC2626;font-weight:600;">&#9679; REC</span>')
        elif obj.recordingStatus == 'failed':
            return format_html('<span style="color:#666;">&#10007; Failed</span>')
        return format_html('<span style="color:#999;">-</span>')
    recording_display.short_description = "Proof"
    
    def odds_display(self, obj):
        if not obj.oddsSnapshot:
            return "-"
        try:
            odds = json.loads(obj.oddsSnapshot)
            r = odds.get('R', '-')
            u = odds.get('U', '-')
            s = odds.get('S', '-')
            v = odds.get('V', '-')
            return format_html(
                '<small>A:{}-{} B:{}-{}</small>',
                u, r, v, s
            )
        except (json.JSONDecodeError, TypeError):
            return "-"
    odds_display.short_description = "Odds"
    
    def duration_display(self, obj):
        if obj.bettingOpenedAt and obj.bettingClosedAt:
            delta = obj.bettingClosedAt - obj.bettingOpenedAt
            mins = int(delta.total_seconds() // 60)
            secs = int(delta.total_seconds() % 60)
            return f"{mins}m {secs}s"
        elif obj.bettingOpenedAt and not obj.bettingClosedAt and obj.winTeam == 0:
            return format_html('<span style="color:#059669;">Live</span>')
        return "-"
    duration_display.short_description = "Duration"
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('china-market-toggle/', self.admin_site.admin_view(self.toggle_auto_match), 
                 name='china_market_toggle'),
            path('china-market-save-odds/', self.admin_site.admin_view(self.save_odds), 
                 name='china_market_save_odds'),
            path('china-market-declare-winner/', self.admin_site.admin_view(self.declare_winner_manual), 
                 name='china_market_declare_winner'),
        ]
        return custom_urls + urls
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        
        # Get current state
        state, _ = AutoMatchPollingState.objects.get_or_create(id=1)
        
        # Get IS_CF_AUTO_ENABLE from DB
        is_enabled = is_china_market_enabled()
        
        # Get odds settings
        odds_settings = {}
        for key in ['R', 'S', 'T', 'U', 'V', 'W']:
            try:
                s = Setting.objects.get(action=key)
                odds_settings[key] = s.actionValue
            except Setting.DoesNotExist:
                odds_settings[key] = ''
        
        # Get win rate stats
        from django.db.models import Count
        total_matches = CockfightAutoMatch.objects.filter(winTeam__in=[1,2,3]).count()
        if total_matches > 0:
            team_a_wins = CockfightAutoMatch.objects.filter(winTeam=1).count()
            team_b_wins = CockfightAutoMatch.objects.filter(winTeam=2).count()
            draw_wins = CockfightAutoMatch.objects.filter(winTeam=3).count()
            win_stats = {
                'total': total_matches,
                'team_a': team_a_wins,
                'team_a_pct': round(team_a_wins/total_matches*100, 1),
                'team_b': team_b_wins,
                'team_b_pct': round(team_b_wins/total_matches*100, 1),
                'draw': draw_wins,
                'draw_pct': round(draw_wins/total_matches*100, 1),
            }
        else:
            win_stats = None
        
        extra_context.update({
            'is_enabled': is_enabled,
            'state': state,
            'odds_settings': odds_settings,
            'win_stats': win_stats,
            'show_china_market_panel': True,
        })
        
        return super().changelist_view(request, extra_context=extra_context)
    
    def toggle_auto_match(self, request):
        """Toggle the auto match on/off via DB Setting Y."""
        if request.method == 'POST':
            current = is_china_market_enabled()
            new_value = 'N' if current else 'Y'
            
            Setting.objects.update_or_create(
                action='Y',
                defaults={'actionValue': new_value}
            )
            
            # If disabling, reset the polling state
            if new_value == 'N':
                state, _ = AutoMatchPollingState.objects.get_or_create(id=1)
                state.isAcceptingBet = False
                state.save()
            
            return JsonResponse({'success': True, 'enabled': new_value == 'Y'})
        return JsonResponse({'error': 'POST required'}, status=405)
    
    def save_odds(self, request):
        """Save odds settings."""
        if request.method == 'POST':
            for key in ['R', 'S', 'T', 'U', 'V', 'W']:
                value = request.POST.get(key, '').strip()
                if value:
                    Setting.objects.update_or_create(
                        action=key,
                        defaults={'actionValue': value}
                    )
            return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/cockfightManager/cockfightautomatch/'))
        return JsonResponse({'error': 'POST required'}, status=405)
    
    def declare_winner_manual(self, request):
        """Manually declare winner for an auto match."""
        if request.method == 'POST':
            match_id = request.POST.get('match_id')
            win_team = int(request.POST.get('win_team', 0))
            
            if not match_id or win_team not in [1, 2, 3, 4]:
                return JsonResponse({'error': 'Invalid match_id or win_team'}, status=400)
            
            try:
                match = CockfightAutoMatch.objects.get(pk=match_id)
                if match.processed:
                    return JsonResponse({'error': 'Match already processed'}, status=400)
                match.winTeam = win_team
                match.save()
                return JsonResponse({'success': True, 'message': f'Winner declared: Team {win_team}'})
            except CockfightAutoMatch.DoesNotExist:
                return JsonResponse({'error': 'Match not found'}, status=404)
        return JsonResponse({'error': 'POST required'}, status=405)


# Register
admin.site.register(CockfightAutoMatch, ChinaMarketAdmin)
