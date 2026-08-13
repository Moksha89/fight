import React, {useState, useRef} from 'react';
import {
  View,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  ActivityIndicator,
} from 'react-native';

import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';

import AppScreen from '../../components/AppScreen';
import AppText from '../../components/AppText';
import {useTheme} from '../../context/ThemeContext';
import {
  forgotPasswordRequestOtp,
  forgotPasswordVerifyOtp,
  forgotPasswordReset,
} from '../../apis/authApi';

const ForgotPasswordScreen = ({navigation}) => {
  const {colors} = useTheme();
  const [step, setStep] = useState('mobile'); // mobile → otp → reset → success
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const [mobile, setMobile] = useState('');
  const [otp, setOtp] = useState(['', '', '', '', '', '']);
  const [resetToken, setResetToken] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  const otpRefs = useRef([]);

  const handleOtpChange = (value, index) => {
    const newOtp = [...otp];
    newOtp[index] = value;
    setOtp(newOtp);
    if (value && index < 5) {
      otpRefs.current[index + 1]?.focus();
    }
  };

  const handleOtpKeyPress = (e, index) => {
    if (e.nativeEvent.key === 'Backspace' && !otp[index] && index > 0) {
      otpRefs.current[index - 1]?.focus();
    }
  };

  const getOtpString = () => otp.join('');

  const handleRequestOtp = async () => {
    if (!mobile) {
      setError('Please enter your mobile number');
      return;
    }
    if (!/^\d{10}$/.test(mobile)) {
      setError('Enter a valid 10-digit mobile number');
      return;
    }

    setIsLoading(true);
    setError('');

    const result = await forgotPasswordRequestOtp(mobile);
    if (result.success) {
      setStep('otp');
      setOtp(['', '', '', '', '', '']);
      setSuccessMsg(result.data.message || 'OTP sent');
    } else {
      const msg =
        result.error?.message || result.data?.error || 'Failed to send OTP';
      setError(msg);
    }

    setIsLoading(false);
  };

  const handleVerifyOtp = async () => {
    const otpStr = getOtpString();
    if (otpStr.length !== 6) {
      setError('Enter the 6-digit OTP');
      return;
    }

    setIsLoading(true);
    setError('');
    setSuccessMsg('');

    const result = await forgotPasswordVerifyOtp(mobile, otpStr);
    if (result.success && result.data.reset_token) {
      setResetToken(result.data.reset_token);
      setStep('reset');
      setSuccessMsg('OTP verified. Set your new password.');
    } else {
      const msg =
        result.error?.message || result.data?.error || 'OTP verification failed';
      setError(msg);
    }

    setIsLoading(false);
  };

  const handleResetPassword = async () => {
    if (!newPassword || !confirmPassword) {
      setError('Please fill in both password fields');
      return;
    }
    if (newPassword.length < 6) {
      setError('Password must be at least 6 characters');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setIsLoading(true);
    setError('');
    setSuccessMsg('');

    const result = await forgotPasswordReset(
      resetToken,
      newPassword,
      confirmPassword,
    );
    if (result.success) {
      setStep('success');
      setSuccessMsg(
        result.data.message || 'Password reset successful!',
      );
    } else {
      const msg =
        result.error?.message || result.data?.error || 'Password reset failed';
      setError(msg);
    }

    setIsLoading(false);
  };

  const renderOtpInputs = () => (
    <View style={styles.otpContainer}>
      <AppText style={[styles.label, {color: colors.text_secondary}]}>
        ENTER OTP
      </AppText>
      <View style={styles.otpRow}>
        {otp.map((digit, i) => (
          <TextInput
            key={i}
            ref={ref => (otpRefs.current[i] = ref)}
            style={[
              styles.otpInput,
              {
                backgroundColor: colors.surface,
                borderColor: colors.border,
                color: colors.text_primary,
              },
            ]}
            value={digit}
            onChangeText={val => handleOtpChange(val, i)}
            onKeyPress={e => handleOtpKeyPress(e, i)}
            keyboardType="numeric"
            maxLength={1}
            placeholderTextColor={colors.text_muted}
            selectionColor={colors.gold}
          />
        ))}
      </View>
    </View>
  );

  return (
    <AppScreen style={styles.container}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.keyboardView}>
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          keyboardShouldPersistTaps="handled">
          <View
            style={[
              styles.card,
              {backgroundColor: colors.card, borderColor: colors.border},
            ]}>
            {/* Header */}
            <View style={styles.headerSection}>
              <AppText style={[styles.title, {color: colors.gold}]}>
                {step === 'success' ? 'Done!' : 'Forgot Password'}
              </AppText>
              <AppText style={[styles.subtitle, {color: colors.text_secondary}]}>
                {step === 'mobile' && 'Enter your registered mobile number'}
                {step === 'otp' && 'Enter the OTP sent to your mobile'}
                {step === 'reset' && 'Set your new password'}
                {step === 'success' && 'Your password has been reset'}
              </AppText>
            </View>

            {/* Success message */}
            {successMsg && !error ? (
              <View
                style={[
                  styles.successBox,
                  {backgroundColor: 'rgba(34,197,94,0.15)'},
                ]}>
                <AppText style={[styles.successText, {color: '#22c55e'}]}>
                  {successMsg}
                </AppText>
              </View>
            ) : null}

            {/* Error */}
            {error ? (
              <View
                style={[
                  styles.errorBox,
                  {backgroundColor: 'rgba(239,68,68,0.15)'},
                ]}>
                <AppText style={[styles.errorText, {color: colors.danger}]}>
                  {error}
                </AppText>
              </View>
            ) : null}

            {/* Step 1: Mobile number */}
            {step === 'mobile' && (
              <View>
                <View style={styles.formGroup}>
                  <AppText style={[styles.label, {color: colors.text_secondary}]}>
                    MOBILE NUMBER
                  </AppText>
                  <TextInput
                    style={[
                      styles.input,
                      {
                        backgroundColor: colors.surface,
                        borderColor: colors.border,
                        color: colors.text_primary,
                      },
                    ]}
                    placeholder="10-digit mobile number"
                    placeholderTextColor={colors.text_muted}
                    value={mobile}
                    onChangeText={setMobile}
                    keyboardType="phone-pad"
                    selectionColor={colors.gold}
                  />
                </View>
                <TouchableOpacity
                  style={[styles.authBtn, {backgroundColor: colors.gold}]}
                  onPress={handleRequestOtp}
                  disabled={isLoading}>
                  {isLoading ? (
                    <ActivityIndicator color={colors.background} />
                  ) : (
                    <AppText
                      style={[styles.authBtnText, {color: colors.background}]}>
                      Send OTP
                    </AppText>
                  )}
                </TouchableOpacity>
              </View>
            )}

            {/* Step 2: OTP */}
            {step === 'otp' && (
              <View>
                {renderOtpInputs()}
                <TouchableOpacity
                  style={[styles.authBtn, {backgroundColor: colors.gold}]}
                  onPress={handleVerifyOtp}
                  disabled={isLoading}>
                  {isLoading ? (
                    <ActivityIndicator color={colors.background} />
                  ) : (
                    <AppText
                      style={[styles.authBtnText, {color: colors.background}]}>
                      Verify OTP
                    </AppText>
                  )}
                </TouchableOpacity>
              </View>
            )}

            {/* Step 3: New password */}
            {step === 'reset' && (
              <View>
                <View style={styles.formGroup}>
                  <AppText style={[styles.label, {color: colors.text_secondary}]}>
                    NEW PASSWORD
                  </AppText>
                  <TextInput
                    style={[
                      styles.input,
                      {
                        backgroundColor: colors.surface,
                        borderColor: colors.border,
                        color: colors.text_primary,
                      },
                    ]}
                    placeholder="Min 6 characters"
                    placeholderTextColor={colors.text_muted}
                    value={newPassword}
                    onChangeText={setNewPassword}
                    secureTextEntry
                    selectionColor={colors.gold}
                  />
                </View>
                <View style={styles.formGroup}>
                  <AppText style={[styles.label, {color: colors.text_secondary}]}>
                    CONFIRM PASSWORD
                  </AppText>
                  <TextInput
                    style={[
                      styles.input,
                      {
                        backgroundColor: colors.surface,
                        borderColor: colors.border,
                        color: colors.text_primary,
                      },
                    ]}
                    placeholder="Re-enter password"
                    placeholderTextColor={colors.text_muted}
                    value={confirmPassword}
                    onChangeText={setConfirmPassword}
                    secureTextEntry
                    selectionColor={colors.gold}
                  />
                </View>
                <TouchableOpacity
                  style={[styles.authBtn, {backgroundColor: colors.gold}]}
                  onPress={handleResetPassword}
                  disabled={isLoading}>
                  {isLoading ? (
                    <ActivityIndicator color={colors.background} />
                  ) : (
                    <AppText
                      style={[styles.authBtnText, {color: colors.background}]}>
                      Reset Password
                    </AppText>
                  )}
                </TouchableOpacity>
              </View>
            )}

            {/* Step 4: Success */}
            {step === 'success' && (
              <View>
                <TouchableOpacity
                  style={[styles.authBtn, {backgroundColor: colors.gold}]}
                  onPress={() => navigation.navigate('LoginRegisterScreen')}>
                  <AppText
                    style={[styles.authBtnText, {color: colors.background}]}>
                    Back to Login
                  </AppText>
                </TouchableOpacity>
              </View>
            )}

            {/* Back to login link */}
            {step !== 'success' && (
              <TouchableOpacity
                style={styles.backLink}
                onPress={() => navigation.navigate('LoginRegisterScreen')}>
                <AppText
                  style={[styles.backLinkText, {color: colors.text_secondary}]}>
                  Back to Login
                </AppText>
              </TouchableOpacity>
            )}
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </AppScreen>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  keyboardView: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: wp(5),
    paddingVertical: hp(4),
  },
  card: {
    borderRadius: 16,
    padding: wp(7),
    width: '100%',
    maxWidth: 400,
    borderWidth: 1,
  },
  headerSection: {
    alignItems: 'center',
    marginBottom: hp(3),
  },
  title: {
    fontSize: fp(2.8),
    fontWeight: '800',
    letterSpacing: -0.5,
  },
  subtitle: {
    fontSize: fp(1.6),
    marginTop: 4,
    textAlign: 'center',
  },
  successBox: {
    borderRadius: 8,
    padding: wp(3),
    marginBottom: hp(1.5),
  },
  successText: {
    fontSize: fp(1.5),
    textAlign: 'center',
  },
  errorBox: {
    borderRadius: 8,
    padding: wp(3),
    marginBottom: hp(1.5),
  },
  errorText: {
    fontSize: fp(1.5),
    textAlign: 'center',
  },
  formGroup: {
    marginBottom: hp(1.6),
  },
  label: {
    fontSize: fp(1.2),
    fontWeight: '600',
    marginBottom: 5,
    letterSpacing: 0.8,
  },
  input: {
    borderWidth: 1,
    borderRadius: 10,
    paddingVertical: hp(1.5),
    paddingHorizontal: wp(4),
    fontSize: fp(1.7),
    fontFamily: 'System',
  },
  otpContainer: {
    marginBottom: hp(1.5),
  },
  otpRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  otpInput: {
    width: wp(11),
    height: wp(12),
    borderWidth: 1,
    borderRadius: 10,
    textAlign: 'center',
    fontSize: fp(2.2),
    fontWeight: '600',
  },
  authBtn: {
    borderRadius: 10,
    paddingVertical: hp(1.6),
    alignItems: 'center',
    marginTop: hp(1),
  },
  authBtnText: {
    fontSize: fp(1.7),
    fontWeight: '600',
  },
  backLink: {
    alignItems: 'center',
    marginTop: hp(2),
  },
  backLinkText: {
    fontSize: fp(1.5),
    textDecorationLine: 'underline',
  },
});

export default ForgotPasswordScreen;
