import React, {useState, useEffect} from 'react';
import {
  View,
  StyleSheet,
  TouchableOpacity,
  Image,
  Clipboard,
  Alert,
  Dimensions,
} from 'react-native';

import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';

import Icon from 'react-native-vector-icons/Feather';
import MaterialCommunityIcons from 'react-native-vector-icons/MaterialCommunityIcons';
import Octicons from 'react-native-vector-icons/Octicons';

import Share from 'react-native-share';

import AppText from '../../../components/AppText';
import AppScreen from '../../../components/AppScreen';
import HeaderComponent from '../../../components/HeaderComponent';
import TutorialVideoModal from '../../../components/TutorialVideoModal';
import {getReferralCode} from '../../../apis/appApi';

const ReferralScreen = ({navigation}) => {
  const [showTutorialModal, setShowTutorialModal] = React.useState(false);
  const [screenWidth, setScreenWidth] = useState(
    Dimensions.get('window').width,
  );
  const [referralCode, setReferralCode] = useState('...');
  const [referralCount, setReferralCount] = useState(0);
  const [referralEarnings, setReferralEarnings] = useState('0.00');
  const [shareMessage, setShareMessage] = useState('');

  useEffect(() => {
    const subscription = Dimensions.addEventListener('change', ({window}) => {
      setScreenWidth(window.width);
    });
    loadReferralData();
    return () => subscription?.remove();
  }, []);

  const loadReferralData = async () => {
    const data = await getReferralCode();
    if (data) {
      setReferralCode(data.referral_code || 'ERROR');
      setReferralCount(data.referral_count || 0);
      setReferralEarnings(data.referral_earnings || '0.00');
      setShareMessage(data.share_message || '');
    }
  };

  const handleCopy = () => {
    Clipboard.setString(referralCode);
    Alert.alert('Copied!', 'Referral code copied to clipboard.');
  };

  const handleShare = async () => {
    try {
      await Share.open({
        message: shareMessage || `Use my referral code ${referralCode} and start earning!`,
      });
    } catch (error) {
      console.log(error);
    }
  };

  return (
    <AppScreen style={styles.container}>
      <HeaderComponent
        title="Referral"
        onBackPress={() => navigation.goBack()}
        onIconPress={() =>
          navigation.reset({
            index: 0,
            routes: [{name: 'HomeScreen'}],
          })
        }
        RightIconComponent={<Octicons name="home" size={17} color="#ffffff" />}
        rightIconWrapperStyle={{backgroundColor: '#d4a843'}}
      />

      {/* Referral Card */}
      <View style={styles.card}>
        <View style={styles.cardIcon}>
          <Image source={require('../../../assets/icons/blackDown.png')} />
        </View>
        <AppText style={styles.title}>Receive 2%{'\n'}Commission.</AppText>
        <AppText style={styles.subtitle}>
          For each bet your referred friend wins, you earn a reward making every
          one of their victories a win for you too!
        </AppText>

        <View style={styles.referralBox}>
          <AppText style={styles.referralCode}>{referralCode}</AppText>
          <TouchableOpacity onPress={handleCopy}>
            <Icon name="copy" size={22} color="#000" />
          </TouchableOpacity>
        </View>
      </View>
      <TouchableOpacity style={styles.shareButton} onPress={handleShare}>
        <AppText style={styles.shareText}>Share & Earn Lifetime</AppText>
        <MaterialCommunityIcons
          name="share-outline"
          size={30}
          color="#000000"
        />
      </TouchableOpacity>
      <AppText style={styles.sectionTitle}>How does it work?</AppText>
      <TouchableOpacity onPress={() => setShowTutorialModal(true)}>
        <View style={styles.videoCard}>
          <Image
            source={require('../../../assets/images/refer.png')}
            style={{width: '100%', resizeMode: 'contain', height: hp(10)}}
          />
          <AppText style={styles.videoTitle}>
            How referral works and how to earn?
          </AppText>
        </View>
      </TouchableOpacity>
      <TutorialVideoModal
        visible={showTutorialModal}
        onClose={() => setShowTutorialModal(false)}
        videoUrl="https://www.w3schools.com/html/mov_bbb.mp4"
      />
    </AppScreen>
  );
};

export default ReferralScreen;

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#ffefe8',
    borderRadius: wp(4),
    paddingHorizontal: wp(10),
    paddingVertical: hp(4.5),
    alignItems: 'center',
    marginBottom: 30,
    width: wp(90),
    marginTop: hp(3),
    marginLeft: wp(5),
  },
  cardIcon: {
    marginBottom: 10,
  },
  title: {
    fontSize: fp(3),
    textAlign: 'center',
    marginVertical: hp(2),
    lineHeight: hp(4),
    fontWeight: '500',
  },
  subtitle: {
    fontSize: fp(1.7),
    textAlign: 'center',
    marginBottom: hp(2.5),
    lineHeight: hp(2.3),
  },
  referralBox: {
    flexDirection: 'row',
    backgroundColor: '#171717',
    padding: wp(4),
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'space-between',
    width: '100%',
  },
  referralCode: {
    fontSize: fp(2),
    fontWeight: '600',
    letterSpacing: 10,
  },
  shareButton: {
    flexDirection: 'row',
    borderRadius: wp(3),
    alignItems: 'center',
    justifyContent: 'space-between',
    width: wp(86),
    borderWidth: 1,
    borderColor: '#DEDEDE',
    height: hp(7),
    paddingHorizontal: wp(6),
    marginBottom: hp(3),
    marginLeft: wp(5),
  },
  shareText: {
    fontSize: 16,
    fontWeight: '500',
  },
  sectionTitle: {
    fontSize: fp(2),
    fontWeight: '500',
    marginBottom: 16,
    marginLeft: wp(5),
  },
  videoCard: {
    backgroundColor: '#f6f6f6',
    borderRadius: 16,
    width: wp(40),
    marginLeft: wp(5),
    borderWidth: wp(0.1),
    overflow: 'hidden',
    borderColor: '#f6f6f6f',
  },
  videoTitle: {
    marginTop: 12,
    fontSize: 16,
    fontWeight: '500',
    marginLeft: wp(4),
    marginBottom: hp(1.5),
  },
});
