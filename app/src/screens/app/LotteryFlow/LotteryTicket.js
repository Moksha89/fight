import React from 'react';
import {View, Text, StyleSheet, Image, ImageBackground} from 'react-native';

import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';

import Ionicons from 'react-native-vector-icons/Ionicons';

import HeaderComponent from '../../../components/HeaderComponent';
import AppText from '../../../components/AppText';
import AppScreen from '../../../components/AppScreen';

const TicketScreen = ({navigation}) => {
  return (
    <AppScreen isTranslucent lightStatusBar>
      {/* Header */}
      <HeaderComponent
        title="LOTTERY LIVE"
        onBackPress={() => navigation.goBack()}
        onIconPress={() => navigation.navigate('DepositWithdrawl')}
        RightIconComponent={
          <View style={{flexDirection: 'row', alignItems: 'center'}}>
            <Ionicons name="wallet-outline" size={20} color="#fff" />
            <AppText
              style={{color: '#fff', marginLeft: wp(3), fontWeight: 'bold'}}>
              ₹125
            </AppText>
          </View>
        }
        containerStyle={styles.headerSection}
        rightIconWrapperStyle={styles.headerIcon}
      />

      {/* Ticket Section */}
      <View style={styles.ticketContainer}>
        <View style={styles.ticketHeader}>
          <Image
            source={require('../../../assets/images/headerTicket.png')}
            style={styles.ticketIcon}
          />
          <Text style={styles.ticketTitle}>Ticket</Text>
        </View>

        <AppText style={styles.infoText}>
          Once the result got announced the wallet balance will automatically
          get updated.
        </AppText>
        <ImageBackground
          style={styles.ticketBody}
          source={require('../../../assets/images/ticketBackground.png')}>
          <Text style={styles.ticketNumbers}>Tickets – 7, 18, 22</Text>
          <View style={styles.row}>
            <Text style={styles.dateText}>12-05-2024</Text>
            <Text style={styles.timeText}>23:45</Text>
          </View>
          <View
            style={{width: '100%', height: hp(0.1), backgroundColor: '#D3D3D3'}}
          />
          <Text style={styles.price}>₹100</Text>
          <View
            style={{width: '100%', height: hp(0.1), backgroundColor: '#D3D3D3'}}
          />
          <Text style={styles.progressText}>In Progress...</Text>
          <View style={styles.progressBarBackground}>
            <View style={styles.progressBarFill} />
          </View>

          <Image
            source={require('../../../assets/images/barcode.png')} // Use a barcode image or generate dynamically
            style={styles.barcode}
          />

          <Text style={styles.resultLabel}>Result Time</Text>
          <Text style={styles.resultTime}>32:58</Text>
        </ImageBackground>
      </View>
    </AppScreen>
  );
};

const styles = StyleSheet.create({
  container: {},
  headerSection: {
    backgroundColor: '#171717',
    paddingHorizontal: wp(7),
    borderRadius: wp(2),
    width: wp(100),
    paddingTop: hp(2),
    height: hp(8),
  },
  headerIcon: {
    backgroundColor: '#d4a843',
    borderColor: 'rgba(212,168,67,0.18)',
    borderWidth: 1,
    width: wp(27),
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: wp(4),
    height: hp(4),
  },

  ticketContainer: {},
  ticketHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    width: wp(100),
    justifyContent: 'center',
    height: hp(9),
  },
  ticketIcon: {
    marginRight: 8,
  },
  ticketTitle: {
    fontSize: fp(4),
    fontWeight: '200',
    marginLeft: wp(4),
    letterSpacing: wp(1.5),
  },
  infoText: {
    fontSize: fp(1.6),
    textAlign: 'center',
    paddingHorizontal: wp(15),
    marginBottom: hp(1),
  },
  ticketBody: {
    alignItems: 'center',
    width: wp(76),
    marginLeft: wp(12.5),
    height: hp(67.5),
    objectFit: 'contain',
    marginTop: hp(3),
    paddingHorizontal: wp(5),
  },
  ticketNumbers: {
    fontSize: 16,
    fontWeight: '600',
    marginTop: hp(5),
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    width: '100%',
    paddingHorizontal: wp(12),
    marginVertical: hp(2.5),
  },
  dateText: {
    color: '#888',
  },
  timeText: {
    color: '#888',
  },
  price: {
    fontSize: fp(4.5),
    paddingVertical: hp(4),
    letterSpacing: wp(2),
  },
  progressText: {
    color: '#888',
    marginTop: hp(3),
    marginBottom: hp(1.5),
  },
  progressBarBackground: {
    height: 8,
    width: '100%',
    backgroundColor: '#ddd',
    borderRadius: 4,
    overflow: 'hidden',
    marginBottom: hp(3),
  },
  progressBarFill: {
    width: '40%', // Example progress
    height: '100%',
    backgroundColor: '#888',
  },
  // barcode: {
  //   width: '100%',
  //   height: 60,
  //   resizeMode: 'contain',
  //   marginBottom: 12,
  // },
  resultLabel: {
    fontSize: fp(3.2),
    marginTop: hp(5),
    color: '#6C6C6C',
    fontWeight: '300',
  },
  resultTime: {
    fontSize: fp(4.2),
    fontWeight: '200',
    color: '#433F3F',
    marginTop: hp(1),
  },
});

export default TicketScreen;
