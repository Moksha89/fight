import React, {useState, useEffect} from 'react';
import {
  Modal,
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  TouchableWithoutFeedback,
} from 'react-native';
import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';

import MaterialIcons from 'react-native-vector-icons/MaterialIcons';
import AppText from '../AppText';
import AppBadge from '../AppBadge';
import {useTheme} from '../../context/ThemeContext';
import COLORS from '../../context/designTokens';

/**
 * Shared bet history modal for CockFight and Gundata/Dice.
 *
 * Props:
 *  - gameType: 'cockfight' | 'dice'
 *  - bets: array of bet objects
 *  - setBets: state setter
 *  - visible: boolean
 *  - onClose: function
 *  - fetchBetsApi: async function(url) => { results/data, next }
 *  - ProvablyFairModal: (dice only) component to render for provably fair verification
 */

// CockFight team mapping
const teamMap = {
  1: 'Red Team',
  2: 'Blue Team',
  3: 'Draw',
};

const getTeamColor = team => {
  switch (team) {
    case 1: return COLORS.meron;
    case 2: return COLORS.wala;
    case 3: return COLORS.success;
    default: return COLORS.text_muted;
  }
};

// CockFight color logic
const getCockfightColor = (matchWinStatus, betTeam) => {
  if (matchWinStatus === 4) return COLORS.text_muted;
  if (matchWinStatus === 0) return COLORS.warning;
  if (matchWinStatus === betTeam) return COLORS.success;
  return COLORS.meron;
};

const getCockfightAmountText = item => {
  const {amount, betRatio, matchWinStatus, betTeam} = item;
  if (matchWinStatus === 4) return `+${amount}`;
  if (matchWinStatus === 0) return 'In Progress';
  if (matchWinStatus === betTeam) {
    const total = amount + Math.floor(amount * betRatio);
    return `+${total}`;
  }
  return `-${amount}`;
};

// Dice color logic
const getDiceColor = matchWinStatus => {
  if (matchWinStatus === 0) return COLORS.warning;
  if (matchWinStatus === 1) return COLORS.success;
  return COLORS.meron;
};

const getDiceWinTotal = item => {
  const count = item.rolled_count;
  if (count != null && count >= 2) {
    return item.amount + count * item.amount;
  }
  return 0;
};

const getDiceAmountText = item => {
  if (item.matchWinStatus === 0) return 'In Progress';
  if (item.matchWinStatus === 1) {
    const total = getDiceWinTotal(item);
    return `+${total}`;
  }
  return `-${item.amount}`;
};

const GameBetHistoryModal = ({
  gameType = 'cockfight',
  bets,
  setBets,
  visible,
  onClose,
  fetchBetsApi,
  ProvablyFairModal: ProvablyFairModalComponent,
}) => {
  const {colors} = useTheme();
  const [nextPage, setNextPage] = useState(null);
  const [loading, setLoading] = useState(false);
  const [fairModalVisible, setFairModalVisible] = useState(false);
  const [fairMatchId, setFairMatchId] = useState(null);
  const [fairCommitHash, setFairCommitHash] = useState(null);

  const isDice = gameType === 'dice';

  const fetchBets = async (url = null, append = false) => {
    try {
      setLoading(true);
      const data = await fetchBetsApi(url);

      if (data) {
        if (isDice) {
          const list = Array.isArray(data) ? data : (data.results || []);
          setBets(prev => (append ? [...prev, ...list] : list));
          setNextPage(data.next || null);
        } else {
          if (data.results) {
            setBets(prev => (append ? [...prev, ...data.results] : data.results));
            setNextPage(data.next);
          }
        }
      }
    } catch (error) {
      console.error(`Error fetching ${gameType} bets:`, error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isDice) {
      if (visible) fetchBets();
    } else {
      fetchBets();
    }
  }, [visible]);

  const loadMore = () => {
    if (nextPage && !loading) {
      fetchBets(nextPage, true);
    }
  };

  const openFairModal = item => {
    setFairMatchId(item.match);
    setFairCommitHash(item.commitment_hash || null);
    setFairModalVisible(true);
  };

  const renderCockfightItem = ({item}) => {
    const color = getCockfightColor(item.matchWinStatus, item.betTeam);
    const circleColor = getTeamColor(item.betTeam);
    const amountText = getCockfightAmountText(item);

    return (
      <View style={[styles.card, {backgroundColor: colors.surfaceElevated || '#1F1F1F'}]}>
        <View style={styles.left}>
          <View style={[styles.circle, {backgroundColor: circleColor}]} />
          <View style={styles.textInfo}>
            <AppText style={[styles.title, {color: colors.text_secondary}]}>
              Bet On {teamMap[item.betTeam]}
            </AppText>
            <AppText style={[styles.subText, {color: colors.text_muted}]}>
              {new Date(item.createdDate).toLocaleDateString()} {'   '}|{'   '}
              Match - {item.matchType}{item.matchId}
            </AppText>
          </View>
        </View>
        <View style={styles.right}>
          {item.matchWinStatus === 0 ? (
            <View style={{alignItems: 'flex-end'}}>
              <AppText style={[styles.inProgress, {color: colors.text_muted}]}>In Progress</AppText>
              <AppText style={styles.amount}>{item.amount}</AppText>
            </View>
          ) : (
            <AppText
              style={[
                styles.amount,
                {
                  color:
                    color === COLORS.text_muted
                      ? COLORS.text_muted
                      : amountText.startsWith('+')
                      ? COLORS.success
                      : COLORS.meron,
                },
              ]}>
              {amountText}
            </AppText>
          )}
        </View>
      </View>
    );
  };

  const renderDiceItem = ({item}) => {
    const amountText = getDiceAmountText(item);
    const hasRolledCount =
      item.matchWinStatus === 1 &&
      item.rolled_count != null &&
      item.rolled_count >= 2;
    const titleText = hasRolledCount
      ? `#${item.diceNumber} × ${item.rolled_count} × ₹${item.amount} + ₹${item.amount} = ₹${item.amount + item.rolled_count * item.amount}`
      : `#${item.diceNumber} — ₹${item.amount}`;
    const isSettled = item.matchWinStatus === 1 || item.matchWinStatus === 2;

    return (
      <View style={[styles.card, {backgroundColor: colors.card}]}>
        <View style={styles.left}>
          <View style={[styles.diceBadge, {backgroundColor: colors.wala_light}]}>
            <Text style={styles.diceBadgeText}>{item.diceNumber}</Text>
          </View>
          <View style={styles.textInfo}>
            <AppText style={[styles.title, {color: colors.text_primary}]}>
              {titleText}
            </AppText>
            <AppText style={[styles.subText, {color: colors.text_muted}]}>
              {new Date(item.createdDate).toLocaleDateString()} {' | '}
              Game #{item.daily_match_number || item.match}
            </AppText>
            {isSettled && (
              <TouchableOpacity
                style={styles.verifyBtn}
                onPress={() => openFairModal(item)}>
                <MaterialIcons name="verified" size={12} color={colors.gold} />
                <Text style={[styles.verifyText, {color: colors.gold}]}>Verify Fair</Text>
              </TouchableOpacity>
            )}
          </View>
        </View>
        <View style={styles.right}>
          {item.matchWinStatus === 0 ? (
            <View style={{alignItems: 'flex-end'}}>
              <AppText style={[styles.inProgress, {color: colors.text_muted}]}>In Progress</AppText>
              <AppText style={styles.amount}>{item.amount}</AppText>
            </View>
          ) : (
            <AppText
              style={[
                styles.amount,
                {color: amountText.startsWith('+') ? colors.success : colors.meron},
              ]}>
              {amountText}
            </AppText>
          )}
        </View>
      </View>
    );
  };

  return (
    <Modal
      visible={visible}
      animationType="fade"
      transparent
      statusBarTranslucent>
      <View style={styles.overlay}>
        <TouchableWithoutFeedback onPress={onClose}>
          <View style={styles.dimmedArea} />
        </TouchableWithoutFeedback>

        <View style={[styles.modalContainer, {backgroundColor: colors.card}]}>
          <View style={styles.handleWrapper}>
            <View style={[styles.handle, {backgroundColor: colors.text_muted}]} />
          </View>

          <FlatList
            data={bets}
            extraData={bets}
            keyExtractor={item => item.id.toString()}
            renderItem={isDice ? renderDiceItem : renderCockfightItem}
            showsVerticalScrollIndicator={false}
            onEndReached={loadMore}
            onEndReachedThreshold={0.5}
            contentContainerStyle={styles.listContent}
            ListEmptyComponent={
              <AppText style={[styles.emptyText, {color: colors.text_muted}]}>
                No bets yet
              </AppText>
            }
          />
        </View>
      </View>

      {isDice && ProvablyFairModalComponent && (
        <ProvablyFairModalComponent
          visible={fairModalVisible}
          onClose={() => setFairModalVisible(false)}
          matchId={fairMatchId}
          commitmentHash={fairCommitHash}
        />
      )}
    </Modal>
  );
};

export default GameBetHistoryModal;

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: COLORS.overlay,
    justifyContent: 'flex-end',
  },
  dimmedArea: {
    flex: 1,
  },
  modalContainer: {
    height: hp(60),
    borderTopLeftRadius: wp(4),
    borderTopRightRadius: wp(4),
    paddingHorizontal: wp(4),
    paddingTop: hp(2),
  },
  handleWrapper: {
    alignItems: 'center',
    marginBottom: hp(1.5),
  },
  handle: {
    width: 40,
    height: 5,
    borderRadius: 3,
  },
  card: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderWidth: wp(0.3),
    marginBottom: hp(1),
    borderColor: 'rgba(212,168,67,0.18)',
    borderRadius: wp(2),
  },
  left: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  circle: {
    width: wp(2.5),
    height: wp(2.5),
    borderRadius: 50,
    marginRight: wp(3),
  },
  diceBadge: {
    width: wp(8),
    height: wp(8),
    borderRadius: wp(4),
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: wp(3),
  },
  diceBadgeText: {
    color: COLORS.text_primary,
    fontWeight: 'bold',
    fontSize: fp(1.8),
  },
  textInfo: {
    flexShrink: 1,
  },
  title: {
    fontSize: fp(1.7),
  },
  subText: {
    fontSize: fp(1.5),
    marginTop: hp(0.5),
  },
  right: {
    alignItems: 'flex-end',
  },
  inProgress: {
    fontSize: 12,
    marginTop: hp(0.5),
  },
  amount: {
    fontSize: 14,
    fontWeight: 'bold',
  },
  listContent: {
    paddingBottom: hp(4),
  },
  emptyText: {
    textAlign: 'center',
    marginTop: hp(2),
  },
  verifyBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 4,
    gap: 3,
  },
  verifyText: {
    fontSize: fp(1.2),
    fontWeight: '600',
  },
});
