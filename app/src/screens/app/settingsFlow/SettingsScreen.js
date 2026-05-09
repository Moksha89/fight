import React, {useState, useRef, useEffect} from 'react';
import {
  View,
  TouchableOpacity,
  Image,
  StyleSheet,
  ScrollView,
  Alert,
  Linking,
} from 'react-native';

import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';
import Icon from 'react-native-vector-icons/MaterialIcons';
import SoundPlayer from 'react-native-sound-player';
import FontAwesome6 from 'react-native-vector-icons/FontAwesome6';

import {useAuth} from '../../../context/AuthContext';

import AntDesign from 'react-native-vector-icons/AntDesign';
import Octicons from 'react-native-vector-icons/Octicons';

import AppScreen from '../../../components/AppScreen';
import HeaderComponent from '../../../components/HeaderComponent';
import AppText from '../../../components/AppText';

const SettingsScreen = ({navigation}) => {
  const {logout, setIsLocked, settings} = useAuth();

  const supportOptions = [
    {
      name: 'Whatsapp',
      image: require('../../../assets/icons/whatsapp.png'),
      link: settings['E']?.actionValue,
    },
    {
      name: 'Telegram',
      image: require('../../../assets/icons/telegram.png'),
      link: settings['F']?.actionValue,
    },
    {
      name: 'Facebook',
      image: require('../../../assets/icons/facebook.png'),
      link: settings['H']?.actionValue,
    },
    {
      name: 'Instagram',
      image: require('../../../assets/icons/instagram.png'),
      link: settings['I']?.actionValue,
    },
    {
      name: 'Youtube',
      image: require('../../../assets/icons/youtube.png'),
      link: settings['G']?.actionValue,
    },
  ];

  return (
    <AppScreen isTranslucent lightStatusBar style={styles.container}>
      <HeaderComponent
        title="Profile & Settings "
        onBackPress={() => navigation.goBack()}
        onIconPress={() => setIsLocked(true)}
        RightIconComponent={<Octicons name="lock" size={17} color="#ffffff" />}
        rightIconWrapperStyle={{backgroundColor: '#d4a843'}}
        containerStyle={{}}
      />
      <ScrollView
        style={{
          marginTop: hp(1),
          paddingHorizontal: wp(6),
        }}
        showsVerticalScrollIndicator={false}>
        <TouchableOpacity
          style={styles.banner}
          onPress={() => navigation.navigate('LearningScreen')}>
          <Image
            source={require('../../../assets/images/banner.png')} // replace with your banner image
            style={styles.bannerImage}
            resizeMode="cover"
          />
          <FontAwesome6
            name="arrow-right-long"
            size={24}
            color="#ffffff"
            style={styles.bannerArrow}
          />
        </TouchableOpacity>
        <AppText style={styles.sectionLabel}>Account:</AppText>
        <TouchableOpacity
          style={styles.itemRow}
          onPress={() => navigation.navigate('ProfileUpdateScreen')}>
          <AppText style={styles.itemText}>Profile</AppText>
          <AntDesign name="right" size={18} color="#000" />
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.itemRow}
          onPress={() => navigation.navigate('NotificationsScreen')}>
          <AppText style={styles.itemText}>Notifications</AppText>
          <AntDesign name="right" size={18} color="#000" />
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.itemRow}
          onPress={() => navigation.navigate('StatementScreen')}>
          <AppText style={styles.itemText}>Transaction History</AppText>
          <AntDesign name="right" size={18} color="#000" />
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.itemRow}
          onPress={() => navigation.navigate('ChangePasswordScreen')}>
          <AppText style={styles.itemText}>Change Password</AppText>
          <AntDesign name="right" size={18} color="#000" />
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.itemRow}
          onPress={() => navigation.navigate('SetLockScreen')}>
          <AppText style={styles.itemText}>Reset Login PIN</AppText>
          <AntDesign name="right" size={18} color="#000" />
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.itemRow, {borderBottomWidth: 0}]}
          onPress={() => navigation.navigate('ReferralScreen')}>
          <AppText style={styles.itemText}>Referral & Earn</AppText>
          <AntDesign name="right" size={18} color="#000" />
        </TouchableOpacity>
        <View style={styles.hrLine} />
        <AppText style={styles.sectionLabel}>Contact / Support:</AppText>
        <View style={{marginBottom: hp(20)}}>
          {supportOptions.map((item, index) => (
            <TouchableOpacity
              style={styles.itemRow}
              key={index}
              onPress={() => Linking.openURL(item.link)}>
              <View style={styles.contactRow}>
                <Image source={item.image} style={styles.contactIcon} />
                <AppText style={styles.itemText}>{item.name}</AppText>
              </View>
              <AntDesign name="right" size={18} color="#000" />
            </TouchableOpacity>
          ))}
        </View>
      </ScrollView>
      {/* Logout */}
      <TouchableOpacity style={styles.logoutButton} onPress={() => logout()}>
        <AppText style={styles.logoutText}>Log out</AppText>
        <AntDesign name="poweroff" size={20} color="#E53935" />
      </TouchableOpacity>
    </AppScreen>
  );
};
const styles = StyleSheet.create({
  container: {
    flex: 1,
    position: 'relative',
    paddingTop: hp(4.5),
  },
  banner: {
    width: wp(86),
    position: 'relative',
    marginVertical: hp(2),
  },
  bannerImage: {
    width: '100%',
  },
  bannerArrow: {
    position: 'absolute',
    right: wp(8),
    top: hp(4),
  },
  sectionLabel: {
    fontSize: fp(1.7),
    marginBottom: hp(0.5),
  },
  itemRow: {
    flexDirection: 'row',
    paddingVertical: hp(1.5),
    justifyContent: 'space-between',
    alignItems: 'center',
    borderBottomWidth: 0.5,
    borderBottomColor: '#eee',
  },
  itemText: {
    fontSize: fp(1.7),
    fontWeight: '500',
  },
  hrLine: {
    width: wp(86),
    height: hp(0.1),
    backgroundColor: '#DFDFDF',
    marginTop: hp(1),
    marginBottom: hp(2.5),
  },
  contactRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  contactIcon: {
    width: wp(8),
    height: wp(8),
    resizeMode: 'contain',
    marginRight: wp(5),
  },
  logoutButton: {
    flexDirection: 'row',
    borderRadius: 12,
    backgroundColor: '#FFEDED',
    justifyContent: 'space-between',
    alignItems: 'center',
    width: wp(86),
    height: hp(6),
    paddingHorizontal: wp(15),
    position: 'absolute',
    bottom: hp(5),
    left: wp(7),
    outlineColor: '#CA0000',
    outlineWidth: wp(0.2),
  },
  logoutText: {
    color: '#CA0000',
    fontSize: fp(2),
  },
  watchTutorialsSection: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    width: wp(50),
    height: hp(9),
    position: 'absolute',
    bottom: 0,
    left: wp(25),
  },
  watchTutorialsButton: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  tutorialText: {
    fontWeight: '700',
    fontSize: fp(2),
    color: '#000000',
    marginLeft: wp(4),
    marginBottom: hp(0.5),
  },
});

export default SettingsScreen;
