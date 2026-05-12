import React, {useState, useEffect} from 'react';
import {
  View,
  StyleSheet,
  Image,
  FlatList,
  TouchableOpacity,
  TextInput,
  Alert,
} from 'react-native';
import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';
import HeaderComponent from '../../../components/HeaderComponent';
import AppScreen from '../../../components/AppScreen';
import AppText from '../../../components/AppText';
import Octicons from 'react-native-vector-icons/Octicons';
import Modal from 'react-native-modal';
import MaterialIcons from 'react-native-vector-icons/MaterialIcons';
import {fetchLearningData} from '../../../apis/appApi';
import TutorialVideoModal from '../../../components/TutorialVideoModal';

const LearningSchoolScreen = ({navigation}) => {
  const [learningData, setLearningData] = useState([]);
  const [selectedVideoUrl, setSelectedVideoUrl] = useState(null);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [isLanguageModalVisible, setLanguageModalVisible] = useState(false);
  const [selectedLanguage, setSelectedLanguage] = useState('Telugu');
  const [searchText, setSearchText] = useState('');

  const [languages, setLanguages] = useState(['All']);

  useEffect(() => {
    const getLearningData = async () => {
      const data = await fetchLearningData();
      setLearningData(data);
      uniqueLanguages = [...new Set(data.map(item => item.language))];
      setLanguages(['All'].concat(uniqueLanguages));
    };
    getLearningData();
  }, []);

  const openVideoModal = videoUrl => {
    setSelectedVideoUrl(videoUrl);
    setIsModalVisible(true);
  };

  const closeVideoModal = () => {
    setSelectedVideoUrl(null);
    setIsModalVisible(false);
  };

  const toggleModal = () => setLanguageModalVisible(!isLanguageModalVisible);

  const selectLanguage = lang => {
    setSelectedLanguage(lang);
    toggleModal();
  };

  const renderItem = ({item}) => (
    <TouchableOpacity
      onPress={() => openVideoModal(item.video)}
      style={styles.card}>
      <Image source={{uri: item.thumbnail}} style={styles.cardImage} />
      <View style={styles.durationTag}>
        {/* <AppText style={styles.durationText}>{'30:04'}</AppText> */}
      </View>
      <View style={styles.cardBody}>
        <View style={styles.languageTextDiv}>
          <Image source={require('../../../assets/icons/fontstyle.png')} />
          <AppText style={styles.languageTag}>{item.language}</AppText>
        </View>
        <AppText style={styles.cardTitle}>{item.title}</AppText>
      </View>
    </TouchableOpacity>
  );

  // Combined Filter for Language + Search
  const filteredData = learningData.filter(item => {
    const matchesLanguage =
      selectedLanguage === 'All' || item.language === selectedLanguage;
    const matchesSearch = item.title
      .toLowerCase()
      .includes(searchText.toLowerCase());
    return matchesLanguage && matchesSearch;
  });

  return (
    <AppScreen isTranslucent lightStatusBar style={styles.container}>
      {/* Header */}
      <HeaderComponent
        title="LEARNING SCHOOL"
        onBackPress={() => navigation.goBack()}
        onIconPress={() => navigation.navigate('HomeScreen')}
        RightIconComponent={<Octicons name="home" size={17} color="#ffffff" />}
        rightIconWrapperStyle={{backgroundColor: '#d4a843'}}
      />

      {/* Search & Language */}
      <View style={styles.searchRow}>
        <Octicons
          name="search"
          size={18}
          color="#888"
          style={styles.searchIcon}
        />
        <TextInput
          placeholder="Find topics"
          placeholderTextColor="#888"
          style={styles.searchInput}
          value={searchText}
          onChangeText={text => setSearchText(text)}
        />
        <TouchableOpacity style={styles.languageButton} onPress={toggleModal}>
          <View style={styles.languageWrapper}>
            <AppText style={styles.languageText}>{selectedLanguage}</AppText>
            <MaterialIcons name="arrow-drop-down" size={20} color="#A8A29E" />
          </View>
        </TouchableOpacity>

        {/* Language Modal */}
        <Modal isVisible={isLanguageModalVisible} onBackdropPress={toggleModal}>
          <View style={styles.modalContent}>
            {languages.map(lang => (
              <TouchableOpacity
                key={lang}
                style={styles.option}
                onPress={() => selectLanguage(lang)}>
                <AppText style={styles.optionText}>{lang}</AppText>
              </TouchableOpacity>
            ))}
          </View>
        </Modal>
      </View>

      {/* Title */}
      <AppText style={styles.mainTitle}>Learn how to use app?</AppText>

      {/* Video List */}
      <View style={{paddingHorizontal: wp(7)}}>
        <FlatList
          data={filteredData}
          keyExtractor={item => item.id.toString()}
          renderItem={renderItem}
          numColumns={2}
          columnWrapperStyle={styles.gridContainer}
          contentContainerStyle={{paddingBottom: 20}}
          ListEmptyComponent={
            <AppText
              style={{textAlign: 'center', marginTop: 20, color: '#999'}}>
              No videos found
            </AppText>
          }
        />
      </View>

      {/* Video Modal */}
      {selectedVideoUrl && (
        <TutorialVideoModal
          visible={isModalVisible}
          onClose={closeVideoModal}
          videoUrl={selectedVideoUrl}
        />
      )}
    </AppScreen>
  );
};

export default LearningSchoolScreen;

const styles = StyleSheet.create({
  container: {
    // paddingHorizontal: wp(7),
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  backArrow: {
    fontSize: 22,
  },
  headerTitle: {
    fontSize: 16,
    fontWeight: 'bold',
  },
  homeButton: {
    backgroundColor: 'orange',
    padding: 8,
    borderRadius: 10,
  },
  homeIcon: {
    fontSize: 18,
  },
  searchRow: {
    flexDirection: 'row',
    marginTop: 20,
    marginBottom: 20,
    position: 'relative',
    paddingHorizontal: wp(7),
  },
  searchIcon: {
    position: 'absolute',
    zIndex: 20,
    left: wp(10),
    bottom: hp(1.3),
  },
  searchInput: {
    flex: 1,
    backgroundColor: '#171717', // Needed for elevation to cast shadow
    borderRadius: 50,
    paddingLeft: wp(10),
    paddingVertical: 12,
    fontSize: 14,
    elevation: 5, // Higher value for more prominent shadow
    shadowColor: '#000',
    shadowOffset: {width: 0, height: 2},
    shadowOpacity: 0.1,
    shadowRadius: 3.84,
  },
  languageButton: {
    marginLeft: 10,
    backgroundColor: '#2a2a2a',
    borderRadius: 30,
    paddingHorizontal: 15,
    justifyContent: 'center',
  },
  languageWrapper: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  languageText: {
    fontSize: 14,
  },
  mainTitle: {
    fontSize: fp(2),
    marginBottom: hp(3),
    marginTop: hp(2),
    marginLeft: wp(7),
  },
  gridContainer: {
    justifyContent: 'space-between',
  },
  card: {
    width: '48%',
    backgroundColor: '#171717',
    borderRadius: 10,
    marginBottom: 15,
    overflow: 'hidden',
    elevation: 3,
  },
  cardImage: {
    width: '100%',
    height: 60,
    resizeMode: 'cover',
    objectFit: 'cover',
    borderRadius: 10,
  },
  durationTag: {
    position: 'absolute',
    bottom: hp(10),
    right: wp(2),
    backgroundColor: '#000',
    paddingVertical: 2,
    paddingHorizontal: 6,
    borderRadius: 4,
  },
  durationText: {
    color: '#fff',
    fontSize: 12,
  },
  cardBody: {
    padding: 10,
  },
  languageTextDiv: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#5856D633',
    width: wp(17),
    paddingHorizontal: wp(2),
    justifyContent: 'space-between',
    borderRadius: wp(0.5),
    marginBottom: hp(1.5),
    marginTop: hp(1),
  },
  languageTag: {
    color: '#5856D6',
    fontSize: 12,
    marginBottom: 4,
  },
  cardTitle: {
    fontSize: 14,
    color: '#F5F1E8',
  },
  modalContent: {
    backgroundColor: '#171717',
    paddingVertical: 10,
    borderRadius: 10,
  },
  option: {
    padding: 15,
    borderBottomColor: '#DDD',
    borderBottomWidth: 1,
  },
  optionText: {
    fontSize: 16,
  },
});
