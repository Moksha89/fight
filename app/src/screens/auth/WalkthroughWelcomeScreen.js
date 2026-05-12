import React, {useState, useEffect, useRef} from 'react';
import {
  View,
  StyleSheet,
  ImageBackground,
  TouchableOpacity,
} from 'react-native';
import Feather from 'react-native-vector-icons/Feather';
import Icon from 'react-native-vector-icons/MaterialIcons';

import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';

import AppScreen from '../../components/AppScreen';
import AppText from '../../components/AppText';
import AppButton from '../../components/AppButton';
import TutorialVideoModal from '../../components/TutorialVideoModal';

import navigationRouteNames from '../../Config/navigationRouteNames';

const audioFileURL =
  'https://interactive-examples.mdn.mozilla.net/media/cc0-audio/t-rex-roar.mp3';
import SoundPlayer from 'react-native-sound-player';

const WalkthroughWelcomeScreen = ({navigation}) => {
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
    <AppScreen isTranslucent={true} lightStatusBar={true}>
      <ImageBackground
        source={require('../../assets/images/walkThrough.png')}
        style={styles.background}
        resizeMode="cover">
        <AppText style={styles.header}>No Ai, Live Gaming !!</AppText>

        <AppText style={styles.middleText}>
          When{'\n'}
          Gaming Live,{'\n'}
          No Gambling !
        </AppText>

        <AppText style={styles.bottomText}>
          Play smart and win more, sometimes the withdrawal takes time but never
          loss!
        </AppText>

        <AppButton
          buttonLight={true}
          showArrow={false}
          buttonStyle={styles.loginButton}
          onPress={() =>
            navigation.navigate(navigationRouteNames.WALK_THROUGH_SCREEN_SECOND)
          }>
          Login, play & win big!
        </AppButton>

        <View style={styles.watchTutorialsSection}>
          <TouchableOpacity
            style={styles.watchTutorialsButton}
            onPress={handleOpenModal}>
            <Feather name="youtube" size={20} color="#ffffff" />
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
      </ImageBackground>
    </AppScreen>
  );
};

const styles = StyleSheet.create({
  background: {
    flex: 1,
  },
  header: {
    fontSize: fp(3.2),
    color: '#F5F1E8',
    fontWeight: '700',
    textAlign: 'center',
    marginTop: hp(8),
  },
  middleText: {
    fontSize: fp(5),
    color: '#F5F1E8',
    marginLeft: wp(7),
    marginTop: hp(8),
  },
  bottomText: {
    color: '#F5F1E8',
    marginHorizontal: wp(7),
    fontSize: fp(2),
    marginTop: hp(2),
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
    marginLeft: wp(25),
  },
  watchTutorialsButton: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  tutorialText: {
    fontWeight: '700',
    fontSize: fp(2),
    color: '#ffffff',
    marginLeft: wp(4),
    marginBottom: hp(0.5),
  },
});

export default WalkthroughWelcomeScreen;
