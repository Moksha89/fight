import {
  View,
  StyleSheet,
  Animated,
  Image,
  TouchableOpacity,
  Text,
  ActivityIndicator,
  TouchableHighlight,
} from 'react-native';
import {useState, useEffect, useRef} from 'react';
import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';

import {useNavigation} from '@react-navigation/native';

import {useAuth} from '../../../../context/AuthContext';

import Video from 'react-native-video';
import {WebView} from 'react-native-webview';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';

function VideoPlayBox({
  activeChannel,
  autoMatchData,
  manualMatchData,
  musicEnabled,
  setMusicEnabled,
  soundEnabled,
  bettingHistory,
  showLiveBadge = false,
}) {
  const navigation = useNavigation();

  const {settings, wallet} = useAuth();
  const [isLiveEnableToSee, setIsLiveEnableToSee] = useState(true);

  const [showWebView, setShowWebView] = useState(true);
  const [manualLiveMatch, setManualLiveMatch] = useState(null);

  const scaleAnim = useRef(new Animated.Value(0)).current;

  // check if user eligible to watch live
  useEffect(() => {
    const timeout = setTimeout(() => {
      const actionValue = parseFloat(settings?.L?.actionValue || '0');
      const balance = parseFloat(wallet?.balance || '0');

      if ((balance < actionValue) & !bettingHistory) {
        setIsLiveEnableToSee(false);
      }
    }, 15000);

    return () => clearTimeout(timeout);
  }, [wallet?.balance, settings?.L?.actionValue]);

  const handleRefresh = () => {
    setShowWebView(false);
    setTimeout(() => {
      setShowWebView(true);
    }, 100);
  };

  useEffect(() => {
    if (activeChannel !== 0 && manualMatchData?.[activeChannel]) {
      const liveMatch = manualMatchData[activeChannel].find(m => m.isLive);
      setManualLiveMatch(liveMatch || null);
    } else {
      setManualLiveMatch(null);
    }
  }, [manualMatchData, activeChannel]);

  const isVideoStream = url => {
    if (!url) return false;
    const videoExtensions = ['.m3u8', '.mp4', '.webm', '.mov'];
    const lowerUrl = url.toLowerCase().split('?')[0];
    return videoExtensions.some(ext => lowerUrl.includes(ext));
  };

  // ========== auto match music logic (UNCHANGED)
  useEffect(() => {
    if (
      showWebView &&
      activeChannel == 0 &&
      !isVideoStream(autoMatchData?.liveUrl)
    ) {
      setMusicEnabled(true);
    } else {
      setMusicEnabled(false);
    }
  }, [showWebView, autoMatchData?.liveUrl, activeChannel]);

  // manual splash animation
  useEffect(() => {
    if (!manualLiveMatch?.youtubeLiveLink) {
      scaleAnim.setValue(0);

      Animated.timing(scaleAnim, {
        toValue: 0.6,
        duration: 600,
        useNativeDriver: true,
      }).start();
    }
  }, [manualLiveMatch?.youtubeLiveLink]);

  if (!isLiveEnableToSee)
    return (
      <TouchableHighlight
        style={styles.videoContainer}
        onPress={() => navigation.navigate('DepositWithdrawl')}>
        <View>
          <ActivityIndicator
            size="small"
            color="#fff"
            style={{
              zIndex: 999,
              marginTop: 10,
              position: 'absolute',
              left: 0,
              top: 0,
            }}
          />
          <Image
            source={require('../../../../assets/images/walletDown.png')}
            style={{width: '100%', height: '100%'}}
          />
        </View>
      </TouchableHighlight>
    );

  return (
    <View style={styles.videoContainer}>
      {activeChannel == 0 ? (
        // ================= AUTO MATCH (UNCHANGED) =================
        <View style={{flex: 1}}>
          {autoMatchData?.liveUrl ? (
            isVideoStream(autoMatchData.liveUrl) ? (
              <Video
                source={{uri: autoMatchData.liveUrl}}
                style={{flex: 1, backgroundColor: '#000'}}
                resizeMode="contain"
                muted={!soundEnabled}
                controls={false}
                paused={false}
              />
            ) : showWebView ? (
              <WebView
                injectedJavaScript={`
                document.body.style.filter = 'brightness(1) contrast(1.2) saturate(1.2)';
                document.body.style.pointerEvents = 'none';
                document.body.style.background = '#000';
                true;
              `}
                source={{uri: autoMatchData.liveUrl}}
                style={{flex: 1}}
              />
            ) : (
              <Image
                style={{width: '100%', height: '100%'}}
                resizeMode="cover"
                source={require('../../../../assets/images/liveDown.png')}
              />
            )
          ) : (
            <Image
              style={{width: '100%', height: '100%'}}
              source={require('../../../../assets/images/liveDown.png')}
            />
          )}

          {showLiveBadge && <Text style={styles.liveBadge}>Live</Text>}

          <TouchableOpacity style={styles.refreshBtn} onPress={handleRefresh}>
            <Icon name="refresh" size={30} color="#000" />
          </TouchableOpacity>
        </View>
      ) : (
        // ================= MANUAL MATCH (UPDATED) =================
        <View style={{flex: 1}}>
          {manualLiveMatch && settings['B']?.actionValue != 'Y' ? (
            <View style={{flex: 1}}>
              {!manualLiveMatch.youtubeLiveLink ? (
                <View style={styles.splashContainer}>
                  <Animated.Image
                    source={require('../../../../assets/logos/logo.png')}
                    style={[styles.logo, {transform: [{scale: scaleAnim}]}]}
                    resizeMode="contain"
                  />
                  <View style={styles.loadingContainer}>
                    <Text style={styles.loadingText}>Loading Stream...</Text>
                    <ActivityIndicator size="small" color="#fff" />
                  </View>
                </View>
              ) : isVideoStream(manualLiveMatch.youtubeLiveLink) ? (
                <Video
                  source={{uri: manualLiveMatch.youtubeLiveLink}}
                  style={{flex: 1, backgroundColor: '#000'}}
                  resizeMode="contain"
                  muted={!soundEnabled}
                  controls={false}
                  paused={false}
                />
              ) : showWebView ? (
                <WebView
                  injectedJavaScript={`
                  document.body.style.filter = 'brightness(1) contrast(1.2) saturate(1.2)';
                  document.body.style.pointerEvents = 'none';
                  document.body.style.background = '#000';
                  true;
                `}
                  source={{uri: manualLiveMatch.youtubeLiveLink}}
                  style={{flex: 1}}
                />
              ) : (
                <Image
                  source={require('../../../../assets/images/liveDown.png')}
                  style={{width: '100%', height: '100%'}}
                />
              )}
            </View>
          ) : manualMatchData?.[activeChannel]?.[0]?.promoVideo ? (
            <Video
              source={{uri: manualMatchData[activeChannel][0].promoVideo}}
              style={{flex: 1}}
              repeat
              muted={!soundEnabled}
              resizeMode="cover"
              controls={false}
              paused={false}
            />
          ) : (
            <Image
              source={require('../../../../assets/images/liveDown.png')}
              style={{width: '100%', height: '100%'}}
            />
          )}
        </View>
      )}
    </View>
  );
}

export default VideoPlayBox;

const styles = StyleSheet.create({
  videoContainer: {
    position: 'relative',
    width: wp(100),
    height: wp(42),
    display: 'flex',
    justifyContent: 'center',
  },
  liveBadge: {
    position: 'absolute',
    top: wp(5),
    right: wp(5),
    backgroundColor: '#FF4000',
    color: '#fff',
    paddingHorizontal: 6,
    borderRadius: 4,
  },
  refreshBtn: {
    position: 'absolute',
    bottom: wp(7),
    right: wp(7),
    backgroundColor: '#171717',
    padding: wp(1.5),
    borderRadius: 30,
  },
  splashContainer: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'black',
    justifyContent: 'center',
    alignItems: 'center',
    zIndex: 9999,
  },
  logo: {
    width: 150,
    height: 150,
  },
  loadingContainer: {
    alignItems: 'center',
    marginTop: 20,
  },
  loadingText: {
    fontSize: 18,
    color: '#fff',
  },
});