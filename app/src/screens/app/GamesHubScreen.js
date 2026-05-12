import React from 'react';
import {View, StyleSheet, ScrollView} from 'react-native';
import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';
import MaterialCommunityIcons from 'react-native-vector-icons/MaterialCommunityIcons';
import FontAwesome6 from 'react-native-vector-icons/FontAwesome6';
import MaterialIcons from 'react-native-vector-icons/MaterialIcons';

import AppScreen from '../../components/AppScreen';
import AppText from '../../components/AppText';
import AppCard from '../../components/AppCard';
import {useTheme} from '../../context/ThemeContext';
import {useAuth} from '../../context/AuthContext';

const GamesHubScreen = ({navigation}) => {
  const {colors, spacing, radius} = useTheme();
  const {settings} = useAuth();

  const games = [
    {
      id: 'cockfight',
      title: 'Cockfight',
      subtitle: 'Live & Manual Matches',
      icon: 'sword-cross',
      iconPack: 'mci',
      color: colors.meron,
      route: 'LiveCockFight',
      setting: 'B',
    },
    {
      id: 'dice',
      title: 'Dice / Gundata',
      subtitle: '24/7 Virtual Games',
      icon: 'dice-6',
      iconPack: 'mci',
      color: colors.gold,
      route: 'DicePlay',
      setting: 'C',
    },
    {
      id: 'lottery_gift',
      title: 'Gift Pool',
      subtitle: 'Lucky Draws',
      icon: 'redeem',
      iconPack: 'mi',
      color: colors.draw,
      route: 'LotteryGift',
      setting: 'K',
    },
    {
      id: 'lottery_price',
      title: 'Price Pool',
      subtitle: 'Lottery Tickets',
      icon: 'ticket-confirmation',
      iconPack: 'mci',
      color: colors.success,
      route: 'LotteryLive',
      setting: 'L',
    },
    {
      id: 'promotions',
      title: 'Promotions',
      subtitle: 'Exclusive Offers',
      icon: 'local-offer',
      iconPack: 'mi',
      color: colors.warning,
      route: 'PromotionsScreen',
    },
    {
      id: 'past',
      title: 'Past Matches',
      subtitle: 'Cockfight History',
      icon: 'history',
      iconPack: 'mi',
      color: colors.text_secondary,
      route: 'PastMatches',
    },
  ];

  const isDisabled = game => {
    if (!game.setting) return false;
    return settings[game.setting]?.actionValue === 'Y';
  };

  const renderIcon = (game, size) => {
    if (game.iconPack === 'mci') {
      return <MaterialCommunityIcons name={game.icon} size={size} color={game.color} />;
    }
    if (game.iconPack === 'fa6') {
      return <FontAwesome6 name={game.icon} size={size} color={game.color} />;
    }
    return <MaterialIcons name={game.icon} size={size} color={game.color} />;
  };

  return (
    <AppScreen>
      <View style={[styles.header, {borderBottomColor: colors.border}]}>
        <AppText variant="h2">Games</AppText>
      </View>
      <ScrollView
        contentContainerStyle={styles.grid}
        showsVerticalScrollIndicator={false}>
        {games.map(game => {
          const disabled = isDisabled(game);
          return (
            <AppCard
              key={game.id}
              variant="outlined"
              padding="lg"
              onPress={disabled ? undefined : () => navigation.navigate(game.route)}
              disabled={disabled}
              style={styles.gameCard}>
              <View
                style={[
                  styles.iconCircle,
                  {backgroundColor: `${game.color}15`},
                ]}>
                {renderIcon(game, 28)}
              </View>
              <AppText variant="h3" style={styles.gameTitle}>
                {game.title}
              </AppText>
              <AppText variant="caption" color="muted">
                {disabled ? 'Under Maintenance' : game.subtitle}
              </AppText>
            </AppCard>
          );
        })}
      </ScrollView>
    </AppScreen>
  );
};

const styles = StyleSheet.create({
  header: {
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: 1,
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    padding: 12,
    gap: 12,
  },
  gameCard: {
    width: wp(44),
    alignItems: 'center',
    paddingVertical: 20,
  },
  iconCircle: {
    width: 56,
    height: 56,
    borderRadius: 28,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 10,
  },
  gameTitle: {
    marginBottom: 4,
    textAlign: 'center',
  },
});

export default GamesHubScreen;
