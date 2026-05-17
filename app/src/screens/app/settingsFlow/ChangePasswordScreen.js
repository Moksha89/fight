import React, {useState} from 'react';
import {
  View,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  Alert,
  ActivityIndicator,
} from 'react-native';

import MaterialIcons from 'react-native-vector-icons/MaterialIcons';

import AppText from '../../../components/AppText';
import AppScreen from '../../../components/AppScreen';
import HeaderComponent from '../../../components/HeaderComponent';

import {apiRequest} from '../../../utils/apiClient';
import COLORS from '../../../context/designTokens';

import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';

const ChangePasswordScreen = ({navigation}) => {
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const handleSubmit = async () => {
    if (!currentPassword || !newPassword || !confirmPassword) {
      Alert.alert('Error', 'Please fill all fields');
      return;
    }
    if (newPassword.length < 6) {
      Alert.alert('Error', 'New password must be at least 6 characters');
      return;
    }
    if (newPassword !== confirmPassword) {
      Alert.alert('Error', 'New password and confirm password do not match');
      return;
    }

    setLoading(true);
    try {
      const result = await apiRequest('/api/user/change-password/', {
        method: 'POST',
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });

      if (result.success) {
        Alert.alert('Success', 'Password changed successfully', [
          {text: 'OK', onPress: () => navigation.goBack()},
        ]);
      } else {
        const msg =
          result.data?.detail ||
          result.data?.current_password?.[0] ||
          result.data?.new_password?.[0] ||
          'Failed to change password';
        Alert.alert('Error', msg);
      }
    } catch (e) {
      Alert.alert('Error', 'Network error. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const renderInput = (label, value, setValue, show, setShow, placeholder) => (
    <View style={styles.inputGroup}>
      <AppText style={styles.inputLabel}>{label}</AppText>
      <View style={styles.inputWrapper}>
        <TextInput
          style={styles.input}
          value={value}
          onChangeText={setValue}
          placeholder={placeholder}
          placeholderTextColor="#aaa"
          secureTextEntry={!show}
          autoCapitalize="none"
        />
        <TouchableOpacity
          style={styles.eyeBtn}
          onPress={() => setShow(!show)}>
          <MaterialIcons
            name={show ? 'visibility' : 'visibility-off'}
            size={22}
            color="#888"
          />
        </TouchableOpacity>
      </View>
    </View>
  );

  return (
    <AppScreen>
      <HeaderComponent
        title="Change Password"
        onBackPress={() => navigation.goBack()}
      />

      <View style={styles.content}>
        <View style={styles.card}>
          <MaterialIcons
            name="lock-outline"
            size={48}
            color="#D4A843"
            style={styles.lockIcon}
          />

          {renderInput(
            'Current Password',
            currentPassword,
            setCurrentPassword,
            showCurrent,
            setShowCurrent,
            'Enter current password',
          )}

          {renderInput(
            'New Password',
            newPassword,
            setNewPassword,
            showNew,
            setShowNew,
            'Enter new password (min 6 chars)',
          )}

          {renderInput(
            'Confirm New Password',
            confirmPassword,
            setConfirmPassword,
            showConfirm,
            setShowConfirm,
            'Re-enter new password',
          )}

          <TouchableOpacity
            style={[styles.submitBtn, loading && styles.submitBtnDisabled]}
            onPress={handleSubmit}
            disabled={loading}>
            {loading ? (
              <ActivityIndicator size="small" color="#fff" />
            ) : (
              <AppText style={styles.submitText}>Update Password</AppText>
            )}
          </TouchableOpacity>
        </View>
      </View>
    </AppScreen>
  );
};

const styles = StyleSheet.create({
  content: {
    flex: 1,
    paddingHorizontal: wp(4),
    paddingTop: 16,
  },
  card: {
    backgroundColor: '#171717',
    borderRadius: 16,
    padding: 24,
    shadowColor: '#000',
    shadowOffset: {width: 0, height: 2},
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 3,
  },
  lockIcon: {
    alignSelf: 'center',
    marginBottom: 20,
  },
  inputGroup: {
    marginBottom: 16,
  },
  inputLabel: {
    fontSize: fp(1.4),
    fontWeight: '600',
    color: '#A8A29E',
    marginBottom: 6,
  },
  inputWrapper: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: 'rgba(212,168,67,0.18)',
    borderRadius: 10,
    backgroundColor: '#1a1a1a',
  },
  input: {
    flex: 1,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: fp(1.7),
    color: '#F5F1E8',
  },
  eyeBtn: {
    padding: 12,
  },
  submitBtn: {
    backgroundColor: COLORS.gold,
    borderRadius: 10,
    paddingVertical: 14,
    alignItems: 'center',
    marginTop: 8,
  },
  submitBtnDisabled: {
    opacity: 0.6,
  },
  submitText: {
    color: COLORS.white,
    fontSize: fp(1.8),
    fontWeight: '700',
  },
});

export default ChangePasswordScreen;
