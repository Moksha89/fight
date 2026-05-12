import React, {useEffect, useState} from 'react';
import NetInfo from '@react-native-community/netinfo';
import MainNavigator from './navigation/MainNavigator';
import {AuthProvider} from './context/AuthContext';
import {ThemeProvider} from './context/ThemeContext';

import NoInternet from './components/NoInternet';
import ErrorBoundary from './components/ErrorBoundary';
import SmartToast, {showToast} from './components/SmartToast';
import {registerErrorCallbacks} from './utils/errorHandler';

export default function App() {
  const [isConnected, setIsConnected] = useState(true);

  useEffect(() => {
    const unsubscribe = NetInfo.addEventListener(state => {
      setIsConnected(state.isConnected);
    });

    // Register global error callbacks for the smart error handler
    registerErrorCallbacks({
      onToast: (message, duration) => {
        showToast(message, {type: 'error', duration: duration || 4000});
      },
    });

    return () => unsubscribe();
  }, []);

  return (
    <ErrorBoundary>
      <ThemeProvider>
        <AuthProvider>
          {isConnected ? <MainNavigator /> : <NoInternet />}
          <SmartToast />
        </AuthProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}
