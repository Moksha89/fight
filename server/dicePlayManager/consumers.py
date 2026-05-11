import json
from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.db.models import Prefetch

from apiManager.dicePlayManager.serializers import BoardWithMatchesSerializer
from .models import Board, DicePlayMatch


class DiceMatchResultConsumer(AsyncWebsocketConsumer):
    """WebSocket for dice match result (winner declared) updates."""

    async def connect(self):
        user = self.scope["user"]
        if user.is_anonymous:
            await self.close()
            return
        await self.channel_layer.group_add("dice_match_result", self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("dice_match_result", self.channel_name)

    async def send_dice_match_result(self, event):
        await self.send(text_data=json.dumps({
            "type": event["result_type"],
            "data": event["data"],
        }))


class DiceMatchConsumer(AsyncWebsocketConsumer):
    """WebSocket for dice match list updates (boards + matches, betting on/off)."""

    async def connect(self):
        user = self.scope["user"]
        if user.is_anonymous:
            await self.close()
            return
        self.group_name = "dice_match_updates"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        data = await self.get_initial_data()
        await self.send(text_data=json.dumps({"type": "dice_match_update", "data": data}))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def send_dice_match_update(self, event):
        await self.send(text_data=json.dumps({
            "type": "dice_match_update",
            "data": event["data"],
        }))

    @sync_to_async
    def get_initial_data(self):
        non_winner = DicePlayMatch.objects.filter(isWinnerDeclared=False)
        boards = Board.objects.prefetch_related(
            Prefetch("diceplaymatch_set", queryset=non_winner)
        ).filter(is_active=True)
        return BoardWithMatchesSerializer(boards, many=True).data
