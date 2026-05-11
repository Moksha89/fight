import React, {useState, useEffect} from 'react';
import {
  View,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  Alert,
} from 'react-native';
import FontAwesome6 from 'react-native-vector-icons/FontAwesome6';
import storage from '../../utils/storage';
import AppScreen from '../../components/AppScreen';
import AppText from '../../components/AppText';
import AppButton from '../../components/AppButton';

import {getOtp, verifyOtp} from '../../apis/authApi';

import {useAuth} from '../../context/AuthContext';

import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';

const OtpScreen = ({route, navigation}) => {
  const {mobile} = route.params;
  const [errorMessage, setErrorMessage] = useState('');

  const {login} = useAuth();

  const [otp, setOtp] = useState('');
  const [timeLeft, setTimeLeft] = useState(30);
  const [isResendVisible, setIsResendVisible] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (timeLeft > 0) {
      const timer = setTimeout(() => setTimeLeft(timeLeft - 1), 1000);
      return () => clearTimeout(timer);
    } else {
      setIsResendVisible(true);
    }
  }, [timeLeft]);

  const handleResend = async () => {
    setTimeLeft(30);
    setIsResendVisible(false);
    setErrorMessage('');
    try {
      setIsLoading(true);
      const result = await getOtp(mobile);

      if (result.success) {
        // Alert.alert('Success', 'OTP sent to your email again!');
      } else {
        console.log('Resend failed:', result.data);
        // Alert.alert('Error', result.data?.message || 'Failed to resend OTP.');
      }
    } catch (error) {
      console.error('Resend error:', error);
      // Alert.alert('Error', 'Something went wrong. Please try again.');
    }

    setIsLoading(false);
  };

  const handleVerifyOtp = async () => {
    const otpValue = Array.isArray(otp) ? otp.join('') : otp;

    if (otpValue.length < 6) {
      // Alert.alert('Error', 'Please enter the 6-digit OTP.');
      return;
    }

    try {
      setIsLoading(true);

      const result = await verifyOtp(mobile, otpValue);

      console.log('verifyOtp result:', result);

      if (result.success) {
        login({
          access: result.data.access_token,
          refresh: result.data.refresh_token,
        });

        navigation.reset({
          index: 0,
          routes: [{name: 'SetLockScreen'}],
        });
      } else {
        console.log('OTP verification failed:', result.data);
        setErrorMessage(
          result.data?.message || 'The OTP you entered is invalid!',
        );
      }
    } catch (error) {
      console.error('Verification error:', error);
      Alert.alert('Error', 'Something went wrong. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AppScreen isTranslucent lightStatusBar style={styles.mainContainer}>
      <TouchableOpacity
        style={styles.backButton}
        onPress={() => navigation.goBack()}>
        <FontAwesome6 name="arrow-left-long" size={28} color="#333" />
      </TouchableOpacity>

      <AppText style={styles.header}>Verify OTP</AppText>

      <AppText style={styles.description}>
        Enter the OTP sent to your mobile number:{' '}
        <AppText style={{fontWeight: 'bold'}}>{mobile}</AppText>.
      </AppText>

      <TextInput
        style={styles.otpInput}
        placeholder="XXXXXX"
        keyboardType="numeric"
        maxLength={6}
        value={otp}
        onChangeText={setOtp}
        placeholderTextColor="#6C6C6C"
        selectionColor="#d4a843"
      />

      <View style={styles.timerContainer}>
        {errorMessage ? (
          <>
            <AppText style={{color: 'red', fontSize: fp(1.8)}}>
              {errorMessage}
            </AppText>
            <TouchableOpacity onPress={handleResend}>
              <AppText style={styles.resendText}>Resend OTP</AppText>
            </TouchableOpacity>
          </>
        ) : isResendVisible ? (
          <>
            <AppText style={styles.timerText}>Didn't receive the OTP?</AppText>
            <TouchableOpacity onPress={handleResend}>
              <AppText style={styles.resendText}>Resend OTP</AppText>
            </TouchableOpacity>
          </>
        ) : (
          <AppText style={styles.timerText}>
            {`Didn't receive the OTP? Retry in 00:${timeLeft
              .toString()
              .padStart(2, '0')}`}
          </AppText>
        )}
      </View>
      <AppButton
        showArrow={true}
        buttonStyle={styles.verifyButton}
        onPress={handleVerifyOtp}
        disabled={isLoading}>
        {isLoading ? 'Please wait...' : 'Verify OTP'}
      </AppButton>
    </AppScreen>
  );
};

const styles = StyleSheet.create({
  mainContainer: {
    paddingHorizontal: wp(7),
  },
  backButton: {
    marginTop: hp(1.5),
  },
  header: {
    fontSize: fp(4.5),
    fontWeight: '600',
    marginTop: hp(4),
    marginBottom: hp(1),
  },
  description: {
    fontSize: fp(2.1),
    color: '#676767',
    marginBottom: hp(2),
    lineHeight: hp(2.5),
  },
  otpInput: {
    width: '100%',
    height: hp(7),
    borderWidth: 1,
    borderRadius: wp(2),
    borderColor: '#B3B3B3',
    color: '#000000',
    fontSize: fp(2.5),
    paddingHorizontal: wp(5),
    letterSpacing: wp(7),
    marginBottom: hp(3),
  },
  timerContainer: {
    marginBottom: hp(3),
  },
  timerText: {
    color: '#666',
    fontSize: fp(1.8),
  },
  resendText: {
    color: '#d4a843',
    fontSize: fp(2.2),
    marginTop: hp(2),
  },
  verifyButton: {
    width: wp(86),
    position: 'absolute',
    bottom: hp(5),
    alignSelf: 'center',
  },
});

export default OtpScreen;
