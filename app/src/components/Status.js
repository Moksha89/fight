import React, {useState, useEffect, useRef, useMemo} from 'react';
import {
  View,
  Image,
  TouchableOpacity,
  StyleSheet,
  Dimensions,
  Share,
  ActivityIndicator,
  Modal,
  Linking,
} from 'react-native';

import storage from '../utils/storage';

import {useAuth} from '../context/AuthContext';

import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';

import AntDesignIcon from 'react-native-vector-icons/AntDesign';

import AppText from '../components/AppText';
import AppScreen from '../components/AppScreen';
import Video from 'react-native-video';

import {fetchStatuses} from '../apis/authApi';

const {width: screenWidth, height: screenHeight} = Dimensions.get('window');

const CATEGORY_CONFIG = {
  Y: {
    label: 'Tutorials',
    icon: require('../assets/logos/logo.png'),
  },
  F: {
    label: 'Cockfight',
    icon: require('../assets/icons/gameCockFight.png'),
  },
  D: {
    label: 'Dice Play',
    icon: require('../assets/icons/gundata.png'),
  },
  C: {
    label: 'Cricket',
    icon: require('../assets/icons/cricketOutline.png'),
  },
};

const StoryMediaItem = ({item, onLoad, onError, onEnd, paused}) => {
  if (!item || !item.url) {
    return <AppText style={styles.errorText}>Invalid media item</AppText>;
  }

  if (item.type === 'image') {
    return (
      <Image
        source={{uri: item.url}}
        style={styles.storyMedia}
        resizeMode="contain"
        onLoadEnd={onLoad}
        onError={onError}
      />
    );
  } else if (item.type === 'video') {
    return (
      <Video
        source={{uri: item.url}}
        style={styles.storyMedia}
        resizeMode="contain"
        paused={paused}
        onLoad={onLoad}
        onError={onError}
        onEnd={onEnd}
        repeat={false}
        muted={false}
        playInBackground={false}
        playWhenInactive={false}
        ignoreSilentSwitch="ignore"
      />
    );
  }

  return (
    <AppText style={styles.errorText}>
      Unsupported story type: {item.type}
    </AppText>
  );
};

const CategoryProgressBars = ({stories, currentId, progress}) => {
  const currentIndex = stories.findIndex(s => s.id === currentId);
  return (
    <View style={styles.categoryProgressBarContainer}>
      {stories.map((story, i) => {
        let width = 0;
        if (i < currentIndex) width = 1;
        else if (i === currentIndex) width = progress;
        return (
          <View key={story.id || i} style={styles.segmentContainer}>
            <View
              style={[styles.segmentProgressBar, {width: `${width * 100}%`}]}
            />
          </View>
        );
      })}
    </View>
  );
};

const StoryPlayer = ({category, stories, startIndex, onClose}) => {
  const [currentIndex, setCurrentIndex] = useState(startIndex);
  const [isPaused, setIsPaused] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [progress, setProgress] = useState(0);
  const [liked, setLiked] = useState(false);
  const animationRef = useRef(null);
  const story = stories[currentIndex];

  useEffect(() => {
    setIsLoading(true);
    setProgress(0);
    setLiked(false);
    setIsPaused(false);
    if (animationRef.current) cancelAnimationFrame(animationRef.current);
  }, [story?.id]);

  useEffect(() => {
    if (!isPaused && !isLoading && story?.duration > 0) {
      const startTime = Date.now();
      const animate = () => {
        const elapsed = Date.now() - startTime;
        const p = Math.min(elapsed / story.duration, 1);
        setProgress(p);
        if (p < 1) animationRef.current = requestAnimationFrame(animate);
        else handleNext();
      };
      animationRef.current = requestAnimationFrame(animate);
    }
    return () => {
      if (animationRef.current) cancelAnimationFrame(animationRef.current);
    };
  }, [isPaused, isLoading, story?.id]);

  const handleLoad = () => setIsLoading(false);
  const handleError = () => {
    console.warn('Media error:', story.url);
    setIsLoading(false);
    setTimeout(handleNext, 500);
  };
  const togglePause = () => setIsPaused(prev => !prev);
  const toggleLike = () => setLiked(prev => !prev);
  const handleShare = async () => {
    try {
      await Share.share({
        message: `Lets' play together download RoosterRun app at : https://roosterrun.io`,
      });
    } catch (err) {
      console.warn('Share failed:', err.message);
    }
  };

  const handleNext = () => {
    if (currentIndex < stories.length - 1) setCurrentIndex(prev => prev + 1);
    else onClose();
  };

  const handlePrev = () => {
    if (currentIndex > 0) setCurrentIndex(prev => prev - 1);
  };

  return (
    <AppScreen style={styles.modalContainer}>
      <CategoryProgressBars
        stories={stories}
        currentId={story.id}
        progress={progress}
      />
      <TouchableOpacity onPress={onClose} style={styles.closeButton}>
        <AppText style={styles.closeButtonText}>✕</AppText>
      </TouchableOpacity>
      <View style={styles.contentArea}>
        {isLoading && <ActivityIndicator color="#FFF" />}
        <StoryMediaItem
          item={story}
          paused={isPaused || isLoading}
          onLoad={handleLoad}
          onError={handleError}
          onEnd={() => {}}
        />
      </View>
      <View style={styles.labelContainer}>
        <AppText style={styles.labelText}>
          {CATEGORY_CONFIG[story.category].label}
        </AppText>
      </View>
      <View style={styles.interactionZones}>
        <TouchableOpacity style={styles.tapZone} onPress={handlePrev} />
        <TouchableOpacity style={styles.tapZone} onPress={togglePause} />
        <TouchableOpacity style={styles.tapZone} onPress={handleNext} />
      </View>
      <View style={styles.bottomActions}>
        <TouchableOpacity onPress={toggleLike} style={styles.actionButton}>
          <AntDesignIcon
            name="heart"
            size={24}
            color={liked ? 'red' : 'white'}
          />
        </TouchableOpacity>
        <TouchableOpacity onPress={handleShare} style={styles.actionButton}>
          <AntDesignIcon name="sharealt" size={24} color="white" />
        </TouchableOpacity>
      </View>
    </AppScreen>
  );
};

const StatusScreen = () => {
  const [stories, setStories] = useState([]);
  const [activeCategory, setActiveCategory] = useState(null);
  const [modalVisible, setModalVisible] = useState(false);
  const [watchedCategories, setWatchedCategories] = useState([]);
  const {settings} = useAuth();

  useEffect(() => {
    const loadInitialData = async () => {
      try {
        const watched = await storage.getItem('watchedCategories');
        if (watched) setWatchedCategories(JSON.parse(watched));
      } catch (err) {
        console.warn('Failed to load watchedCategories:', err.message);
      }
    };
    loadInitialData();
  }, []);

  useEffect(() => {
    const loadStories = async () => {
      try {
        const response = await fetchStatuses();
        const parsed = response.map(item => ({
          id: item.id.toString(),
          category: item.category,
          url: item.status,
          duration: item.status.endsWith('.mp4') ? 10000 : 5000,
          type: item.status.endsWith('.mp4') ? 'video' : 'image',
        }));
        setStories(parsed);
      } catch (err) {
        console.warn('Failed to load statuses:', err.message);
      }
    };
    loadStories();
  }, []);

  const groupedStories = useMemo(() => {
    const map = {F: [], D: [], C: []};
    stories.forEach(s => map[s.category]?.push(s));
    return map;
  }, [stories]);

  const openModal = async category => {
    const updated = [...new Set([...watchedCategories, category])];
    setWatchedCategories(updated);
    await storage.setItem('watchedCategories', JSON.stringify(updated));

    setActiveCategory(category);
    setModalVisible(true);
  };

  return (
    <View>
      <View style={styles.categoryRow}>
        {Object.entries(CATEGORY_CONFIG).map(([key, {label, icon}]) => {
          const isWatched = watchedCategories.includes(key);
          const borderColor = isWatched ? '#bfbfbf' : 'orange';

          const content = (
            <View style={styles.categoryItemContainer}>
              <View
                style={[styles.circle, {borderColor, borderWidth: wp(0.5)}]}>
                <Image source={icon} style={styles.categoryImage} />
              </View>
              <AppText style={styles.categoryLabel}>{label}</AppText>
            </View>
          );

          return key === 'Y' ? (
            <TouchableOpacity
              key={key}
              onPress={() => Linking.openURL(settings['G']?.actionValue)}
              activeOpacity={0.7}>
              {content}
            </TouchableOpacity>
          ) : (
            <TouchableOpacity
              key={key}
              onPress={() => openModal(key)}
              activeOpacity={0.7}>
              {content}
            </TouchableOpacity>
          );
        })}
      </View>

      {modalVisible &&
        activeCategory &&
        groupedStories[activeCategory]?.length > 0 && (
          <Modal
            visible={modalVisible}
            onRequestClose={() => setModalVisible(false)}>
            <StoryPlayer
              category={activeCategory}
              stories={groupedStories[activeCategory]}
              startIndex={0}
              onClose={() => setModalVisible(false)}
            />
          </Modal>
        )}
    </View>
  );
};

export default StatusScreen;

const styles = StyleSheet.create({
  container: {position: 'relative'},
  categoryRow: {
    flexDirection: 'row',
    alignItems: 'center',
    width: wp(65),
    justifyContent: 'space-between',
    height: hp(8),
  },
  categoryItemContainer: {
    alignItems: 'center',
    marginRight: wp(2.5),
    // backgroundColor: '#ffcc00',
    height: hp(8),
    width: wp(13),
  },
  circle: {
    width: wp(13),
    height: wp(13),
    borderRadius: 50,
    borderWidth: wp(1),
    borderColor: '#ffa53f',
    justifyContent: 'center',
    alignItems: 'center',
    overflow: 'hidden',
  },
  categoryImage: {
    width: '90%',
    height: '90%',
    resizeMode: 'cover',
    // backgroundColor: '#ffcc00',
  },
  categoryLabel: {
    marginTop: 4,
    fontSize: 10,
    color: '#555',
    textAlign: 'center',
  },

  //===================== story Palyer =======================
  modalContainer: {
    flex: 1,
    backgroundColor: 'black',
  },
  closeButton: {
    position: 'absolute',
    right: 15,
    padding: 10,
    zIndex: 30,
  },
  closeButtonText: {
    fontSize: 24,
    color: 'white',
    fontWeight: 'bold',
    textShadowColor: 'rgba(0, 0, 0, 0.6)',
    textShadowOffset: {width: 0, height: 1},
    textShadowRadius: 3,
    position: 'absolute',
    right: wp(3),
    top: hp(2),
  },
  contentArea: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loader: {
    position: 'absolute',
    alignSelf: 'center',
    top: '50%',
    zIndex: 10,
  },
  labelContainer: {
    position: 'absolute',
    width: '100%',
    alignItems: 'center',
    padding: 10,
    zIndex: 20,
  },
  labelText: {
    color: 'white',
    fontSize: fp(2),
    fontWeight: 'bold',
    textAlign: 'center',
    textShadowColor: 'rgba(0, 0, 0, 0.7)',
    textShadowOffset: {width: 0, height: 1},
    textShadowRadius: 3,
    position: 'absolute',
    left: wp(3),
    top: hp(3),
  },
  interactionZones: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    flexDirection: 'row',
    zIndex: 5,
  },
  tapZone: {
    flex: 1,
    height: '100%',
  },
  bottomActions: {
    position: 'absolute',
    bottom: hp(4),
    right: wp(5),
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 40,
    zIndex: 30,
  },
  actionButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },

  //===================== CategoryProgressBars =======================

  categoryProgressBarContainer: {
    position: 'absolute',
    left: 10,
    right: 10,
    flexDirection: 'row',
    height: 3.5,
    zIndex: 20,
    gap: 4,
  },
  segmentContainer: {
    flex: 1,
    height: '100%',
    backgroundColor: 'rgba(255,255,255,0.35)',
    borderRadius: 2,
    overflow: 'hidden',
  },
  segmentProgressBar: {
    height: '100%',
    backgroundColor: 'white',
    borderRadius: 2,
  },

  //===================== StoryMediaItem =======================

  storyMedia: {
    width: screenWidth,
    height: screenHeight,
  },
  errorText: {
    color: 'red',
    fontSize: 16,
    textAlign: 'center',
    padding: 20,
    backgroundColor: 'rgba(0,0,0,0.5)',
  },
});
