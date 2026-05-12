import React, {useEffect, useState, useCallback} from 'react';
import {
  View,
  FlatList,
  StyleSheet,
  TouchableOpacity,
  RefreshControl,
} from 'react-native';

import MaterialIcons from 'react-native-vector-icons/MaterialIcons';

import AppText from '../../components/AppText';
import AppScreen from '../../components/AppScreen';
import HeaderComponent from '../../components/HeaderComponent';
import AppLoader from '../../components/AppLoader';
import EmptyState from '../../components/EmptyState';

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

import {useTheme} from '../../context/ThemeContext';

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

const NotificationsScreen = ({navigation}) => {
  const {colors} = useTheme();
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const NOTIF_COLORS = {
    DEPOSIT_APPROVED: colors.success,
    BET_WON: colors.success,
    BONUS_RECEIVED: colors.gold,
    DEPOSIT_REJECTED: colors.danger,
    WITHDRAWAL_REJECTED: colors.danger,
    BET_LOST: colors.danger,
    default: colors.gold,
  };

  useEffect(() => {
    connectNotificationWebSocket(handleNotification, setUnreadCount);
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
      <View style={[styles.notifItem, {borderBottomColor: colors.border}, !item.read && {backgroundColor: colors.surface_elevated}]}>
        <View style={[styles.notifIcon, {backgroundColor: iconColor + '15'}]}>
          <MaterialIcons name={iconName} size={22} color={iconColor} />
        </View>
        <View style={styles.notifContent}>
          <AppText style={[styles.notifTitle, {color: colors.text_primary}]} numberOfLines={1}>
            {item.title || type.replace(/_/g, ' ')}
          </AppText>
          {item.body ? (
            <AppText style={[styles.notifBody, {color: colors.text_muted}]} numberOfLines={2}>
              {item.body}
            </AppText>
          ) : null}
          <AppText style={[styles.notifTime, {color: colors.text_muted}]}>
            {getTimeAgo(item.created_at)}
          </AppText>
        </View>
        {!item.read && <View style={[styles.unreadDot, {backgroundColor: colors.gold}]} />}
      </View>
    );
  };

  return (
    <AppScreen>
      <HeaderComponent
        title="Notifications"
        onBackPress={() => navigation.goBack()}
        RightIconComponent={
          unreadCount > 0 ? (
            <MaterialIcons name="done-all" size={24} color={colors.gold} />
          ) : null
        }
        onIconPress={handleMarkAllRead}
      />

      {loading ? (
        <AppLoader fullScreen text="Loading notifications..." />
      ) : (
        <FlatList
          data={notifications}
          keyExtractor={(item, index) => `notif-${index}-${item.created_at}`}
          renderItem={renderItem}
          ListEmptyComponent={
            <EmptyState
              icon="notifications-none"
              title="No notifications yet"
              message="You'll see bet results, deposit/withdrawal updates, and more here."
            />
          }
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              tintColor={colors.gold}
              colors={[colors.gold]}
            />
          }
        />
      )}
    </AppScreen>
  );
};

const styles = StyleSheet.create({
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
  },
  notifBody: {
    fontSize: fp(1.4),
    marginTop: 2,
  },
  notifTime: {
    fontSize: fp(1.2),
    marginTop: 3,
  },
  unreadDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginLeft: 8,
  },
});

export default NotificationsScreen;
