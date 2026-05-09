import React, {useState, useRef} from 'react';

import Octicons from 'react-native-vector-icons/Octicons';

import {View, StyleSheet, TextInput} from 'react-native';

import AppScreen from '../../../components/AppScreen';
import AppText from '../../../components/AppText';
import AppButton from '../../../components/AppButton';
import HeaderComponent from '../../../components/HeaderComponent';

import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';

import {useAuth} from '../../../context/AuthContext';

import storage from '../../../utils/storage';

const SetLockScreen = ({navigation}) => {
  const {setIsPinSet, setCheckPin} = useAuth();

  const handleSetPin = async () => {
    try {
      const pinValue = otp.join('');
      if (pinValue.length !== 4) {
        alert('Set 4-digit PIN, for secure login!');
        return;
      }
      setIsPinSet(true);
      setCheckPin(pinValue);

      await storage.setItem('checkPin', pinValue);

      navigation.goBack();
    } catch (error) {
      console.error('Error saving PIN:', error);
    }
  };

  const [otp, setOtp] = useState(['', '', '', '']);

  // Create refs for each TextInput
  const inputRefs = [useRef(null), useRef(null), useRef(null), useRef(null)];

  const handleInputChange = (text, index) => {
    let otpCopy = [...otp];
    otpCopy[index] = text;

    // Update the OTP state
    setOtp(otpCopy);

    // Move focus to the next input if text is entered and it's not the last box
    if (text && index < 3) {
      inputRefs[index + 1].current.focus();
    }
  };

  const handleKeyPress = (e, index) => {
    if (e.nativeEvent.key === 'Backspace') {
      const updatedOtp = [...otp];
      if (otp[index] !== '') {
        updatedOtp[index] = '';
        setOtp(updatedOtp);
      } else if (index > 0) {
        updatedOtp[index - 1];
        setOtp(updatedOtp);
        inputRefs[index - 1].current.focus();
      }
    }
  };

  return (
    <AppScreen isTranslucent lightStatusBar style={styles.mainContainer}>
      <HeaderComponent
        title="RE-SET PIN"
        onBackPress={() => navigation.goBack()}
        onIconPress={() =>
          navigation.reset({
            index: 0,
            routes: [{name: 'HomeScreen'}],
          })
        }
        RightIconComponent={<Octicons name="home" size={17} color="#ffffff" />}
        rightIconWrapperStyle={{backgroundColor: '#d4a843'}}
      />
      <AppText style={styles.header}>Set New Login PIN</AppText>
      <AppText style={styles.description}>
        Protect from children & other people!
      </AppText>
      <View style={styles.pinEnter}>
        {otp.map((digit, index) => (
          <TextInput
            key={index}
            value={digit}
            onChangeText={text => handleInputChange(text, index)}
            onKeyPress={e => handleKeyPress(e, index)}
            keyboardType="numeric"
            maxLength={1}
            selectionColor="#d4a843"
            textAlign="center"
            style={styles.input}
            ref={inputRefs[index]}
          />
        ))}
      </View>
      <AppButton
        iconSize={40}
        textStyle={{fontSize: fp(2)}}
        showArrow={true}
        onPress={handleSetPin}
        buttonStyle={styles.loginButton}>
        Reset pin
      </AppButton>
    </AppScreen>
  );
};

const styles = StyleSheet.create({
  mainContainer: {
    position: 'relative',
    paddingTop: hp(4.5),
  },
  header: {
    fontSize: fp(2.7),
    textAlign: 'center',
    marginTop: hp(5),
    marginBottom: hp(1),
  },
  description: {
    color: '#A0A0A0',
    fontSize: fp(1.7),
    textAlign: 'center',
    marginBottom: hp(2),
  },
  pinEnter: {
    display: 'flex',
    flexDirection: 'row',
    justifyContent: 'space-between',
    width: wp(50),
    height: hp(6),
    marginLeft: wp(25),
    marginTop: hp(1),
  },
  input: {
    width: hp(4.5),
    height: hp(4.5),
    borderWidth: wp(0.5),
    borderColor: '#ccc',
    borderRadius: 10,
    fontSize: hp(2.2),
    textAlign: 'center',
    textAlignVertical: 'center', // for Android vertical alignment
    paddingTop: 0,
    paddingBottom: 0,
    includeFontPadding: false, // Android only
  },
  loginButton: {
    width: wp(86),
    position: 'absolute',
    bottom: hp(5),
    left: wp(7),
  },
});

export default SetLockScreen;
