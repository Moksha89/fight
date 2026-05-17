import React, {useEffect, useState} from 'react';
import {View, ActivityIndicator} from 'react-native';
import {NavigationContainer} from '@react-navigation/native';
import AuthNavigator from './AuthNavigator';
import AppNavigator from './AppNavigator';
import {getNewAccess} from '../apis/authApi';
import {loadTokens} from '../utils/tokenStorage';
import {useAuth} from '../context/AuthContext';
import {SafeAreaProvider} from 'react-native-safe-area-context';

import AppUnderMaintenanceScreen from '../screens/AppUnderMaintenanceScreen';

const MainNavigator = () => {
  const [authChecked, setAuthChecked] = useState(false);

  const {
    isAuthenticated,
    login,
    logout,
    isProfileUpdated,
    settings,
  } = useAuth();

  useEffect(() => {
    const checkAuthStatus = async () => {
      try {
        const {refreshToken} = await loadTokens();
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

  // Show loading while auth is still checking
  if (!authChecked) {
    return (
      <SafeAreaProvider>
        <View style={{flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#0B0B0B'}}>
          <ActivityIndicator size="large" color="#D4A843" />
        </View>
      </SafeAreaProvider>
    );
  }

  const navKey = `${isAuthenticated}-${isProfileUpdated}`;

  return (
    <SafeAreaProvider>
      <NavigationContainer key={navKey}>
        {settings['A']?.actionValue === 'Y' ? (
          <AppUnderMaintenanceScreen />
        ) : isAuthenticated && isProfileUpdated ? (
          <AppNavigator />
        ) : (
          <AuthNavigator />
        )}
      </NavigationContainer>
    </SafeAreaProvider>
  );
};

export default MainNavigator;
