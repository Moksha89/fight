import {Text, StyleSheet, View, TouchableOpacity} from 'react-native';
import MaterialIcons from 'react-native-vector-icons/MaterialIcons';
import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';

export default function AppButton({
  children,
  buttonStyle,
  textStyle,
  onPress,
  buttonLight,
  disabled,
  showArrow,
  contentContainerStyle,
  iconName = 'arrow-right-alt', // default icon
  iconColor,
  iconSize = 40,
}) {
  const ButtonContent = () => (
    <View style={[styles.contentContainer, contentContainerStyle]}>
      <Text
        style={
          buttonLight
            ? [styles.buttonText, {color: '#000'}, textStyle]
            : [styles.buttonText, textStyle]
        }>
        {children}
      </Text>
      {showArrow && (
        <MaterialIcons
          name={iconName}
          size={iconSize}
          color={iconColor || (buttonLight ? '#000' : '#fff')}
        />
      )}
    </View>
  );

  return disabled ? (
    <View
      style={
        buttonLight
          ? [styles.button, styles.buttonLight, buttonStyle]
          : [styles.button, buttonStyle]
      }>
      <ButtonContent />
    </View>
  ) : (
    <TouchableOpacity
      style={
        buttonLight
          ? [styles.button, styles.buttonLight, buttonStyle]
          : [styles.button, buttonStyle]
      }
      onPress={onPress}>
      <ButtonContent />
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  button: {
    width: wp(84),
    height: hp(6),
    backgroundColor: '#D4A843',
    borderRadius: 50,
    justifyContent: 'center',
    alignItems: 'center',
  },
  buttonText: {
    fontSize: fp(2),
    color: '#fff',
    fontWeight: '500',
  },
  buttonLight: {
    backgroundColor: 'transparent',
    borderWidth: 1,
    borderColor: '#D4A843',
  },
  contentContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    width: wp(50),
  },
});

{
  /* <AppButton
  onPress={() => console.log('Clicked')}
  showArrow={true}
  buttonLight={false}
  iconName="close"
  iconColor="#ffffff"
  iconSize={30}
  contentContainerStyle={{
    justifyContent: 'space-between',
    width: '90%',
  }}
  buttonStyle={{marginBottom: 20}}>
  Cancel Withdrawal
</AppButton>; */
}
