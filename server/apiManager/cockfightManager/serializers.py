from decimal import Decimal
from rest_framework import serializers
from base.models import Setting
from cockfightManager.models import CockfightMatchBet, CockfightAutoMatch, CockfightMatch, MatchPremiumHighlights, Zone
from rest_framework.pagination import PageNumberPagination


class CockfightAutoMatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = CockfightAutoMatch
        fields = ['id', 'matchNumber', 'winTeam', 'createdDate', 'recordingStatus', 'recordingFile', 'screenshotFile']


class CockfightMatchBetSerializer(serializers.ModelSerializer):
    matchNumber = serializers.SerializerMethodField()

    class Meta:
        model = CockfightMatchBet
        fields = ['id', 'matchId', 'matchType', 'betTeam',
                  'amount', 'betRatio', 'matchWinStatus', 'createdDate', 'matchNumber']
        read_only_fields = ['id', 'matchId', 'matchWinStatus', 'createdDate']

    def get_matchNumber(self, obj):
        try:
            if obj.matchType == 'A':
                match = CockfightAutoMatch.objects.filter(pk=obj.matchId).first()
                return match.matchNumber if match else None
            elif obj.matchType == 'M':
                match = CockfightMatch.objects.filter(pk=obj.matchId).first()
                return match.title if match else None
        except Exception:
            return None
        return None


class PlaceBetSerializer(serializers.Serializer):
    matchType = serializers.ChoiceField(
        choices=CockfightMatchBet.MATCH_TYPE_CHOICE)
    betTeam = serializers.IntegerField()
    amount = serializers.IntegerField(min_value=1)
    betRatio = serializers.DecimalField(max_digits=5, decimal_places=2)

    def validate(self, data):
        request = self.context['request']
        user = request.user
        wallet = user.wallet

        if data['amount'] > wallet.balance:
            raise serializers.ValidationError("Insufficient wallet balance.")

        match_type = data['matchType']
        bet_team = data['betTeam']
        ratio = data['betRatio']

        if match_type == 'A':
            if bet_team not in [1, 2, 3]:
                raise serializers.ValidationError(
                    "Invalid bet team for auto match.")

            from cockfightManager.odds_engine import get_current_odds, get_pool_odds_for_match, get_odds_config
            config = get_odds_config()

            if config.odds_system == 'pool':
                from cockfightManager.models import AutoMatchPollingState
                state, _ = AutoMatchPollingState.objects.get_or_create(id=1)
                if state.runningAutoMatchId:
                    pool = get_pool_odds_for_match(state.runningAutoMatchId)
                    team_key = {1: 'meron', 2: 'wala', 3: 'draw'}[bet_team]
                    lower = pool.get(f'{team_key}_min', Decimal('0.10'))
                    upper = pool.get(f'{team_key}_max', Decimal('5.00'))
                else:
                    raise serializers.ValidationError("No active match for pool odds.")
            else:
                odds = get_current_odds()
                team_key = {1: 'meron', 2: 'wala', 3: 'draw'}[bet_team]
                lower = odds.get(f'{team_key}_min', Decimal('0.50'))
                upper = odds.get(f'{team_key}_max', Decimal('0.95'))

            if not (lower <= ratio <= upper):
                raise serializers.ValidationError(
                    f"Ratio should be between {lower} and {upper} for Team {bet_team}.")

        elif match_type == 'M':
            zone_id = request.query_params.get('zone')
            if not zone_id:
                raise serializers.ValidationError(
                    "Zone ID is required for manual match.")

            try:
                match = CockfightMatch.objects.get(
                    zone_id=zone_id,
                    isLive=True,
                    isWinnerDeclared=False
                )
            except CockfightMatch.DoesNotExist:
                raise serializers.ValidationError(
                    "No live manual match found in this zone.")

            team_thresholds = {
                1: (match.minThresholdTeamA, match.maxThresholdTeamA),
                2: (match.minThresholdTeamB, match.maxThresholdTeamB),
                3: (match.minThresholdTeamDraw, match.maxThresholdTeamDraw),
            }

            if bet_team not in team_thresholds:
                raise serializers.ValidationError(
                    "Invalid bet team for manual match.")

            min_ratio, max_ratio = team_thresholds[bet_team]
            if min_ratio is None or max_ratio is None:
                raise serializers.ValidationError(
                    "Thresholds are not properly set for this team.")

            if not (min_ratio <= ratio <= max_ratio):
                raise serializers.ValidationError(
                    f"Ratio should be between {min_ratio} and {max_ratio} for Team {bet_team}.")

            self.context['validated_match_id'] = match.id

        return data


class CockfightMatchMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = CockfightMatch
        fields = [
            'id',
            'title',
            'zone',
            'winTeam',
            'updated_at',
        ]


class CockfightMatchPagination(PageNumberPagination):
    page_size = 20

    def get_paginated_data(self, queryset, request, view):
        page = self.paginate_queryset(queryset, request, view=view)
        serializer = CockfightMatchSerializer(
            page, many=True, context={'request': request})
        return self.get_paginated_response(serializer.data).data


class ZoneSerializer(serializers.ModelSerializer):
    matches = serializers.SerializerMethodField()

    class Meta:
        model = Zone
        fields = ['id', 'name', 'matches']

    def get_matches(self, obj):
        request = self.context.get('request')
        view = self.context.get('view')
        matches_qs = CockfightMatch.objects.filter(
            zone=obj).order_by('-liveDate')

        paginator = CockfightMatchPagination()
        paginated_data = paginator.get_paginated_data(
            matches_qs, request, view)
        return paginated_data


class MatchPremiumHighlightsSerializer(serializers.ModelSerializer):
    class Meta:
        model = MatchPremiumHighlights
        fields = ['id', 'title', 'video']


class CockfightMatchDeepListSerializer(serializers.ModelSerializer):
    premiumHighlights = MatchPremiumHighlightsSerializer(
        source='matchpremiumhighlights_set', many=True
    )

    minThresholdTeamA = serializers.FloatField(allow_null=True)
    maxThresholdTeamA = serializers.FloatField(allow_null=True)
    minThresholdTeamB = serializers.FloatField(allow_null=True)
    maxThresholdTeamB = serializers.FloatField(allow_null=True)
    minThresholdTeamDraw = serializers.FloatField(allow_null=True)
    maxThresholdTeamDraw = serializers.FloatField(allow_null=True)

    class Meta:
        model = CockfightMatch
        fields = [
            'id', 'title', 'isLive', 'isBettingEnabled',
            'youtubeLiveLink', 'promoVideo', 'liveDate',
            'teamAIcon', 'teamBIcon', 'teamAName', 'teamBName',
            'minThresholdTeamA', 'maxThresholdTeamA',
            'minThresholdTeamB', 'maxThresholdTeamB',
            'minThresholdTeamDraw', 'maxThresholdTeamDraw',
            'winTeam',
            'created_at', 'updated_at', 'premiumHighlights',
            'match_mode', 'matchVideo', 'scheduledStart',
            'bettingOpensAt', 'bettingDurationMinutes',
        ]


class ZoneWithMatchesSerializer(serializers.ModelSerializer):
    matches = serializers.SerializerMethodField()

    class Meta:
        model = Zone
        fields = ['id', 'name', 'matches']

    def get_matches(self, zone):
        matches = zone.cockfightmatch_set.all()
        return CockfightMatchDeepListSerializer(matches, many=True).data


class CockfightMatchSerializer(serializers.ModelSerializer):
    minThresholdTeamA = serializers.FloatField(allow_null=True)
    maxThresholdTeamA = serializers.FloatField(allow_null=True)
    minThresholdTeamB = serializers.FloatField(allow_null=True)
    maxThresholdTeamB = serializers.FloatField(allow_null=True)
    minThresholdTeamDraw = serializers.FloatField(allow_null=True)
    maxThresholdTeamDraw = serializers.FloatField(allow_null=True)

    class Meta:
        model = CockfightMatch
        fields = [
            'id', 'title', 'zone', 'winTeam', 'updated_at',
            'isLive', 'isBettingEnabled', 'youtubeLiveLink',
            'teamAName', 'teamBName', 'teamAIcon', 'teamBIcon',
            'minThresholdTeamA', 'maxThresholdTeamA',
            'minThresholdTeamB', 'maxThresholdTeamB',
            'minThresholdTeamDraw', 'maxThresholdTeamDraw',
            'liveDate', 'match_mode', 'matchVideo',
            'scheduledStart', 'bettingOpensAt',
        ]
