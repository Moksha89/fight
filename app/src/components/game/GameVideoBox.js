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
import {useAuth} from '../../context/AuthContext';
import {useTheme} from '../../context/ThemeContext';
import COLORS from '../../context/designTokens';

import Video from 'react-native-video';
import {WebView} from 'react-native-webview';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';

let YoutubePlayer;
try {
  YoutubePlayer = require('react-native-youtube-iframe').default;
} catch (e) {
  YoutubePlayer = null;
}

/**
 * Shared video player box for CockFight and Gundata/Dice.
 *
 * Props:
 *  - gameType: 'cockfight' | 'dice'
 *  - activeChannel
 *  - autoMatchData
 *  - manualMatchData
 *  - musicEnabled / setMusicEnabled
 *  - soundEnabled
 *  - bettingHistory
 *  - showLiveBadge
 *  - manualOnly (dice only — skip auto channel rendering)
 *  - isVirtualBoard (dice only — show dice arena)
 *  - countdownSeconds (dice only)
 *  - commitmentHash (dice only)
 *  - videoHeight — optional override for video container height
 */
function GameVideoBox({
  gameType = 'cockfight',
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
  videoHeight,
}) {
  const navigation = useNavigation();
  const {colors} = useTheme();
  const {settings, wallet} = useAuth();
  const [isLiveEnableToSee, setIsLiveEnableToSee] = useState(true);
  const [showWebView, setShowWebView] = useState(true);
  const [manualLiveMatch, setManualLiveMatch] = useState(null);

  const scaleAnim = useRef(new Animated.Value(0)).current;
  const [isYoutubePlaying, setIsYoutubePlaying] = useState(false);
  const [reloadKey, setReloadKey] = useState(Date.now());
  const hasReloadedRef = useRef(false);
  const reloadTimeoutRef = useRef(null);
  const playerRef = useRef();

  const isDice = gameType === 'dice';

  // Pending bets check (for dice)
  const hasPendingBets = Array.isArray(bettingHistory)
    ? bettingHistory.some(b => b.matchWinStatus === 0)
    : false;

  // Check if user eligible to watch live
  useEffect(() => {
    const timeout = setTimeout(() => {
      const actionValue = parseFloat(settings?.L?.actionValue || '0');
      const balance = parseFloat(wallet?.balance || '0');

      if (isDice) {
        if (balance < actionValue && !hasPendingBets) {
          setIsLiveEnableToSee(false);
        }
      } else {
        if ((balance < actionValue) & !bettingHistory) {
          setIsLiveEnableToSee(false);
        }
      }
    }, 15000);

    return () => clearTimeout(timeout);
  }, [wallet?.balance, settings?.L?.actionValue, hasPendingBets, bettingHistory]);

  // YouTube lag detection (dice only)
  useEffect(() => {
    if (!isDice || !YoutubePlayer) return;
    const interval = setInterval(async () => {
      try {
        const currentTime = await playerRef.current?.getCurrentTime();
        const duration = await playerRef.current?.getDuration();
        if (typeof currentTime === 'number' && typeof duration === 'number') {
          const lag = duration - currentTime;
          if (lag > 15000) {
            await playerRef.current.seekTo(duration, true);
          }
        }
      } catch (err) {
        // ignore
      }
    }, 10000);
    return () => clearInterval(interval);
  }, [isDice]);

  const handleYoutubeStateChange = state => {
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
        setReloadKey(Date.now());
        setTimeout(() => {
          hasReloadedRef.current = false;
        }, 1500);
      }, 500);
    }
  };

  useEffect(() => {
    return () => {
      if (reloadTimeoutRef.current) clearTimeout(reloadTimeoutRef.current);
    };
  }, []);

  const handleRefresh = () => {
    setShowWebView(false);
    setTimeout(() => setShowWebView(true), 100);
  };

  // Find manual live match
  useEffect(() => {
    if (isDice) {
      if (manualMatchData?.[activeChannel]) {
        const liveMatch = manualMatchData[activeChannel].find(m => m.isLive);
        setManualLiveMatch(liveMatch || null);
      } else {
        setManualLiveMatch(null);
      }
    } else {
      if (activeChannel !== 0 && manualMatchData?.[activeChannel]) {
        const liveMatch = manualMatchData[activeChannel].find(m => m.isLive);
        setManualLiveMatch(liveMatch || null);
      } else {
        setManualLiveMatch(null);
      }
    }
  }, [manualMatchData, activeChannel, isDice]);

  const getYoutubeVideoId = link => {
    if (!link || typeof link !== 'string') return null;
    const trimmed = link.trim();
    if (!trimmed) return null;
    if (!trimmed.includes('/') && !trimmed.includes('?')) return trimmed;
    const vMatch = trimmed.match(/(?:v=|\/)([a-zA-Z0-9_-]{11})(?:\?|&|$)/);
    return vMatch ? vMatch[1] : trimmed;
  };

  const youtubeVideoId = getYoutubeVideoId(manualLiveMatch?.youtubeLiveLink);

  const isVideoStream = url => {
    if (!url) return false;
    const videoExtensions = ['.m3u8', '.mp4', '.webm', '.mov'];
    const lowerUrl = url.toLowerCase().split('?')[0];
    return videoExtensions.some(ext => lowerUrl.includes(ext));
  };

  // Auto match music logic (cockfight only)
  useEffect(() => {
    if (isDice) return;
    if (
      showWebView &&
      activeChannel == 0 &&
      !isVideoStream(autoMatchData?.liveUrl)
    ) {
      setMusicEnabled(true);
    } else {
      setMusicEnabled(false);
    }
  }, [showWebView, autoMatchData?.liveUrl, activeChannel, isDice]);

  // Splash animation
  useEffect(() => {
    if (isDice) {
      const videoId = manualLiveMatch?.youtubeLiveLink;
      if (!videoId) return;
      setIsYoutubePlaying(false);
      scaleAnim.setValue(0);
      Animated.timing(scaleAnim, {
        toValue: 0.6,
        duration: 600,
        useNativeDriver: true,
      }).start();
    } else {
      if (!manualLiveMatch?.youtubeLiveLink) {
        scaleAnim.setValue(0);
        Animated.timing(scaleAnim, {
          toValue: 0.6,
          duration: 600,
          useNativeDriver: true,
        }).start();
      }
    }
  }, [reloadKey, manualLiveMatch?.youtubeLiveLink, isDice]);

  const containerHeight = videoHeight || (isDice ? wp(57) : wp(42));

  // Not eligible to watch live
  if (!isLiveEnableToSee)
    return (
      <TouchableHighlight
        style={[styles.videoContainer, {height: containerHeight}]}
        onPress={() => navigation.navigate('DepositWithdrawl')}>
        <View>
          <ActivityIndicator
            size="small"
            color="#fff"
            style={{zIndex: 999, marginTop: 10, position: 'absolute', left: 0, top: 0}}
          />
          <Image
            source={require('../../assets/images/walletDown.png')}
            style={{width: '100%', height: '100%'}}
          />
        </View>
      </TouchableHighlight>
    );

  // Virtual board (dice only)
  if (isDice && isVirtualBoard) {
    const isUrgent = countdownSeconds > 0 && countdownSeconds <= 5;
    return (
      <View style={[styles.videoContainer, {height: containerHeight, backgroundColor: COLORS.bg_surface}]}>
        <View style={styles.virtualArena}>
          {countdownSeconds > 0 ? (
            <View style={styles.virtualCountdown}>
              <Text
                style={[
                  styles.virtualCountdownText,
                  {color: colors.gold},
                  isUrgent && {color: colors.meron},
                ]}>
                {countdownSeconds}s
              </Text>
              <Text style={styles.virtualSubtext}>until dice roll</Text>
            </View>
          ) : (
            <View style={styles.virtualCountdown}>
              <Icon name="dice-multiple" size={28} color={colors.gold} />
              <Text style={[styles.virtualSubtext, {marginTop: 4}]}>
                Rolling dice...
              </Text>
            </View>
          )}
          <Text style={styles.virtualDiceIcon}>🎲</Text>
          <Text style={[styles.virtualTitle, {color: colors.gold}]}>VIRTUAL DICE</Text>
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

  const showManualContent = isDice ? (manualOnly || activeChannel != 0) : activeChannel != 0;

  // RENDER: Auto match (cockfight channel 0)
  const renderAutoMatch = () => (
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
            source={require('../../assets/images/liveDown.png')}
          />
        )
      ) : (
        <Image
          style={{width: '100%', height: '100%'}}
          source={require('../../assets/images/liveDown.png')}
        />
      )}
      {showLiveBadge && <Text style={styles.liveBadge}>Live</Text>}
      <TouchableOpacity style={[styles.refreshBtn, {backgroundColor: colors.card}]} onPress={handleRefresh}>
        <Icon name="refresh" size={30} color={colors.gold} />
      </TouchableOpacity>
    </View>
  );

  // RENDER: Manual match — cockfight uses WebView, dice uses YouTube
  const renderManualMatch = () => {
    if (isDice && YoutubePlayer) {
      // Dice: YouTube player
      return (
        <View style={{flex: 1}}>
          {manualLiveMatch && youtubeVideoId && settings['#']?.actionValue != 'N' ? (
            <View style={{flex: 1}}>
              {!isYoutubePlaying && (
                <View style={styles.splashContainer}>
                  <Animated.Image
                    source={require('../../assets/logos/logo.png')}
                    style={[styles.logo, {transform: [{scale: scaleAnim}]}]}
                    resizeMode="contain"
                  />
                  <View style={styles.loadingContainer}>
                    <Text style={styles.loadingText}>Loading Stream...</Text>
                    <ActivityIndicator size="small" color="#fff" style={{marginTop: 10}} />
                  </View>
                </View>
              )}
              <View style={{flex: 1}} pointerEvents={'none'}>
                <YoutubePlayer
                  ref={playerRef}
                  key={reloadKey}
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
              source={require('../../assets/images/liveDown.png')}
              style={{width: '100%', height: '100%'}}
            />
          )}
          {showLiveBadge && manualLiveMatch && <Text style={styles.liveBadge}>Live</Text>}
          <TouchableOpacity style={[styles.refreshBtn, {backgroundColor: colors.card}]} onPress={handleRefresh}>
            <Icon name="refresh" size={30} color={colors.gold} />
          </TouchableOpacity>
        </View>
      );
    }

    // Cockfight: WebView-based manual match
    return (
      <View style={{flex: 1}}>
        {manualLiveMatch && settings['B']?.actionValue != 'Y' ? (
          <View style={{flex: 1}}>
            {!manualLiveMatch.youtubeLiveLink ? (
              <View style={styles.splashContainer}>
                <Animated.Image
                  source={require('../../assets/logos/logo.png')}
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
                source={require('../../assets/images/liveDown.png')}
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
            source={require('../../assets/images/liveDown.png')}
            style={{width: '100%', height: '100%'}}
          />
        )}
        {showLiveBadge && <Text style={styles.liveBadge}>Live</Text>}
        <TouchableOpacity style={[styles.refreshBtn, {backgroundColor: colors.card}]} onPress={handleRefresh}>
          <Icon name="refresh" size={30} color={colors.gold} />
        </TouchableOpacity>
      </View>
    );
  };

  return (
    <View style={[styles.videoContainer, {height: containerHeight}]}>
      {showManualContent ? renderManualMatch() : renderAutoMatch()}
    </View>
  );
}

export default GameVideoBox;

const styles = StyleSheet.create({
  videoContainer: {
    position: 'relative',
    width: wp(100),
    display: 'flex',
    justifyContent: 'center',
  },
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
    color: COLORS.text_primary,
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
  },
  virtualSubtext: {
    fontSize: fp(1.4),
    color: COLORS.text_muted,
  },
  virtualDiceIcon: {
    fontSize: 48,
  },
  virtualTitle: {
    fontSize: fp(2.2),
    fontWeight: '800',
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
    color: COLORS.success,
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 1,
  },
  hashDisplay: {
    fontSize: 9,
    color: COLORS.text_muted,
    marginTop: 6,
    fontFamily: 'monospace',
    opacity: 0.8,
  },
});
