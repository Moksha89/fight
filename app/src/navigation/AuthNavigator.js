import {createNativeStackNavigator} from '@react-navigation/native-stack';

import WalkthroughWelcomeScreen from '../screens/auth/WalkthroughWelcomeScreen';
import WalkThroughScreenSecond from '../screens/auth/WalkThroughScreenSecond';
import PhoneNumberScreen from '../screens/auth/PhoneNumberScreen';
import OtpScreen from '../screens/auth/OtpScreen';
import SetLockScreen from '../screens/auth/SetLockScreen';
import ProfileUpdateScreen from '../screens/app/settingsFlow/ProfileUpdateScreen';

import AppNavigator from './AppNavigator';

import navigationRouteNames from '../Config/navigationRouteNames';

import {useAuth} from '../context/AuthContext';

const AuthStack = createNativeStackNavigator();

export default function AuthNavigation() {
  const {isAuthenticated, isPinSet, isProfileUpdated} = useAuth();

  return (
    <AuthStack.Navigator
      screenOptions={{headerShown: false}}
      initialRouteName={
        !isAuthenticated
          ? navigationRouteNames.WALK_THROUGH_WELCOME_SCREEN
          : !isPinSet
          ? navigationRouteNames.SET_LOCK_SCREEN
          : !isProfileUpdated
          ? 'ProfileUpdateScreen'
          : navigationRouteNames.WALK_THROUGH_WELCOME_SCREEN // fallback
      }>
      <AuthStack.Screen
        name={navigationRouteNames.WALK_THROUGH_WELCOME_SCREEN}
        component={WalkthroughWelcomeScreen}
      />
      <AuthStack.Screen
        name={navigationRouteNames.WALK_THROUGH_SCREEN_SECOND}
        component={WalkThroughScreenSecond}
      />
      <AuthStack.Screen
        name={navigationRouteNames.PHONE_NUMBER_SCREEN}
        component={PhoneNumberScreen}
      />
      <AuthStack.Screen
        name={navigationRouteNames.OTP_SCREEN}
        component={OtpScreen}
      />
      <AuthStack.Screen
        name={navigationRouteNames.SET_LOCK_SCREEN}
        component={SetLockScreen}
      />
      <AuthStack.Screen
        name="ProfileUpdateScreen"
        component={ProfileUpdateScreen}
      />
    </AuthStack.Navigator>
  );
}
