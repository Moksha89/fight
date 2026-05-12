import React from 'react';
import {
  View,
  StyleSheet,
  StatusBar,
  Platform,
  SafeAreaView,
} from 'react-native';
import {getStatusBarHeight} from 'react-native-status-bar-height';
import {useSafeAreaInsets} from 'react-native-safe-area-context';

const AppScreen = ({
  children,
  style,
  isTranslucent = false,
  lightStatusBar = false,
}) => {
  const statusBarHeight = getStatusBarHeight();
  const insets = useSafeAreaInsets(); // Get bottom inset

  return isTranslucent ? (
    <View
      style={[
        styles.screen,
        style,
        {
          paddingTop: Platform.OS === 'android' ? statusBarHeight : 0,
          paddingBottom: insets.bottom, // ✅ Avoid overlap with bottom nav bar
        },
      ]}>
      <StatusBar
        barStyle={lightStatusBar ? 'dark-content' : 'light-content'}
        backgroundColor={'#00000000'}
        translucent={true}
      />
      {children}
    </View>
  ) : (
    <SafeAreaView style={[styles.screen, style]}>
      <StatusBar
        barStyle="light-content"
        backgroundColor="#0B0B0B"
        translucent={false}
      />
      {children}
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: '#0B0B0B',
  },
});

export default AppScreen;
