import React from 'react';
import {Text, StyleSheet, View, TouchableOpacity, ActivityIndicator} from 'react-native';
import MaterialIcons from 'react-native-vector-icons/MaterialIcons';
import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';
import {useTheme} from '../context/ThemeContext';

/**
 * AppButton — Kokoroko Design System
 *
 * Props:
 *   variant:  'primary' | 'secondary' | 'danger' | 'ghost' | 'outline'  (default: 'primary')
 *   size:     'sm' | 'md' | 'lg'  (default: 'md')
 *   fullWidth: boolean (default: false)
 *   disabled:  boolean
 *   loading:   boolean
 *   leftIcon:  string (MaterialIcons name)
 *   rightIcon: string (MaterialIcons name)
 *
 * Legacy props (backward compat):
 *   buttonLight: boolean → maps to variant='outline'
 *   showArrow:   boolean → maps to rightIcon
 *   iconName, iconColor, iconSize
 *   buttonStyle, textStyle, contentContainerStyle
 */
export default function AppButton({
  children,
  // New API
  variant = 'primary',
  size = 'md',
  fullWidth = false,
  loading = false,
  leftIcon,
  rightIcon,
  // Legacy API (backward compat)
  buttonStyle,
  textStyle,
  onPress,
  buttonLight,
  disabled,
  showArrow,
  contentContainerStyle,
  iconName = 'arrow-right-alt',
  iconColor,
  iconSize = 40,
}) {
  const {colors, radius} = useTheme();

  // Legacy: buttonLight maps to outline variant
  const resolvedVariant = buttonLight ? 'outline' : variant;

  // Variant styles
  const variantStyles = {
    primary: {
      bg: colors.gold,
      text: colors.text_on_gold,
      border: 'transparent',
      iconFallback: colors.text_on_gold,
    },
    secondary: {
      bg: colors.bg_elevated,
      text: colors.text_primary,
      border: colors.border,
      iconFallback: colors.text_primary,
    },
    danger: {
      bg: colors.danger,
      text: '#ffffff',
      border: 'transparent',
      iconFallback: '#ffffff',
    },
    ghost: {
      bg: 'transparent',
      text: colors.gold,
      border: 'transparent',
      iconFallback: colors.gold,
    },
    outline: {
      bg: 'transparent',
      text: colors.gold,
      border: colors.gold,
      iconFallback: colors.gold,
    },
  };

  // Size styles
  const sizeStyles = {
    sm: {height: hp(4.5), paddingH: wp(4), fontSize: fp(1.6), iconSz: 18},
    md: {height: hp(6), paddingH: wp(6), fontSize: fp(2), iconSz: 22},
    lg: {height: hp(7), paddingH: wp(8), fontSize: fp(2.2), iconSz: 26},
  };

  const v = variantStyles[resolvedVariant] || variantStyles.primary;
  const s = sizeStyles[size] || sizeStyles.md;

  const isDisabled = disabled || loading;
  const finalBg = isDisabled ? colors.disabled : v.bg;
  const finalText = isDisabled ? colors.disabled_text : v.text;
  const finalBorder = isDisabled ? colors.disabled : v.border;

  const containerStyle = [
    {
      height: s.height,
      backgroundColor: finalBg,
      borderRadius: resolvedVariant === 'primary' ? 50 : radius.md,
      justifyContent: 'center',
      alignItems: 'center',
      borderWidth: resolvedVariant === 'outline' || resolvedVariant === 'secondary' ? 1 : 0,
      borderColor: finalBorder,
    },
    fullWidth
      ? {width: '100%'}
      : showArrow || contentContainerStyle
      ? {width: wp(84)} // Legacy compat: keep old width when using old API
      : {paddingHorizontal: s.paddingH},
    buttonStyle,
  ];

  // Determine icons
  const showLeftIcon = leftIcon && !loading;
  const showRightIcon = rightIcon || (showArrow && !loading);
  const rightIconName = rightIcon || iconName;
  const rightIconColor = iconColor || v.iconFallback;
  const rightIconSize = rightIcon ? s.iconSz : iconSize;

  const ButtonContent = () => (
    <View
      style={[
        styles.contentContainer,
        showArrow && {width: wp(50)},
        contentContainerStyle,
      ]}>
      {loading ? (
        <ActivityIndicator size="small" color={finalText} />
      ) : (
        <>
          {showLeftIcon && (
            <MaterialIcons
              name={leftIcon}
              size={s.iconSz}
              color={finalText}
              style={{marginRight: 6}}
            />
          )}
          <Text style={[{fontSize: s.fontSize, color: finalText, fontWeight: '600'}, textStyle]}>
            {children}
          </Text>
          {showRightIcon && (
            <MaterialIcons
              name={rightIconName}
              size={rightIconSize}
              color={rightIconColor}
            />
          )}
        </>
      )}
    </View>
  );

  return isDisabled && !loading ? (
    <View style={containerStyle}>
      <ButtonContent />
    </View>
  ) : (
    <TouchableOpacity
      style={containerStyle}
      onPress={onPress}
      disabled={isDisabled}
      activeOpacity={0.7}>
      <ButtonContent />
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  contentContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
});
