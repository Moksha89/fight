import React, {useState} from 'react';
import {View, TextInput, StyleSheet, TouchableOpacity} from 'react-native';
import MaterialIcons from 'react-native-vector-icons/MaterialIcons';
import AppText from './AppText';
import {useTheme} from '../context/ThemeContext';

/**
 * AppInput — Kokoroko Design System
 *
 * Props:
 *   label, value, onChangeText, placeholder, error, helperText,
 *   leftIcon, rightIcon, secureTextEntry, keyboardType, multiline,
 *   disabled, style, inputStyle, onRightIconPress
 */
export default function AppInput({
  label,
  value,
  onChangeText,
  placeholder,
  error,
  helperText,
  leftIcon,
  rightIcon,
  secureTextEntry,
  keyboardType,
  multiline = false,
  disabled = false,
  style,
  inputStyle,
  onRightIconPress,
  ...props
}) {
  const {colors, radius, spacing} = useTheme();
  const [focused, setFocused] = useState(false);

  const borderColor = error
    ? colors.danger
    : focused
    ? colors.gold
    : colors.border;

  return (
    <View style={[styles.container, style]}>
      {label ? (
        <AppText
          variant="label"
          color="secondary"
          style={styles.label}>
          {label}
        </AppText>
      ) : null}

      <View
        style={[
          styles.inputRow,
          {
            backgroundColor: colors.bg_input,
            borderColor: borderColor,
            borderRadius: radius.sm,
          },
          multiline && {minHeight: 80, alignItems: 'flex-start'},
          disabled && {opacity: 0.5},
        ]}>
        {leftIcon ? (
          <MaterialIcons
            name={leftIcon}
            size={20}
            color={colors.text_muted}
            style={styles.leftIcon}
          />
        ) : null}

        <TextInput
          value={value}
          onChangeText={onChangeText}
          placeholder={placeholder}
          placeholderTextColor={colors.text_muted}
          secureTextEntry={secureTextEntry}
          keyboardType={keyboardType}
          multiline={multiline}
          editable={!disabled}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          style={[
            styles.input,
            {color: colors.text_primary},
            multiline && {textAlignVertical: 'top', paddingTop: 12},
            inputStyle,
          ]}
          {...props}
        />

        {rightIcon ? (
          <TouchableOpacity
            onPress={onRightIconPress}
            disabled={!onRightIconPress}
            style={styles.rightIcon}>
            <MaterialIcons
              name={rightIcon}
              size={20}
              color={colors.text_muted}
            />
          </TouchableOpacity>
        ) : null}
      </View>

      {error ? (
        <AppText variant="caption" color="danger" style={styles.helper}>
          {error}
        </AppText>
      ) : helperText ? (
        <AppText variant="caption" color="muted" style={styles.helper}>
          {helperText}
        </AppText>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginBottom: 14,
  },
  label: {
    marginBottom: 6,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
  },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    paddingHorizontal: 12,
  },
  leftIcon: {
    marginRight: 8,
  },
  input: {
    flex: 1,
    fontSize: 14,
    paddingVertical: 12,
    fontFamily: undefined,
  },
  rightIcon: {
    marginLeft: 8,
    padding: 4,
  },
  helper: {
    marginTop: 4,
    marginLeft: 2,
  },
});
