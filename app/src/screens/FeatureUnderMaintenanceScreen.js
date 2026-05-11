import React from 'react';
import {StyleSheet, TouchableOpacity} from 'react-native';
import LottieView from 'lottie-react-native';

import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';

import AppScreen from '../components/AppScreen';
import AppText from '../components/AppText';

const FeatureUnderMaintenanceScreen = ({navigation}) => {
  return (
    <AppScreen style={styles.mainContainer} isTranslucent={true}>
      <LottieView
        source={require('../assets/lottie/lottery.json')}
        autoPlay
        loop
        style={styles.lottie}
      />
      <AppText style={styles.maintenanceText}>Under Maintenance!</AppText>
      <AppText style={styles.description}>
        This feature is currently under maintenance. We're upgrading the experience.
        Please check back soon for thrilling new matches!
      </AppText>
      <TouchableOpacity
        style={styles.button}
        onPress={() => navigation.navigate('HomeScreen', {index: 0})}>
        <AppText style={styles.buttonText}>Return To Home</AppText>
      </TouchableOpacity>
    </AppScreen>
  );
};

const styles = StyleSheet.create({
  mainContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  lottie: {
    height: hp(20),
    width: hp(50),
  },
  maintenanceText: {
    marginTop: hp(4),
    fontSize: fp(3),
    fontWeight: 'bold',
    color: '#333',
  },
  description: {
    paddingHorizontal: wp(10),
    textAlign: 'center',
    lineHeight: hp(2),
    marginTop: hp(2),
    fontSize: fp(1.7),
  },
  button: {
    width: wp(80),
    height: hp(6),
    backgroundColor: '#d4a843',
    borderRadius: wp(1.5),
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: hp(4),
  },
  buttonText: {color: '#ffffff', fontSize: fp(2), fontWeight: '600'},
});

export default FeatureUnderMaintenanceScreen;
