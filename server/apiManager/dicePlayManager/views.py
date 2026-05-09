from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.db.models import F

from dicePlayManager.models import Board, DicePlayMatch, DicePlayMatchBet
from dicePlayManager.tasks import auto_roll_virtual_match, create_next_virtual_round
from wallet.models import WalletHistory
from .serializers import (
    BoardSerializer,
    BoardWithMatchesSerializer,
    DicePlayMatchSerializer,
    DicePlayMatchBetSerializer,
    PlaceDiceBetSerializer,
)


class BoardViewSet(viewsets.ReadOnlyModelViewSet):
    """List boards with their live/undecided matches (for app)."""
    serializer_class = BoardWithMatchesSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Board.objects.filter(is_active=True).order_by("name")

    @action(detail=True, methods=["post"], url_path="start-virtual")
    def start_virtual(self, request, pk=None):
        """Start a new virtual round on this board (admin only or auto-triggered)."""
        board = self.get_object()
        if not board.is_virtual:
            return Response({"detail": "This board is not configured for virtual mode."}, status=status.HTTP_400_BAD_REQUEST)

        active = DicePlayMatch.objects.filter(board=board, isWinnerDeclared=False).exists()
        if active:
            return Response({"detail": "Board already has an active match."}, status=status.HTTP_400_BAD_REQUEST)

        create_next_virtual_round.delay(board.id)
        return Response({"message": "Virtual round starting..."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="roll-dice")
    def roll_dice(self, request, pk=None):
        """Trigger the dice roll for the active virtual match on this board."""
        board = self.get_object()
        try:
            match = DicePlayMatch.objects.get(
                board=board, isLive=True, isWinnerDeclared=False, match_type="V"
            )
        except DicePlayMatch.DoesNotExist:
            return Response({"detail": "No active virtual match on this board."}, status=status.HTTP_404_NOT_FOUND)

        auto_roll_virtual_match.delay(match.id)
        return Response({"message": "Dice rolling...", "match_id": match.id}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="match-results")
    def match_results(self, request):
        """Get recent completed virtual dice match results, newest first."""
        board_id = request.query_params.get("board_id")
        limit = min(int(request.query_params.get("limit", 50)), 100)
        qs = DicePlayMatch.objects.filter(
            match_type="V",
            isWinnerDeclared=True,
        ).order_by("-updated_at")
        if board_id:
            qs = qs.filter(board_id=board_id)
        qs = qs[:limit]
        return Response(DicePlayMatchSerializer(qs, many=True).data)


class DicePlayMatchBetViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DicePlayMatchBetSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return (
            DicePlayMatchBet.objects.filter(customer=self.request.user)
            .select_related("match", "match__board")
            .order_by("-createdDate")
        )

    @action(detail=False, methods=["post"], url_path="place-bet")
    def place_bet(self, request):
        serializer = PlaceDiceBetSerializer(
            data=request.data, context={"request": request}
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        wallet = user.wallet
        data = serializer.validated_data
        match = data["_match"]
        amount = data["amount"]
        dice_number = data["diceNumber"]

        with transaction.atomic():
            wallet.refresh_from_db()
            if wallet.balance < amount:
                return Response(
                    {"detail": "Insufficient wallet balance."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            wallet.balance = F("balance") - amount
            wallet.save()

            bet = DicePlayMatchBet.objects.create(
                match=match,
                customer=user,
                diceNumber=dice_number,
                amount=amount,
            )
            WalletHistory.objects.create(
                wallet=wallet,
                transaction_type="I",
                transactionId=str(bet.id),
                change=amount,
                isSuccess=False,
                description=f"Dice Game #{match.daily_match_number} bet {amount} on face {dice_number}",
            )

        return Response(
            {
                "message": "Bet placed successfully.",
                "bet": DicePlayMatchBetSerializer(bet).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"], url_path="pending-bets")
    def pending_bets(self, request):
        pending = DicePlayMatchBet.objects.filter(
            customer=request.user, matchWinStatus=0
        ).select_related("match").order_by("-createdDate")
        return Response(DicePlayMatchBetSerializer(pending, many=True).data)
