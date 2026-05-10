import React, {createContext, useContext, useEffect, useState} from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import {baseApiEndpoint} from '../Config/baseEndpoint';

const THEME_STORAGE_KEY = 'kokoroko_theme';

const DEFAULT_COLORS = {
  gold: '#D4A843',
  gold_dark: '#B8922E',
  gold_light: '#f0d78c',
  bg: '#0B0B0B',
  bg_card: '#171717',
  bg_elevated: '#1F1A12',
  bg_surface: '#121212',
  bg_white: '#171717',
  text_primary: '#F5F1E8',
  text_secondary: '#A8A29E',
  text_muted: '#6B6560',
  border: 'rgba(212,168,67,0.18)',
  border_light: 'rgba(212,168,67,0.10)',
  success: '#22C55E',
  danger: '#EF4444',
  warning: '#F59E0B',
  meron: '#DC2626',
  wala: '#2563EB',
  draw: '#A855F7',
};

const ThemeContext = createContext();

export const useTheme = () => useContext(ThemeContext);

export const ThemeProvider = ({children}) => {
  const [colors, setColors] = useState(DEFAULT_COLORS);
  const [themeName, setThemeName] = useState('Gold & Black (Original)');

  useEffect(() => {
    loadTheme();
    const interval = setInterval(fetchTheme, 60000);
    return () => clearInterval(interval);
  }, []);

  const loadTheme = async () => {
    try {
      const cached = await AsyncStorage.getItem(THEME_STORAGE_KEY);
      if (cached) {
        const parsed = JSON.parse(cached);
        setColors({...DEFAULT_COLORS, ...parsed.colors});
        if (parsed.name) setThemeName(parsed.name);
      }
    } catch (e) {}
    fetchTheme();
  };

  const fetchTheme = async () => {
    try {
      const res = await fetch(`${baseApiEndpoint}/admin-api/get-theme/`);
      const data = await res.json();
      if (data && data.colors) {
        setColors({...DEFAULT_COLORS, ...data.colors});
        if (data.name) setThemeName(data.name);
        await AsyncStorage.setItem(
          THEME_STORAGE_KEY,
          JSON.stringify({colors: data.colors, name: data.name}),
        );
      }
    } catch (e) {}
  };

  return (
    <ThemeContext.Provider value={{colors, themeName, refreshTheme: fetchTheme}}>
      {children}
    </ThemeContext.Provider>
  );
};
