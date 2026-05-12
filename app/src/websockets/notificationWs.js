import {baseWSEndpoint as BASE_URL} from '../Config/baseEndpoint';
import storage from '../utils/storage';

let notifSocket = null;
let notifReconnectTimeout = null;
let notifShouldReconnect = true;
let notifRetryCount = 0;
const MAX_RECONNECT_DELAY = 30000;

/**
 * Connect to the notifications WebSocket.
 * Receives real-time notifications (bet won/lost, deposit approved, etc.)
 *
 * @param {Function} onNotification - Called with notification data when a new one arrives
 * @param {Function} setUnreadCount - Called to update the unread notification badge count
 */
export const connectNotificationWebSocket = async (onNotification, setUnreadCount) => {
  notifShouldReconnect = true;

  const accessToken = await storage.getItem('accessToken');
  if (!accessToken) {
    console.warn('[WS:Notif] No access token');
    return;
  }

  if (notifSocket) {
    if (
      notifSocket.readyState === WebSocket.OPEN ||
      notifSocket.readyState === WebSocket.CONNECTING
    ) {
      return;
    }
    notifSocket = null;
  }

  const socketUrl = `${BASE_URL}/ws/notifications/?token=${accessToken}`;
  notifSocket = new WebSocket(socketUrl);

  notifSocket.onopen = () => {
    console.log('[WS:Notif] Connected');
    notifRetryCount = 0;
  };

  notifSocket.onmessage = event => {
    try {
      const message = JSON.parse(event.data);

      if (message.type === 'notification_init') {
        if (typeof setUnreadCount === 'function') {
          setUnreadCount(message.unread_count || 0);
        }
      } else if (message.type === 'new_notification') {
        if (typeof onNotification === 'function') {
          onNotification(message.data);
        }
        if (typeof setUnreadCount === 'function') {
          setUnreadCount(prev => (typeof prev === 'number' ? prev + 1 : 1));
        }
      } else if (message.type === 'notification_count') {
        if (typeof setUnreadCount === 'function') {
          setUnreadCount(message.unread_count || 0);
        }
      } else if (message.type === 'notifications_list') {
        // Response to get_notifications request
        if (typeof onNotification === 'function') {
          onNotification({type: 'list', data: message.data});
        }
      }
    } catch (err) {
      console.error('[WS:Notif] Parse error:', err);
    }
  };

  notifSocket.onerror = error => {
    console.error('[WS:Notif] Error:', error.message || error);
  };

  notifSocket.onclose = () => {
    notifSocket = null;
    if (notifShouldReconnect) {
      const delay = Math.min(1000 * Math.pow(2, notifRetryCount), MAX_RECONNECT_DELAY);
      notifRetryCount++;
      notifReconnectTimeout = setTimeout(() => {
        connectNotificationWebSocket(onNotification, setUnreadCount);
      }, delay);
    }
  };
};

/**
 * Send a message to the notification WS (e.g., mark as read).
 */
export const sendNotificationAction = (action, data = {}) => {
  if (notifSocket && notifSocket.readyState === WebSocket.OPEN) {
    notifSocket.send(JSON.stringify({action, ...data}));
  }
};

export const markNotificationRead = (notificationId) => {
  sendNotificationAction('mark_read', {notification_id: notificationId});
};

export const markAllNotificationsRead = () => {
  sendNotificationAction('mark_all_read');
};

export const requestNotificationsList = () => {
  sendNotificationAction('get_notifications');
};

export const closeNotificationWebSocket = () => {
  notifShouldReconnect = false;
  if (notifSocket) {
    notifSocket.close();
    notifSocket = null;
  }
  clearTimeout(notifReconnectTimeout);
};
