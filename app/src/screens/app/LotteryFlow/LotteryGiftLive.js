import React, {useState} from 'react';
import {
  View,
  StyleSheet,
  TouchableOpacity,
  Image,
  ScrollView,
} from 'react-native';

import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';

import AppScreen from '../../../components/AppScreen';
import HeaderComponent from '../../../components/HeaderComponent';
import AppText from '../../../components/AppText';

import Ionicons from 'react-native-vector-icons/Ionicons';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import Entypo from 'react-native-vector-icons/Entypo';
import MaterialIcons from 'react-native-vector-icons/MaterialIcons';
import {useAuth} from '../../../context/AuthContext';
import COLORS from '../../../context/designTokens';

import Video from 'react-native-video';

const ticketsData = [
  {
    id: 1,
    numbers: [7, 18, 22],
    date: '12-05-2024',
    time: '04:00',
    status: 'In Progress....',
    extraNumbers: [],
  },
  {
    id: 2,
    numbers: [3, 6, 9],
    date: '12-05-2024',
    time: '23:45',
    status: '',
    extraNumbers: [9, 13, 7],
  },
  {
    id: 3,
    numbers: [9, 15, 29],
    date: '12-05-2024',
    time: '06:15',
    status: '',
    extraNumbers: [9, 13, 7],
    moreNumbers: [5, 16, 3],
  },
];
const LotteryGiftLive = ({navigation}) => {
  const [expanded, setExpanded] = useState(false);
  const [activeView, setActiveView] = useState('medal');
  const {wallet} = useAuth();

  return (
    <AppScreen style={{position: 'relative'}} isTranslucent lightStatusBar>
      <HeaderComponent
        title="LOTTERY LIVE"
        onBackPress={() => navigation.goBack()}
        onIconPress={() => navigation.navigate('DepositWithdrawl')}
        RightIconComponent={
          <View style={{flexDirection: 'row', alignItems: 'center'}}>
            <Ionicons name="wallet-outline" size={20} color="#fff" />
            <AppText
              style={{color: COLORS.text_primary, marginLeft: wp(3), fontWeight: 'bold'}}>
              ₹{String(wallet.balanceWithBonus).split('.')[0]}
            </AppText>
          </View>
        }
        containerStyle={styles.headerSection}
        rightIconWrapperStyle={styles.headerIcon}
      />

      <View style={styles.videoContainer}>
        <Video
          source={{uri: 'https://www.w3schools.com/html/mov_bbb.mp4'}}
          style={styles.video}
          resizeMode="cover"
          repeat
          paused={false}
          controls={false}
          ignoreSilentSwitch="ignore"
        />
        <AppText style={styles.liveBadge}>Live</AppText>
        <TouchableOpacity style={styles.refreshBtn}>
          <Icon name="refresh" size={30} color="#D4A843" />
        </TouchableOpacity>
      </View>
      <View>
        <View style={styles.selection}>
          <TouchableOpacity
            style={styles.iconBox}
            onPress={() => setActiveView('medal')}>
            <Image
              source={require('../../../assets/icons/medalImage.png')}
              style={{width: wp(5)}}
              resizeMode="contain"
            />
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.iconBox}
            onPress={() => setActiveView('document')}>
            <Ionicons name="document-text-outline" size={20} color="#D4A843" />
            <View style={styles.badge} />
          </TouchableOpacity>

          <TouchableOpacity style={[styles.dropdownBox, {width: wp(20)}]}>
            <AppText style={{marginRight: wp(3)}}>GIFT</AppText>
            <Entypo name="chevron-down" size={20} color="#A8A29E" />
          </TouchableOpacity>

          <TouchableOpacity style={styles.dropdownBox}>
            <Ionicons name="ticket-outline" size={20} color="#D4A843" />
            <AppText style={styles.dropdownText}>BIKE</AppText>
            <Entypo name="chevron-down" size={20} color="#A8A29E" />
          </TouchableOpacity>
        </View>

        {activeView === 'medal' && (
          <View style={styles.medalMainContainer}>
            <ScrollView>
              <View style={styles.giftArea}>
                <Image
                  style={styles.giftImage}
                  source={require('../../../assets/images/car.png')}
                />
                <View style={styles.timerSection}>
                  <AppText style={styles.timerText}>Closing in</AppText>
                  <AppText style={{fontSize: fp(3), marginTop: hp(1)}}>
                    32:58
                  </AppText>
                </View>
              </View>
              <View style={styles.prizeContainer}>
                <View style={styles.prizeRow}>
                  <View style={styles.meadlSection}>
                    <Image
                      source={require('../../../assets/icons/medal.png')}
                      style={styles.medalImage}
                      resizeMode="contain"
                    />
                    <AppText style={styles.medalPlaceText}>1</AppText>
                  </View>
                  <AppText style={styles.prizeText}>1st Winning - </AppText>
                  <AppText style={styles.prizeValue}>Honda Car</AppText>
                </View>
                <View style={styles.prizeRow}>
                  <View style={styles.meadlSection}>
                    <Image
                      source={require('../../../assets/icons/medal.png')}
                      style={styles.medalImage}
                      resizeMode="contain"
                    />
                    <AppText style={styles.medalPlaceText}>2</AppText>
                  </View>
                  <AppText style={styles.prizeText}>2nd Winning - </AppText>
                  <AppText style={styles.prizeValue}>1,50,000</AppText>
                </View>
                <View style={styles.prizeRow}>
                  <View style={styles.meadlSection}>
                    <Image
                      source={require('../../../assets/icons/medal.png')}
                      style={styles.medalImage}
                      resizeMode="contain"
                    />
                    <AppText style={styles.medalPlaceText}>3</AppText>
                  </View>
                  <AppText style={styles.prizeText}>3rd Winning - </AppText>
                  <AppText style={styles.prizeValue}>100000</AppText>
                </View>
              </View>
            </ScrollView>
          </View>
        )}

        {activeView === 'document' && (
          <View style={{paddingHorizontal: wp(4), paddingBottom: hp(10)}}>
            {ticketsData.map(ticket => {
              const isExpanded = expanded === ticket.id;

              return (
                <View
                  key={ticket.id}
                  style={[
                    styles.historyCard,
                    {
                      backgroundColor: ticket.status?.includes('In Progress')
                        ? COLORS.text_primary
                        : '#EEEEEE',
                      borderColor: ticket.status?.includes('In Progress')
                        ? '#DDDDDD'
                        : '#EEEEEE',
                    },
                  ]}>
                  <TouchableOpacity
                    onPress={() =>
                      setExpanded(prev =>
                        prev === ticket.id ? null : ticket.id,
                      )
                    }
                    style={{
                      flexDirection: 'row',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                    }}>
                    {/* Left Content */}
                    <View style={styles.historyLeftContent}>
                      <Image
                        source={require('../../../assets/icons/colorTicket.png')}
                        style={{width: 32, height: 32, marginRight: wp(3)}}
                      />
                      <View>
                        <AppText
                          style={{
                            fontWeight: 'bold',
                            fontSize: fp(1.8),
                            marginBottom: hp(1),
                          }}>
                          Tickets – {ticket.numbers.join(', ')}
                        </AppText>
                        <AppText style={{color: COLORS.text_muted, fontSize: fp(1.6)}}>
                          {ticket.date} | {ticket.time}
                        </AppText>
                      </View>
                    </View>

                    {/* Right Content */}
                    {ticket.status ? (
                      <View style={{alignItems: 'flex-end'}}>
                        <MaterialIcons
                          name="arrow-right-alt"
                          size={32}
                          color="#666"
                        />
                        <AppText style={styles.progressText}>
                          {ticket.status}
                        </AppText>
                      </View>
                    ) : (
                      <View
                        style={{flexDirection: 'row', alignItems: 'center'}}>
                        {ticket.extraNumbers?.map(n => (
                          <View key={n} style={styles.lotteryNumbers}>
                            <AppText
                              style={{fontWeight: '600', fontSize: fp(1.6)}}>
                              {n}
                            </AppText>
                          </View>
                        ))}
                        <Entypo
                          name={isExpanded ? 'chevron-up' : 'chevron-down'}
                          size={20}
                          color="#666"
                          style={{marginLeft: wp(2)}}
                        />
                      </View>
                    )}
                  </TouchableOpacity>
                  {isExpanded && ticket.moreNumbers?.length > 0 && (
                    <View style={styles.extrsNumbersSection}>
                      {ticket.moreNumbers.map(n => (
                        <View key={n} style={styles.extraNumbers}>
                          <AppText
                            style={{fontWeight: '600', fontSize: fp(1.6)}}>
                            {n}
                          </AppText>
                        </View>
                      ))}
                    </View>
                  )}
                  {ticket.status && (
                    <View style={{marginTop: hp(1), alignItems: 'center'}}>
                      <View style={styles.progressBar}>
                        <View style={styles.filledBar} />
                      </View>
                    </View>
                  )}
                </View>
              );
            })}
          </View>
        )}
      </View>

      {/* Bottom Bar */}
      <View style={styles.bottomBar}>
        <AppText style={styles.totalText}>1500/-</AppText>
        <TouchableOpacity
          style={styles.buyButton}
          onPress={() => navigation.navigate('LotteryTicket')}>
          <AppText style={styles.buyText}>Buy Ticket</AppText>
          <MaterialIcons name="arrow-right-alt" size={34} color="#ffffff" />
        </TouchableOpacity>
      </View>
    </AppScreen>
  );
};

const styles = StyleSheet.create({
  content: {},

  headerSection: {
    backgroundColor: COLORS.bg_card,
    paddingHorizontal: wp(7),
    borderRadius: wp(2),
    width: wp(100),
    paddingTop: hp(2),
    height: hp(9),
  },
  headerIcon: {
    backgroundColor: COLORS.gold,
    borderColor: 'rgba(212,168,67,0.18)',
    borderWidth: 1,
    width: wp(27),
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: wp(4),
    height: hp(4),
  },
  numbersWrapper: {
    flexDirection: 'row',
    alignItems: 'center',
    height: hp(5),
  },
  circle: {
    width: 30,
    height: 30,
    borderRadius: 50,
    backgroundColor: COLORS.bg_chip,
    marginHorizontal: wp(1),
    justifyContent: 'center',
    alignItems: 'center',
  },
  divider: {
    width: 1,
    height: hp(5),
    backgroundColor: COLORS.disabled,
    marginHorizontal: wp(3),
  },
  refreshButton: {
    marginLeft: wp(4),
  },
  walletIcon: {flexDirection: 'row', alignItems: 'center'},
  walletAmount: {color: COLORS.text_primary, marginLeft: wp(2), fontWeight: 'bold'},

  ticketImage: {
    width: '100%',
    height: hp(25),
    marginBottom: hp(1),
  },
  selection: {
    backgroundColor: '#E6E6E6',
    borderRadius: 12,
    flexDirection: 'row',
    paddingHorizontal: wp(2),
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: hp(2),
    width: wp(92),
    marginLeft: wp(4),
    height: hp(6.5),
    marginTop: hp(2),
  },
  iconBox: {
    width: 40,
    height: 40,
    backgroundColor: COLORS.bg_card,
    borderRadius: 10,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 8,
    position: 'relative',
    elevation: 2,
  },
  meadlSection: {
    width: wp(8),
    height: wp(8),
    position: 'relative',
    alignItems: 'center',
    justifyContent: 'center',
  },
  medalImage: {width: '100%', height: '100%'},
  medalPlaceText: {
    position: 'absolute',
    fontSize: fp(1.2),
    color: COLORS.text_primary,
    top: hp(1.65),
  },
  icon: {
    width: 20,
    height: 20,
    resizeMode: 'contain',
  },
  badge: {
    position: 'absolute',
    top: hp(1),
    right: wp(2),
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: 'orange',
  },
  dropdownBox: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: COLORS.bg_card,
    paddingHorizontal: 12,
    borderRadius: 10,
    height: hp(4.5),
    width: wp(30),
  },
  dropdownText: {
    fontSize: fp(1.8),
    color: COLORS.text_secondary,
    marginRight: wp(5),
    marginLeft: wp(2),
  },
  medalMainContainer: {
    width: wp(100),
    height: hp(54.5),
    paddingBottom: hp(7.2),
  },
  giftArea: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    width: wp(80),
    marginLeft: wp(10),
  },
  giftImage: {width: wp(50), objectFit: 'contain', height: wp(50)},
  timerSection: {alignItems: 'center', justifyContent: 'center'},
  timerText: {
    fontSize: fp(2.2),
    color: '#433F3F',
    fontWeight: '200',
  },
  selectionRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginBottom: 16,
    gap: 8,
    marginLeft: wp(4),
  },
  timeSlot: {
    backgroundColor: COLORS.bg_chip,
    borderRadius: wp(1),
    paddingVertical: 7,
    paddingHorizontal: 16,
  },
  timeSlotSelected: {
    backgroundColor: COLORS.gold,
  },
  timeSlotText: {
    color: COLORS.text_secondary,
  },
  timeSlotTextSelected: {
    color: COLORS.text_primary,
    fontWeight: 'bold',
  },

  numberGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: wp(2),
    marginBottom: 24,
    width: wp(92),
    marginLeft: wp(4),
  },
  numberBox: {
    width: wp(6.7),
    height: wp(8),
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: COLORS.bg_chip,
    borderRadius: 8,
  },
  numberBoxSelected: {
    backgroundColor: COLORS.gold,
  },
  numberText: {
    color: COLORS.text_secondary,
  },
  numberTextSelected: {
    color: COLORS.text_primary,
    fontWeight: 'bold',
  },
  videoContainer: {position: 'relative', marginTop: hp(1)},
  video: {width: wp(100), height: hp(27)},
  liveBadge: {
    position: 'absolute',
    top: wp(5),
    right: wp(5),
    backgroundColor: COLORS.meron,
    color: COLORS.text_primary,
    paddingHorizontal: 6,
    borderRadius: 4,
  },
  refreshBtn: {
    position: 'absolute',
    bottom: wp(7),
    right: wp(7),
    backgroundColor: COLORS.bg_card,
    padding: wp(1.5),
    borderRadius: 30,
  },
  prizeContainer: {
    marginTop: hp(1),
    gap: 10,
    width: wp(90),
    marginLeft: wp(5),
  },
  prizeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: hp(1.5),
    marginTop: hp(0.5),
  },

  prizeText: {
    flex: 1,
    fontSize: 16,
    color: '#433F3F',
  },
  prizeValue: {
    fontSize: fp(2.2),
    color: '#433F3F',
  },
  historyCard: {
    borderRadius: 12,
    marginBottom: hp(1.5),
    paddingVertical: hp(1),
    paddingHorizontal: wp(3),
    borderWidth: wp(0.2),
  },
  historyLeftContent: {flexDirection: 'row', alignItems: 'center'},
  progressText: {
    fontSize: fp(1.6),
    color: COLORS.text_muted,
  },
  lotteryNumbers: {
    width: 26,
    height: 26,
    borderRadius: 13,
    backgroundColor: COLORS.bg_card,
    justifyContent: 'center',
    alignItems: 'center',
    marginHorizontal: 2,
  },
  extrsNumbersSection: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: wp(2),
    marginTop: hp(1.2),
    marginLeft: 38,
  },
  extraNumbers: {
    width: 26,
    height: 26,
    borderRadius: 13,
    backgroundColor: COLORS.bg_card,
    justifyContent: 'center',
    alignItems: 'center',
  },
  progressBar: {
    width: '100%',
    height: 6,
    backgroundColor: COLORS.disabled,
    borderRadius: 3,
    overflow: 'hidden',
  },
  filledBar: {
    width: '50%',
    height: '100%',
    backgroundColor: '#AEAEAE',
  },
  bottomBar: {
    backgroundColor: '#000',
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: wp(10),
    alignItems: 'center',
    position: 'absolute',
    bottom: 0,
    width: wp(100),
    height: hp(7),
  },
  totalText: {
    color: COLORS.text_primary,
    fontWeight: '600',
    fontSize: fp(2.5),
  },
  buyButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 15,
  },
  buyText: {
    color: COLORS.text_primary,
    fontSize: fp(2.2),
  },
});

export default LotteryGiftLive;
