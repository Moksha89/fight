import React, {useEffect, useState} from 'react';
import {View, FlatList, StyleSheet} from 'react-native';

import MaterialCommunityIcons from 'react-native-vector-icons/MaterialCommunityIcons';
import Ionicons from 'react-native-vector-icons/Ionicons';

import AppText from '../../../components/AppText';
import AppScreen from '../../../components/AppScreen';
import HeaderComponent from '../../../components/HeaderComponent';

import {getWalletInfo} from '../../../apis/appApi';
import {useAuth} from '../../../context/AuthContext';

import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';

const HistoryScreen = ({navigation}) => {
  const {wallet} = useAuth();
  const [walletData, setWalletData] = useState([]);
  const [nextPageLink, setNextPageLink] = useState(0);

  useEffect(() => {
    fetchWalletInfo();
  }, []);

  const fetchWalletInfo = async () => {
    if (nextPageLink == 0 || nextPageLink) {
      const result = await getWalletInfo(nextPageLink);
      if (result.success) {
        setWalletData(prev => [...prev, ...result.data.results.history]);
        setNextPageLink(result.data.next);
      } else {
        console.warn('Failed to load wallet data');
      }
    }
  };

  const getIconByType = type => {
    switch (type) {
      case 'P':
        return 'shopping';
      case 'D':
        return 'arrow-bottom-left';
      case 'W':
        return 'bank-transfer-out';
      case 'B':
        return 'bitcoin';
      case 'C':
        return 'cricket';
      case 'F':
        return 'sword-cross';
      case 'L':
        return 'ticket-outline';
      case 'S':
        return 'check-decagram';
      default:
        return 'cash';
    }
  };

  return (
    <AppScreen lightStatusBar isTranslucent style={{paddingTop: hp(4.5)}}>
      <HeaderComponent
        title="Wallet History"
        onBackPress={() => navigation.goBack()}
        RightIconComponent={
          <>
            <Ionicons name="wallet-outline" size={20} color="#fff" />
            <AppText style={{color: '#fff'}}>
              ₹{String(wallet.balanceWithBonus).split('.')[0]}
            </AppText>
          </>
        }
        containerStyle={styles.headerSection}
        rightIconWrapperStyle={styles.headerIcon}
      />
      <FlatList
        data={walletData}
        onEndReached={fetchWalletInfo}
        onEndReachedThreshold={0.4}
        keyExtractor={item => item.id.toString()}
        renderItem={({item}) => (
          <View style={styles.historyRow}>
            <View style={styles.historySection}>
              <View style={styles.transactionTypeIcon}>
                <MaterialCommunityIcons
                  name={getIconByType(item.transaction_type)}
                  size={23}
                  color="#000"
                />
              </View>
              <View style={{width: wp(50), marginRight: wp(5)}}>
                <AppText>
                  {new Date(item.created_at).toLocaleDateString()}
                </AppText>
                <AppText
                  style={{
                    fontSize: fp(1.6),
                    lineHeight: wp(4.5),
                    marginTop: hp(0.5),
                  }}>
                  {item.description}
                </AppText>
              </View>
              <View style={{width: wp(20), alignItems: 'flex-end'}}>
                <AppText
                  style={[
                    styles.amountText,
                    {
                      color:
                        item.transaction_type === 'D'
                          ? item.isSuccess
                            ? 'green'
                            : '#000'
                          : item.transaction_type === 'W'
                          ? item.isSuccess
                            ? 'red'
                            : '#000'
                          : item.isSuccess
                          ? 'green'
                          : 'red',
                    },
                  ]}>
                  {item.transaction_type === 'D'
                    ? item.isSuccess
                      ? '+ '
                      : ''
                    : item.transaction_type === 'W'
                    ? item.isSuccess
                      ? '- '
                      : ''
                    : item.isSuccess
                    ? '+ '
                    : '- '}
                  ₹{item.change.toLocaleString()}
                </AppText>
                {!item.isSuccess &&
                  ['W', 'D'].includes(item.transaction_type) && (
                    <View style={styles.paymentStatusRow}>
                      <AppText style={[styles.ststusText, {color: 'red'}]}>
                        Failed
                      </AppText>
                    </View>
                  )}
              </View>
            </View>
          </View>
        )}
      />
    </AppScreen>
  );
};

const styles = StyleSheet.create({
  headerSection: {
    paddingHorizontal: wp(5),
    borderRadius: wp(2),
    width: wp(100),
    height: hp(8),
    borderBottomWidth: 1,
    borderColor: 'rgba(212,168,67,0.18)',
    paddingBottom: wp(3),
  },
  headerIcon: {
    backgroundColor: '#d4a843',
    borderColor: 'rgba(212,168,67,0.18)',
    width: wp(27),
    flexDirection: 'row',
    justifyContent: 'space-evenly',
    height: hp(4),
  },
  historyRow: {
    paddingHorizontal: wp(4),
    flexDirection: 'row',
    borderBottomWidth: wp(0.5),
    paddingBottom: hp(1.5),
    paddingTop: hp(1.5),
    borderColor: '#f3f3f3',
  },
  historySection: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  transactionTypeIcon: {
    width: wp(12),
    height: wp(12),
    borderRadius: wp(4),
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#F3F3F3',
    marginRight: wp(5),
  },

  paymentStatusRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  amountText: {
    fontSize: fp(2.0),
    marginBottom: hp(1),
  },
});

export default HistoryScreen;
