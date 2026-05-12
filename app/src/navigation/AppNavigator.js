import {createNativeStackNavigator} from '@react-navigation/native-stack';
import BottomTabNavigator from './BottomTabNavigator';
import LiveCockFight from '../screens/app/CockFightFlow/LiveCockFight';
import PastMatches from '../screens/app/CockFightFlow/PastMatches';
import LotteryGift from '../screens/app/LotteryFlow/LotteryGift';
import LotteryGiftLive from '../screens/app/LotteryFlow/LotteryGiftLive';

import LotteryLive from '../screens/app/LotteryFlow/LotteryLive';
import LotteryTicket from '../screens/app/LotteryFlow/LotteryTicket';
import PromotionsScreen from '../screens/app/PromotionsFlow/PromotionsScreen';
import LearningScreen from '../screens/app/settingsFlow/LearningScreen';
import ProfileUpdateScreen from '../screens/app/settingsFlow/ProfileUpdateScreen';
import ReferralScreen from '../screens/app/settingsFlow/ReferralScreen';
import SetLockScreen from '../screens/app/settingsFlow/SetLockScreen';
import ChangePasswordScreen from '../screens/app/settingsFlow/ChangePasswordScreen';
import DepositUpiAndBankAccount from '../screens/app/walletFlow/DepositUpiAndBankAccount';
import WithdrawlUpiAndBankAccount from '../screens/app/walletFlow/WithdrawlUpiAndBankAccount';
import StatementScreen from '../screens/app/walletFlow/StatementScreen';
import GundataLive from '../screens/app/Gundata/GundataLive';
import NotificationsScreen from '../screens/app/NotificationsScreen';

import FeatureUnderMaintenanceScreen from "../screens/FeatureUnderMaintenanceScreen";

const Stack = createNativeStackNavigator();

export default function AppNavigator() {
  return (
    <Stack.Navigator
      screenOptions={{headerShown: false}}
      initialRouteName="MainTabs">
      {/* Bottom tab navigator is the root screen */}
      <Stack.Screen name="MainTabs" component={BottomTabNavigator} />

      {/* Detail/deep screens accessible from any tab via navigation.navigate() */}
      <Stack.Screen name="PromotionsScreen" component={PromotionsScreen} />

      <Stack.Screen name="LotteryGift" component={LotteryGift} />
      <Stack.Screen name="LotteryGiftLive" component={LotteryGiftLive} />

      <Stack.Screen
        name="DicePlay"
        component={GundataLive}
        options={{unmountOnBlur: true}}
      />

      <Stack.Screen
        name="LiveCockFight"
        component={LiveCockFight}
        options={{unmountOnBlur: true}}
      />
      
      <Stack.Screen name="PastMatches" component={PastMatches} />
      <Stack.Screen name="LotteryLive" component={LotteryLive} />
      <Stack.Screen name="LotteryTicket" component={LotteryTicket} />
      <Stack.Screen name="LearningScreen" component={LearningScreen} />

      <Stack.Screen
        name="ProfileUpdateScreen"
        component={ProfileUpdateScreen}
      />
      <Stack.Screen name="ReferralScreen" component={ReferralScreen} />
      <Stack.Screen name="SetLockScreen" component={SetLockScreen} />
      <Stack.Screen name="ChangePasswordScreen" component={ChangePasswordScreen} />
      <Stack.Screen
        name="DepositUpiAndBankAccount"
        component={DepositUpiAndBankAccount}
      />
      <Stack.Screen
        name="WithdrawlUpiAndBankAccount"
        component={WithdrawlUpiAndBankAccount}
      />
      <Stack.Screen name="StatementScreen" component={StatementScreen} />
      <Stack.Screen name="NotificationsScreen" component={NotificationsScreen} />
    </Stack.Navigator>
  );
}
