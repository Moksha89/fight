import {
  StyleSheet,
  View,
  Modal,
  ScrollView,
  Image,
  TouchableOpacity,
  TouchableWithoutFeedback,
} from 'react-native';
import React, {useState} from 'react';
import AppButton from '../AppButton';
import AppText from '../AppText';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import {useTheme} from '../../context/ThemeContext';
import COLORS from '../../context/designTokens';
import {
  responsiveHeight as hp,
  responsiveWidth as wp,
} from 'react-native-responsive-dimensions';

const videoCards = [
  {
    image: require('../../assets/images/savala.png'),
    title: 'Savala Vs Nemali',
  },
  {
    image: require('../../assets/images/blackCock.png'),
    title: 'lack Cock Vs Fire Fight',
  },
  {
    image: require('../../assets/images/blackCock.png'),
    title: 'lack Cock Vs Fire Fight',
  },
];

export default function GamePremiumVideos() {
  const {colors} = useTheme();
  const [subscribeVisible, setSubscribeVisible] = useState(false);
  const [showPremiumVideos, setShowPremiumVideos] = useState(false);

  return (
    <>
      <View style={styles.sectionHeader}>
        <AppText style={[styles.sectionTitle, {color: colors.text_primary}]}>
          Premium Trail Videos
        </AppText>
        <TouchableOpacity
          style={styles.subscribeContainer}
          onPress={() => setSubscribeVisible(true)}>
          <AppText style={{color: colors.gold, fontWeight: '500'}}>
            Subscribe
          </AppText>
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.arrowIcon}
          onPress={() => setShowPremiumVideos(!showPremiumVideos)}>
          <Icon
            name={showPremiumVideos ? 'chevron-up' : 'chevron-down'}
            size={18}
            color={colors.text_primary}
          />
        </TouchableOpacity>
        <Modal
          animationType="slide"
          transparent={true}
          statusBarTranslucent
          visible={subscribeVisible}
          onRequestClose={() => setSubscribeVisible(false)}>
          <TouchableWithoutFeedback onPress={() => setSubscribeVisible(false)}>
            <View style={styles.modalOverlay}>
              <View style={[styles.modalContainer, {backgroundColor: colors.card}]}>
                <View style={styles.handle} />
                <AppText style={[styles.modalTitle, {color: colors.gold}]}>
                  Subscribe to Premium
                </AppText>
                <AppText style={{color: colors.text_secondary}}>
                  Unlock all premium videos and features!
                </AppText>
                <AppButton
                  onPress={() => console.log('Clicked')}
                  showArrow={true}
                  buttonLight={false}
                  iconName="arrow-right-alt"
                  iconColor="#ffffff"
                  iconSize={40}
                  contentContainerStyle={{
                    justifyContent: 'space-between',
                    width: '80%',
                  }}
                  buttonStyle={{marginTop: hp(5)}}>
                  Subscribe
                </AppButton>
              </View>
            </View>
          </TouchableWithoutFeedback>
        </Modal>
      </View>
      {showPremiumVideos && (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={styles.videosSection}>
          {videoCards.map((item, index) => (
            <View key={index} style={[styles.videoCard, {backgroundColor: colors.card}]}>
              <Image source={item.image} style={styles.cardImage} />
              <View style={styles.bottomIcons}>
                <Icon name="play-circle-outline" size={20} color="#fff" />
                <Icon name="lock" size={18} color="#fff" />
              </View>
              <AppText numberOfLines={2} style={styles.cardTitle}>
                {item.title}
              </AppText>
            </View>
          ))}
        </ScrollView>
      )}
    </>
  );
}

const styles = StyleSheet.create({
  sectionHeader: {
    flexDirection: 'row',
    paddingHorizontal: wp(7),
    marginTop: hp(2.5),
    alignItems: 'center',
  },
  sectionTitle: {fontSize: 16, fontWeight: 'bold'},
  subscribeContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginLeft: wp(30),
  },
  arrowIcon: {marginLeft: wp(2)},
  videosSection: {
    flexDirection: 'row',
    marginTop: hp(1),
    marginBottom: hp(1),
    position: 'relative',
  },
  videoCard: {
    width: wp(40),
    height: hp(12),
    borderRadius: 8,
    overflow: 'hidden',
    marginRight: wp(3.5),
    position: 'relative',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.7)',
    justifyContent: 'flex-end',
  },
  modalContainer: {
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 24,
    alignItems: 'center',
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    marginBottom: 8,
  },
  handle: {
    width: 40,
    height: 5,
    backgroundColor: COLORS.bg_chip_light,
    borderRadius: 3,
    marginBottom: 16,
  },
  bottomIcons: {
    position: 'absolute',
    bottom: 4,
    left: 4,
    right: 4,
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  cardTitle: {
    position: 'absolute',
    bottom: 24,
    left: 4,
    color: COLORS.text_primary,
    fontSize: 10,
  },
  cardImage: {
    width: '100%',
    height: '100%',
    resizeMode: 'cover',
  },
});
