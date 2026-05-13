from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from cockfightManager.models import *
from .serializers import *

from wallet.models import Wallet, WalletHistory
from kokoroko.throttles import CockfightBetThrottle
from kokoroko.cache_helpers import get_cached_or_set, KEYS, TTL

from django.db import transaction
from django.db.models import F


class CockfightAutoMatchViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CockfightAutoMatch.objects.filter(processed=True).order_by("-id")
    serializer_class = CockfightAutoMatchSerializer
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request, *args, **kwargs):
        def _fetch():
            qs = CockfightAutoMatch.objects.filter(processed=True).order_by("-id")
            return list(CockfightAutoMatchSerializer(qs, many=True).data)

        data = get_cached_or_set(
            KEYS["cockfight_results"], _fetch, TTL["cockfight_results"]
        )
        return Response(data)


class CockfightMatchBetViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CockfightMatchBetSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CockfightMatchBet.objects.filter(customer=self.request.user).order_by('-createdDate')

    @action(detail=False, methods=['post'], url_path='place-bet',
            throttle_classes=[CockfightBetThrottle])
    def place_bet(self, request):
        serializer = PlaceBetSerializer(
            data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        wallet = user.wallet
        data = serializer.validated_data
        amount = int(data['amount'])
        match_type = data['matchType']
        bet_team = data['betTeam']
        ratio = data['betRatio']

        # First: Handle Auto Match
        if match_type == 'A':
            state, _ = AutoMatchPollingState.objects.get_or_create(id=1)
            if not state.isAcceptingBet:
                return Response({"detail": "Bet not allowed."}, status=status.HTTP_406_NOT_ACCEPTABLE)
            match_id = state.runningAutoMatchId

        # Then: Handle Manual Match
        elif match_type == 'M':
            match_id = serializer.context.get('validated_match_id')
            if not match_id:
                return Response({"detail": "Validated match ID not found."}, status=status.HTTP_400_BAD_REQUEST)

        else:
            return Response({"detail": "Invalid match type."}, status=status.HTTP_400_BAD_REQUEST)

        # Wallet deduction & bet creation inside transaction
        with transaction.atomic():
            wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
            if wallet.balance < amount:
                return Response({"detail": "Insufficient wallet balance."}, status=status.HTTP_400_BAD_REQUEST)

            wallet.balance = F('balance') - amount
            wallet.save()

            bet = CockfightMatchBet.objects.create(
                matchId=match_id,
                matchType=match_type,
                customer=user,
                betTeam=bet_team,
                amount=amount,
                betRatio=ratio
            )

            WalletHistory.objects.create(
                wallet=wallet,
                transaction_type='F',
                transactionId=str(bet.id),
                change=amount,
                isSuccess=False,
                description=f"Cockfight bet of ₹{amount} on team {'meron' if bet.betTeam == 1 else 'wala' if bet_team == 2 else 'draw'} for {'manual' if match_type == 'M' else 'auto'} match {bet.matchId}"
            )

        return Response({
            "message": "Bet placed successfully.",
            "bet": CockfightMatchBetSerializer(bet).data
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='pending-bets')
    def pending_bets(self, request):
        user = request.user
        pending_bets = CockfightMatchBet.objects.filter(
            customer=user,
            matchWinStatus=0
        ).order_by('-createdDate')

        serializer = self.get_serializer(pending_bets, many=True)
        return Response(serializer.data)


class OddsViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='current')
    def current_odds(self, request):
        from cockfightManager.odds_engine import get_current_odds, get_pool_odds_for_match, get_odds_config
        config = get_odds_config()
        odds = get_current_odds()

        if config.odds_system == 'pool':
            state, _ = AutoMatchPollingState.objects.get_or_create(id=1)
            if state.runningAutoMatchId:
                pool_odds = get_pool_odds_for_match(state.runningAutoMatchId)
                odds.update(pool_odds)

        odds['system_display'] = config.get_odds_system_display()
        for k, v in odds.items():
            if hasattr(v, 'quantize'):
                odds[k] = str(v)
        return Response(odds)


class ZoneViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ZoneSerializer

    def get_queryset(self):
        return Zone.objects.filter(is_active=True).order_by('name')

    def list(self, request, *args, **kwargs):
        def _fetch():
            qs = Zone.objects.filter(is_active=True).order_by('name')
            return list(ZoneSerializer(qs, many=True).data)

        data = get_cached_or_set(KEYS["zones"], _fetch, TTL["zones"])
        return Response(data)
