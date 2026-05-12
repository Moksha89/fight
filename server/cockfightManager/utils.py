from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from cockfightManager.models import Zone, CockfightMatch, MatchPremiumHighlights
from apiManager.cockfightManager.serializers import ZoneWithMatchesSerializer
from django.db.models import Prefetch


def broadcast_manual_match_update():
    non_winner_qs = CockfightMatch.objects.filter(
        isWinnerDeclared=False
    ).prefetch_related(
        Prefetch('matchpremiumhighlights_set',
                 queryset=MatchPremiumHighlights.objects.all())
    )

    zones = Zone.objects.prefetch_related(
        Prefetch('cockfightmatch_set', queryset=non_winner_qs)
    ).filter(is_active=True)

    data = ZoneWithMatchesSerializer(zones, many=True).data

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "match_updates",
        {
            "type": "send_manual_match_update",
            "data": data
        }
    )
