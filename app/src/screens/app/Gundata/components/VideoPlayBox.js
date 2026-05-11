import {
  View,
  StyleSheet,
  Animated,
  Image,
  TouchableOpacity,
  Text,
  ActivityIndicator,
  TouchableWithoutFeedback,
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

import YoutubePlayer from 'react-native-youtube-iframe';
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
  showLiveBadge = false,
  manualOnly = false,
  bettingHistory,
  isVirtualBoard = false,
  countdownSeconds = 0,
  commitmentHash = null,
}) {
  const navigation = useNavigation();

  const {settings, wallet} = useAuth();
  const [isLiveEnableToSee, setIsLiveEnableToSee] = useState(true);

  const [showWebView, setShowWebView] = useState(true);
  const [manualLiveMatch, setManualLiveMatch] = useState(null);

  // For hiding youtube load effect in beginning
  const scaleAnim = useRef(new Animated.Value(0)).current;
  const [isYoutubePlaying, setIsYoutubePlaying] = useState(false);

  // For youtube video to reload if video got ended
  const [reloadKey, setReloadKey] = useState(Date.now());
  const hasReloadedRef = useRef(false);
  const reloadTimeoutRef = useRef(null);

  // Pending = matchWinStatus === 0 (in progress). Don't stop live if user has pending bets (still in game).
  const hasPendingBets = Array.isArray(bettingHistory)
    ? bettingHistory.some(b => b.matchWinStatus === 0)
    : false;

  // check if user eligible to watch live (same as CockFight: don't hide live if user has pending bets)
  useEffect(() => {
    const timeout = setTimeout(() => {
      const actionValue = parseFloat(settings?.L?.actionValue || '0');
      const balance = parseFloat(wallet?.balance || '0');

      if (balance < actionValue && !hasPendingBets) {
        setIsLiveEnableToSee(false);
      }
    }, 15000); // check after 15 seconds of wallet balance got changed

    return () => clearTimeout(timeout); // cleanup on unmount
  }, [wallet?.balance, settings?.L?.actionValue, hasPendingBets]);

  // for auto push user to live ending if not in sink with live
  const playerRef = useRef();
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const currentTime = await playerRef.current?.getCurrentTime();
        const duration = await playerRef.current?.getDuration();

        if (typeof currentTime === 'number' && typeof duration === 'number') {
          const lag = duration - currentTime;

          if (lag > 15000) {
            console.log('⚠️ Lag detected, auto-seeking to live');
            await playerRef.current.seekTo(duration, true); // true = allowSeekAhead
          }
        }
      } catch (err) {
        console.warn('Error checking live status:', err);
      }
    }, 10000); // check every 25 seconds

    return () => clearInterval(interval);
  }, []);

  const handleYoutubeStateChange = state => {
    console.log('YouTube state:', state);

    if (state === 'buffering') {
      setIsYoutubePlaying(false);
      playerRef.current?.mute(true);
    }

    if (state === 'playing' && !isYoutubePlaying) {
      setIsYoutubePlaying(true);
      playerRef.current?.mute(false);
    }

    if ((state === 'ended' || state === 'paused') && !hasReloadedRef.current) {
      hasReloadedRef.current = true;

      reloadTimeoutRef.current = setTimeout(() => {
        console.log('Reloading YouTube player...');
        setReloadKey(Date.now());

        // 👇 Reset guard after reload to allow future reloads
        setTimeout(() => {
          hasReloadedRef.current = false;
          console.log('Reset reload guard');
        }, 1500); // Delay must be enough to let component fully re-mount
      }, 500);
    }
  };

  useEffect(() => {
    return () => {
      if (reloadTimeoutRef.current) clearTimeout(reloadTimeoutRef.current);
    };
  }, []);

  useEffect(() => {
    const videoId = manualLiveMatch?.youtubeLiveLink;
    if (!videoId) return;
    setIsYoutubePlaying(false);
    scaleAnim.setValue(0);

    Animated.timing(scaleAnim, {
      toValue: 0.6,
      duration: 600,
      useNativeDriver: true,
    }).start();
  }, [reloadKey, manualLiveMatch?.youtubeLiveLink]);

  const handleRefresh = () => {
    setShowWebView(false);
    setTimeout(() => {
      setShowWebView(true);
    }, 100);
  };

  useEffect(() => {
    if (manualMatchData?.[activeChannel]) {
      const liveMatch = manualMatchData[activeChannel].find(m => m.isLive);
      setManualLiveMatch(liveMatch || null);
    } else {
      setManualLiveMatch(null);
    }
  }, [manualMatchData, activeChannel]);

  // Backend stores only the YouTube video code (ID). Pass it directly to the player.
  const getYoutubeVideoId = link => {
    if (!link || typeof link !== 'string') return null;
    const trimmed = link.trim();
    if (!trimmed) return null;
    // Already just the video code (e.g. 11-char ID, no URL)
    if (!trimmed.includes('/') && !trimmed.includes('?')) return trimmed;
    // Extract from URL (in case backend ever sends full URL)
    const vMatch = trimmed.match(/(?:v=|\/)([a-zA-Z0-9_-]{11})(?:\?|&|$)/);
    return vMatch ? vMatch[1] : trimmed;
  };

  const youtubeVideoId = getYoutubeVideoId(manualLiveMatch?.youtubeLiveLink);

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

  // Virtual board: show dice arena instead of video
  if (isVirtualBoard) {
    const isUrgent = countdownSeconds > 0 && countdownSeconds <= 5;
    return (
      <View style={[styles.videoContainer, {backgroundColor: '#1a1a2e'}]}>
        <View style={styles.virtualArena}>
          {countdownSeconds > 0 ? (
            <View style={styles.virtualCountdown}>
              <Text style={[styles.virtualCountdownText, isUrgent && {color: '#f44336'}]}>
                {countdownSeconds}s
              </Text>
              <Text style={styles.virtualSubtext}>until dice roll</Text>
            </View>
          ) : (
            <View style={styles.virtualCountdown}>
              <Icon name="dice-multiple" size={28} color="#d4a843" />
              <Text style={[styles.virtualSubtext, {marginTop: 4}]}>Rolling dice...</Text>
            </View>
          )}
          <Text style={styles.virtualDiceIcon}>🎲</Text>
          <Text style={styles.virtualTitle}>VIRTUAL DICE</Text>
          <Text style={styles.virtualSubtext}>Server rolls 6 dice automatically</Text>
          {commitmentHash ? (
            <Text style={styles.hashDisplay}>
              🔒 {commitmentHash.slice(0, 16)}...
            </Text>
          ) : null}
        </View>
        <View style={styles.virtualBadge}>
          <Text style={styles.virtualBadgeText}>VIRTUAL</Text>
        </View>
      </View>
    );
  }

  const showManualContent = manualOnly || activeChannel != 0;

  return (
    <View style={styles.videoContainer}>
      {showManualContent ? (
        <View style={{flex: 1}}>
          {manualLiveMatch && youtubeVideoId && settings['#']?.actionValue != 'N' ? (
            <View style={{flex: 1}}>
              {!isYoutubePlaying && (
                <View style={styles.splashContainer}>
                  <Animated.Image
                    source={require('../../../../assets/logos/logo.png')}
                    style={[styles.logo, {transform: [{scale: scaleAnim}]}]}
                    resizeMode="contain"
                  />
                  <View style={styles.loadingContainer}>
                    <Text style={styles.loadingText}>Loading Stream...</Text>
                    <ActivityIndicator
                      size="small"
                      color="#fff"
                      style={{marginTop: 10}}
                    />
                  </View>
                </View>
              )}
              <View style={{flex: 1}} pointerEvents={'none'}>
                <YoutubePlayer
                  ref={playerRef}
                  key={reloadKey} // 👈 force re-render
                  height={'100%'}
                  width={wp(100)}
                  play={true}
                  videoId={youtubeVideoId}
                  mute={!soundEnabled}
                  initialPlayerParams={{
                    controls: false,
                    modestbranding: false,
                    rel: false,
                    showinfo: false,
                    fs: false,
                    iv_load_policy: 3,
                  }}
                  webViewProps={{
                    allowsInlineMediaPlayback: false,
                    mediaPlaybackRequiresUserAction: false,
                    scrollEnabled: false,
                  }}
                  onChangeState={handleYoutubeStateChange}
                />
              </View>
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
          {showLiveBadge && manualLiveMatch && (
            <Text style={styles.liveBadge}>Live</Text>
          )}
          <TouchableOpacity style={styles.refreshBtn} onPress={handleRefresh}>
            <Icon name="refresh" size={30} color="#000" />
          </TouchableOpacity>
        </View>
      ) : null}
    </View>
  );
}

export default VideoPlayBox;

const styles = StyleSheet.create({
  videoContainer: {
    position: 'relative',
    width: wp(100),
    height: wp(57),
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
  virtualArena: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 6,
  },
  virtualCountdown: {
    alignItems: 'center',
    marginBottom: 8,
  },
  virtualCountdownText: {
    fontSize: fp(4),
    fontWeight: '800',
    color: '#d4a843',
  },
  virtualSubtext: {
    fontSize: fp(1.4),
    color: '#888',
  },
  virtualDiceIcon: {
    fontSize: 48,
  },
  virtualTitle: {
    fontSize: fp(2.2),
    fontWeight: '800',
    color: '#d4a843',
    letterSpacing: 2,
  },
  virtualBadge: {
    position: 'absolute',
    top: 10,
    right: 10,
    backgroundColor: 'rgba(76,175,80,0.25)',
    paddingHorizontal: 10,
    paddingVertical: 3,
    borderRadius: 12,
  },
  virtualBadgeText: {
    color: '#4caf50',
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 1,
  },
  hashDisplay: {
    fontSize: 9,
    color: '#666',
    marginTop: 6,
    fontFamily: 'monospace',
    opacity: 0.8,
  },
});
