import React from 'react';
import {View, TouchableOpacity, StyleSheet} from 'react-native';
import FontAwesome6 from 'react-native-vector-icons/FontAwesome6';
import AppText from './AppText';
import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';
import {useTheme} from '../context/ThemeContext';

const HeaderComponent = ({
  title,
  onBackPress = null,
  onIconPress,
  rightIconWrapperStyle = {},
  containerStyle = {},
  RightIconComponent = null,
}) => {
  const {colors} = useTheme();
  return (
    <View style={[styles.container, {backgroundColor: colors.bg_card, borderBottomColor: colors.border}, containerStyle]}>
      {onBackPress ? (
        <TouchableOpacity onPress={onBackPress}>
          <FontAwesome6 name="arrow-left-long" size={24} color={colors.text_primary} />
        </TouchableOpacity>
      ) : (
        <View style={{width: 28}} />
      )}

      <AppText style={[styles.title, {color: colors.text_primary}]}>{title}</AppText>

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
    borderBottomWidth: 1,
  },
  title: {
    fontSize: fp(1.9),
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
