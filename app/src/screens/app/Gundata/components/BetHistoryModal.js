// @deprecated — Use shared component from app/src/components/game/ instead. This file is kept for reference only.
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
import {getDicePlayUserBets} from '../../../../apis/dicePlayApi';
import ProvablyFairModal from './ProvablyFairModal';
import {useTheme} from '../../../../context/ThemeContext';
import COLORS from '../../../../context/designTokens';

const getColor = (matchWinStatus) => {
  if (matchWinStatus === 0) return COLORS.warning;
  if (matchWinStatus === 1) return COLORS.success;
  return COLORS.meron;
};

// Total payout when won: bet returned + rolled_count * amount
const getWinTotal = (item) => {
  const count = item.rolled_count;
  if (count != null && count >= 2) {
    return item.amount + count * item.amount;
  }
  return 0;
};

const getAmountText = (item) => {
  if (item.matchWinStatus === 0) return '—';
  if (item.matchWinStatus === 1) {
    const total = getWinTotal(item);
    return `+₹${total.toLocaleString('en-IN')}`;
  }
  return '₹0';
};

const BetHistoryModal = ({bets, setBets, visible, onClose}) => {
  const [nextPage, setNextPage] = useState(null);
  const [loading, setLoading] = useState(false);
  const [fairModalVisible, setFairModalVisible] = useState(false);
  const [fairMatchId, setFairMatchId] = useState(null);
  const [fairCommitHash, setFairCommitHash] = useState(null);

  const fetchBets = async (url = null, append = false) => {
    try {
      setLoading(true);
      const data = await getDicePlayUserBets(url);

      if (data) {
        const list = Array.isArray(data) ? data : (data.results || []);
        setBets(prev => (append ? [...prev, ...list] : list));
        setNextPage(data.next || null);
      }
    } catch (error) {
      console.error('Error fetching dice play bets:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (visible) {
      fetchBets();
    }
  }, [visible]);

  const loadMore = () => {
    if (nextPage && !loading) {
      fetchBets(nextPage, true);
    }
  };

  const openFairModal = (item) => {
    setFairMatchId(item.match);
    setFairCommitHash(item.commitment_hash || null);
    setFairModalVisible(true);
  };

  const renderItem = ({item}) => {
    const amountText = getAmountText(item);
    const hasRolledCount =
      item.matchWinStatus === 1 &&
      item.rolled_count != null &&
      item.rolled_count >= 2;
    const titleText = hasRolledCount
      ? `#${item.diceNumber} × ${item.rolled_count} × ₹${item.amount} + ₹${item.amount} = ₹${item.amount + item.rolled_count * item.amount}`
      : `#${item.diceNumber} — ₹${item.amount}`;
    const isSettled = item.matchWinStatus === 1 || item.matchWinStatus === 2;

    return (
      <View style={styles.card}>
        <View style={styles.left}>
          <View style={[styles.diceBadge, {backgroundColor: '#5C6BC0'}]}>
            <Text style={styles.diceBadgeText}>{item.diceNumber}</Text>
          </View>
          <View style={styles.textInfo}>
            <Text style={styles.title}>{titleText}</Text>
            <Text style={styles.subText}>
              {new Date(item.createdDate).toLocaleDateString()} {' | '}
              Game #{item.daily_match_number || item.match}
            </Text>
            {isSettled && (
              <TouchableOpacity
                style={styles.verifyBtn}
                onPress={() => openFairModal(item)}>
                <MaterialIcons name="verified" size={12} color="#D4A843" />
                <Text style={styles.verifyText}>Verify Fair</Text>
              </TouchableOpacity>
            )}
          </View>
        </View>

        <View style={styles.right}>
          {item.matchWinStatus === 0 ? (
            <View style={{alignItems: 'flex-end'}}>
              <Text style={styles.inProgress}>In Progress</Text>
              <Text style={styles.amount}>{item.amount}</Text>
            </View>
          ) : (
            <Text
              style={[
                styles.amount,
                {
                  color:
                    amountText.startsWith('+') ? '#43A048' : '#BA2343',
                },
              ]}>
              {amountText}
            </Text>
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

        <View style={styles.modalContainer}>
          <View style={styles.handleWrapper}>
            <View style={styles.handle} />
          </View>

          <FlatList
            data={bets}
            extraData={bets}
            keyExtractor={item => item.id.toString()}
            renderItem={renderItem}
            showsVerticalScrollIndicator={false}
            onEndReached={loadMore}
            onEndReachedThreshold={0.5}
            contentContainerStyle={styles.listContent}
            ListEmptyComponent={<Text style={styles.emptyText}>No bets yet</Text>}
          />
        </View>
      </View>

      <ProvablyFairModal
        visible={fairModalVisible}
        onClose={() => setFairModalVisible(false)}
        matchId={fairMatchId}
        commitmentHash={fairCommitHash}
      />
    </Modal>
  );
};

export default BetHistoryModal;

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: '#00000070',
    justifyContent: 'flex-end',
  },
  dimmedArea: {
    flex: 1,
  },
  modalContainer: {
    backgroundColor: '#171717',
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
    backgroundColor: '#ccc',
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
    backgroundColor: '#171717',
  },
  left: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
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
    color: COLORS.white,
    fontWeight: 'bold',
    fontSize: fp(1.8),
  },
  textInfo: {
    flexShrink: 1,
  },
  title: {
    fontSize: fp(1.7),
    color: COLORS.text_primary,
  },
  subText: {
    fontSize: fp(1.5),
    color: COLORS.text_label,
    marginTop: hp(0.5),
  },
  right: {
    alignItems: 'flex-end',
  },
  inProgress: {
    fontSize: 12,
    color: COLORS.text_label,
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
    color: COLORS.text_label,
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
    color: COLORS.gold,
    fontWeight: '600',
  },
});
