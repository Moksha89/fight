import AsyncStorage from '@react-native-async-storage/async-storage';

export default {
  getItem: async key => {
    try {
      const value = await AsyncStorage.getItem(key);
      return value;
    } catch (error) {
      console.error('Storage Get Error:', error);
      return null;
    }
  },
  setItem: async (key, value) => {
    try {
      if (value == null) {
        await AsyncStorage.removeItem(key);
        return;
      }
      await AsyncStorage.setItem(key, String(value));
    } catch (error) {
      console.error('Storage Set Error:', error);
    }
  },
  removeItem: async key => {
    try {
      await AsyncStorage.removeItem(key);
    } catch (error) {
      console.error('Storage Remove Error:', error);
    }
  },
};
