import React, {useState} from 'react';
import {
  View,
  Modal,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
  Clipboard,
  ToastAndroid,
} from 'react-native';

import MaterialIcons from 'react-native-vector-icons/MaterialIcons';

import AppText from '../../../../components/AppText';
import {apiRequest} from '../../../../utils/apiClient';
import COLORS from '../../../../context/designTokens';

import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';

const ProvablyFairModal = ({visible, onClose, matchId, commitmentHash}) => {
  const [loading, setLoading] = useState(false);
  const [verifyData, setVerifyData] = useState(null);
  const [error, setError] = useState(null);

  const verify = async () => {
    if (!matchId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await apiRequest(`/api/dice/fairness/verify/${matchId}/`);
      if (result.success) {
        setVerifyData(result.data);
      } else {
        setError(result.data?.detail || 'Verification failed');
      }
    } catch (e) {
      setError('Network error');
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text, label) => {
    Clipboard.setString(text);
    ToastAndroid.show(`${label} copied`, ToastAndroid.SHORT);
  };

  const handleOpen = () => {
    if (!verifyData) verify();
  };

  React.useEffect(() => {
    if (visible && !verifyData) {
      verify();
    }
  }, [visible]);

  const renderSeedRow = (label, value) => (
    <View style={styles.seedRow}>
      <AppText style={styles.seedLabel}>{label}</AppText>
      <TouchableOpacity
        style={styles.seedValueWrapper}
        onPress={() => copyToClipboard(value, label)}
        activeOpacity={0.7}>
        <AppText style={styles.seedValue} numberOfLines={1}>
          {value}
        </AppText>
        <MaterialIcons name="content-copy" size={14} color="#888" />
      </TouchableOpacity>
    </View>
  );

  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={onClose}>
      <View style={styles.overlay}>
        <View style={styles.modalContainer}>
          {/* Header */}
          <View style={styles.header}>
            <View style={styles.headerLeft}>
              <MaterialIcons name="verified" size={24} color="#D4A843" />
              <AppText style={styles.headerTitle}>Provably Fair</AppText>
            </View>
            <TouchableOpacity onPress={onClose}>
              <MaterialIcons name="close" size={24} color="#666" />
            </TouchableOpacity>
          </View>

          <ScrollView style={styles.body} showsVerticalScrollIndicator={false}>
            {/* Explanation */}
            <View style={styles.infoCard}>
              <MaterialIcons name="info-outline" size={18} color="#D4A843" />
              <AppText style={styles.infoText}>
                This game uses a provably fair system. The server commits to a
                result hash before the round starts. After the round, you can
                verify that the result was determined before bets were placed.
              </AppText>
            </View>

            {/* Commitment Hash */}
            {commitmentHash ? (
              <View style={styles.section}>
                <AppText style={styles.sectionTitle}>
                  Commitment Hash (shown before round)
                </AppText>
                <TouchableOpacity
                  style={styles.hashBox}
                  onPress={() => copyToClipboard(commitmentHash, 'Hash')}>
                  <AppText style={styles.hashText} numberOfLines={2}>
                    {commitmentHash}
                  </AppText>
                  <MaterialIcons name="content-copy" size={16} color="#D4A843" />
                </TouchableOpacity>
              </View>
            ) : null}

            {loading ? (
              <View style={styles.loadingContainer}>
                <ActivityIndicator size="large" color="#D4A843" />
                <AppText style={styles.loadingText}>Verifying...</AppText>
              </View>
            ) : error ? (
              <View style={styles.errorContainer}>
                <MaterialIcons name="error-outline" size={32} color="#ef4444" />
                <AppText style={styles.errorText}>{error}</AppText>
                <TouchableOpacity style={styles.retryBtn} onPress={verify}>
                  <AppText style={styles.retryText}>Retry</AppText>
                </TouchableOpacity>
              </View>
            ) : verifyData ? (
              <>
                {/* Verification Status */}
                <View
                  style={[
                    styles.statusBanner,
                    verifyData.verified
                      ? styles.statusSuccess
                      : styles.statusFail,
                  ]}>
                  <MaterialIcons
                    name={verifyData.verified ? 'check-circle' : 'cancel'}
                    size={20}
                    color={verifyData.verified ? COLORS.success : COLORS.meron_light}
                  />
                  <AppText
                    style={[
                      styles.statusText,
                      {color: verifyData.verified ? COLORS.success : COLORS.meron_light},
                    ]}>
                    {verifyData.verified
                      ? 'Result Verified — Fair'
                      : 'Verification Failed'}
                  </AppText>
                </View>

                {/* Seeds */}
                <View style={styles.section}>
                  <AppText style={styles.sectionTitle}>Seeds</AppText>
                  {verifyData.server_seed &&
                    renderSeedRow('Server Seed', verifyData.server_seed)}
                  {verifyData.client_seed &&
                    renderSeedRow('Client Seed', verifyData.client_seed)}
                  {verifyData.nonce != null &&
                    renderSeedRow('Nonce', String(verifyData.nonce))}
                </View>

                {/* Dice Result */}
                {verifyData.dice_result ? (
                  <View style={styles.section}>
                    <AppText style={styles.sectionTitle}>Dice Result</AppText>
                    <View style={styles.diceRow}>
                      {verifyData.dice_result.map((face, i) => (
                        <View key={i} style={styles.diceBox}>
                          <AppText style={styles.diceText}>{face}</AppText>
                        </View>
                      ))}
                    </View>
                  </View>
                ) : null}
              </>
            ) : null}
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
};

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end',
  },
  modalContainer: {
    backgroundColor: '#171717',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    maxHeight: hp(80),
    paddingBottom: 24,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#f0f0f0',
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  headerTitle: {
    fontSize: fp(2),
    fontWeight: '700',
    color: '#F5F1E8',
  },
  body: {
    paddingHorizontal: 16,
    paddingTop: 12,
  },
  infoCard: {
    flexDirection: 'row',
    backgroundColor: '#1F1A12',
    borderRadius: 10,
    padding: 12,
    gap: 8,
    marginBottom: 16,
  },
  infoText: {
    flex: 1,
    fontSize: fp(1.3),
    color: '#666',
    lineHeight: 18,
  },
  section: {
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: fp(1.4),
    fontWeight: '700',
    color: '#888',
    textTransform: 'uppercase',
    marginBottom: 8,
  },
  hashBox: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1a1a1a',
    borderRadius: 8,
    padding: 12,
    gap: 8,
  },
  hashText: {
    flex: 1,
    fontSize: fp(1.3),
    color: '#A8A29E',
    fontFamily: 'monospace',
  },
  seedRow: {
    marginBottom: 10,
  },
  seedLabel: {
    fontSize: fp(1.3),
    color: '#888',
    marginBottom: 4,
  },
  seedValueWrapper: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1a1a1a',
    borderRadius: 6,
    paddingHorizontal: 10,
    paddingVertical: 8,
    gap: 6,
  },
  seedValue: {
    flex: 1,
    fontSize: fp(1.3),
    color: '#A8A29E',
    fontFamily: 'monospace',
  },
  statusBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: 10,
    padding: 12,
    gap: 8,
    marginBottom: 16,
  },
  statusSuccess: {
    backgroundColor: 'rgba(34,197,94,0.1)',
  },
  statusFail: {
    backgroundColor: 'rgba(239,68,68,0.1)',
  },
  statusText: {
    fontSize: fp(1.6),
    fontWeight: '700',
  },
  diceRow: {
    flexDirection: 'row',
    gap: 8,
    flexWrap: 'wrap',
  },
  diceBox: {
    width: 44,
    height: 44,
    borderRadius: 8,
    backgroundColor: COLORS.gold,
    alignItems: 'center',
    justifyContent: 'center',
  },
  diceText: {
    fontSize: fp(2.2),
    fontWeight: '700',
    color: COLORS.white,
  },
  loadingContainer: {
    alignItems: 'center',
    paddingVertical: 24,
  },
  loadingText: {
    marginTop: 8,
    color: COLORS.text_label,
    fontSize: fp(1.4),
  },
  errorContainer: {
    alignItems: 'center',
    paddingVertical: 20,
  },
  errorText: {
    marginTop: 8,
    color: COLORS.meron_light,
    fontSize: fp(1.5),
  },
  retryBtn: {
    marginTop: 12,
    paddingHorizontal: 20,
    paddingVertical: 8,
    borderRadius: 6,
    backgroundColor: COLORS.gold,
  },
  retryText: {
    color: COLORS.white,
    fontWeight: '600',
  },
});

export default ProvablyFairModal;
