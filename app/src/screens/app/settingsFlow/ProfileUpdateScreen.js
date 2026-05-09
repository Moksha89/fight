import React, {useState, useRef, useEffect} from 'react';
import {BackHandler} from 'react-native';

import {useAuth} from '../../../context/AuthContext';

import storage from '../../../utils/storage';

import {updateUserInfo} from '../../../apis/authApi';

import {View, StyleSheet, TextInput, TouchableOpacity} from 'react-native';

import AppScreen from '../../../components/AppScreen';
import AppText from '../../../components/AppText';
import AppButton from '../../../components/AppButton';
import HeaderComponent from '../../../components/HeaderComponent';
import Octicons from 'react-native-vector-icons/Octicons';

import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';

const ProfileUpdateScreen = ({navigation, route}) => {
  const {
    setIsProfileUpdated,
    isProfileUpdated,
    userInfo,
    setUserInfo,
    isLocked,
    setIsLocked,
  } = useAuth();

  const [gender, setGender] = useState('');
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');

  const isFirstTime = route?.params?.fromFirstTime || !isProfileUpdated;

  useEffect(() => {
    setName(userInfo.username);
    setPhone(userInfo.phoneNumber);
    setGender(userInfo.gender);
  }, [userInfo]);

  const handleUpdate = async () => {
    const updatedData = {
      username: name,
      phoneNumber: phone,
      gender: gender,
    };

    const indianPhoneRegex = /^[6-9]\d{9}$/;

    if (!name || name.trim().length <= 2) {
      alert('Please enter a valid name.');
      return;
    }

    if (!phone || !indianPhoneRegex.test(phone.trim())) {
      alert('Please enter a valid 10-digit Indian phone number.');
      return;
    }

    if (!gender) {
      alert('Please select your gender.');
      return;
    }

    const result = await updateUserInfo(updatedData);

    if (result.success) {
      await storage.setItem('isProfileUpdated', 'true');
      setIsProfileUpdated(true);

      await setUserInfo(result.data);

      if (isLocked) {
        setIsLocked(false);
      }
      if (!isFirstTime) {
        navigation.goBack();
      }
    } else {
      alert('Failed to update profile');
    }
  };

  useEffect(() => {
    const backHandler = BackHandler.addEventListener(
      'hardwareBackPress',
      () => {
        if (isFirstTime) return true; // disable back
        return false;
      },
    );
    return () => backHandler.remove();
  }, [isFirstTime]);

  return (
    <AppScreen isTranslucent lightStatusBar style={styles.mainContainer}>
      <HeaderComponent
        title="Profile"
        onBackPress={isFirstTime ? null : () => navigation.goBack()}
        onIconPress={() =>
          navigation.reset({
            index: 0,
            routes: [{name: 'HomeScreen'}],
          })
        }
        RightIconComponent={
          isFirstTime ? null : (
            <Octicons name="home" size={17} color="#ffffff" />
          )
        }
        rightIconWrapperStyle={{backgroundColor: '#d4a843'}}
        containerStyle={{marginBottom: hp(4)}}
      />
      <TextInput
        editable={false}
        placeholder="Email"
        style={[styles.input, {backgroundColor: '#f0f0f0'}]}
        keyboardType="email-address"
        value={userInfo.email}
      />
      <TextInput
        placeholder="Name"
        value={name}
        onChangeText={setName}
        style={styles.input}
      />
      <TextInput
        placeholder="Phone Number - for Support / Contact"
        value={phone}
        onChangeText={setPhone}
        style={styles.input}
        keyboardType="phone-pad"
      />

      {/* Gender Section */}
      <AppText style={styles.label}>Gender</AppText>
      <View style={styles.genderRow}>
        <TouchableOpacity
          style={styles.genderOption}
          onPress={() => setGender('M')}>
          <View style={styles.circle}>
            {gender === 'M' && <View style={styles.selectedCircle} />}
          </View>
          <AppText style={styles.genderText}>Male</AppText>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.genderOption}
          onPress={() => setGender('F')}>
          <View style={styles.circle}>
            {gender === 'F' && <View style={styles.selectedCircle} />}
          </View>
          <AppText style={styles.genderText}>Female</AppText>
        </TouchableOpacity>
      </View>
      <AppButton
        iconSize={40}
        textStyle={{fontSize: fp(2)}}
        showArrow={true}
        buttonStyle={styles.loginButton}
        onPress={handleUpdate}>
        Update Details
      </AppButton>
    </AppScreen>
  );
};

const styles = StyleSheet.create({
  mainContainer: {
    position: 'relative',
    paddingTop: hp(4.5),
  },
  input: {
    borderWidth: 1,
    borderColor: '#ccc',
    borderRadius: wp(2),
    paddingVertical: hp(1.2),
    paddingHorizontal: wp(4),
    fontSize: fp(1.9),
    marginBottom: hp(3),
    marginLeft: wp(5),
    color: '#000',
    width: wp(90),
    height: hp(6.5),
  },
  label: {
    fontSize: fp(1.8),
    marginBottom: hp(2),
    marginLeft: wp(5),
  },
  genderRow: {
    marginLeft: wp(5),
    flexDirection: 'row',
    alignItems: 'center',
  },
  genderOption: {
    flexDirection: 'row',
    alignItems: 'center',
    marginRight: wp(6),
  },
  circle: {
    width: wp(5),
    height: wp(5),
    borderRadius: wp(2.5),
    borderWidth: 2,
    borderColor: '#d4a843',
    marginRight: wp(3),
    alignItems: 'center',
    justifyContent: 'center',
  },
  selectedCircle: {
    backgroundColor: '#d4a843',
    width: wp(3),
    height: wp(3),
    borderRadius: 50,
  },
  genderText: {
    fontSize: fp(1.6),
  },
  loginButton: {
    width: wp(86),
    position: 'absolute',
    bottom: hp(5),
    left: wp(7),
  },
});

export default ProfileUpdateScreen;
