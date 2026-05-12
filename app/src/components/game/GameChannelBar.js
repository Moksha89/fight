import React, {useEffect} from 'react';
import {
  StyleSheet,
  View,
  TouchableOpacity,
  DeviceEventEmitter,
} from 'react-native';
import SoundPlayer from 'react-native-sound-player';
import MaterialCommunityIcons from 'react-native-vector-icons/MaterialCommunityIcons';
import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';

import AppText from '../AppText';
import {useTheme} from '../../context/ThemeContext';

export default function GameChannelBar({
  availableChannels,
  activeChannel,
  setActiveChannel,
  soundEnabled,
  toggleSound,
  musicEnabled,
  setMusicEnabled,
}) {
  const {colors} = useTheme();

  const playBackgroundMusic = () => {
    try {
      SoundPlayer.loadSoundFile('background_music', 'mp3');
      SoundPlayer.play();
    } catch (error) {
      console.log('Error playing background music', error);
    }
  };

  useEffect(() => {
    const onFinishedPlayingSubscription = DeviceEventEmitter.addListener(
      'FinishedPlaying',
      () => {
        if (musicEnabled) {
          playBackgroundMusic();
        }
      },
    );

    return () => {
      onFinishedPlayingSubscription.remove();
    };
  }, [musicEnabled]);

  useEffect(() => {
    if (musicEnabled) {
      playBackgroundMusic();
    }
    return () => {
      SoundPlayer.stop();
    };
  }, []);

  useEffect(() => {
    if (!musicEnabled) {
      SoundPlayer.stop();
    } else {
      playBackgroundMusic();
    }
  }, [musicEnabled]);

  const toggleMusic = () => {
    setMusicEnabled(!musicEnabled);
    if (!musicEnabled) {
      playBackgroundMusic();
    } else {
      SoundPlayer.stop();
    }
  };

  return (
    <View style={styles.countrySelection}>
      {Object.entries(availableChannels).map(([id, title]) => (
        <TouchableOpacity
          key={id}
          style={[
            styles.button,
            activeChannel == id && {backgroundColor: colors.gold},
          ]}
          onPress={() => setActiveChannel(id)}>
          <AppText
            style={[
              styles.buttonText,
              {color: colors.text_primary},
              activeChannel == id && {color: '#fff', fontWeight: 'bold'},
            ]}>
            {title}
          </AppText>
          {activeChannel == id && (
            <View style={[styles.triangle, {borderBottomColor: colors.gold}]} />
          )}
        </TouchableOpacity>
      ))}

      <View style={styles.iconRow}>
        <TouchableOpacity onPress={toggleSound}>
          <MaterialCommunityIcons
            name={soundEnabled ? 'volume-high' : 'volume-off'}
            size={24}
            color={colors.text_primary}
          />
        </TouchableOpacity>

        <TouchableOpacity style={styles.musicIcon} onPress={toggleMusic}>
          <MaterialCommunityIcons
            name={musicEnabled ? 'music' : 'music-off'}
            size={20}
            color={colors.text_primary}
          />
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  countrySelection: {
    flexDirection: 'row',
    width: wp(96),
    marginLeft: wp(2),
    position: 'relative',
    marginTop: hp(1),
  },
  button: {
    alignItems: 'center',
    marginRight: hp(1.2),
    paddingVertical: hp(0.3),
    paddingHorizontal: wp(2.4),
    borderRadius: wp(1),
    backgroundColor: '#555',
  },
  buttonText: {
    fontSize: fp(1.5),
  },
  triangle: {
    marginTop: 4,
    width: 0,
    height: 0,
    backgroundColor: 'transparent',
    borderStyle: 'solid',
    borderLeftWidth: 7,
    borderRightWidth: 7,
    borderBottomWidth: 8,
    borderLeftColor: 'transparent',
    borderRightColor: 'transparent',
    position: 'absolute',
    left: 15,
    top: -12,
  },
  iconRow: {
    position: 'absolute',
    right: wp(0),
    flexDirection: 'row',
  },
  musicIcon: {
    marginLeft: wp(4),
    marginTop: hp(0.2),
  },
});
