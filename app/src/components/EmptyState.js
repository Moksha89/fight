import React from 'react';
import {View, StyleSheet} from 'react-native';
import MaterialIcons from 'react-native-vector-icons/MaterialIcons';
import AppText from './AppText';
import AppButton from './AppButton';
import {useTheme} from '../context/ThemeContext';

/**
 * EmptyState — Kokoroko Design System
 *
 * Props:
 *   icon: MaterialIcons name (default: 'inbox')
 *   title: string
 *   message: string
 *   actionLabel: string (renders a button)
 *   onAction: function
 */
export default function EmptyState({
  icon = 'inbox',
  title = 'Nothing here yet',
  message,
  actionLabel,
  onAction,
}) {
  const {colors, spacing} = useTheme();

  return (
    <View style={styles.container}>
      <View
        style={[
          styles.iconCircle,
          {backgroundColor: colors.gold_bg},
        ]}>
        <MaterialIcons name={icon} size={40} color={colors.gold} />
      </View>

      <AppText variant="h3" align="center" style={styles.title}>
        {title}
      </AppText>

      {message ? (
        <AppText variant="bodySmall" color="muted" align="center" style={styles.message}>
          {message}
        </AppText>
      ) : null}

      {actionLabel && onAction ? (
        <AppButton
          variant="outline"
          size="sm"
          onPress={onAction}
          style={{marginTop: spacing.lg}}>
          {actionLabel}
        </AppButton>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 48,
    paddingHorizontal: 32,
  },
  iconCircle: {
    width: 72,
    height: 72,
    borderRadius: 36,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
  },
  title: {
    marginBottom: 6,
  },
  message: {
    maxWidth: 260,
  },
});
