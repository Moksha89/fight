import AsyncStorage from '@react-native-async-storage/async-storage';

export default {
  getItem: async key => {
    try {
      const value = await AsyncStorage.getItem(key);
      return value;
    } catch (error) {
      console.error('Storage Get Error:', error);
    }
  },
  setItem: async (key, value) => {
    await AsyncStorage.setItem(key, value.toString());
  },
  removeItem: async key => {
    try {
      await AsyncStorage.removeItem(key);
    } catch (error) {
      console.error('Storage Remove Error:', error);
    }
  },
};
