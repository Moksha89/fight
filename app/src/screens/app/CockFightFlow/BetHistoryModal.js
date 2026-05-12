import React, {useState, useEffect} from 'react';
import {
  Modal,
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableWithoutFeedback,
} from 'react-native';
import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';

import {getCockfightUserBets} from '../../../apis/cockfightApi';

const teamMap = {
  1: 'Red Team',
  2: 'Blue Team',
  3: 'Draw',
};

const getTeamColor = team => {
  switch (team) {
    case 1:
      return '#BA2343'; // Red Team
    case 2:
      return '#0000FF'; // Blue Team
    case 3:
      return '#43A048'; // Draw
  }
};

const getColor = (matchWinStatus, betTeam) => {
  if (matchWinStatus === 4) return '#888'; // Canceled
  if (matchWinStatus === 0) return '#FFA500'; // In progress (orange)
  if (matchWinStatus === betTeam) return '#43A048'; // Green (won)
  return '#BA2343'; // Red (lost)
};

const getAmountText = item => {
  const {amount, betRatio, matchWinStatus, betTeam} = item;

  if (matchWinStatus === 4) {
    return `+${amount}`; // Canceled
  }

  if (matchWinStatus === 0) {
    return 'In Progress';
  }

  if (matchWinStatus === betTeam) {
    const total = amount + Math.floor(amount * betRatio);
    return `+${total}`;
  } else {
    return `-${amount}`;
  }
};

const BetHistoryModal = ({bets, setBets, visible, onClose}) => {
  const [nextPage, setNextPage] = useState(null);
  const [loading, setLoading] = useState(false);

  const fetchBets = async (url = null, append = false) => {
    try {
      setLoading(true);
      const data = await getCockfightUserBets(url);

      if (data && data.results) {
        setBets(prev => (append ? [...prev, ...data.results] : data.results));
        setNextPage(data.next);
      }
    } catch (error) {
      console.error('Error fetching bets:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBets();
  }, []);

  const loadMore = () => {
    if (nextPage && !loading) {
      fetchBets(nextPage, true);
    }
  };

  const renderItem = ({item}) => {
    const color = getColor(item.matchWinStatus, item.betTeam);
    const circleColor = getTeamColor(item.betTeam);
    const amountText = getAmountText(item);

    return (
      <View style={styles.card}>
        <View style={styles.left}>
          <View style={[styles.circle, {backgroundColor: circleColor}]} />
          <View style={styles.textInfo}>
            <Text style={styles.title}>Bet On {teamMap[item.betTeam]}</Text>
            <Text style={styles.subText}>
              {new Date(item.createdDate).toLocaleDateString()} {'   '}|{'   '}
              Match - {item.matchType}
              {item.matchId}
            </Text>
          </View>
        </View>

        <View style={styles.right}>
          {item.matchWinStatus == 0 ? (
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
                    color === '#888'
                      ? '#888'
                      : amountText.startsWith('+')
                      ? '#43A048'
                      : '#BA2343',
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
        {/* Close modal on tapping dimmed area */}
        <TouchableWithoutFeedback onPress={onClose}>
          <View style={styles.dimmedArea} />
        </TouchableWithoutFeedback>

        {/* Bottom sheet */}
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
          />
        </View>
      </View>
    </Modal>
  );
};

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
    backgroundColor: '#4a4a4a',
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
    backgroundColor: '#1F1F1F',
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
  textInfo: {
    flexShrink: 1,
  },
  title: {
    fontSize: fp(1.7),
    color: '#414141',
  },
  subText: {
    fontSize: fp(1.5),
    color: '#999',
    marginTop: hp(0.5),
  },
  right: {
    alignItems: 'flex-end',
  },
  closeBtn: {
    fontSize: 16,
    color: '#666',
    marginBottom: 2,
  },
  inProgress: {
    fontSize: 12,
    color: '#999',
    marginTop: hp(0.5),
  },
  amount: {
    fontSize: 14,
    fontWeight: 'bold',
  },
});

export default BetHistoryModal;
