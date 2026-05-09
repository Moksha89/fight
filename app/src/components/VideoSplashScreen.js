import React, {useEffect} from 'react';
import {View, StyleSheet, Dimensions, Alert} from 'react-native';
import Video from 'react-native-video';

const {width, height} = Dimensions.get('window');

const VideoSplashScreen = ({onFinish}) => {
  return (
    <View style={styles.container}>
      <Video
        source={require('../assets/videos/intro.mp4')}
        resizeMode="cover"
        style={styles.video}
        onEnd={() => {
          console.log('Video ended');
          onFinish();
        }}
        onError={e => {
          console.error('Video error:', e);
          onFinish(); // fallback to hide splash
        }}
        repeat={false}
        controls={false}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
  },
  video: {
    width,
    height,
  },
});

export default VideoSplashScreen;
