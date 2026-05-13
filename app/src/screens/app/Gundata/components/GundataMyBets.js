import React, {useMemo} from 'react';
import {View, ScrollView, StyleSheet, TouchableOpacity} from 'react-native';
import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import AppText from '../../../../components/AppText';

const GOLD = '#D4A843';
const CARD_BG = '#171717';
const TEXT_MUTED = '#A8A29E';
const TEXT_PRIMARY = '#F5F1E8';
const WIN_GREEN = '#22C55E';
const LOSS_RED = '#EF4444';
const PENDING_AMBER = '#F59E0B';
const BORDER = 'rgba(212,168,67,0.12)';

const STATUS_CONFIG = {
  won: {color: WIN_GREEN, icon: 'check-circle', label: 'Won'},
  lost: {color: LOSS_RED, icon: 'close-circle', label: 'Lost'},
  pending: {color: PENDING_AMBER, icon: 'timer-sand', label: 'Pending'},
};

const BetRow = ({bet}) => {
  const status =
    bet.matchWinStatus === 1
      ? 'won'
      : bet.matchWinStatus === 2
      ? 'lost'
      : 'pending';
  const config = STATUS_CONFIG[status];
  const amount = parseFloat(bet.amount || 0);
  const winAmount = parseFloat(bet.winning_amount || 0);

  return (
    <View style={styles.betRow}>
      <View style={styles.betDiceCol}>
        <View style={[styles.diceNumberBadge, {borderColor: config.color}]}>
          <AppText style={[styles.diceNumberText, {color: config.color}]}>
            {bet.diceNumber}
          </AppText>
        </View>
      </View>
      <View style={styles.betAmountCol}>
        <AppText style={styles.amountText}>
          {'\u20B9'}{amount}
        </AppText>
      </View>
      <View style={styles.betStatusCol}>
        <View style={[styles.statusBadge, {backgroundColor: `${config.color}15`}]}>
          <Icon name={config.icon} size={fp(1.3)} color={config.color} />
          <AppText style={[styles.statusText, {color: config.color}]}>
            {config.label}
          </AppText>
        </View>
      </View>
      <View style={styles.betReturnCol}>
        {status === 'won' ? (
          <AppText style={styles.returnWon}>
            +{'\u20B9'}{winAmount.toFixed(0)}
          </AppText>
        ) : status === 'lost' ? (
          <AppText style={styles.returnLost}>
            -{'\u20B9'}{amount.toFixed(0)}
          </AppText>
        ) : (
          <AppText style={styles.returnPending}>-</AppText>
        )}
      </View>
    </View>
  );
};

const GundataMyBets = ({
  bets = [],
  onViewAll,
  maxDisplay = 10,
}) => {
  const displayBets = useMemo(
    () => bets.slice(0, maxDisplay),
    [bets, maxDisplay],
  );

  return (
    <View style={styles.container}>
      <View style={styles.headerRow}>
        <AppText style={styles.title}>My Bets</AppText>
        {bets.length > maxDisplay && onViewAll && (
          <TouchableOpacity onPress={onViewAll} activeOpacity={0.7}>
            <AppText style={styles.viewAllText}>View All</AppText>
          </TouchableOpacity>
        )}
      </View>

      {displayBets.length === 0 ? (
        <View style={styles.emptyState}>
          <Icon name="dice-multiple-outline" size={fp(3)} color={TEXT_MUTED} />
          <AppText style={styles.emptyText}>No bets placed yet</AppText>
        </View>
      ) : (
        <>
          {/* Column headers */}
          <View style={styles.colHeaders}>
            <AppText style={[styles.colHeader, styles.betDiceCol]}>
              Dice
            </AppText>
            <AppText style={[styles.colHeader, styles.betAmountCol]}>
              Amount
            </AppText>
            <AppText style={[styles.colHeader, styles.betStatusCol]}>
              Status
            </AppText>
            <AppText style={[styles.colHeader, styles.betReturnCol]}>
              Return
            </AppText>
          </View>

          <ScrollView
            style={styles.betsList}
            nestedScrollEnabled
            showsVerticalScrollIndicator={false}>
            {displayBets.map((bet, i) => (
              <BetRow key={bet.id || i} bet={bet} />
            ))}
          </ScrollView>
        </>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    width: wp(95),
    alignSelf: 'center',
    backgroundColor: CARD_BG,
    borderRadius: wp(4),
    overflow: 'hidden',
    paddingVertical: hp(1),
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: wp(3),
    marginBottom: hp(0.5),
  },
  title: {
    color: GOLD,
    fontSize: fp(1.5),
    fontWeight: '700',
    letterSpacing: 1,
    textTransform: 'uppercase',
  },
  viewAllText: {
    color: GOLD,
    fontSize: fp(1.3),
    fontWeight: '600',
  },
  colHeaders: {
    flexDirection: 'row',
    paddingHorizontal: wp(3),
    paddingBottom: hp(0.5),
    borderBottomWidth: 1,
    borderColor: BORDER,
  },
  colHeader: {
    color: TEXT_MUTED,
    fontSize: fp(1.1),
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  betRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: wp(3),
    paddingVertical: hp(0.8),
    borderBottomWidth: 0.5,
    borderColor: BORDER,
  },
  betDiceCol: {
    width: wp(15),
  },
  betAmountCol: {
    width: wp(20),
  },
  betStatusCol: {
    width: wp(25),
  },
  betReturnCol: {
    flex: 1,
    alignItems: 'flex-end',
  },
  diceNumberBadge: {
    width: wp(7),
    height: wp(7),
    borderRadius: wp(1.5),
    borderWidth: 1.5,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: 'rgba(212,168,67,0.05)',
  },
  diceNumberText: {
    fontSize: fp(1.6),
    fontWeight: '800',
  },
  amountText: {
    color: TEXT_PRIMARY,
    fontSize: fp(1.4),
    fontWeight: '600',
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: wp(1),
    paddingHorizontal: wp(2),
    paddingVertical: hp(0.3),
    borderRadius: wp(2),
  },
  statusText: {
    fontSize: fp(1.2),
    fontWeight: '600',
  },
  returnWon: {
    color: WIN_GREEN,
    fontSize: fp(1.4),
    fontWeight: '700',
  },
  returnLost: {
    color: LOSS_RED,
    fontSize: fp(1.4),
    fontWeight: '500',
  },
  returnPending: {
    color: TEXT_MUTED,
    fontSize: fp(1.4),
  },
  betsList: {
    maxHeight: hp(25),
  },
  emptyState: {
    paddingVertical: hp(3),
    alignItems: 'center',
    gap: hp(0.5),
  },
  emptyText: {
    color: TEXT_MUTED,
    fontSize: fp(1.4),
  },
});

export default GundataMyBets;
