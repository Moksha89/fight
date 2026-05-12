/**
 * Kokoroko Smart Toast
 * =====================
 * Enhanced toast notification system with:
 * - Multiple severity levels (info, success, warning, error)
 * - Auto-dismiss with configurable duration
 * - Queue support (shows multiple toasts sequentially)
 * - Slide-in/out animation
 */

import React, {useState, useEffect, useRef, useCallback} from 'react';
import {View, Text, StyleSheet, Animated, TouchableOpacity} from 'react-native';
import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';

const TOAST_COLORS = {
  error: {bg: '#2D1B1B', border: '#D44343', text: '#FF6B6B', icon: '✕'},
  warning: {bg: '#2D2A1B', border: '#D4A843', text: '#D4A843', icon: '⚠'},
  success: {bg: '#1B2D1E', border: '#43D46E', text: '#43D46E', icon: '✓'},
  info: {bg: '#1B1E2D', border: '#4387D4', text: '#4387D4', icon: 'ℹ'},
};

let _showToast = null;

/**
 * Call this from anywhere to show a toast.
 * @param {string} message
 * @param {object} options - { type: 'error'|'warning'|'success'|'info', duration: ms }
 */
export function showToast(message, options = {}) {
  if (_showToast) {
    _showToast(message, options);
  }
}

const SmartToast = () => {
  const [visible, setVisible] = useState(false);
  const [message, setMessage] = useState('');
  const [type, setType] = useState('error');
  const translateY = useRef(new Animated.Value(-100)).current;
  const opacity = useRef(new Animated.Value(0)).current;
  const timerRef = useRef(null);
  const queueRef = useRef([]);

  const showNext = useCallback(() => {
    if (queueRef.current.length === 0) return;

    const next = queueRef.current.shift();
    setMessage(next.message);
    setType(next.type || 'error');
    setVisible(true);

    Animated.parallel([
      Animated.spring(translateY, {
        toValue: 0,
        useNativeDriver: true,
        tension: 80,
        friction: 10,
      }),
      Animated.timing(opacity, {
        toValue: 1,
        duration: 200,
        useNativeDriver: true,
      }),
    ]).start();

    timerRef.current = setTimeout(() => {
      dismiss();
    }, next.duration || 4000);
  }, []);

  const dismiss = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);

    Animated.parallel([
      Animated.timing(translateY, {
        toValue: -100,
        duration: 200,
        useNativeDriver: true,
      }),
      Animated.timing(opacity, {
        toValue: 0,
        duration: 200,
        useNativeDriver: true,
      }),
    ]).start(() => {
      setVisible(false);
      // Show next in queue after small delay
      setTimeout(() => showNext(), 100);
    });
  }, [showNext]);

  useEffect(() => {
    _showToast = (msg, opts = {}) => {
      queueRef.current.push({
        message: msg,
        type: opts.type || 'error',
        duration: opts.duration || 4000,
      });

      if (!visible) {
        showNext();
      }
    };

    return () => {
      _showToast = null;
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [visible, showNext]);

  if (!visible) return null;

  const colors = TOAST_COLORS[type] || TOAST_COLORS.error;

  return (
    <Animated.View
      style={[
        styles.container,
        {
          backgroundColor: colors.bg,
          borderColor: colors.border,
          transform: [{translateY}],
          opacity,
        },
      ]}>
      <Text style={[styles.icon, {color: colors.text}]}>{colors.icon}</Text>
      <Text style={[styles.message, {color: '#E0E0E0'}]} numberOfLines={3}>
        {message}
      </Text>
      <TouchableOpacity onPress={dismiss} style={styles.closeBtn}>
        <Text style={styles.closeText}>✕</Text>
      </TouchableOpacity>
    </Animated.View>
  );
};

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    top: hp(6),
    left: wp(4),
    right: wp(4),
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 14,
    paddingHorizontal: 16,
    borderRadius: 12,
    borderWidth: 1,
    zIndex: 99999,
    elevation: 10,
    shadowColor: '#000',
    shadowOpacity: 0.3,
    shadowRadius: 10,
    shadowOffset: {width: 0, height: 4},
  },
  icon: {
    fontSize: 18,
    fontWeight: '700',
    marginRight: 12,
  },
  message: {
    flex: 1,
    fontSize: fp(1.6),
    lineHeight: 20,
  },
  closeBtn: {
    marginLeft: 8,
    padding: 4,
  },
  closeText: {
    color: '#666',
    fontSize: 14,
  },
});

export default SmartToast;
