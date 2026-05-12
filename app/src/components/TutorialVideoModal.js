import React, {useEffect, useRef} from 'react';
import {
  Modal,
  View,
  StyleSheet,
  TouchableOpacity,
  StatusBar,
  Platform,
} from 'react-native';
import Video from 'react-native-video';
import Orientation from 'react-native-orientation-locker';

import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';

const TutorialVideoModal = ({visible, onClose, videoUrl}) => {
  const videoRef = useRef(null);

  useEffect(() => {
    let timer;
    if (visible) {
      timer = setTimeout(() => {
        Orientation.lockToLandscape();
        StatusBar.setHidden(true);
      }, 200);
    } else {
      Orientation.lockToPortrait();
      StatusBar.setHidden(false);
    }

    return () => {
      clearTimeout(timer);
      Orientation.lockToPortrait();
      StatusBar.setHidden(false);
    };
  }, [visible]);

  const handleLoad = () => {
    // Automatically enter fullscreen on video load
    if (videoRef.current?.presentFullscreenPlayer) {
      videoRef.current.presentFullscreenPlayer();
    }
  };

  const handleFullscreenExit = () => {
    onClose(); // Call when exiting fullscreen
  };

  return (
    <Modal
      visible={visible}
      animationType="none"
      transparent={false}
      presentationStyle="fullScreen"
      statusBarTranslucent={true}
      onRequestClose={onClose}>
      <View style={styles.container}>
        <Video
          ref={videoRef}
          source={{uri: videoUrl}}
          style={styles.video}
          controls
          resizeMode="contain"
          onLoad={handleLoad}
          onFullscreenPlayerDidDismiss={handleFullscreenExit}
        />
      </View>
    </Modal>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: 'black',
  },
  video: {
    flex: 1,
  },
  closeButton: {
    position: 'absolute',
    right: 20,
    top: 20,
    zIndex: 20,
    width: wp(10),
    height: wp(10),
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#000000aa',
    borderRadius: wp(2),
  },
});

export default TutorialVideoModal;
