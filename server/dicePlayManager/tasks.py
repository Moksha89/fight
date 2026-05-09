import hashlib
import secrets
from datetime import timedelta, date, datetime, time, timezone as dt_tz
from decimal import Decimal
from celery import shared_task
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from wallet.models import WalletHistory
from .models import DicePlayMatch, DicePlayMatchBet

IST_OFFSET = dt_tz(timedelta(hours=5, minutes=30))


def get_ist_now():
    """Current time in IST."""
    return timezone.now().astimezone(IST_OFFSET)


def get_ist_date():
    """Current date in IST."""
    return get_ist_now().date()


def generate_game_hash(board_id, match_date, daily_number, server_seed=None):
    """Generate a unique SHA-256 hash for game verification."""
    if not server_seed:
        server_seed = secrets.token_hex(32)
    raw = f"{board_id}:{match_date}:{daily_number}:{server_seed}"
    return hashlib.sha256(raw.encode()).hexdigest()


def get_rolled_count(match, dice_number):
    """Return count rolled for face 1-6."""
    attr = f"total{dice_number}Rolled"
    return getattr(match, attr, 0)


def roll_six_dice():
    """Cryptographically secure roll of 6 dice. Returns list of 6 ints (1-6)."""
    return [secrets.randbelow(6) + 1 for _ in range(6)]


def count_dice(dice_list):
    """Count occurrences of each face. Returns dict {1:count,...,6:count}."""
    counts = {i: 0 for i in range(1, 7)}
    for d in dice_list:
        counts[d] += 1
    return counts


@shared_task
def process_single_dice_winning_bet(bet_id: int, payout: int):
    """Credit wallet for a winning dice bet."""
    try:
        bet = DicePlayMatchBet.objects.select_related("customer__wallet").get(id=bet_id)
        wallet = bet.customer.wallet
        amount_decimal = Decimal(payout)

        with transaction.atomic():
            wallet.balance = F("balance") + amount_decimal
            wallet.save()
            WalletHistory.objects.create(
                wallet=wallet,
                transaction_type="I",
                change=amount_decimal,
                isSuccess=True,
                description=f"Dice Game #{bet.match.daily_match_number} win: {bet.amount} on face {bet.diceNumber} (x{bet.rolled_count} = {payout})",
            )
    except Exception as e:
        return str(e)


@shared_task
def process_dice_play_match_result(match_id: int):
    """
    After winner is declared: for each bet on a dice number N, if totalNRolled >= 2,
    payout = rolled_count * amount. Mark bet won (1) or lost (2).
    """
    try:
        match = DicePlayMatch.objects.get(id=match_id)
        if match.processed:
            return "Already processed"

        bets = DicePlayMatchBet.objects.filter(match=match).select_related("customer__wallet")

        for bet in bets:
            rolled = get_rolled_count(match, bet.diceNumber)
            bet.rolled_count = rolled
            if rolled >= 2:
                payout = rolled * bet.amount
                bet.matchWinStatus = 1
                bet.save(update_fields=["matchWinStatus", "rolled_count", "updatedDate"])
                process_single_dice_winning_bet.delay(bet.id, payout)
            else:
                bet.matchWinStatus = 2
                bet.save(update_fields=["matchWinStatus", "rolled_count", "updatedDate"])

        match.processed = True
        match.save(update_fields=["processed", "updated_at"])
        return "Dice match result processed"
    except DicePlayMatch.DoesNotExist:
        return "Match not found"
    except Exception as e:
        return str(e)


@shared_task
def auto_roll_virtual_match(match_id: int):
    """
    For virtual matches: generate 6 dice results using secure RNG,
    set the counts, declare winner, and trigger settlement.
    Transitions match: betting -> betting_closed (3s pause) -> shuffling
    """
    try:
        match = DicePlayMatch.objects.get(id=match_id)
        if match.isWinnerDeclared or match.processed:
            return "Match already settled"
        if match.match_type != "V":
            return "Not a virtual match"

        # Roll 6 dice
        dice_list = roll_six_dice()
        counts = count_dice(dice_list)

        # Store the individual dice results
        match.dice_result_json = ",".join(str(d) for d in dice_list)

        # Set counts
        match.total1Rolled = counts[1]
        match.total2Rolled = counts[2]
        match.total3Rolled = counts[3]
        match.total4Rolled = counts[4]
        match.total5Rolled = counts[5]
        match.total6Rolled = counts[6]

        # Close betting, move to shuffling phase
        match.isBettingEnabled = False
        match.virtual_phase = "shuffling"
        match.phase_started_at = timezone.now()
        match.save(update_fields=[
            'dice_result_json',
            'total1Rolled', 'total2Rolled', 'total3Rolled',
            'total4Rolled', 'total5Rolled', 'total6Rolled',
            'isBettingEnabled', 'virtual_phase', 'phase_started_at', 'updated_at'
        ])

        return f"Virtual dice rolled: {dice_list}, entering shuffle phase"
    except DicePlayMatch.DoesNotExist:
        return "Match not found"
    except Exception as e:
        return str(e)


@shared_task
def declare_virtual_match_result(match_id: int):
    """Transition from shuffling -> result display phase. Declares winner and processes bets."""
    try:
        match = DicePlayMatch.objects.get(id=match_id)
        if match.isWinnerDeclared:
            return "Already declared"

        match.isWinnerDeclared = True
        match.virtual_phase = "result"
        match.phase_started_at = timezone.now()
        match.save()  # triggers post_save -> process_dice_play_match_result via model save()

        # Broadcast result on the result channel so frontend gets immediate notification
        try:
            from .utils import broadcast_dice_result
            broadcast_dice_result(match)
        except Exception:
            pass

        return f"Match {match_id} result declared, entering result display phase"
    except DicePlayMatch.DoesNotExist:
        return "Match not found"
    except Exception as e:
        return str(e)


@shared_task
def create_next_virtual_round(board_id: int):
    """
    After a virtual match settles, auto-create the next round.
    Uses daily match numbering (resets at 12:00 AM IST).
    """
    from .models import Board
    try:
        board = Board.objects.get(id=board_id)

        # Check no active undone match on this board
        active = DicePlayMatch.objects.filter(
            board=board, match_type="V"
        ).exclude(virtual_phase="done").exists()
        if active:
            return "Board already has an active match"

        # Check IST time bounds: only run between 12:00 AM and 11:59 PM IST
        ist_now = get_ist_now()
        today_ist = ist_now.date()

        # Get next daily match number
        todays_count = DicePlayMatch.objects.filter(
            board=board, match_type="V", match_date=today_ist
        ).count()
        daily_num = todays_count + 1

        # Generate unique game hash
        game_hash = generate_game_hash(board.id, today_ist, daily_num)

        match = DicePlayMatch.objects.create(
            board=board,
            title=f"Game #{daily_num}",
            match_type="V",
            isLive=True,
            isBettingEnabled=True,
            liveDate=timezone.now(),
            game_hash=game_hash,
            daily_match_number=daily_num,
            match_date=today_ist,
            virtual_phase="betting",
            phase_started_at=timezone.now(),
        )
        return f"Created Game #{daily_num} for {today_ist} (match {match.id}, hash: {game_hash[:12]}...)"
    except Board.DoesNotExist:
        return "Board not found"
    except Exception as e:
        return str(e)


@shared_task
def manage_virtual_dice_rounds():
    """
    Celery beat task: runs every 5 seconds.
    Manages the full virtual dice lifecycle:

    Phase 1 - BETTING (2 minutes): Users place bets
    Phase 2 - SHUFFLING (30 seconds): Dice are rolled, shuffle animation plays
    Phase 3 - RESULT (15 seconds): Result displayed with winner info
    Phase 4 - DONE: Create next round

    Schedule: 12:00 AM IST to 11:59 PM IST daily.
    Match numbers reset at midnight IST.
    """
    from .models import Board
    now = timezone.now()
    results = []

    virtual_boards = Board.objects.filter(is_active=True, is_virtual=True)

    for board in virtual_boards:
        # Find active virtual match (not in 'done' phase)
        active_match = DicePlayMatch.objects.filter(
            board=board,
            match_type="V",
        ).exclude(virtual_phase="done").order_by("-id").first()

        if active_match:
            phase = active_match.virtual_phase or "betting"
            phase_start = active_match.phase_started_at or active_match.liveDate or active_match.created_at
            elapsed = (now - phase_start).total_seconds()

            if phase == "betting":
                betting_secs = board.virtual_betting_seconds or 120
                if elapsed >= betting_secs:
                    # Time's up - roll dice and enter shuffling phase
                    auto_roll_virtual_match(active_match.id)
                    results.append(f"{board.name}: Game #{active_match.daily_match_number} -> shuffling")

            elif phase == "shuffling":
                shuffle_secs = board.virtual_shuffle_seconds or 30
                if elapsed >= shuffle_secs:
                    # Shuffle done - declare result
                    declare_virtual_match_result(active_match.id)
                    results.append(f"{board.name}: Game #{active_match.daily_match_number} -> result")

            elif phase == "result":
                result_secs = board.virtual_result_seconds or 15
                if elapsed >= result_secs:
                    # Result display done - mark as done and create next round
                    active_match.virtual_phase = "done"
                    active_match.isLive = False
                    active_match.save(update_fields=["virtual_phase", "isLive", "updated_at"])
                    # Create next round immediately
                    create_next_virtual_round(board.id)
                    results.append(f"{board.name}: Game #{active_match.daily_match_number} -> done, creating next")

        else:
            # No active match - create one
            create_next_virtual_round(board.id)
            results.append(f"{board.name}: no active match, creating round")

    return "; ".join(results) if results else "No action needed"
