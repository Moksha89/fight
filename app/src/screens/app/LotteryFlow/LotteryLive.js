import React, {useState} from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Image,
  ScrollView,
} from 'react-native';
import FontAwesome from 'react-native-vector-icons/FontAwesome';

import AppScreen from '../../../components/AppScreen';
import HeaderComponent from '../../../components/HeaderComponent';
import Ionicons from 'react-native-vector-icons/Ionicons';
import AppText from '../../../components/AppText';

import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';

import Video from 'react-native-video';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';

import Entypo from 'react-native-vector-icons/Entypo';
import MaterialIcons from 'react-native-vector-icons/MaterialIcons';

import {useAuth} from '../../../context/AuthContext';
import COLORS from '../../../context/designTokens';

const ticketNumbers = Array.from({length: 15}, (_, i) => i + 1);
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
const LotteryLive = ({numbers = [1, 15, 3, 9, 6], onRefresh, navigation}) => {
  // const {wallet} = useAuth();

  const [selectedTime, setSelectedTime] = useState('13:00');
  const [selectedNumbers, setSelectedNumbers] = useState([12]);
  const [expanded, setExpanded] = useState(false);

  const toggleNumber = num => {
    if (selectedNumbers.includes(num)) {
      setSelectedNumbers(selectedNumbers.filter(n => n !== num));
    } else {
      setSelectedNumbers([...selectedNumbers, num]);
    }
  };
  const [activeView, setActiveView] = useState('medal'); // Default to 'medal'

  const [selectNumbers, setSelectNumbers] = useState(false);
  const [count, setCount] = useState(0);
  return (
    <AppScreen style={{position: 'relative'}} isTranslucent lightStatusBar>
      {/* Header */}
      <HeaderComponent
        title="LOTTERY LIVE"
        onBackPress={() => navigation.goBack()}
        onIconPress={() => navigation.navigate('DepositWithdrawl')}
        RightIconComponent={
          <View style={{flexDirection: 'row', alignItems: 'center'}}>
            <Ionicons name="wallet-outline" size={20} color="#fff" />
            <AppText
              style={{color: COLORS.text_primary, marginLeft: wp(3), fontWeight: 'bold'}}>
              {/* ₹{String(wallet.balanceWithBonus).split('.')[0]} */}
            </AppText>
          </View>
        }
        containerStyle={styles.headerSection}
        rightIconWrapperStyle={styles.headerIcon}
      />
      <View style={styles.numbersWrapper}>
        {/* Refresh Icon */}
        <TouchableOpacity onPress={onRefresh} style={styles.refreshButton}>
          <Ionicons name="refresh" size={20} color="#A8A29E" />
        </TouchableOpacity>
        <View style={styles.divider} />

        {numbers.map((num, index) => (
          <View key={index} style={styles.circle}>
            <Text style={styles.numberText}>{num}</Text>
          </View>
        ))}
      </View>

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
        <Text style={styles.liveBadge}>Live</Text>
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

          <TouchableOpacity style={styles.dropdownBox}>
            <AppText style={{fontSize: fp(1.3)}}>Ticket price</AppText>
            <AppText style={{fontSize: fp(1.5)}}>₹100</AppText>
          </TouchableOpacity>

          <TouchableOpacity style={[styles.dropdownBox, {height: hp(3.5)}]}>
            <FontAwesome name="graduation-cap" size={12} color="#000000" />
            <AppText style={{fontSize: fp(1.3)}}>Watch Tutorials</AppText>
          </TouchableOpacity>
        </View>

        {activeView === 'medal' && (
          <View>
            {selectNumbers ? (
              <View style={styles.numberGrid}>
                {ticketNumbers.map(num => (
                  <TouchableOpacity
                    key={num}
                    style={[
                      styles.numberBox,
                      selectedNumbers.includes(num) && styles.numberBoxSelected,
                      (num === 6 || (num > 6 && (num - 6) % 10 === 0)) && {
                        marginLeft: wp(5),
                      },
                    ]}
                    onPress={() => toggleNumber(num)}>
                    <Text
                      style={[
                        styles.numberText,
                        selectedNumbers.includes(num) &&
                          styles.numberTextSelected,
                      ]}>
                      {num}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
            ) : (
              <View style={[styles.addTickets]}>
                <AppText style={{width: '50%'}}>
                  Select number of tickets - the more you buy, the more chance
                  to win.
                </AppText>
                <View style={styles.counter}>
                  {/* Decrement Button */}
                  <TouchableOpacity
                    style={styles.circleButton}
                    onPress={() => setCount(count > 0 ? count - 1 : 0)} // prevent going negative
                  >
                    <AppText style={styles.symbol}>-</AppText>
                  </TouchableOpacity>

                  {/* Number Box */}
                  <View style={styles.countBox}>
                    <AppText style={styles.countText}>{count}</AppText>
                  </View>

                  {/* Increment Button */}
                  <TouchableOpacity
                    style={styles.circleButton}
                    onPress={() => setCount(count + 1)}>
                    <AppText style={styles.symbol}>+</AppText>
                  </TouchableOpacity>
                </View>
              </View>
            )}

            {/* Prize Breakdown */}
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
                <Text style={styles.prizeText}>1st Winning - </Text>
                <Text style={styles.prizeValue}>1000/-</Text>
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
                <Text style={styles.prizeText}>2nd Winning - </Text>
                <Text style={styles.prizeValue}>300/-</Text>
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
                <Text style={styles.prizeText}>3rd Winning - </Text>
                <Text style={styles.prizeValue}>100/-</Text>
              </View>
            </View>
          </View>
        )}

        {activeView === 'document' && (
          <View style={{paddingHorizontal: wp(4), paddingBottom: hp(10)}}>
            {ticketsData.map(ticket => {
              const isExpanded = expanded === ticket.id;

              return (
                <View
                  key={ticket.id}
                  style={{
                    backgroundColor:
                      ticket.status === 'In Progress' ? COLORS.text_primary : '#EEEEEE',
                    borderRadius: 12,
                    marginBottom: hp(1.5),
                    paddingVertical: hp(1.5),
                    paddingHorizontal: wp(3),
                    borderColor: '#EEEEEE',
                    borderWidth: wp(0.2),
                  }}>
                  {/* Header Row */}
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
                    <View style={{flexDirection: 'row', alignItems: 'center'}}>
                      <Image
                        source={require('../../../assets/icons/colorTicket.png')}
                        style={{width: 32, height: 32, marginRight: wp(3)}}
                      />
                      <View>
                        <Text
                          style={{
                            fontWeight: 'bold',
                            fontSize: fp(1.8),
                            marginBottom: hp(1.5),
                          }}>
                          Tickets – {ticket.numbers.join(', ')}
                        </Text>
                        <Text style={{color: COLORS.text_muted, fontSize: fp(1.6)}}>
                          {ticket.date} | {ticket.time}
                        </Text>
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
                        <Text
                          style={{
                            fontSize: fp(1.6),
                            color: COLORS.text_muted,
                          }}>
                          {ticket.status}
                        </Text>
                      </View>
                    ) : (
                      <View
                        style={{flexDirection: 'row', alignItems: 'center'}}>
                        {ticket.extraNumbers?.map(n => (
                          <View
                            key={n}
                            style={{
                              width: 26,
                              height: 26,
                              borderRadius: 13,
                              backgroundColor: COLORS.bg_card,
                              justifyContent: 'center',
                              alignItems: 'center',
                              marginHorizontal: 2,
                            }}>
                            <Text
                              style={{fontWeight: '600', fontSize: fp(1.6)}}>
                              {n}
                            </Text>
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

                  {/* Expanded Content */}
                  {isExpanded && ticket.moreNumbers?.length > 0 && (
                    <View
                      style={{
                        flexDirection: 'row',
                        flexWrap: 'wrap',
                        gap: wp(2),
                        marginTop: hp(1.2),
                        marginLeft: 38,
                      }}>
                      {ticket.moreNumbers.map(n => (
                        <View
                          key={n}
                          style={{
                            width: 26,
                            height: 26,
                            borderRadius: 13,
                            backgroundColor: COLORS.bg_card,
                            justifyContent: 'center',
                            alignItems: 'center',
                          }}>
                          <Text style={{fontWeight: '600', fontSize: fp(1.6)}}>
                            {n}
                          </Text>
                        </View>
                      ))}
                    </View>
                  )}

                  {/* Progress Bar at Bottom */}
                  {ticket.status && (
                    <View style={{marginTop: hp(2), alignItems: 'center'}}>
                      <View
                        style={{
                          width: '100%',
                          height: 6,
                          backgroundColor: COLORS.disabled,
                          borderRadius: 3,
                          overflow: 'hidden',
                        }}>
                        <View
                          style={{
                            width: '50%',
                            height: '100%',
                            backgroundColor: '#AEAEAE',
                          }}
                        />
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
        <Text style={styles.totalText}>500/-</Text>
        <TouchableOpacity
          style={styles.buyButton}
          onPress={() => navigation.navigate('LotteryTicket')}>
          <Text style={styles.buyText}>Buy Ticket</Text>
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
    width: wp(25),
    height: hp(4),
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: wp(4),
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
    backgroundColor: 'rgba(212,168,67,0.18)',
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
    backgroundColor: COLORS.bg_card,
    borderRadius: 12,
    flexDirection: 'row',
    paddingHorizontal: wp(2),
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: hp(2),
    width: wp(92),
    marginLeft: wp(4),
    height: hp(6.5),
    marginTop: hp(1.2),
  },
  iconBox: {
    width: wp(10),
    aspectRatio: 1 / 1,
    backgroundColor: COLORS.bg_card,
    borderRadius: 10,
    justifyContent: 'center',
    alignItems: 'center',
    position: 'relative',
    elevation: 2,
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
    justifyContent: 'space-between',
  },
  dropdownText: {
    fontSize: 14,
    color: COLORS.text_secondary,
    marginRight: wp(8),
    marginLeft: wp(3),
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
    marginRight: wp(2),
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
    marginBottom: hp(1),
    width: wp(92),
    marginLeft: wp(4),
  },
  addTickets: {
    width: wp(92),
    marginLeft: wp(4),
    backgroundColor: COLORS.bg_card,
    borderRadius: wp(4),
    padding: wp(3),
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  counter: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
  circleButton: {
    width: wp(7),
    aspectRatio: 1 / 1,
    borderRadius: wp(5),
    backgroundColor: COLORS.bg_card,
    justifyContent: 'center',
    alignItems: 'center',
    display: 'flex',
  },
  symbol: {
    fontSize: fp(2),
  },
  countBox: {
    marginHorizontal: wp(4),
    borderRadius: wp(1),
    backgroundColor: COLORS.gold,
    justifyContent: 'center',
    alignItems: 'center',
    width: wp(6),
    aspectRatio: 1 / 1,
  },
  countText: {
    color: COLORS.text_primary,
  },

  numberBox: {
    width: wp(6.7),
    height: wp(7),
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
  videoContainer: {position: 'relative'},
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
    marginTop: hp(2),
    gap: 10,
    width: wp(100),
    paddingHorizontal: wp(5),
  },
  prizeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: hp(1.5),
    marginTop: hp(0.5),
  },
  meadlSection: {
    width: wp(7),
    height: wp(7),
    position: 'relative',
    alignItems: 'center',
    justifyContent: 'center',
  },
  medalImage: {width: '100%', height: '100%'},
  medalPlaceText: {
    position: 'absolute',
    fontSize: fp(0.8),
    color: COLORS.text_primary,
    top: hp(1.5),
  },
  prizeText: {
    flex: 1,
    fontSize: fp(1.6),
    color: '#433F3F',
  },
  prizeValue: {
    fontSize: fp(2),
    color: '#433F3F',
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

export default LotteryLive;
