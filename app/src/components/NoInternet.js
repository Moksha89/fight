import React from 'react';
import {
  View,
  StyleSheet,
  Dimensions,
  StatusBar,
} from 'react-native';
import AppScreen from './AppScreen';
import AppText from './AppText';
import LottieView from 'lottie-react-native';
import OfflineGame from './OfflineGame';
import {useTheme} from '../context/ThemeContext';

const {width} = Dimensions.get('window');

export default function NoInternetScreen() {
  const {colors, radius, shadows} = useTheme();

  return (
    <AppScreen style={styles.container}>
      <StatusBar barStyle="light-content" backgroundColor={colors.background} />

      <LottieView
        source={require('../assets/lottie/no-internet.json')}
        autoPlay
        loop
        style={styles.lottie}
      />

      <AppText variant="h1" align="center">
        No Internet Connection !
      </AppText>
      <AppText variant="body" color="muted" align="center" style={styles.subtitle}>
        Looks like you're offline. While we reconnect you, enjoy a quick game!
      </AppText>

      <View
        style={[
          styles.gameWrapper,
          {
            backgroundColor: colors.card,
            borderRadius: radius.lg,
            ...shadows.card,
          },
        ]}>
        <OfflineGame />
      </View>
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    paddingHorizontal: 24,
    justifyContent: 'space-evenly',
  },
  lottie: {
    width: width * 0.65,
    height: width * 0.65,
  },
  subtitle: {
    paddingHorizontal: 10,
    marginBottom: 20,
  },
  gameWrapper: {
    width: '100%',
    alignItems: 'center',
    padding: 10,
    marginBottom: 30,
  },
});
