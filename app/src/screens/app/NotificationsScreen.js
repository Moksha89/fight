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

import AppText from '../../components/AppText';
import AppScreen from '../../components/AppScreen';
import HeaderComponent from '../../components/HeaderComponent';

import {
  connectNotificationWebSocket,
  closeNotificationWebSocket,
  markAllNotificationsRead,
  requestNotificationsList,
} from '../../websockets/notificationWs';

import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';

import COLORS from '../../context/designTokens';

const NOTIF_ICONS = {
  DEPOSIT_SUBMITTED: 'account_balance',
  DEPOSIT_APPROVED: 'check_circle',
  DEPOSIT_REJECTED: 'cancel',
  WITHDRAWAL_SUBMITTED: 'send',
  WITHDRAWAL_APPROVED: 'check_circle',
  WITHDRAWAL_REJECTED: 'cancel',
  BET_PLACED: 'casino',
  BET_WON: 'emoji_events',
  BET_LOST: 'sentiment_dissatisfied',
  MATCH_CANCELLED: 'event_busy',
  BONUS_RECEIVED: 'card_giftcard',
  default: 'notifications',
};

const NOTIF_COLORS = {
  DEPOSIT_APPROVED: COLORS.success,
  BET_WON: COLORS.success,
  BONUS_RECEIVED: COLORS.gold,
  DEPOSIT_REJECTED: COLORS.meron_light,
  WITHDRAWAL_REJECTED: COLORS.meron_light,
  BET_LOST: COLORS.meron_light,
  default: COLORS.gold,
};

const NotificationsScreen = ({navigation}) => {
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    connectNotificationWebSocket(handleNotification, setUnreadCount);
    // Request initial list
    setTimeout(() => {
      requestNotificationsList();
    }, 500);

    return () => closeNotificationWebSocket();
  }, []);

  const handleNotification = (data) => {
    if (data && data.type === 'list') {
      setNotifications(data.data || []);
      setLoading(false);
      setRefreshing(false);
    } else if (data) {
      setNotifications(prev => [data, ...prev]);
    }
  };

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    requestNotificationsList();
  }, []);

  const handleMarkAllRead = () => {
    markAllNotificationsRead();
    setUnreadCount(0);
    setNotifications(prev =>
      prev.map(n => ({...n, read: true})),
    );
  };

  const getTimeAgo = (dateStr) => {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now - date;
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return 'Just now';
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHrs = Math.floor(diffMin / 60);
    if (diffHrs < 24) return `${diffHrs}h ago`;
    const diffDays = Math.floor(diffHrs / 24);
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString('en-IN', {day: 'numeric', month: 'short'});
  };

  const renderItem = ({item, index}) => {
    const type = item.notification_type || item.type || 'default';
    const iconName = NOTIF_ICONS[type] || NOTIF_ICONS.default;
    const iconColor = NOTIF_COLORS[type] || NOTIF_COLORS.default;

    return (
      <View style={[styles.notifItem, !item.read && styles.notifUnread]}>
        <View style={[styles.notifIcon, {backgroundColor: iconColor + '15'}]}>
          <MaterialIcons name={iconName} size={22} color={iconColor} />
        </View>
        <View style={styles.notifContent}>
          <AppText style={styles.notifTitle} numberOfLines={1}>
            {item.title || type.replace(/_/g, ' ')}
          </AppText>
          {item.body ? (
            <AppText style={styles.notifBody} numberOfLines={2}>
              {item.body}
            </AppText>
          ) : null}
          <AppText style={styles.notifTime}>
            {getTimeAgo(item.created_at)}
          </AppText>
        </View>
        {!item.read && <View style={styles.unreadDot} />}
      </View>
    );
  };

  const renderEmpty = () => (
    <View style={styles.emptyState}>
      <MaterialIcons name="notifications-none" size={56} color="#ccc" />
      <AppText style={styles.emptyText}>No notifications yet</AppText>
      <AppText style={styles.emptySubtext}>
        You'll see bet results, deposit/withdrawal updates, and more here.
      </AppText>
    </View>
  );

  return (
    <AppScreen>
      <HeaderComponent
        title="Notifications"
        onBackPress={() => navigation.goBack()}
        RightIconComponent={
          unreadCount > 0 ? (
            <MaterialIcons name="done-all" size={24} color="#D4A843" />
          ) : null
        }
        onIconPress={handleMarkAllRead}
      />

      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#D4A843" />
        </View>
      ) : (
        <FlatList
          data={notifications}
          keyExtractor={(item, index) => `notif-${index}-${item.created_at}`}
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
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  listContent: {
    paddingHorizontal: wp(4),
    paddingBottom: 24,
    flexGrow: 1,
  },
  notifItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 14,
    paddingHorizontal: 4,
    borderBottomWidth: 1,
    borderBottomColor: '#f0f0f0',
  },
  notifUnread: {
    backgroundColor: '#1F1A12',
  },
  notifIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  notifContent: {
    flex: 1,
  },
  notifTitle: {
    fontSize: fp(1.6),
    fontWeight: '600',
    color: COLORS.text_primary,
  },
  notifBody: {
    fontSize: fp(1.4),
    color: COLORS.text_muted,
    marginTop: 2,
  },
  notifTime: {
    fontSize: fp(1.2),
    color: COLORS.text_label,
    marginTop: 3,
  },
  unreadDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: COLORS.gold,
    marginLeft: 8,
  },
  emptyState: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingTop: hp(15),
  },
  emptyText: {
    marginTop: 12,
    fontSize: fp(1.8),
    fontWeight: '600',
    color: COLORS.text_muted,
  },
  emptySubtext: {
    marginTop: 6,
    fontSize: fp(1.4),
    color: COLORS.text_label,
    textAlign: 'center',
    paddingHorizontal: wp(10),
  },
});

export default NotificationsScreen;
