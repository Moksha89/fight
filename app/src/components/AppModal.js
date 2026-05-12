import React from 'react';
import {
  View,
  Modal,
  TouchableOpacity,
  TouchableWithoutFeedback,
  StyleSheet,
  Dimensions,
  ScrollView,
} from 'react-native';
import MaterialIcons from 'react-native-vector-icons/MaterialIcons';
import AppText from './AppText';
import {useTheme} from '../context/ThemeContext';

const {height: SCREEN_HEIGHT} = Dimensions.get('window');

/**
 * AppModal — Kokoroko Design System
 *
 * Props:
 *   visible, onClose, title, children, footer,
 *   size: 'sm' | 'md' | 'lg' | 'fullscreen' (default: 'md')
 *   closeOnBackdrop: boolean (default: true)
 */
const SIZE_MAP = {
  sm: 0.4,
  md: 0.6,
  lg: 0.8,
  fullscreen: 1,
};

export default function AppModal({
  visible,
  onClose,
  title,
  children,
  footer,
  size = 'md',
  closeOnBackdrop = true,
}) {
  const {colors, radius, shadows, spacing} = useTheme();
  const isFullscreen = size === 'fullscreen';
  const maxH = SCREEN_HEIGHT * (SIZE_MAP[size] || SIZE_MAP.md);

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={onClose}
      statusBarTranslucent>
      <TouchableWithoutFeedback
        onPress={closeOnBackdrop ? onClose : undefined}>
        <View style={[styles.overlay, {backgroundColor: colors.overlay}]}>
          <TouchableWithoutFeedback>
            <View
              style={[
                styles.content,
                {
                  backgroundColor: colors.card,
                  borderRadius: isFullscreen ? 0 : radius.lg,
                  maxHeight: isFullscreen ? '100%' : maxH,
                  ...(!isFullscreen && shadows.modal),
                },
                isFullscreen && styles.fullscreen,
              ]}>
              {/* Header */}
              {(title || onClose) && (
                <View
                  style={[
                    styles.header,
                    {borderBottomColor: colors.border},
                  ]}>
                  <AppText variant="h3" style={{flex: 1}}>
                    {title || ''}
                  </AppText>
                  {onClose && (
                    <TouchableOpacity onPress={onClose} style={styles.closeBtn}>
                      <MaterialIcons
                        name="close"
                        size={22}
                        color={colors.text_muted}
                      />
                    </TouchableOpacity>
                  )}
                </View>
              )}

              {/* Body */}
              <ScrollView
                style={styles.body}
                contentContainerStyle={{paddingBottom: spacing.lg}}
                showsVerticalScrollIndicator={false}>
                {children}
              </ScrollView>

              {/* Footer */}
              {footer && (
                <View
                  style={[
                    styles.footer,
                    {borderTopColor: colors.border},
                  ]}>
                  {footer}
                </View>
              )}
            </View>
          </TouchableWithoutFeedback>
        </View>
      </TouchableWithoutFeedback>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  content: {
    width: '90%',
    overflow: 'hidden',
  },
  fullscreen: {
    width: '100%',
    height: '100%',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: 1,
  },
  closeBtn: {
    padding: 4,
  },
  body: {
    paddingHorizontal: 16,
    paddingTop: 12,
  },
  footer: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderTopWidth: 1,
    gap: 8,
  },
});
