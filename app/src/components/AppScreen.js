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
import {useTheme} from '../context/ThemeContext';

const AppScreen = ({
  children,
  style,
  isTranslucent = false,
  lightStatusBar = false,
}) => {
  const {colors} = useTheme();
  const statusBarHeight = getStatusBarHeight();
  const insets = useSafeAreaInsets();

  const screenStyle = {flex: 1, backgroundColor: colors.background};

  return isTranslucent ? (
    <View
      style={[
        screenStyle,
        style,
        {
          paddingTop: Platform.OS === 'android' ? statusBarHeight : 0,
          paddingBottom: insets.bottom,
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
    <SafeAreaView style={[screenStyle, style]}>
      <StatusBar
        barStyle="light-content"
        backgroundColor={colors.background}
        translucent={false}
      />
      {children}
    </SafeAreaView>
  );
};

export default AppScreen;
