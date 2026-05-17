import React, {useState, useRef, useEffect} from 'react';
import {View, StyleSheet, TextInput, TouchableOpacity} from 'react-native';

import AppScreen from '../../components/AppScreen';
import AppText from '../../components/AppText';
import AppButton from '../../components/AppButton';
import storage from '../../utils/storage';
import {savePin} from '../../utils/pinStorage';
import CustomMessage from '../../components/ToestMessege';
import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';

import Feather from 'react-native-vector-icons/Feather';
import Icon from 'react-native-vector-icons/MaterialIcons';

import TutorialVideoModal from '../../components/TutorialVideoModal';
const audioFileURL =
  'https://interactive-examples.mdn.mozilla.net/media/cc0-audio/t-rex-roar.mp3';

import SoundPlayer from 'react-native-sound-player';

import {useAuth} from '../../context/AuthContext';
import ToestMessege from '../../components/ToestMessege';

const SetLockScreen = ({navigation}) => {
  // ======================toest Messege=========================
  const [messageVisible, setMessageVisible] = useState(false);
  const [messageText, setMessageText] = useState('');

  const showMessage = text => {
    setMessageText(text);
    setMessageVisible(true);
  };

  const {setIsPinSet, setCheckPin} = useAuth();

  // const handleSetPin = async () => {
  //   try {
  //     const pinValue = otp.join('');
  //     if (pinValue.length !== 4) {
  //       alert('Set 4-digit PIN, for secure login!');
  //       return;
  //     }
  //     setIsPinSet(true);
  //     setCheckPin(pinValue);

  //     await storage.setItem('checkPin', pinValue);

  //     navigation.reset({
  //       index: 0,
  //       routes: [
  //         {
  //           name: 'ProfileUpdateScreen',
  //           params: {fromFirstTime: true},
  //         },
  //       ],
  //     });
  //   } catch (error) {
  //     console.error('Error saving PIN:', error);
  //   }
  // };
  const handleSetPin = async () => {
    try {
      const pinValue = otp.join('');
      if (pinValue.length !== 4) {
        showMessage('Set 4-digit PIN, for secure login!');
        return;
      }

      setIsPinSet(true);
      const hashed = await savePin(pinValue);
      setCheckPin(hashed);

      navigation.reset({
        index: 0,
        routes: [
          {
            name: 'ProfileUpdateScreen',
            params: {fromFirstTime: true},
          },
        ],
      });
    } catch (error) {
      console.error('Error saving PIN:', error);
    }
  };
  const [otp, setOtp] = useState(['', '', '', '']);
  const inputRefs = Array(4)
    .fill()
    .map(() => useRef(null));

  const handleInputChange = (text, index) => {
    const updatedOtp = [...otp];

    // Deletion fallback: if user clears current field manually
    if (text === '') {
      updatedOtp[index] = '';
      setOtp(updatedOtp);
      return;
    }

    updatedOtp[index] = text;
    setOtp(updatedOtp);

    if (index < 3) {
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

  //========================= Watch Tutorial Video ==========================
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
    <AppScreen style={styles.container}>
      <AppText style={styles.header}>Set Login PIN</AppText>
      <AppText style={styles.subtext}>
        Protect from children & other people!
      </AppText>

      <View style={styles.pinContainer}>
        {otp.map((digit, index) => (
          <TextInput
            key={index}
            ref={inputRefs[index]}
            value={digit}
            onChangeText={text => handleInputChange(text, index)}
            onKeyPress={e => handleKeyPress(e, index)}
            keyboardType="numeric"
            maxLength={1}
            style={styles.inputBox}
            textAlign="center"
            selectionColor="#d4a843"
          />
        ))}
      </View>

      <AppButton
        showArrow
        buttonStyle={styles.continueButton}
        onPress={handleSetPin}>
        Continue
      </AppButton>
      {/* <View style={styles.watchTutorialsSection}>
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
      </View> */}
      <TutorialVideoModal
        visible={isModalVisible}
        onClose={handleCloseModal}
        videoUrl="https://www.w3schools.com/html/mov_bbb.mp4"
      />
      <CustomMessage
        message={messageText}
        visible={messageVisible}
        onHide={() => setMessageVisible(false)}
      />
    </AppScreen>
  );
};

const styles = StyleSheet.create({
  container: {
    paddingHorizontal: wp(7),
    flex: 1,
  },
  header: {
    fontSize: fp(3),
    fontWeight: '500',
    textAlign: 'center',
    marginTop: hp(5),
    marginBottom: hp(1),
  },
  subtext: {
    fontSize: fp(1.7),
    color: '#A0A0A0',
    textAlign: 'center',
    marginBottom: hp(4),
  },
  pinContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignSelf: 'center',
    width: wp(50),
    marginBottom: hp(4),
  },
  inputBox: {
    width: hp(4.5),
    height: hp(4.5),
    outlineWidth: 2,
    outlineColor: '#ccc',
    borderRadius: 10,
    fontSize: hp(2.2),
    textAlign: 'center',
    textAlignVertical: 'center', // for Android vertical alignment
    paddingTop: 0,
    paddingBottom: 0,
    includeFontPadding: false, // Android only
  },
  continueButton: {
    width: wp(86),
    position: 'absolute',
    bottom: hp(5),
    alignSelf: 'center',
  },

  watchTutorialsSection: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    width: wp(50),
    height: hp(9),
    position: 'absolute',
    bottom: 0,
    marginLeft: wp(25),
  },
  watchTutorialsButton: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  tutorialText: {
    fontWeight: '700',
    fontSize: fp(2),
    color: '#F5F1E8',
    marginLeft: wp(4),
    marginBottom: hp(0.5),
  },
});

export default SetLockScreen;
