import React, {useEffect, useState} from 'react';
import {View, FlatList, StyleSheet, RefreshControl} from 'react-native';

import MaterialCommunityIcons from 'react-native-vector-icons/MaterialCommunityIcons';
import Ionicons from 'react-native-vector-icons/Ionicons';

import AppText from '../../../components/AppText';
import AppScreen from '../../../components/AppScreen';
import HeaderComponent from '../../../components/HeaderComponent';
import AppLoader from '../../../components/AppLoader';
import EmptyState from '../../../components/EmptyState';

import {getWalletInfo} from '../../../apis/appApi';
import {useAuth} from '../../../context/AuthContext';
import {useTheme} from '../../../context/ThemeContext';

import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';

const HistoryScreen = ({navigation}) => {
  const {wallet} = useAuth();
  const {colors} = useTheme();
  const [walletData, setWalletData] = useState([]);
  const [nextPageLink, setNextPageLink] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

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
    setLoading(false);
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    setWalletData([]);
    setNextPageLink(0);
    const result = await getWalletInfo(0);
    if (result.success) {
      setWalletData(result.data.results.history);
      setNextPageLink(result.data.next);
    }
    setRefreshing(false);
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

  if (loading) {
    return (
      <AppScreen lightStatusBar isTranslucent style={{paddingTop: hp(4.5)}}>
        <HeaderComponent
          title="Wallet History"
          onBackPress={() => navigation.canGoBack() && navigation.goBack()}
        />
        <AppLoader fullScreen text="Loading history..." />
      </AppScreen>
    );
  }

  return (
    <AppScreen lightStatusBar isTranslucent style={{paddingTop: hp(4.5)}}>
      <HeaderComponent
        title="Wallet History"
        onBackPress={() => navigation.canGoBack() && navigation.goBack()}
        RightIconComponent={
          <>
            <Ionicons name="wallet-outline" size={20} color={colors.text_primary} />
            <AppText style={{color: colors.text_primary}}>
              ₹{String(wallet.balanceWithBonus).split('.')[0]}
            </AppText>
          </>
        }
        containerStyle={styles.headerSection}
        rightIconWrapperStyle={[styles.headerIcon, {backgroundColor: colors.gold, borderColor: colors.border_gold}]}
      />
      {walletData.length === 0 ? (
        <EmptyState
          icon="receipt-long"
          title="No transactions yet"
          message="Your wallet history will appear here"
        />
      ) : (
        <FlatList
          data={walletData}
          onEndReached={fetchWalletInfo}
          onEndReachedThreshold={0.4}
          keyExtractor={item => item.id.toString()}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={handleRefresh}
              tintColor={colors.gold}
              colors={[colors.gold]}
            />
          }
          renderItem={({item}) => (
            <View style={[styles.historyRow, {borderColor: colors.border}]}>
              <View style={styles.historySection}>
                <View style={[styles.transactionTypeIcon, {backgroundColor: colors.surface_elevated}]}>
                  <MaterialCommunityIcons
                    name={getIconByType(item.transaction_type)}
                    size={23}
                    color={colors.gold}
                  />
                </View>
                <View style={{width: wp(50), marginRight: wp(5)}}>
                  <AppText style={{color: colors.text_secondary}}>
                    {new Date(item.created_at).toLocaleDateString()}
                  </AppText>
                  <AppText
                    style={{
                      fontSize: fp(1.6),
                      lineHeight: wp(4.5),
                      marginTop: hp(0.5),
                      color: colors.text_primary,
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
                              ? colors.success
                              : colors.text_muted
                            : item.transaction_type === 'W'
                            ? item.isSuccess
                              ? colors.danger
                              : colors.text_muted
                            : item.isSuccess
                            ? colors.success
                            : colors.danger,
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
                        <AppText style={[styles.ststusText, {color: colors.danger}]}>
                          Failed
                        </AppText>
                      </View>
                    )}
                </View>
              </View>
            </View>
          )}
        />
      )}
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
