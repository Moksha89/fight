import React from 'react';
import {View, TouchableOpacity, StyleSheet, Image} from 'react-native';
import FontAwesome6 from 'react-native-vector-icons/FontAwesome6';
import AppText from './AppText';
import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';

const HeaderComponent = ({
  title,
  onBackPress = null,
  onIconPress,
  rightIconWrapperStyle = {},
  containerStyle = {},
  RightIconComponent = null,
}) => {
  return (
    <View style={[styles.container, containerStyle]}>
      {onBackPress ? (
        <TouchableOpacity onPress={onBackPress}>
          <FontAwesome6 name="arrow-left-long" size={24} color="#1a1a1a" />
        </TouchableOpacity>
      ) : (
        <View style={{width: 28}} />
      )}

      <AppText style={styles.title}>{title}</AppText>

      {RightIconComponent ? (
        <TouchableOpacity
          style={[styles.rightIconWrapper, rightIconWrapperStyle]}
          onPress={onIconPress}>
          {RightIconComponent}
        </TouchableOpacity>
      ) : (
        <View style={{width: wp(10)}} />
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    width: wp(100),
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: wp(4),
    alignItems: 'center',
    height: hp(7),
    backgroundColor: '#ffffff',
    borderBottomWidth: 1,
    borderBottomColor: '#e5e7eb',
  },
  title: {
    fontSize: fp(1.9),
    color: '#1a1a1a',
    fontWeight: '600',
  },
  rightIconWrapper: {
    width: wp(10),
    height: wp(10),
    borderRadius: wp(2),
    flexDirection: 'row',
    justifyContent: 'space-evenly',
    alignItems: 'center',
  },
});

export default HeaderComponent;
