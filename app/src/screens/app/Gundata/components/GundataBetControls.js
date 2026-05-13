import React, {useState} from 'react';
import {
  View,
  TouchableOpacity,
  TextInput,
  StyleSheet,
  Vibration,
} from 'react-native';
import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import AppText from '../../../../components/AppText';

const GOLD = '#D4A843';
const TEXT_PRIMARY = '#F5F1E8';
const TEXT_MUTED = '#A8A29E';
const CARD_BG = '#171717';
const CHIP_BG = '#2a2a2a';

const QUICK_CHIPS = [50, 100, 200, 500, 1000, 2500];

const GundataBetControls = ({
  selectedNumbers = [],
  betAmount = 0,
  onBetAmountChange,
  onPlaceBet,
  isBettingOpen = false,
  isBettingEnabled = true,
  balance = 0,
  maxBetAllowed = 0,
}) => {
  const [activeChip, setActiveChip] = useState(null);

  const effectiveCap = maxBetAllowed > 0
    ? Math.min(balance, maxBetAllowed)
    : balance;

  const handleChipPress = (value) => {
    setActiveChip(value);
    const newAmount = Math.min(value, effectiveCap);
    onBetAmountChange(newAmount);
    Vibration.vibrate(30);
  };

  const handleCustomAmount = (text) => {
    const num = parseInt(text.replace(/[^0-9]/g, ''), 10) || 0;
    const capped = Math.min(num, effectiveCap);
    setActiveChip(null);
    onBetAmountChange(capped);
  };

  const canPlaceBet =
    isBettingOpen &&
    isBettingEnabled &&
    selectedNumbers.length > 0 &&
    betAmount > 0 &&
    betAmount <= balance;

  const totalBet = betAmount * selectedNumbers.length;

  return (
    <View style={styles.container}>
      {/* Selected numbers display */}
      {selectedNumbers.length > 0 && (
        <View style={styles.selectedRow}>
          <AppText style={styles.sectionLabel}>Selected:</AppText>
          <View style={styles.selectedChips}>
            {selectedNumbers.map(n => (
              <View key={n} style={styles.selectedChip}>
                <AppText style={styles.selectedChipText}>{n}</AppText>
              </View>
            ))}
          </View>
          {selectedNumbers.length > 1 && (
            <AppText style={styles.totalLabel}>
              Total: {'\u20B9'}{totalBet}
            </AppText>
          )}
        </View>
      )}

      {/* Bet amount input */}
      <View style={styles.amountRow}>
        <View style={styles.inputWrapper}>
          <AppText style={styles.currencySymbol}>{'\u20B9'}</AppText>
          <TextInput
            style={styles.amountInput}
            keyboardType="numeric"
            placeholder="Amount"
            placeholderTextColor="#555"
            value={betAmount > 0 ? String(betAmount) : ''}
            onChangeText={handleCustomAmount}
            editable={isBettingOpen}
          />
        </View>
      </View>

      {/* Quick chips */}
      <View style={styles.chipsRow}>
        {QUICK_CHIPS.map(val => (
          <TouchableOpacity
            key={val}
            style={[
              styles.chip,
              activeChip === val && styles.chipActive,
              !isBettingOpen && styles.chipDisabled,
            ]}
            onPress={() => handleChipPress(val)}
            disabled={!isBettingOpen}
            activeOpacity={0.7}>
            <AppText
              style={[
                styles.chipText,
                activeChip === val && styles.chipTextActive,
              ]}>
              {val >= 1000 ? `${val / 1000}K` : val}
            </AppText>
          </TouchableOpacity>
        ))}
      </View>

      {/* Place bet button */}
      <TouchableOpacity
        style={[
          styles.placeBetButton,
          !canPlaceBet && styles.placeBetDisabled,
        ]}
        onPress={() => {
          if (canPlaceBet) {
            Vibration.vibrate(100);
            onPlaceBet();
          }
        }}
        disabled={!canPlaceBet}
        activeOpacity={0.8}>
        {!isBettingOpen ? (
          <View style={styles.placeBetContent}>
            <Icon name="timer-sand" size={fp(2.2)} color="#666" />
            <AppText style={styles.placeBetTextDisabled}>
              Wait for betting...
            </AppText>
          </View>
        ) : !isBettingEnabled ? (
          <View style={styles.placeBetContent}>
            <Icon name="lock" size={fp(2.2)} color="#666" />
            <AppText style={styles.placeBetTextDisabled}>
              Placing bet...
            </AppText>
          </View>
        ) : selectedNumbers.length === 0 ? (
          <View style={styles.placeBetContent}>
            <Icon name="dice-multiple" size={fp(2.2)} color="#888" />
            <AppText style={styles.placeBetTextDisabled}>
              Select numbers
            </AppText>
          </View>
        ) : (
          <View style={styles.placeBetContent}>
            <Icon name="check-circle" size={fp(2.2)} color={TEXT_PRIMARY} />
            <AppText style={styles.placeBetText}>
              Place Bet {'\u20B9'}{totalBet}
            </AppText>
          </View>
        )}
      </TouchableOpacity>

      {/* Balance info */}
      <View style={styles.balanceRow}>
        <Icon name="wallet-outline" size={fp(1.6)} color={TEXT_MUTED} />
        <AppText style={styles.balanceText}>
          Balance: {'\u20B9'}{String(balance).split('.')[0]}
        </AppText>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    width: wp(95),
    alignSelf: 'center',
    backgroundColor: CARD_BG,
    borderRadius: wp(4),
    padding: wp(4),
    gap: hp(1.2),
  },
  selectedRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: wp(2),
    flexWrap: 'wrap',
  },
  sectionLabel: {
    color: TEXT_MUTED,
    fontSize: fp(1.5),
    fontWeight: '600',
  },
  selectedChips: {
    flexDirection: 'row',
    gap: wp(1.5),
  },
  selectedChip: {
    backgroundColor: 'rgba(212,168,67,0.15)',
    borderWidth: 1,
    borderColor: GOLD,
    borderRadius: wp(2),
    paddingHorizontal: wp(3),
    paddingVertical: hp(0.3),
  },
  selectedChipText: {
    color: GOLD,
    fontSize: fp(1.6),
    fontWeight: '700',
  },
  totalLabel: {
    color: GOLD,
    fontSize: fp(1.5),
    fontWeight: '600',
    marginLeft: 'auto',
  },
  amountRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  inputWrapper: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1a1a1a',
    borderRadius: wp(2),
    borderWidth: 1,
    borderColor: '#2a2a2a',
    paddingHorizontal: wp(3),
  },
  currencySymbol: {
    color: GOLD,
    fontSize: fp(2),
    fontWeight: '700',
    marginRight: wp(1),
  },
  amountInput: {
    flex: 1,
    color: TEXT_PRIMARY,
    fontSize: fp(2),
    fontWeight: '600',
    paddingVertical: hp(1),
  },
  chipsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: wp(1),
  },
  chip: {
    flex: 1,
    paddingVertical: hp(0.8),
    backgroundColor: CHIP_BG,
    borderRadius: wp(2),
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#3a3a3a',
  },
  chipActive: {
    backgroundColor: 'rgba(212,168,67,0.15)',
    borderColor: GOLD,
  },
  chipDisabled: {
    opacity: 0.4,
  },
  chipText: {
    color: TEXT_MUTED,
    fontSize: fp(1.4),
    fontWeight: '600',
  },
  chipTextActive: {
    color: GOLD,
  },
  placeBetButton: {
    backgroundColor: GOLD,
    borderRadius: wp(3),
    paddingVertical: hp(1.5),
    alignItems: 'center',
    justifyContent: 'center',
    elevation: 3,
    shadowColor: GOLD,
    shadowOffset: {width: 0, height: 2},
    shadowOpacity: 0.3,
    shadowRadius: 4,
  },
  placeBetDisabled: {
    backgroundColor: '#2a2a2a',
    elevation: 0,
    shadowOpacity: 0,
  },
  placeBetContent: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: wp(2),
  },
  placeBetText: {
    color: TEXT_PRIMARY,
    fontSize: fp(2),
    fontWeight: '800',
    letterSpacing: 0.5,
  },
  placeBetTextDisabled: {
    color: '#666',
    fontSize: fp(1.8),
    fontWeight: '600',
  },
  balanceRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: wp(1),
  },
  balanceText: {
    color: TEXT_MUTED,
    fontSize: fp(1.3),
  },
});

export default GundataBetControls;
