import React, {useEffect, useState, useCallback} from 'react';
import {
  View,
  FlatList,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';

import MaterialIcons from 'react-native-vector-icons/MaterialIcons';
import MaterialCommunityIcons from 'react-native-vector-icons/MaterialCommunityIcons';

import AppText from '../../../components/AppText';
import AppScreen from '../../../components/AppScreen';
import HeaderComponent from '../../../components/HeaderComponent';

import {apiRequest} from '../../../utils/apiClient';
import {useAuth} from '../../../context/AuthContext';

import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';

const FILTERS = [
  {key: 'all', label: 'All'},
  {key: 'deposit', label: 'Deposit'},
  {key: 'withdraw', label: 'Withdraw'},
  {key: 'bet', label: 'Bet'},
];

const StatementScreen = ({navigation}) => {
  const {wallet} = useAuth();
  const [transactions, setTransactions] = useState([]);
  const [filteredTxns, setFilteredTxns] = useState([]);
  const [activeFilter, setActiveFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    loadStatement();
  }, []);

  useEffect(() => {
    applyFilter(activeFilter);
  }, [transactions, activeFilter]);

  const loadStatement = async () => {
    try {
      const result = await apiRequest('/api/user/statement/');
      if (result.success && result.data) {
        setTransactions(result.data.transactions || []);
      }
    } catch (e) {
      console.warn('Statement load error:', e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const applyFilter = (filter) => {
    if (filter === 'all') {
      setFilteredTxns(transactions);
    } else if (filter === 'deposit') {
      setFilteredTxns(
        transactions.filter(
          t =>
            t.type === 'Funds In' ||
            (t.description || '').toLowerCase().includes('deposit'),
        ),
      );
    } else if (filter === 'withdraw') {
      setFilteredTxns(
        transactions.filter(
          t =>
            t.type === 'Funds Out' ||
            (t.description || '').toLowerCase().includes('withdraw'),
        ),
      );
    } else if (filter === 'bet') {
      setFilteredTxns(
        transactions.filter(
          t =>
            (t.description || '').toLowerCase().includes('bet') ||
            (t.description || '').toLowerCase().includes('cockfight') ||
            (t.description || '').toLowerCase().includes('dice'),
        ),
      );
    }
  };

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    loadStatement();
  }, []);

  const formatAmount = (num) => {
    num = parseFloat(num || 0);
    if (num >= 10000000) return (num / 10000000).toFixed(2) + 'Cr';
    if (num >= 100000) return (num / 100000).toFixed(2) + 'L';
    return num.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2});
  };

  const isCredit = (t) => {
    const desc = (t.description || '').toLowerCase();
    return t.type === 'Funds In' || desc.includes('win') || desc.includes('refund') || desc.includes('deposit');
  };

  const renderItem = ({item}) => {
    const credit = isCredit(item);
    return (
      <View style={styles.txnItem}>
        <View style={[styles.txnIcon, credit ? styles.creditIcon : styles.debitIcon]}>
          <MaterialIcons
            name={credit ? 'arrow_downward' : 'arrow_upward'}
            size={18}
            color={credit ? '#22c55e' : '#ef4444'}
          />
        </View>
        <View style={styles.txnDetails}>
          <AppText style={styles.txnDesc} numberOfLines={1}>
            {item.description}
          </AppText>
          <AppText style={styles.txnDate}>{item.date}</AppText>
          {item.hash ? (
            <AppText style={styles.txnHash}>#{item.hash}</AppText>
          ) : null}
        </View>
        <AppText style={[styles.txnAmount, credit ? styles.creditText : styles.debitText]}>
          {credit ? '+' : '-'}₹{item.amount}
        </AppText>
      </View>
    );
  };

  const renderEmpty = () => (
    <View style={styles.emptyState}>
      <MaterialIcons name="receipt-long" size={48} color="#666" />
      <AppText style={styles.emptyText}>No transactions found</AppText>
    </View>
  );

  return (
    <AppScreen>
      <HeaderComponent
        title="Statement"
        onBackPress={() => navigation.goBack()}
      />

      {/* Wallet Summary */}
      <View style={styles.summaryRow}>
        <View style={styles.summaryItem}>
          <AppText style={styles.summaryLabel}>Balance</AppText>
          <AppText style={[styles.summaryValue, styles.creditText]}>
            ₹{formatAmount(wallet?.balanceWithBonus || wallet?.balance || 0)}
          </AppText>
        </View>
      </View>

      {/* Filter Tabs */}
      <View style={styles.filterRow}>
        {FILTERS.map(f => (
          <TouchableOpacity
            key={f.key}
            style={[styles.filterTab, activeFilter === f.key && styles.filterTabActive]}
            onPress={() => setActiveFilter(f.key)}>
            <AppText
              style={[
                styles.filterLabel,
                activeFilter === f.key && styles.filterLabelActive,
              ]}>
              {f.label}
            </AppText>
          </TouchableOpacity>
        ))}
      </View>

      {/* Transaction List */}
      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#D4A843" />
        </View>
      ) : (
        <FlatList
          data={filteredTxns}
          keyExtractor={(item, index) => `txn-${index}-${item.date}`}
          renderItem={renderItem}
          ListEmptyComponent={renderEmpty}
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
          }
        />
      )}
    </AppScreen>
  );
};

const styles = StyleSheet.create({
  summaryRow: {
    flexDirection: 'row',
    paddingHorizontal: wp(4),
    marginBottom: 12,
  },
  summaryItem: {
    flex: 1,
    backgroundColor: '#171717',
    borderRadius: 12,
    padding: 14,
    alignItems: 'center',
  },
  summaryLabel: {
    fontSize: fp(1.4),
    color: '#888',
    fontWeight: '600',
    textTransform: 'uppercase',
  },
  summaryValue: {
    fontSize: fp(2.2),
    fontWeight: '700',
    marginTop: 4,
  },
  filterRow: {
    flexDirection: 'row',
    paddingHorizontal: wp(4),
    marginBottom: 12,
    gap: 8,
  },
  filterTab: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: '#2a2a2a',
  },
  filterTabActive: {
    backgroundColor: '#D4A843',
  },
  filterLabel: {
    fontSize: fp(1.5),
    fontWeight: '600',
    color: '#666',
  },
  filterLabelActive: {
    color: '#fff',
  },
  listContent: {
    paddingHorizontal: wp(4),
    paddingBottom: 24,
  },
  txnItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#f0f0f0',
  },
  txnIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  creditIcon: {
    backgroundColor: 'rgba(34,197,94,0.1)',
  },
  debitIcon: {
    backgroundColor: 'rgba(239,68,68,0.1)',
  },
  txnDetails: {
    flex: 1,
  },
  txnDesc: {
    fontSize: fp(1.6),
    fontWeight: '600',
    color: '#1a1a1a',
  },
  txnDate: {
    fontSize: fp(1.3),
    color: '#888',
    marginTop: 2,
  },
  txnHash: {
    fontSize: fp(1.2),
    color: '#aaa',
    marginTop: 1,
  },
  txnAmount: {
    fontSize: fp(1.7),
    fontWeight: '700',
  },
  creditText: {
    color: '#22c55e',
  },
  debitText: {
    color: '#ef4444',
  },
  emptyState: {
    alignItems: 'center',
    paddingTop: hp(10),
  },
  emptyText: {
    marginTop: 12,
    color: '#888',
    fontSize: fp(1.6),
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
});

export default StatementScreen;
