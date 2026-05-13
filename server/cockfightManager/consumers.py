import json
from apiManager.cockfightManager.serializers import ZoneWithMatchesSerializer
from cockfightManager.models import AutoMatchPollingState, CockfightMatch, MatchPremiumHighlights, Zone
from asgiref.sync import sync_to_async
from django.db.models import Prefetch
from rest_framework.renderers import JSONRenderer
from kokoroko.ws_protection import ProtectedConsumer


class MatchResultConsumer(ProtectedConsumer):
    async def on_connect(self):
        await self.channel_layer.group_add("match_result", self.channel_name)

    async def on_disconnect(self, close_code):
        await self.channel_layer.group_discard("match_result", self.channel_name)

    async def send_match_result(self, event):
        await self.send(text_data=json.dumps({
            "type": event["result_type"],
            "data": event["data"]
        }))


class MatchConsumer(ProtectedConsumer):
    async def on_connect(self):
        self.group_name = "match_updates"
        await self.channel_layer.group_add(self.group_name, self.channel_name)

        # 1. Send initial auto match state
        auto_match_data = await self.get_initial_match_data()
        if auto_match_data:
            await self.send(text_data=json.dumps({
                "type": "accepting_auto_bet_update",
                "data": auto_match_data,
            }))

        # 2. Send initial manual match data
        manual_match_data = await self.get_manual_matches_data()
        await self.send(text_data=JSONRenderer().render({
            "type": "manual_match_update",
            "data": manual_match_data,
        }).decode("utf-8"))

    async def on_disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def send_accepting_auto_bet_update(self, event):
        await self.send(text_data=json.dumps({
            "type": "accepting_auto_bet_update",
            "data": event["data"]
        }))

    async def send_manual_match_update(self, event):
        await self.send(text_data=json.dumps({
            "type": "manual_match_update",
            "data": event["data"]
        }))

    @sync_to_async
    def get_initial_match_data(self):
        try:
            match = AutoMatchPollingState.objects.get(id=1)
            return {
                "isAcceptingBet": match.isAcceptingBet,
                "matchNumber": match.matchNumber,
                "matchId": match.runningAutoMatchId,
                "liveUrl": match.liveUrl,
            }
        except AutoMatchPollingState.DoesNotExist:
            return None

    @sync_to_async
    def get_manual_matches_data(self):
        non_winner_matches_qs = CockfightMatch.objects.filter(
            isWinnerDeclared=False
        ).prefetch_related(
            Prefetch(
                'matchpremiumhighlights_set',
                queryset=MatchPremiumHighlights.objects.all()
            )
        )

        zones = Zone.objects.prefetch_related(
            Prefetch('cockfightmatch_set', queryset=non_winner_matches_qs)
        ).filter(is_active=True)

        return ZoneWithMatchesSerializer(zones, many=True).data
