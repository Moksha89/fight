import React, {useEffect, useState} from 'react';
import {View, ActivityIndicator} from 'react-native';
import {NavigationContainer} from '@react-navigation/native';
import AuthNavigator from './AuthNavigator';
import AppNavigator from './AppNavigator';
import {getNewAccess} from '../apis/authApi';
import storage from '../utils/storage';
import {useAuth} from '../context/AuthContext';
import {SafeAreaProvider} from 'react-native-safe-area-context';

import PinEnterScreen from '../screens/app/PinEnterScreen';
import AppUnderMaintenanceScreen from '../screens/AppUnderMaintenanceScreen';
import VideoSplashScreen from '../components/VideoSplashScreen';

const MainNavigator = () => {
  const [authChecked, setAuthChecked] = useState(false);
  const [showSplash, setShowSplash] = useState(true);

  const {
    isAuthenticated,
    isPinSet,
    login,
    logout,
    isLocked,
    isProfileUpdated,
    settings,
  } = useAuth();

  useEffect(() => {
    const checkAuthStatus = async () => {
      try {
        const refreshToken = await storage.getItem('refreshToken');
        if (refreshToken) {
          const result = await getNewAccess(refreshToken);
          if (result?.ok && result.data.access) {
            await login({access: result.data.access, refresh: refreshToken});
          } else {
            logout();
          }
        } else {
          logout();
        }
      } catch (error) {
        console.error('Error checking auth status:', error);
        logout();
      } finally {
        setAuthChecked(true);
      }
    };

    checkAuthStatus();
  }, []);

  // Show splash screen first
  if (showSplash) {
    return <VideoSplashScreen onFinish={() => setShowSplash(false)} />;
  }

  // Show loading while auth is still checking
  if (!authChecked) {
    return (
      <SafeAreaProvider>
        <View style={{flex: 1, justifyContent: 'center', alignItems: 'center'}}>
          <ActivityIndicator size="large" color="#000" />
        </View>
      </SafeAreaProvider>
    );
  }

  const navKey = `${isAuthenticated}-${isPinSet}-${isProfileUpdated}-${isLocked}`;

  return (
    <SafeAreaProvider>
      <NavigationContainer key={navKey}>
        {settings['A']?.actionValue === 'Y' ? (
          <AppUnderMaintenanceScreen />
        ) : isAuthenticated && isPinSet && isProfileUpdated ? (
          isLocked ? (
            <PinEnterScreen />
          ) : (
            <AppNavigator />
          )
        ) : (
          <AuthNavigator />
        )}
      </NavigationContainer>
    </SafeAreaProvider>
  );
};

export default MainNavigator;
