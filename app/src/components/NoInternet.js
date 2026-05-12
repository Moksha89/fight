import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  Dimensions,
  TouchableOpacity,
  StatusBar,
} from 'react-native';
import AppScreen from './AppScreen';
import LottieView from 'lottie-react-native';
import OfflineGame from './OfflineGame';
import {BlurView} from '@react-native-community/blur'; // Optional, for iOS polish

const {width} = Dimensions.get('window');

export default function NoInternetScreen() {
  return (
    <AppScreen style={styles.container}>
      <StatusBar barStyle="light-content" backgroundColor="#0B0B0B" />

      <LottieView
        source={require('../assets/lottie/no-internet.json')}
        autoPlay
        loop
        style={styles.lottie}
      />

      <Text style={styles.title}>No Internet Connection !</Text>
      <Text style={styles.subtitle}>
        Looks like you're offline. While we reconnect you, enjoy a quick game!
      </Text>

      <View style={styles.gameWrapper}>
        <OfflineGame />
      </View>
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0B0B0B',
    alignItems: 'center',
    paddingHorizontal: 24,
    justifyContent: 'space-evenly',
  },
  lottie: {
    width: width * 0.65,
    height: width * 0.65,
  },
  title: {
    fontSize: 28,
    color: '#F5F1E8',
    textAlign: 'center',
  },
  subtitle: {
    fontSize: 16,
    color: '#6B6560',
    textAlign: 'center',
    paddingHorizontal: 10,
    marginBottom: 20,
  },
  gameWrapper: {
    width: '100%',
    alignItems: 'center',
    padding: 10,
    backgroundColor: '#171717',
    borderRadius: 16,
    elevation: 3,
    shadowColor: '#000',
    shadowOpacity: 0.1,
    shadowRadius: 6,
    shadowOffset: {width: 0, height: 3},
    marginBottom: 30,
  },
});
