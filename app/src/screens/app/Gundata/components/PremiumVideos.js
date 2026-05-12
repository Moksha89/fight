// @deprecated — Use shared component from app/src/components/game/ instead. This file is kept for reference only.
import {
  StyleSheet,
  Text,
  View,
  Modal,
  ScrollView,
  TouchableOpacity,
  TouchableWithoutFeedback,
} from 'react-native';
import React from 'react';
import AppButton from '../../../../components/AppButton';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';

const videoCards = [
  {
    image: require('../../../../assets/images/savala.png'),
    title: 'Savala Vs Nemali',
  },
  {
    image: require('../../../../assets/images/blackCock.png'),
    title: 'lack Cock Vs Fire Fight',
  },
  {
    image: require('../../../../assets/images/blackCock.png'),
    title: 'lack Cock Vs Fire Fight',
  },
];

export default function PremiumVideos() {
  const [subscribeVisible, setSubscribeVisible] = useState(false);
  const [showPremiumVideos, setShowPremiumVideos] = useState(false);
  return (
    <>
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>Premium Trail Videos</Text>
        <TouchableOpacity
          style={styles.subscribeContainer}
          onPress={() => setSubscribeVisible(true)}>
          <Text style={styles.subscribeBtn}>Subscribe</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.arrowIcon}
          onPress={() => setShowPremiumVideos(!showPremiumVideos)}>
          <Icon
            name={showPremiumVideos ? 'chevron-up' : 'chevron-down'}
            size={18}
            color="#000000"
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
              <View style={styles.modalContainer}>
                <View style={styles.handle} />
                <Text style={styles.modalTitle}>Subscribe to Premium</Text>
                <Text style={styles.modalContent}>
                  Unlock all premium videos and features!
                </Text>
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
            <View key={index} style={styles.videoCard}>
              <Image source={item.image} style={styles.cardImage} />

              <View style={styles.bottomIcons}>
                <Icon name="play-circle-outline" size={20} color="#fff" />
                <Icon name="lock" size={18} color="#fff" />
              </View>

              <Text numberOfLines={2} style={styles.cardTitle}>
                {item.title}
              </Text>
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
  subscribeBtn: {color: '#F5F1E8', fontWeight: '500'},
  videosSection: {
    flexDirection: 'row',
    marginTop: hp(1),
    marginBottom: hp(1),
    position: 'relative',
  },
  videoList: {
    paddingHorizontal: wp(7),
    overflow: 'visible',
  },
  videoCard: {
    width: wp(40),
    height: hp(12),
    borderRadius: 8,
    overflow: 'hidden',
    marginRight: wp(3.5),
    position: 'relative',
  },
});
