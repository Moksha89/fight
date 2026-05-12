import React, {useState, useRef} from 'react';
import {
  View,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  Image,
  Alert,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
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
import storage from '../../utils/storage';

const LoginRegisterScreen = ({navigation}) => {
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
      <AppText style={styles.label}>ENTER OTP</AppText>
      <View style={styles.otpRow}>
        {otp.map((digit, i) => (
          <TextInput
            key={i}
            ref={ref => (otpRefs.current[i] = ref)}
            style={styles.otpInput}
            value={digit}
            onChangeText={val => handleOtpChange(val, i)}
            onKeyPress={e => handleOtpKeyPress(e, i)}
            keyboardType="numeric"
            maxLength={1}
            placeholderTextColor="#666"
            selectionColor="#D4A843"
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
          <View style={styles.card}>
            {/* Logo */}
            <View style={styles.logoSection}>
              <Image
                source={require('../../assets/logos/logo.png')}
                style={styles.logo}
                resizeMode="contain"
              />
              <AppText style={styles.brandName}>Kokoroko</AppText>
              <AppText style={styles.subtitle}>
                {activeTab === 'login' ? 'Welcome back' : 'Create your account'}
              </AppText>
            </View>

            {/* Tabs */}
            <View style={styles.tabsContainer}>
              <TouchableOpacity
                style={[styles.tab, activeTab === 'login' && styles.tabActive]}
                onPress={() => switchTab('login')}>
                <AppText
                  style={[
                    styles.tabText,
                    activeTab === 'login' && styles.tabTextActive,
                  ]}>
                  Login
                </AppText>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.tab, activeTab === 'register' && styles.tabActive]}
                onPress={() => switchTab('register')}>
                <AppText
                  style={[
                    styles.tabText,
                    activeTab === 'register' && styles.tabTextActive,
                  ]}>
                  Register
                </AppText>
              </TouchableOpacity>
            </View>

            {/* Error */}
            {error ? (
              <View style={styles.errorBox}>
                <AppText style={styles.errorText}>{error}</AppText>
              </View>
            ) : null}

            {/* Login Form */}
            {activeTab === 'login' && (
              <View>
                <View style={styles.formGroup}>
                  <AppText style={styles.label}>MOBILE NUMBER</AppText>
                  <TextInput
                    style={styles.input}
                    placeholder="Enter mobile number"
                    placeholderTextColor="#666"
                    value={loginMobile}
                    onChangeText={setLoginMobile}
                    keyboardType="default"
                    autoCapitalize="none"
                    selectionColor="#D4A843"
                  />
                </View>
                <View style={styles.formGroup}>
                  <AppText style={styles.label}>PASSWORD</AppText>
                  <TextInput
                    style={styles.input}
                    placeholder="Enter password"
                    placeholderTextColor="#666"
                    value={loginPassword}
                    onChangeText={setLoginPassword}
                    secureTextEntry
                    selectionColor="#D4A843"
                  />
                </View>
                {step === 'otp' && renderOtpInputs()}
                <TouchableOpacity
                  style={styles.authBtn}
                  onPress={handleLogin}
                  disabled={isLoading}>
                  <AppText style={styles.authBtnText}>
                    {isLoading
                      ? 'Please wait...'
                      : step === 'form'
                      ? 'Send OTP & Login'
                      : 'Verify & Login'}
                  </AppText>
                </TouchableOpacity>
              </View>
            )}

            {/* Register Form */}
            {activeTab === 'register' && (
              <View>
                <View style={styles.formGroup}>
                  <AppText style={styles.label}>MOBILE NUMBER</AppText>
                  <TextInput
                    style={styles.input}
                    placeholder="10-digit mobile number"
                    placeholderTextColor="#666"
                    value={regMobile}
                    onChangeText={setRegMobile}
                    keyboardType="phone-pad"
                    selectionColor="#D4A843"
                  />
                </View>
                <View style={styles.formGroup}>
                  <AppText style={styles.label}>USERNAME</AppText>
                  <TextInput
                    style={styles.input}
                    placeholder="Choose a username"
                    placeholderTextColor="#666"
                    value={regUsername}
                    onChangeText={setRegUsername}
                    autoCapitalize="none"
                    selectionColor="#D4A843"
                  />
                </View>
                <View style={styles.formGroup}>
                  <AppText style={styles.label}>PASSWORD</AppText>
                  <TextInput
                    style={styles.input}
                    placeholder="Min 6 characters"
                    placeholderTextColor="#666"
                    value={regPassword}
                    onChangeText={setRegPassword}
                    secureTextEntry
                    selectionColor="#D4A843"
                  />
                </View>
                <View style={styles.formGroup}>
                  <AppText style={styles.label}>CONFIRM PASSWORD</AppText>
                  <TextInput
                    style={styles.input}
                    placeholder="Re-enter password"
                    placeholderTextColor="#666"
                    value={regConfirm}
                    onChangeText={setRegConfirm}
                    secureTextEntry
                    selectionColor="#D4A843"
                  />
                </View>
                {step === 'otp' && renderOtpInputs()}
                <TouchableOpacity
                  style={styles.authBtn}
                  onPress={handleRegister}
                  disabled={isLoading}>
                  <AppText style={styles.authBtnText}>
                    {isLoading
                      ? 'Please wait...'
                      : step === 'form'
                      ? 'Send OTP & Register'
                      : 'Verify & Register'}
                  </AppText>
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
    backgroundColor: '#0B0B0B',
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
    backgroundColor: '#1a1a1a',
    borderRadius: 16,
    padding: wp(7),
    width: '100%',
    maxWidth: 400,
    borderWidth: 1,
    borderColor: '#2a2a2a',
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
    color: '#D4A843',
    letterSpacing: -0.5,
  },
  subtitle: {
    color: '#a0a0a0',
    fontSize: fp(1.6),
    marginTop: 4,
  },
  tabsContainer: {
    flexDirection: 'row',
    backgroundColor: '#111111',
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
  tabActive: {
    backgroundColor: '#D4A843',
  },
  tabText: {
    fontSize: fp(1.6),
    fontWeight: '600',
    color: '#a0a0a0',
  },
  tabTextActive: {
    color: '#000',
  },
  errorBox: {
    backgroundColor: 'rgba(239,68,68,0.15)',
    borderRadius: 8,
    padding: wp(3),
    marginBottom: hp(1.5),
  },
  errorText: {
    color: '#ef4444',
    fontSize: fp(1.5),
    textAlign: 'center',
  },
  formGroup: {
    marginBottom: hp(1.6),
  },
  label: {
    fontSize: fp(1.2),
    fontWeight: '600',
    color: '#a0a0a0',
    marginBottom: 5,
    letterSpacing: 0.8,
  },
  input: {
    backgroundColor: '#111111',
    borderWidth: 1,
    borderColor: '#2a2a2a',
    borderRadius: 10,
    paddingVertical: hp(1.5),
    paddingHorizontal: wp(4),
    color: '#f0f0f0',
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
    backgroundColor: '#111111',
    borderWidth: 1,
    borderColor: '#2a2a2a',
    borderRadius: 10,
    textAlign: 'center',
    color: '#f0f0f0',
    fontSize: fp(2.2),
    fontWeight: '600',
  },
  authBtn: {
    backgroundColor: '#D4A843',
    borderRadius: 10,
    paddingVertical: hp(1.6),
    alignItems: 'center',
    marginTop: hp(1),
  },
  authBtnText: {
    color: '#000',
    fontSize: fp(1.7),
    fontWeight: '600',
  },
});

export default LoginRegisterScreen;
