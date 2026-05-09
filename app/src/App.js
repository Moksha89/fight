// import React from 'react';
// import PinEnterScreen from './screens/app/PinEnterScreen';
// import WalkthroughWelcomeScreen from './screens/auth/WalkthroughWelcomeScreen';
// import WalkThroughScreenSecond from './screens/auth/WalkThroughScreenSecond';
// import PhoneNumberScreen from './screens/auth/PhoneNumberScreen';
// import OtpScreen from './screens/auth/OtpScreen';
// import SetLockScreen from './screens/auth/SetLockScreen';
// import DepositWithdrawl from './screens/app/walletFlow/DepositWithdrawl';
// import DepositUpiAndBankAccount from './screens/app/walletFlow/DepositUpiAndBankAccount';
// import WithdrawlUpiAndBankAccount from './screens/app/walletFlow/WithdrawlUpiAndBankAccount';
// import SettingsScreen from './screens/app/settingsFlow/SettingsScreen';
// import ProfileUpdateScreen from './screens/app/settingsFlow/ProfileUpdateScreen';
// import SettingsSetLockScreen from './screens/app/settingsFlow/SetLockScreen';
// import ReferralScreen from './screens/app/settingsFlow/ReferralScreen';
// import LearningScreen from './screens/app/settingsFlow/LearningScreen';
// import HomeScreen from './screens/app/HomeScreen';
// import LiveCockFight from './screens/app/CockFightFlow/LiveCockFight';
// import PastMatches from './screens/app/CockFightFlow/PastMatches';
// import LotteryLive from './screens/app/LotteryFlow/LotteryLive';
// import LotteryGiftLive from './screens/app/LotteryFlow/LotteryGiftLive';
// import LotteryGift from './screens/app/LotteryFlow/LotteryGift';

// import LotteryTicket from './screens/app/LotteryFlow/LotteryTicket';
// import PromotionsScreen from './screens/app/PromotionsFlow/PromotionsScreen';
// import AppUnderMaintenanceScreen from './screens/AppUnderMaintenanceScreen';
// import CockFightUnderMaintenanceScreen from './screens/CockFightUnderMaintenanceScreen';
// import LotteryUnderMaintenanceScreen from './screens/LotteryUnderMaintenanceScreen';
// import HistoryScreen from './screens/app/walletFlow/HistoryScreen';
// import Status from './components/Status';
// import GundataLive from './screens/app/Gundata/GundataLive';
// import {SafeAreaProvider} from 'react-native-safe-area-context';

// const App = () => {
//   return (
//     <SafeAreaProvider>
//       <GundataLive />
//       {/* <WalkthroughWelcomeScreen /> */}
//       {/* <WalkThroughScreenSecond /> */}
//       {/* <PhoneNumberScreen /> */}
//       {/* <OtpScreen /> */}
//       {/* <SetLockScreen /> */}
//       {/* <HomeScreen /> */}
//       {/* <DepositWithdrawl /> */}
//       {/* <DepositUpiAndBankAccount /> */}
//       {/* <WithdrawlUpiAndBankAccount /> */}
//       {/* <SettingsScreen /> */}
//       {/* <ProfileUpdateScreen /> */}
//       {/* <SettingsSetLockScreen /> */}
//       {/* <ReferralScreen /> */}
//       {/* <LearningScreen /> */}
//       {/* <LiveCockFight /> */}
//       {/* <PastMatches /> */}
//       {/* <CockFightUnderMaintenanceScreen /> */}
//       {/* <LotteryUnderMaintenanceScreen /> */}
//       {/* <AppUnderMaintenanceScreen /> */}
//       {/* <LotteryLive /> */}
//       {/* <LotteryTicket /> */}
//       {/* <LotteryGiftLive /> */}
//       {/* <LotteryGift /> */}

//       {/* <PromotionsScreen /> */}
//       {/* <HistoryScreen /> */}
//       {/* <Status /> */}
//     </SafeAreaProvider>
//   );
// };

// export default App;

import React, {useEffect, useState} from 'react';
import NetInfo from '@react-native-community/netinfo';
import MainNavigator from './navigation/MainNavigator';
import {AuthProvider} from './context/AuthContext';

import NoInternet from './components/NoInternet';

export default function App() {
  const [isConnected, setIsConnected] = useState(true);

  useEffect(() => {
    const unsubscribe = NetInfo.addEventListener(state => {
      setIsConnected(state.isConnected);
    });

    return () => unsubscribe();
  }, []);

  return (
    <AuthProvider>
      {isConnected ? <MainNavigator /> : <NoInternet />}
    </AuthProvider>
  );
}
