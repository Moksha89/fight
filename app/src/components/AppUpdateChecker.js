import React, {useEffect, useState} from 'react';
import {
  Modal,
  View,
  StyleSheet,
  Linking,
  BackHandler,
  Platform,
} from 'react-native';
import {useTheme} from '../context/ThemeContext';
import AppText from './AppText';
import AppButton from './AppButton';
import {baseApiEndpoint} from '../Config/baseEndpoint';
import {getVersionCode} from '../utils/version';

export default function AppUpdateChecker() {
  const {colors} = useTheme();
  const [visible, setVisible] = useState(false);
  const [updateInfo, setUpdateInfo] = useState(null);

  useEffect(() => {
    checkForUpdate();
  }, []);

  useEffect(() => {
    if (visible && updateInfo?.force_update) {
      const handler = BackHandler.addEventListener('hardwareBackPress', () => true);
      return () => handler.remove();
    }
  }, [visible, updateInfo]);

  const checkForUpdate = async () => {
    try {
      const response = await fetch(`${baseApiEndpoint}/api/app-version/`);
      if (!response.ok) return;

      const data = await response.json();
      const currentVersionCode = getVersionCode();

      if (data.latest_version_code > currentVersionCode) {
        setUpdateInfo(data);
        setVisible(true);
      }
    } catch (_) {}
  };

  const handleUpdate = () => {
    if (updateInfo?.download_url) {
      Linking.openURL(updateInfo.download_url);
    }
  };

  if (!visible || !updateInfo) return null;

  return (
    <Modal transparent animationType="fade" visible={visible}>
      <View style={styles.overlay}>
        <View style={[styles.dialog, {backgroundColor: colors.surface}]}>
          <View style={[styles.iconContainer, {backgroundColor: colors.gold + '20'}]}>
            <AppText style={[styles.icon]}>🔄</AppText>
          </View>

          <AppText style={[styles.title, {color: colors.gold}]}>
            Update Available
          </AppText>

          <AppText style={[styles.version, {color: colors.textSecondary}]}>
            Version {updateInfo.latest_version_name}
          </AppText>

          {updateInfo.release_notes ? (
            <AppText style={[styles.notes, {color: colors.text}]}>
              {updateInfo.release_notes}
            </AppText>
          ) : null}

          <AppButton
            title="Update Now"
            onPress={handleUpdate}
            style={styles.updateBtn}
          />

          {!updateInfo.force_update && (
            <AppButton
              title="Later"
              onPress={() => setVisible(false)}
              style={[styles.laterBtn, {backgroundColor: 'transparent'}]}
              textStyle={{color: colors.textSecondary}}
            />
          )}
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.7)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 30,
  },
  dialog: {
    width: '100%',
    borderRadius: 16,
    padding: 24,
    alignItems: 'center',
  },
  iconContainer: {
    width: 56,
    height: 56,
    borderRadius: 28,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
  },
  icon: {
    fontSize: 28,
  },
  title: {
    fontSize: 20,
    fontWeight: '700',
    marginBottom: 4,
  },
  version: {
    fontSize: 14,
    marginBottom: 12,
  },
  notes: {
    fontSize: 14,
    textAlign: 'center',
    marginBottom: 20,
    lineHeight: 20,
  },
  updateBtn: {
    width: '100%',
    marginBottom: 8,
  },
  laterBtn: {
    width: '100%',
  },
});
