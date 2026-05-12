import React, {useState, useEffect} from 'react';
import {
  View,
  Text,
  Image,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  StatusBar,
} from 'react-native';
import FontAwesome6 from 'react-native-vector-icons/FontAwesome6';
import Icon from 'react-native-vector-icons/MaterialIcons';
import Octicons from 'react-native-vector-icons/Octicons';

import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';
import AppScreen from '../../../components/AppScreen';
import AppText from '../../../components/AppText';
import TutorialVideoModal from '../../../components/TutorialVideoModal';
import {fetchHighlights} from '../../../apis/authApi';
import HeaderComponent from '../../../components/HeaderComponent';
const PastMatches = ({navigation}) => {
  const [highlights, setHighlights] = useState([]);
  const [isMatchModalVisible, setMatchModalVisible] = useState(false);
  const [selectedVideo, setSelectedVideo] = useState(null);

  useEffect(() => {
    loadHighlights();
  }, []);

  const loadHighlights = async () => {
    const fetchedHighlights = await fetchHighlights();
    const filteredHighlights = fetchedHighlights.filter(
      highlight => highlight.category == 'C',
    );
    setHighlights(filteredHighlights);
  };

  const handleMatchOpenModal = videoUrl => {
    setSelectedVideo(videoUrl);
    setMatchModalVisible(true);
  };

  const handleMatchCloseModal = () => {
    setSelectedVideo(null);
    setMatchModalVisible(false);
  };

  const renderItem = ({item}) => (
    <TouchableOpacity
      style={styles.card}
      onPress={() => handleMatchOpenModal(item.video)}>
      <Image
        source={{uri: item.thumbnail}}
        style={styles.cardImage}
        resizeMode="cover"
      />
      <View style={styles.imageOverlay} />
      <View style={styles.overlayContent}>
        <Text style={styles.matchText}>{item.title}</Text>
        <Text style={styles.dateText}>
          {new Date(item.updated_at).toLocaleDateString('en-GB')}
        </Text>
      </View>
    </TouchableOpacity>
  );

  return (
    <AppScreen isTranslucent lightStatusBar style={styles.container}>
      {/* Header */}
      <HeaderComponent
        title="Cock Fight highlights"
        onBackPress={() => navigation.goBack()}
        onIconPress={() => navigation.navigate('LiveCockFight')}
        RightIconComponent={
          <>
            <Icon name="play-arrow" size={fp(2.5)} color="#fff" />
            <AppText
              style={{color: '#fff', fontWeight: '500', fontSize: fp(1.7)}}>
              Live
            </AppText>
          </>
        }
        rightIconWrapperStyle={{backgroundColor: '#d4a843', width: wp(20)}}
      />
      {/* Match List */}
      <FlatList
        data={highlights}
        keyExtractor={item => item.id.toString()}
        renderItem={renderItem}
        contentContainerStyle={styles.list}
        showsVerticalScrollIndicator={false}
      />

      {/* Fullscreen Video Modal */}
      <TutorialVideoModal
        visible={isMatchModalVisible}
        onClose={handleMatchCloseModal}
        videoUrl={selectedVideo}
      />
    </AppScreen>
  );
};

export default PastMatches;

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0B0B0B',
    paddingTop: hp(3.5),
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginVertical: hp(2),
  },
  title: {
    fontSize: fp(2),
    fontWeight: '700',
    color: '#F5F1E8',
  },
  liveButton: {
    flexDirection: 'row',
    backgroundColor: '#FF7B00',
    paddingVertical: hp(0.7),
    paddingHorizontal: wp(3),
    borderRadius: wp(2),
    alignItems: 'center',
  },
  list: {
    paddingVertical: hp(3),
    alignItems: 'center',
  },
  card: {
    marginBottom: hp(2),
    borderRadius: wp(3),
    overflow: 'hidden',
    elevation: 3,
    backgroundColor: '#171717',
    width: wp(86),
    height: hp(18),
  },
  cardImage: {
    width: '100%',
    height: '100%',
    borderRadius: wp(3),
  },
  imageOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0,0,0,0.25)',
  },
  overlayContent: {
    position: 'absolute',
    bottom: hp(1.5),
    left: wp(3),
  },
  matchText: {
    color: '#fff',
    fontWeight: '700',
    fontSize: fp(2),
  },
  dateText: {
    color: '#eee',
    fontSize: fp(1.6),
    marginTop: hp(0.3),
  },
});
