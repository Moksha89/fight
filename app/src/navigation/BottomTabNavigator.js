import React from 'react';
import {View, StyleSheet} from 'react-native';
import {createBottomTabNavigator} from '@react-navigation/bottom-tabs';
import MaterialIcons from 'react-native-vector-icons/MaterialIcons';
import MaterialCommunityIcons from 'react-native-vector-icons/MaterialCommunityIcons';
import {
  responsiveHeight as hp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';

import HomeScreen from '../screens/app/HomeScreen';
import GamesHubScreen from '../screens/app/GamesHubScreen';
import DepositWithdrawl from '../screens/app/walletFlow/DepositWithdrawl';
import HistoryScreen from '../screens/app/walletFlow/HistoryScreen';
import SettingsScreen from '../screens/app/settingsFlow/SettingsScreen';
import {useTheme} from '../context/ThemeContext';

const Tab = createBottomTabNavigator();

const TAB_ICONS = {
  HomeScreen: {name: 'home', pack: 'mi'},
  GamesTab: {name: 'gamepad-variant', pack: 'mci'},
  DepositWithdrawl: {name: 'account-balance-wallet', pack: 'mi'},
  HistoryScreen: {name: 'receipt-long', pack: 'mi'},
  SettingsScreen: {name: 'settings', pack: 'mi'},
};

export default function BottomTabNavigator() {
  const {colors, radius} = useTheme();

  return (
    <Tab.Navigator
      screenOptions={({route}) => ({
        headerShown: false,
        tabBarIcon: ({focused, color, size}) => {
          const iconDef = TAB_ICONS[route.name];
          const iconSize = focused ? 26 : 22;
          if (iconDef.pack === 'mci') {
            return (
              <MaterialCommunityIcons
                name={iconDef.name}
                size={iconSize}
                color={color}
              />
            );
          }
          return (
            <MaterialIcons
              name={iconDef.name}
              size={iconSize}
              color={color}
            />
          );
        },
        tabBarActiveTintColor: colors.gold,
        tabBarInactiveTintColor: colors.text_muted,
        tabBarStyle: {
          backgroundColor: colors.card,
          borderTopColor: colors.border,
          borderTopWidth: 1,
          height: hp(8),
          paddingBottom: hp(1),
          paddingTop: hp(0.5),
        },
        tabBarLabelStyle: {
          fontSize: fp(1.3),
          fontWeight: '600',
        },
      })}>
      <Tab.Screen
        name="HomeScreen"
        component={HomeScreen}
        options={{tabBarLabel: 'Home'}}
      />
      <Tab.Screen
        name="GamesTab"
        component={GamesHubScreen}
        options={{tabBarLabel: 'Games'}}
      />
      <Tab.Screen
        name="DepositWithdrawl"
        component={DepositWithdrawl}
        options={{tabBarLabel: 'Wallet'}}
      />
      <Tab.Screen
        name="HistoryScreen"
        component={HistoryScreen}
        options={{tabBarLabel: 'History'}}
      />
      <Tab.Screen
        name="SettingsScreen"
        component={SettingsScreen}
        options={{tabBarLabel: 'Settings'}}
      />
    </Tab.Navigator>
  );
}
