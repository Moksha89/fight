import React from 'react';
import {
  StyleSheet,
  Text,
  View,
  TouchableOpacity,
} from 'react-native';
import MaterialCommunityIcons from 'react-native-vector-icons/MaterialCommunityIcons';
import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';

export default function BoardBar({
  boards,
  activeBoardId,
  setActiveBoardId,
  soundEnabled,
  toggleSound,
}) {
  if (!boards || boards.length === 0) {
    return null;
  }

  return (
    <View style={styles.container}>
      <View style={styles.boardRow}>
        {boards.map(board => {
          const isVirtual = board.is_virtual;
          const modeIcon = isVirtual ? '🎰' : '📺';
          const hasLive = (board.matches || []).some(m => !m.isWinnerDeclared);
          return (
            <TouchableOpacity
              key={board.id}
              style={[
                styles.button,
                activeBoardId == board.id && styles.activeButton,
                isVirtual && activeBoardId == board.id && styles.activeVirtualButton,
              ]}
              onPress={() => setActiveBoardId(String(board.id))}>
              <View style={styles.boardLabelRow}>
                {hasLive && <View style={styles.liveDot} />}
                <Text
                  style={[
                    styles.buttonText,
                    activeBoardId == board.id && styles.activeButtonText,
                  ]}>
                  {modeIcon} {board.name}
                </Text>
              </View>
              {activeBoardId == board.id && <View style={[styles.triangle, isVirtual && styles.virtualTriangle]} />}
            </TouchableOpacity>
          );
        })}
      </View>
      <View style={styles.iconRow}>
        <TouchableOpacity onPress={toggleSound}>
          <MaterialCommunityIcons
            name={soundEnabled ? 'volume-high' : 'volume-off'}
            size={24}
            color="#000000"
          />
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    width: wp(96),
    marginLeft: wp(2),
    position: 'relative',
    marginTop: hp(1.5),
    marginBottom: hp(1),
  },
  boardRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    flex: 1,
  },
  button: {
    alignItems: 'center',
    marginRight: hp(1.2),
    paddingVertical: hp(0.3),
    paddingHorizontal: wp(2.4),
    borderRadius: wp(1),
    backgroundColor: '#ccc',
  },
  activeButton: {
    backgroundColor: '#d4a843',
  },
  activeVirtualButton: {
    backgroundColor: '#4caf50',
  },
  boardLabelRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  liveDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: '#f44336',
  },
  virtualTriangle: {
    borderBottomColor: '#4caf50',
  },
  buttonText: {
    fontSize: fp(1.5),
    color: '#F5F1E8',
  },
  activeButtonText: {
    color: '#fff',
    fontWeight: 'bold',
  },
  triangle: {
    marginTop: 4,
    width: 0,
    height: 0,
    backgroundColor: 'transparent',
    borderStyle: 'solid',
    borderLeftWidth: 7,
    borderRightWidth: 7,
    borderBottomWidth: 8,
    borderLeftColor: 'transparent',
    borderRightColor: 'transparent',
    borderBottomColor: '#d4a843',
    position: 'absolute',
    left: 15,
    top: -12,
  },
  iconRow: {
    position: 'absolute',
    right: wp(0),
  },
});
