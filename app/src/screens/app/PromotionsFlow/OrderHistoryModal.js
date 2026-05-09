import React, {useState, useEffect} from 'react';
import {
  View,
  Modal,
  FlatList,
  Image,
  ActivityIndicator,
  StyleSheet,
} from 'react-native';

import {getOrderHistory} from '../../../apis/appApi';
import HeaderComponent from '../../../components/HeaderComponent';

import AppText from '../../../components/AppText';

const OrderHistoryModal = ({visible, onClose}) => {
  const [historyData, setHistoryData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  useEffect(() => {
    if (visible) {
      fetchHistory();
    }
  }, [visible]);

  const fetchHistory = async () => {
    setLoading(true);
    setErrorMsg('');
    const result = await getOrderHistory();
    setLoading(false);

    if (result.success) {
      setHistoryData(result.data);
    } else {
      setErrorMsg('Failed to load purchase history.');
      setHistoryData([]);
    }
  };

  const renderItem = ({item}) => (
    <View style={styles.historyItem}>
      <Image source={{uri: item.product_image}} style={styles.historyImage} />
      <View style={{flex: 1, marginLeft: 10}}>
        <AppText style={styles.historyTitle}>{item.product_title}</AppText>
        <AppText style={styles.historyDate}>
          Ordered on: {new Date(item.created_at).toLocaleDateString()}
        </AppText>

        <AppText style={{marginTop: 5, fontWeight: 'bold'}}>
          Status: {item.status_display}
        </AppText>

        {item.status === 'P' && (
          <View style={styles.progressContainer}>
            <View style={styles.progressBar}>
              <View style={styles.progressFill} />
            </View>
          </View>
        )}
      </View>
    </View>
  );

  return (
    <Modal visible={visible} animationType="slide">
      <View style={styles.modalContainer}>
        <HeaderComponent
          hideRightIcon={false}
          title="PURCHASE HISTORY"
          onBackPress={onClose}
          containerStyle={styles.historyHeader}
        />
        {loading && (
          <ActivityIndicator
            size="large"
            color="#007bff"
            style={{marginTop: 20}}
          />
        )}

        {errorMsg !== '' && (
          <AppText
            style={{color: 'red', textAlign: 'center', marginVertical: 20}}>
            {errorMsg}
          </AppText>
        )}

        {!loading && !errorMsg && (
          <FlatList
            data={historyData}
            keyExtractor={item => item.id.toString()}
            renderItem={renderItem}
            ListEmptyComponent={() => (
              <AppText style={{textAlign: 'center', marginTop: 30}}>
                No purchase history found.
              </AppText>
            )}
            showsVerticalScrollIndicator={false}
          />
        )}
      </View>
    </Modal>
  );
};

const styles = StyleSheet.create({
  modalContainer: {flex: 1, padding: 20, backgroundColor: '#fff'},

  closeButtonText: {color: 'white', fontWeight: 'bold'},
  historyItem: {
    flexDirection: 'row',
    marginVertical: 10,
    padding: 10,
    backgroundColor: '#f2f2f2',
    borderRadius: 6,
  },
  historyImage: {width: 60, height: 60, borderRadius: 6},
  historyTitle: {fontSize: 16, fontWeight: 'bold'},
  historyDate: {fontSize: 12, color: 'gray', marginTop: 4},
  deliveryText: {fontSize: 13, marginTop: 2},
  progressContainer: {
    marginTop: 8,
    marginBottom: 5,
  },
  progressBar: {
    width: '100%',
    height: 6,
    backgroundColor: '#ddd',
    borderRadius: 3,
    overflow: 'hidden',
  },
  progressFill: {
    width: '50%', // Half filled
    height: '100%',
    backgroundColor: '#d4a843',
  },
  progressText: {
    fontSize: 12,
    color: 'gray',
    marginTop: 4,
  },
});

export default OrderHistoryModal;
