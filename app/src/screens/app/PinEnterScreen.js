import React, {useState, useRef, useEffect} from 'react';
import {
  View,
  Image,
  TouchableOpacity,
  StyleSheet,
  TextInput,
  BackHandler,
  Dimensions,
  Linking,
} from 'react-native';

import storage from '../../utils/storage';

import {useAuth} from '../../context/AuthContext';

import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';

import MaterialIcon from 'react-native-vector-icons/MaterialIcons';
import Feather from 'react-native-vector-icons/Feather';

import AppScreen from '../../components/AppScreen';
import AppButton from '../../components/AppButton';
import AppText from '../../components/AppText';
import TutorialVideoModal from '../../components/TutorialVideoModal';
import Status from '../../components/Status';

const audioFileURL =
  'https://interactive-examples.mdn.mozilla.net/media/cc0-audio/t-rex-roar.mp3';

import SoundPlayer from 'react-native-sound-player';

const PinEnterScreen = ({navigation}) => {
  const [otp, setOtp] = useState(['', '', '', '']);
  const inputRefs = [useRef(null), useRef(null), useRef(null), useRef(null)];

  const {logout, setIsLocked, settings} = useAuth();

  const [screenDimensions, setScreenDimensions] = useState(
    Dimensions.get('window'),
  );

  useEffect(() => {
    const onChange = ({window}) => {
      setScreenDimensions(window); // triggers rerender
    };

    const subscription = Dimensions.addEventListener('change', onChange);
    return () => subscription?.remove();
  }, []);

  useEffect(() => {
    const backHandler = BackHandler.addEventListener(
      'hardwareBackPress',
      () => true,
    );
    return () => backHandler.remove();
  }, []);

  const handleInputChange = (text, index) => {
    if (/^\d?$/.test(text)) {
      const newOtp = [...otp];
      newOtp[index] = text;
      setOtp(newOtp);

      if (text && index < 3) {
        inputRefs[index + 1].current.focus();
      }
    }
  };

  const handleKeyPress = (e, index) => {
    if (e.nativeEvent.key === 'Backspace' && !otp[index] && index > 0) {
      inputRefs[index - 1].current.focus();
    }
  };

  const clearOtp = () => {
    setOtp(['', '', '', '']);
    inputRefs[0].current.focus();
  };
  const handleLogin = async () => {
    const enteredPin = otp.join('');
    const storedPin = await storage.getItem('checkPin');

    if (enteredPin === storedPin) {
      setIsLocked(false);
    } else {
      alert('Incorrect PIN');
      clearOtp();
    }

    inputRefs.forEach(ref => ref.current?.blur());
  };

  return (
    <AppScreen isTranslucent lightStatusBar style={styles.mainContainer}>
      <View style={styles.categoryRow}>
        <Status />
      </View>

      <Image
        source={require('../../assets/logos/logo.png')}
        style={styles.image}
        resizeMode="contain"
      />
      <AppText style={styles.header}>Login Password</AppText>
      <AppText style={styles.info}>
        Logout & login if you forgot your pin!
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
            style={styles.input}
            textAlign="center"
            textAlignVertical="center"
            ref={inputRefs[index]}
            selectionColor="#d4a843"
            // secureTextEntry={true}
            accessible={true}
            accessibilityLabel={`Digit ${index + 1}`}
          />
        ))}
      </View>

      <View style={styles.logoutContainer}>
        <AppText style={styles.rememberText}>Didn’t remember code?</AppText>
        <TouchableOpacity onPress={() => logout()}>
          <AppText style={styles.logoutText}>Logout!</AppText>
        </TouchableOpacity>
      </View>

      <View style={styles.buttons}>
        <TouchableOpacity onPress={logout}>
          <View style={styles.logoutButton}>
            <Feather name="power" size={20} color="#CA0000" />
          </View>
        </TouchableOpacity>

        <AppButton
          onPress={handleLogin}
          showArrow={true}
          buttonLight={false}
          iconName="arrow-right-alt"
          iconColor="#ffffff"
          iconSize={40}
          contentContainerStyle={styles.buttonContent}
          buttonStyle={styles.loginButton}>
          Login
        </AppButton>
      </View>

      <View style={styles.watchTutorialsSection}>
        <TouchableOpacity
          style={styles.watchTutorialsButton}
          onPress={() => Linking.openURL(settings['G']?.actionValue)}>
          <Feather name="youtube" size={20} color="#FF0A0A" />
          <AppText style={styles.tutorialText}>Watch Tutorials</AppText>
        </TouchableOpacity>
      </View>
    </AppScreen>
  );
};

const styles = StyleSheet.create({
  mainContainer: {
    alignItems: 'center',
    position: 'relative',
  },
  categoryRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    width: wp(100),
    height: hp(8),
  },
  image: {
    marginTop: hp(3),
    width: wp(25),
    height: wp(25),
    outlineWidth: wp(3.5),
    borderRadius: wp(100),
    marginBottom: hp(3),
    marginTop: hp(5),
    backgroundColor: '#000',
  },
  header: {
    fontSize: fp(3),
    fontWeight: '500',
  },
  info: {
    fontSize: fp(1.7),
    color: '#585858',
    marginTop: hp(1),
    textAlign: 'center',
  },
  pinEnter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    width: wp(50),
    height: hp(6),
    marginVertical: hp(2),
  },
  input: {
    width: hp(4.5),
    height: hp(4.5),
    outlineWidth: 2,
    outlineColor: '#ccc',
    borderRadius: 10,
    fontSize: hp(2.2),
    paddingTop: 0,
    paddingBottom: 0,
    includeFontPadding: false, // Android only
  },
  logoutContainer: {
    flexDirection: 'row',
  },
  rememberText: {
    fontSize: fp(1.7),
    color: '#585858',
    marginRight: wp(2),
  },
  logoutText: {
    fontSize: fp(1.7),
    color: '#d4a843',
    textDecorationLine: 'underline',
  },
  buttons: {
    width: wp(86),
    flexDirection: 'row',
    justifyContent: 'space-between',
    position: 'absolute',
    bottom: hp(9),
    alignItems: 'center',
  },
  logoutButton: {
    width: hp(6),
    height: hp(6),
    borderRadius: 50,
    borderColor: '#CA0000',
    backgroundColor: 'rgba(239,68,68,0.12)',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: wp(0.1),
  },
  loginButton: {
    width: wp(70),
  },
  buttonContent: {
    justifyContent: 'space-between',
    width: '80%',
  },
  watchTutorialsSection: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    width: 'auto',
    height: hp(9),
    position: 'absolute',
    bottom: 0,
  },
  watchTutorialsButton: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  tutorialText: {
    fontWeight: '700',
    fontSize: fp(2),
    color: '#F5F1E8',
    marginBottom: hp(0.5),
    marginLeft: wp(4),
  },
});

export default PinEnterScreen;
