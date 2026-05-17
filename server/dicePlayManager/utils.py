from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from apiManager.dicePlayManager.serializers import BoardWithMatchesSerializer, DicePlayMatchSerializer
from .models import Board, DicePlayMatch
from django.db.models import Prefetch, Q


def broadcast_dice_match_update():
    """Broadcast current boards and their non-finished matches to WS group.
    Includes matches in result display phase so frontend can show results."""
    # Include: undecided OR currently in result display phase
    active_qs = DicePlayMatch.objects.filter(
        Q(isWinnerDeclared=False) | Q(virtual_phase="result")
    )
    boards = Board.objects.prefetch_related(
        Prefetch("diceplaymatch_set", queryset=active_qs)
    ).filter(is_active=True)
    data = BoardWithMatchesSerializer(boards, many=True).data
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "dice_match_updates",
        {"type": "send_dice_match_update", "data": data},
    )


def broadcast_dice_result(match):
    """Send result event on the dice_match_result channel when winner is declared."""
    data = DicePlayMatchSerializer(match).data
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "dice_match_result",
        {
            "type": "send_dice_match_result",
            "result_type": "dice_result",
            "data": data,
        },
    )
