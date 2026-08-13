import React, {useState, useRef} from 'react';
import {
  View,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  Image,
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
import {getOtp, loginWithPassword, registerUser} from '../../apis/authApi';
import {useAuth} from '../../context/AuthContext';
import {useTheme} from '../../context/ThemeContext';
import storage from '../../utils/storage';

const LoginRegisterScreen = ({navigation}) => {
  const {colors, radius, spacing} = useTheme();
  const [activeTab, setActiveTab] = useState('login');
  const [step, setStep] = useState('form'); // 'form' or 'otp'
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  // Login fields
  const [loginMobile, setLoginMobile] = useState('');
  const [loginPassword, setLoginPassword] = useState('');

  // Register fields
  const [regMobile, setRegMobile] = useState('');
  const [regUsername, setRegUsername] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [regConfirm, setRegConfirm] = useState('');

  // OTP
  const [otp, setOtp] = useState(['', '', '', '', '', '']);
  const otpRefs = useRef([]);

  const {login} = useAuth();

  const switchTab = tab => {
    setActiveTab(tab);
    setStep('form');
    setError('');
    setOtp(['', '', '', '', '', '']);
  };

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

  const handleLogin = async () => {
    if (!loginMobile || !loginPassword) {
      setError('Please enter mobile number and password');
      return;
    }

    setIsLoading(true);
    setError('');

    if (step === 'form') {
      const result = await getOtp(loginMobile);
      if (result.success) {
        setStep('otp');
        setOtp(['', '', '', '', '', '']);
      } else {
        const msg = result.error?.message || result.data?.error || 'Failed to send OTP';
        setError(msg);
      }
    } else {
      const otpStr = getOtpString();
      if (otpStr.length !== 6) {
        setError('Enter the 6-digit OTP');
        setIsLoading(false);
        return;
      }

      const result = await loginWithPassword(loginMobile, loginPassword, otpStr);
      if (result.success) {
        await storage.setItem('isProfileUpdated', 'true');
        await storage.setItem('isPinSet', 'true');
        await login({
          access: result.data.access_token,
          refresh: result.data.refresh_token,
        });
      } else {
        const msg = result.error?.message || result.data?.error || 'Login failed';
        setError(msg);
      }
    }

    setIsLoading(false);
  };

  const handleRegister = async () => {
    if (!regMobile || !regUsername || !regPassword || !regConfirm) {
      setError('Please fill all fields');
      return;
    }
    if (!/^\d{10}$/.test(regMobile)) {
      setError('Enter a valid 10-digit mobile number');
      return;
    }
    if (regPassword.length < 6) {
      setError('Password must be at least 6 characters');
      return;
    }
    if (regPassword !== regConfirm) {
      setError('Passwords do not match');
      return;
    }

    setIsLoading(true);
    setError('');

    if (step === 'form') {
      const result = await getOtp(regMobile);
      if (result.success) {
        setStep('otp');
        setOtp(['', '', '', '', '', '']);
      } else {
        const msg = result.error?.message || result.data?.error || 'Failed to send OTP';
        setError(msg);
      }
    } else {
      const otpStr = getOtpString();
      if (otpStr.length !== 6) {
        setError('Enter the 6-digit OTP');
        setIsLoading(false);
        return;
      }

      const result = await registerUser(regMobile, regUsername, regPassword, regConfirm, otpStr);
      if (result.success) {
        await storage.setItem('isProfileUpdated', 'true');
        await storage.setItem('isPinSet', 'true');
        await login({
          access: result.data.access_token,
          refresh: result.data.refresh_token,
        });
      } else {
        const msg = result.error?.message || result.data?.error || 'Registration failed';
        setError(msg);
      }
    }

    setIsLoading(false);
  };

  const renderOtpInputs = () => (
    <View style={styles.otpContainer}>
      <AppText style={[styles.label, {color: colors.text_secondary}]}>ENTER OTP</AppText>
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
          <View style={[styles.card, {backgroundColor: colors.card, borderColor: colors.border}]}>
            {/* Logo */}
            <View style={styles.logoSection}>
              <Image
                source={require('../../assets/logos/logo.png')}
                style={styles.logo}
                resizeMode="contain"
              />
              <AppText style={[styles.brandName, {color: colors.gold}]}>Kokoroko</AppText>
              <AppText style={[styles.subtitle, {color: colors.text_secondary}]}>
                {activeTab === 'login' ? 'Welcome back' : 'Create your account'}
              </AppText>
            </View>

            {/* Tabs */}
            <View style={[styles.tabsContainer, {backgroundColor: colors.surface}]}>
              <TouchableOpacity
                style={[
                  styles.tab,
                  activeTab === 'login' && {backgroundColor: colors.gold},
                ]}
                onPress={() => switchTab('login')}>
                <AppText
                  style={[
                    styles.tabText,
                    {color: colors.text_secondary},
                    activeTab === 'login' && {color: colors.background},
                  ]}>
                  Login
                </AppText>
              </TouchableOpacity>
              <TouchableOpacity
                style={[
                  styles.tab,
                  activeTab === 'register' && {backgroundColor: colors.gold},
                ]}
                onPress={() => switchTab('register')}>
                <AppText
                  style={[
                    styles.tabText,
                    {color: colors.text_secondary},
                    activeTab === 'register' && {color: colors.background},
                  ]}>
                  Register
                </AppText>
              </TouchableOpacity>
            </View>

            {/* Error */}
            {error ? (
              <View style={[styles.errorBox, {backgroundColor: 'rgba(239,68,68,0.15)'}]}>
                <AppText style={[styles.errorText, {color: colors.danger}]}>{error}</AppText>
              </View>
            ) : null}

            {/* Login Form */}
            {activeTab === 'login' && (
              <View>
                <View style={styles.formGroup}>
                  <AppText style={[styles.label, {color: colors.text_secondary}]}>MOBILE NUMBER</AppText>
                  <TextInput
                    style={[styles.input, {backgroundColor: colors.surface, borderColor: colors.border, color: colors.text_primary}]}
                    placeholder="Enter mobile number"
                    placeholderTextColor={colors.text_muted}
                    value={loginMobile}
                    onChangeText={setLoginMobile}
                    keyboardType="default"
                    autoCapitalize="none"
                    selectionColor={colors.gold}
                  />
                </View>
                <View style={styles.formGroup}>
                  <AppText style={[styles.label, {color: colors.text_secondary}]}>PASSWORD</AppText>
                  <TextInput
                    style={[styles.input, {backgroundColor: colors.surface, borderColor: colors.border, color: colors.text_primary}]}
                    placeholder="Enter password"
                    placeholderTextColor={colors.text_muted}
                    value={loginPassword}
                    onChangeText={setLoginPassword}
                    secureTextEntry
                    selectionColor={colors.gold}
                  />
                </View>
                {step === 'otp' && renderOtpInputs()}
                <TouchableOpacity
                  style={[styles.authBtn, {backgroundColor: colors.gold}]}
                  onPress={handleLogin}
                  disabled={isLoading}>
                  {isLoading ? (
                    <ActivityIndicator color={colors.background} />
                  ) : (
                    <AppText style={[styles.authBtnText, {color: colors.background}]}>
                      {step === 'form' ? 'Send OTP & Login' : 'Verify & Login'}
                    </AppText>
                  )}
                </TouchableOpacity>
                <TouchableOpacity
                  style={styles.forgotLink}
                  onPress={() => navigation.navigate('ForgotPasswordScreen')}>
                  <AppText
                    style={[styles.forgotLinkText, {color: colors.gold}]}>
                    Forgot Password?
                  </AppText>
                </TouchableOpacity>
              </View>
            )}

            {/* Register Form */}
            {activeTab === 'register' && (
              <View>
                <View style={styles.formGroup}>
                  <AppText style={[styles.label, {color: colors.text_secondary}]}>MOBILE NUMBER</AppText>
                  <TextInput
                    style={[styles.input, {backgroundColor: colors.surface, borderColor: colors.border, color: colors.text_primary}]}
                    placeholder="10-digit mobile number"
                    placeholderTextColor={colors.text_muted}
                    value={regMobile}
                    onChangeText={setRegMobile}
                    keyboardType="phone-pad"
                    selectionColor={colors.gold}
                  />
                </View>
                <View style={styles.formGroup}>
                  <AppText style={[styles.label, {color: colors.text_secondary}]}>USERNAME</AppText>
                  <TextInput
                    style={[styles.input, {backgroundColor: colors.surface, borderColor: colors.border, color: colors.text_primary}]}
                    placeholder="Choose a username"
                    placeholderTextColor={colors.text_muted}
                    value={regUsername}
                    onChangeText={setRegUsername}
                    autoCapitalize="none"
                    selectionColor={colors.gold}
                  />
                </View>
                <View style={styles.formGroup}>
                  <AppText style={[styles.label, {color: colors.text_secondary}]}>PASSWORD</AppText>
                  <TextInput
                    style={[styles.input, {backgroundColor: colors.surface, borderColor: colors.border, color: colors.text_primary}]}
                    placeholder="Min 6 characters"
                    placeholderTextColor={colors.text_muted}
                    value={regPassword}
                    onChangeText={setRegPassword}
                    secureTextEntry
                    selectionColor={colors.gold}
                  />
                </View>
                <View style={styles.formGroup}>
                  <AppText style={[styles.label, {color: colors.text_secondary}]}>CONFIRM PASSWORD</AppText>
                  <TextInput
                    style={[styles.input, {backgroundColor: colors.surface, borderColor: colors.border, color: colors.text_primary}]}
                    placeholder="Re-enter password"
                    placeholderTextColor={colors.text_muted}
                    value={regConfirm}
                    onChangeText={setRegConfirm}
                    secureTextEntry
                    selectionColor={colors.gold}
                  />
                </View>
                {step === 'otp' && renderOtpInputs()}
                <TouchableOpacity
                  style={[styles.authBtn, {backgroundColor: colors.gold}]}
                  onPress={handleRegister}
                  disabled={isLoading}>
                  {isLoading ? (
                    <ActivityIndicator color={colors.background} />
                  ) : (
                    <AppText style={[styles.authBtnText, {color: colors.background}]}>
                      {step === 'form' ? 'Send OTP & Register' : 'Verify & Register'}
                    </AppText>
                  )}
                </TouchableOpacity>
              </View>
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
  logoSection: {
    alignItems: 'center',
    marginBottom: hp(3),
  },
  logo: {
    width: 56,
    height: 56,
    borderRadius: 14,
    marginBottom: 12,
  },
  brandName: {
    fontSize: fp(2.8),
    fontWeight: '800',
    letterSpacing: -0.5,
  },
  subtitle: {
    fontSize: fp(1.6),
    marginTop: 4,
  },
  tabsContainer: {
    flexDirection: 'row',
    borderRadius: 10,
    padding: 3,
    marginBottom: hp(2.5),
  },
  tab: {
    flex: 1,
    paddingVertical: hp(1.2),
    alignItems: 'center',
    borderRadius: 8,
  },
  tabText: {
    fontSize: fp(1.6),
    fontWeight: '600',
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
  forgotLink: {
    alignItems: 'center',
    marginTop: hp(1.5),
  },
  forgotLinkText: {
    fontSize: fp(1.5),
    fontWeight: '600',
  },
});

export default LoginRegisterScreen;
