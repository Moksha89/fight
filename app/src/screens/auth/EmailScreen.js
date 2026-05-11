import React, {useState, useRef, useEffect} from 'react';
import {
  View,
  StyleSheet,
  Image,
  TextInput,
  TouchableOpacity,
  Alert,
} from 'react-native';

import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';

import Feather from 'react-native-vector-icons/Feather';
import Icon from 'react-native-vector-icons/MaterialIcons';

import AppScreen from '../../components/AppScreen';
import AppText from '../../components/AppText';
import AppButton from '../../components/AppButton';
import {getOtp} from '../../apis/authApi';

import TutorialVideoModal from '../../components/TutorialVideoModal';
const audioFileURL =
  'https://interactive-examples.mdn.mozilla.net/media/cc0-audio/t-rex-roar.mp3';

import SoundPlayer from 'react-native-sound-player';
import navigationRouteNames from '../../Config/navigationRouteNames';

const PhoneNumberScreen = ({navigation}) => {
  const [showInput, setShowInput] = useState(false);
  const [mobile, setMobile] = useState('');
  const [error, setError] = useState('');

  const allSameDigits = num => /^(\d)\1+$/.test(num);

  const validateMobile = text => {
    const cleaned = text.replace(/[^0-9a-zA-Z_]/g, '');
    setMobile(cleaned);

    if (cleaned.length === 0) {
      setError('');
    } else if (/^\d+$/.test(cleaned)) {
      if (cleaned.length !== 10) {
        setError('Please enter a valid 10-digit mobile number');
      } else if (allSameDigits(cleaned)) {
        setError('Invalid mobile number');
      } else {
        setError('');
      }
    } else if (cleaned.length < 3) {
      setError('Username must be at least 3 characters');
    } else {
      setError('');
    }
  };

  const handleGetOtp = async () => {
    const isPhone = /^\d+$/.test(mobile);
    if (isPhone && mobile.length !== 10) {
      setError('Please enter a valid 10-digit mobile number');
      return;
    }
    if (!isPhone && mobile.length < 3) {
      setError('Please enter a valid username or mobile number');
      return;
    }

    setError('');

    const response = await getOtp(mobile);

    if (response.success) {
      navigation.navigate(navigationRouteNames.OTP_SCREEN, {mobile: mobile});
    } else {
      const msg = response.error?.message || response.data?.error || 'Failed to send OTP';
      Alert.alert('Error', msg);
    }
  };

  const isPhone = /^\d+$/.test(mobile);
  const isValid = isPhone ? mobile.length === 10 && !allSameDigits(mobile) : mobile.length >= 3;

  const [isModalVisible, setModalVisible] = useState(false);

  const handleOpenModal = () => {
    setModalVisible(true);
  };

  const handleCloseModal = () => {
    setModalVisible(false);
  };

  //=============================== for audio ===============================
  const [isPlaying, setIsPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const soundRef = useRef(null);

  useEffect(() => {
    SoundPlayer.setVolume(isMuted ? 0 : 1);
  }, [isMuted]);

  const loadSound = async () => {
    try {
      soundRef.current = await SoundPlayer.loadUrl(audioFileURL);
    } catch (error) {
      console.error('Error loading sound:', error);
    }
  };

  useEffect(() => {
    loadSound();
    return () => {
      if (soundRef.current) {
        SoundPlayer.unload();
      }
    };
  }, []);

  const togglePlayPauseMute = async () => {
    if (isPlaying) {
      // If playing, pause
      try {
        await SoundPlayer.pause();
        setIsPlaying(false);
      } catch (error) {
        console.error('Error pausing sound:', error);
      }
    } else {
      // If not playing, and currently muted, unmute and play
      if (isMuted) {
        setIsMuted(false);
        try {
          await SoundPlayer.play();
          setIsPlaying(true);
        } catch (error) {
          console.error('Error playing sound after unmute:', error);
        }
      } else {
        // If not playing and not muted, play
        try {
          await SoundPlayer.play();
          setIsPlaying(true);
        } catch (error) {
          console.error('Error playing sound:', error);
        }
      }
    }
  };

  return (
    <AppScreen isTranslucent={true} lightStatusBar={true}>
      <AppText style={styles.topText}>3 Major Steps</AppText>
      <AppText style={styles.middleText}>Risk Win Party !</AppText>
      <AppText style={styles.bottomText}>Login & Enter !</AppText>

      <TextInput
        style={styles.mobileInput}
        placeholder="Mobile Number or Username"
        keyboardType="default"
        autoCapitalize="none"
        value={mobile}
        onChangeText={validateMobile}
      />

      {/* {!showInput ? (
        <TouchableOpacity onPress={() => setShowInput(true)}>
          <AppText style={styles.referralText}>Have a referral code?</AppText>
        </TouchableOpacity>
      ) : (
        <TextInput
          style={styles.referralInput}
          placeholder="Get bonus on every reference"
        />
      )} */}

      {error !== '' && <AppText style={styles.errorText}>{error}</AppText>}

      <AppButton
        showArrow={true}
        buttonStyle={styles.loginButton}
        onPress={handleGetOtp}>
        Get OTP
      </AppButton>

      <View style={styles.watchTutorialsSection}>
        <TouchableOpacity
          style={styles.watchTutorialsButton}
          onPress={handleOpenModal}>
          <Feather name="youtube" size={20} color="#FF0A0A" />
          <AppText style={styles.tutorialText}>Watch Tutorials</AppText>
        </TouchableOpacity>
        <TouchableOpacity onPress={togglePlayPauseMute}>
          <Icon
            name={isPlaying ? 'pause' : isMuted ? 'volume-off' : 'volume-up'}
            size={25}
            color={isPlaying ? '#d4a843' : isMuted ? '#d4a843' : '#d4a843'}
          />
        </TouchableOpacity>
      </View>
      <TutorialVideoModal
        visible={isModalVisible}
        onClose={handleCloseModal}
        videoUrl="https://www.w3schools.com/html/mov_bbb.mp4"
      />
    </AppScreen>
  );
};

const styles = StyleSheet.create({
  mainContainer: {
    position: 'relative',
  },
  topText: {
    fontSize: fp(2),
    fontWeight: '500',
    marginLeft: wp(7),
    marginTop: hp(2),
  },
  middleText: {
    fontSize: fp(5.5),
    fontWeight: '700',
    marginLeft: wp(7),
    marginTop: hp(1.5),
  },
  bottomText: {
    fontSize: fp(2.3),
    fontWeight: '700',
    marginLeft: wp(7),
    marginTop: hp(1.5),
  },
  numberInputContainer: {
    width: wp(86),
    height: hp(7),
    marginLeft: wp(7),
    marginTop: hp(3),
    marginBottom: hp(2),
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  countryBox: {
    flexDirection: 'row',
    alignItems: 'center',
    width: wp(18),
    height: hp(7),
    borderWidth: wp(0.1),
    borderRadius: wp(2),
    justifyContent: 'center',
  },
  flagImage: {
    marginRight: 5,
  },
  mobileInput: {
    width: wp(86),
    height: hp(7),
    borderWidth: wp(0.1),
    borderRadius: wp(2),
    paddingLeft: wp(5),
    fontSize: fp(2.2),
    marginTop: hp(3),
    marginLeft: wp(7),
  },
  errorText: {
    color: 'red',
    marginTop: 8,
    fontSize: fp(2),
    textAlign: 'left',
    marginLeft: wp(7),
  },
  referralText: {
    fontSize: fp(2),
    marginLeft: wp(7),
  },
  referralInput: {
    width: wp(86),
    height: hp(7),
    marginLeft: wp(7),
    borderWidth: wp(0.3),
    borderRadius: wp(2),
    borderColor: '#B3B3B3',
    color: '#858585',
    fontSize: fp(2.3),
    paddingLeft: wp(5),
    marginTop: hp(0.5),
  },
  loginButton: {
    width: wp(86),
    position: 'absolute',
    bottom: hp(9),
    left: wp(7),
  },
  watchTutorialsSection: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    width: wp(50),
    height: hp(9),
    position: 'absolute',
    bottom: 0,
    left: wp(25),
  },
  watchTutorialsButton: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  tutorialText: {
    fontWeight: '700',
    fontSize: fp(2),
    color: '#000000',
    marginLeft: wp(4),
    marginBottom: hp(0.5),
  },
});

export default PhoneNumberScreen;
