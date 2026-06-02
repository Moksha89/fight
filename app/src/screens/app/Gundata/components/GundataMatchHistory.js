import React, {useRef, useMemo} from 'react';
import {View, ScrollView, StyleSheet} from 'react-native';
import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';
import AppText from '../../../../components/AppText';
import {DiceFace} from './GundataDice';

const GOLD = '#D4A843';
const CARD_BG = '#171717';
const TEXT_MUTED = '#A8A29E';
const WIN_GREEN = '#22C55E';
const BORDER = 'rgba(212,168,67,0.12)';

const DICE_NUMBERS = [1, 2, 3, 4, 5, 6];

const getDiceRollsForMatch = (match) => {
  if (!match) return [];
  const faces = [];
  DICE_NUMBERS.forEach(face => {
    const count = match[`total${face}Rolled`] ?? 0;
    for (let i = 0; i < count; i++) faces.push(face);
  });
  return faces.length === 6 ? faces : [];
};

const getWinningNumbers = (rolls) => {
  const counts = {};
  rolls.forEach(f => {
    counts[f] = (counts[f] || 0) + 1;
  });
  return Object.entries(counts)
    .filter(([_, c]) => c >= 2)
    .map(([n]) => parseInt(n, 10));
};

const GundataLatestResult = ({match}) => {
  const rolls = useMemo(() => getDiceRollsForMatch(match), [match]);
  const winners = useMemo(() => getWinningNumbers(rolls), [rolls]);
  const winSet = useMemo(() => new Set(winners), [winners]);

  if (rolls.length === 0) return null;

  return (
    <View style={styles.latestContainer}>
      <AppText style={styles.latestTitle}>Latest Result</AppText>
      <View style={styles.latestDiceRow}>
        {rolls.map((val, i) => (
          <View
            key={i}
            style={[
              styles.latestDiceWrap,
              winSet.has(val) && styles.latestDiceWin,
            ]}>
            <DiceFace value={val} size={wp(9)} />
          </View>
        ))}
      </View>
      {winners.length > 0 && (
        <View style={styles.winnersRow}>
          <AppText style={styles.winnersLabel}>Winning:</AppText>
          {winners.map(n => (
            <View key={n} style={styles.winnerBadge}>
              <AppText style={styles.winnerBadgeText}>{n}</AppText>
            </View>
          ))}
        </View>
      )}
    </View>
  );
};

const GundataMatchHistory = ({matches = []}) => {
  const scrollRef = useRef(null);

  const displayHistory = useMemo(
    () => [...matches].reverse(),
    [matches],
  );

  if (displayHistory.length === 0) {
    return (
      <View style={styles.historyContainer}>
        <AppText style={styles.historyTitle}>Match History</AppText>
        <View style={styles.emptyState}>
          <AppText style={styles.emptyText}>No completed rounds yet</AppText>
        </View>
      </View>
    );
  }

  return (
    <View style={styles.historyContainer}>
      <AppText style={styles.historyTitle}>Match History</AppText>
      <ScrollView
        ref={scrollRef}
        horizontal
        showsHorizontalScrollIndicator={false}
        onLayout={() => scrollRef.current?.scrollToEnd({animated: false})}
        onContentSizeChange={() =>
          scrollRef.current?.scrollToEnd({animated: true})
        }
        contentContainerStyle={styles.historyScroll}>
        {/* Header row */}
        <View>
          <View style={styles.headerRow}>
            {displayHistory.map((_, i) => (
              <View key={`h-${i}`} style={styles.headerCell}>
                <AppText style={styles.headerText}>R{i + 1}</AppText>
              </View>
            ))}
          </View>
          {/* Dice rows (6 dice per column) */}
          <View style={{flexDirection: 'row'}}>
            {displayHistory.map((match, colIdx) => {
              const rolls = getDiceRollsForMatch(match);
              const winners = new Set(getWinningNumbers(rolls));
              return (
                <View key={match?.id ?? colIdx} style={styles.historyColumn}>
                  {rolls.map((val, rowIdx) => (
                    <View
                      key={rowIdx}
                      style={[
                        styles.historyCell,
                        winners.has(val) && styles.historyCellWin,
                      ]}>
                      <DiceFace value={val} size={wp(5.5)} />
                    </View>
                  ))}
                </View>
              );
            })}
          </View>
        </View>
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  // Latest Result
  latestContainer: {
    width: wp(95),
    alignSelf: 'center',
    backgroundColor: CARD_BG,
    borderRadius: wp(3),
    padding: wp(3),
    gap: hp(0.8),
  },
  latestTitle: {
    color: GOLD,
    fontSize: fp(1.5),
    fontWeight: '700',
    letterSpacing: 1,
    textTransform: 'uppercase',
  },
  latestDiceRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: wp(2),
  },
  latestDiceWrap: {
    padding: wp(1),
    borderRadius: wp(2),
    borderWidth: 1,
    borderColor: 'transparent',
  },
  latestDiceWin: {
    borderColor: WIN_GREEN,
    backgroundColor: 'rgba(34,197,94,0.08)',
  },
  winnersRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: wp(1.5),
    marginTop: hp(0.3),
  },
  winnersLabel: {
    color: TEXT_MUTED,
    fontSize: fp(1.3),
  },
  winnerBadge: {
    backgroundColor: 'rgba(34,197,94,0.15)',
    borderWidth: 1,
    borderColor: WIN_GREEN,
    borderRadius: wp(1.5),
    paddingHorizontal: wp(2.5),
    paddingVertical: hp(0.2),
  },
  winnerBadgeText: {
    color: WIN_GREEN,
    fontSize: fp(1.4),
    fontWeight: '700',
  },

  // Match History
  historyContainer: {
    width: wp(95),
    alignSelf: 'center',
    backgroundColor: CARD_BG,
    borderRadius: wp(4),
    overflow: 'hidden',
    paddingVertical: hp(1),
  },
  historyTitle: {
    color: GOLD,
    fontSize: fp(1.5),
    fontWeight: '700',
    letterSpacing: 1,
    textTransform: 'uppercase',
    paddingHorizontal: wp(3),
    marginBottom: hp(0.5),
  },
  historyScroll: {
    flexGrow: 1,
    paddingHorizontal: wp(2),
  },
  headerRow: {
    flexDirection: 'row',
  },
  headerCell: {
    width: wp(10),
    height: hp(2.5),
    justifyContent: 'center',
    alignItems: 'center',
    borderBottomWidth: 1,
    borderColor: BORDER,
  },
  headerText: {
    color: TEXT_MUTED,
    fontSize: fp(1.1),
    fontWeight: '600',
  },
  historyColumn: {
    flexDirection: 'column',
  },
  historyCell: {
    width: wp(10),
    height: wp(8),
    justifyContent: 'center',
    alignItems: 'center',
    borderRightWidth: 0.5,
    borderBottomWidth: 0.5,
    borderColor: BORDER,
  },
  historyCellWin: {
    backgroundColor: 'rgba(34,197,94,0.06)',
  },
  emptyState: {
    paddingVertical: hp(3),
    alignItems: 'center',
  },
  emptyText: {
    color: TEXT_MUTED,
    fontSize: fp(1.4),
  },
});

export {GundataLatestResult, GundataMatchHistory, getDiceRollsForMatch, getWinningNumbers};
export default GundataMatchHistory;
