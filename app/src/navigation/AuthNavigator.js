import {createNativeStackNavigator} from '@react-navigation/native-stack';

import LoginRegisterScreen from '../screens/auth/LoginRegisterScreen';
import ProfileUpdateScreen from '../screens/app/settingsFlow/ProfileUpdateScreen';

import {useAuth} from '../context/AuthContext';

const AuthStack = createNativeStackNavigator();

export default function AuthNavigation() {
  const {isAuthenticated, isProfileUpdated} = useAuth();

  return (
    <AuthStack.Navigator
      screenOptions={{headerShown: false}}
      initialRouteName={
        !isAuthenticated
          ? 'LoginRegisterScreen'
          : !isProfileUpdated
          ? 'ProfileUpdateScreen'
          : 'LoginRegisterScreen'
      }>
      <AuthStack.Screen
        name="LoginRegisterScreen"
        component={LoginRegisterScreen}
      />
      <AuthStack.Screen
        name="ProfileUpdateScreen"
        component={ProfileUpdateScreen}
      />
    </AuthStack.Navigator>
  );
}
