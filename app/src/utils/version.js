import {Platform} from 'react-native';

let versionCode = 2;

try {
  const packageInfo = require('../../package.json');
  if (packageInfo.versionCode) {
    versionCode = packageInfo.versionCode;
  }
} catch (_) {}

export function getVersionCode() {
  return versionCode;
}

export function getVersionName() {
  try {
    const packageInfo = require('../../package.json');
    return packageInfo.version || '2.0.0';
  } catch (_) {
    return '2.0.0';
  }
}
