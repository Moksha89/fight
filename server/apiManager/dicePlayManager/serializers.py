from rest_framework import serializers
from rest_framework.pagination import PageNumberPagination

from base.models import Setting
from dicePlayManager.models import Board, DicePlayMatch, DicePlayMatchBet


class DicePlayMatchSerializer(serializers.ModelSerializer):
    """Compact for match result WS."""
    class Meta:
        model = DicePlayMatch
        fields = [
            "id", "title", "board", "match_type", "isLive", "isBettingEnabled",
            "total1Rolled", "total2Rolled", "total3Rolled",
            "total4Rolled", "total5Rolled", "total6Rolled",
            "dice_result_json", "isWinnerDeclared", "updated_at",
            "game_hash", "daily_match_number", "match_date", "virtual_phase",
            "commitment_hash", "client_seed", "nonce", "server_seed_revealed",
        ]


class DicePlayMatchDeepListSerializer(serializers.ModelSerializer):
    """Full match for board listing (WS / API)."""
    class Meta:
        model = DicePlayMatch
        fields = [
            "id", "title", "board", "match_type", "isLive", "isBettingEnabled",
            "youtubeLiveLink", "promoVideo", "liveDate",
            "total1Rolled", "total2Rolled", "total3Rolled",
            "total4Rolled", "total5Rolled", "total6Rolled",
            "dice_result_json", "isWinnerDeclared", "created_at", "updated_at",
            "game_hash", "daily_match_number", "match_date", "virtual_phase", "phase_started_at",
            "commitment_hash", "client_seed", "nonce", "server_seed_revealed",
        ]


class BoardWithMatchesSerializer(serializers.ModelSerializer):
    matches = serializers.SerializerMethodField()

    class Meta:
        model = Board
        fields = [
            "id", "name", "is_virtual",
            "virtual_betting_seconds", "virtual_shuffle_seconds", "virtual_result_seconds",
            "matches",
        ]

    def get_matches(self, board):
        # Include: undecided matches + matches in result phase + recent completed
        undecided = board.diceplaymatch_set.filter(isWinnerDeclared=False).exclude(virtual_phase="done")
        # Include matches currently in result display phase (even though winner is declared)
        in_result_phase = board.diceplaymatch_set.filter(
            isWinnerDeclared=True, virtual_phase="result"
        )
        completed = (
            board.diceplaymatch_set.filter(isWinnerDeclared=True, virtual_phase="done")
            .order_by("-updated_at")[:20]
        )
        matches = list(undecided) + list(in_result_phase) + list(completed)
        return DicePlayMatchDeepListSerializer(matches, many=True).data


class DicePlayMatchBetMatchInfoSerializer(serializers.ModelSerializer):
    """Minimal match info to include in bet history."""
    class Meta:
        model = DicePlayMatch
        fields = [
            "id", "daily_match_number", "match_date", "dice_result_json",
            "total1Rolled", "total2Rolled", "total3Rolled",
            "total4Rolled", "total5Rolled", "total6Rolled",
            "isWinnerDeclared", "virtual_phase", "game_hash", "match_type",
        ]


class DicePlayMatchBetSerializer(serializers.ModelSerializer):
    match_info = DicePlayMatchBetMatchInfoSerializer(source="match", read_only=True)

    class Meta:
        model = DicePlayMatchBet
        fields = [
            "id", "match", "diceNumber", "amount",
            "matchWinStatus", "rolled_count", "payout_amount",
            "createdDate", "match_info",
        ]
        read_only_fields = ["id", "matchWinStatus", "rolled_count", "payout_amount", "createdDate"]


class PlaceDiceBetSerializer(serializers.Serializer):
    matchId = serializers.IntegerField()
    diceNumber = serializers.IntegerField(min_value=1, max_value=6)
    amount = serializers.IntegerField(min_value=1)

    def validate(self, data):
        request = self.context["request"]
        user = request.user
        if data["amount"] > user.wallet.balance:
            raise serializers.ValidationError("Insufficient wallet balance.")
        try:
            match = DicePlayMatch.objects.get(
                pk=data["matchId"],
                isLive=True,
                isBettingEnabled=True,
                isWinnerDeclared=False,
            )
        except DicePlayMatch.DoesNotExist:
            raise serializers.ValidationError(
                "No live match with betting enabled found for this match ID."
            )
        data["_match"] = match

        try:
            max_bet_setting = Setting.objects.get(action="Q")
            max_bet = int(max_bet_setting.actionValue.strip())
            if max_bet > 0 and data["amount"] > max_bet:
                raise serializers.ValidationError(
                    {"amount": f"Bet amount cannot exceed {max_bet}."}
                )
        except (Setting.DoesNotExist, ValueError):
            pass

        return data


class BoardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Board
        fields = ["id", "name", "is_virtual", "virtual_betting_seconds"]


class DicePlayMatchPagination(PageNumberPagination):
    page_size = 20

    def get_paginated_data(self, queryset, request, view):
        page = self.paginate_queryset(queryset, request, view=view)
        serializer = DicePlayMatchSerializer(page, many=True, context={"request": request})
        return self.get_paginated_response(serializer.data).data
