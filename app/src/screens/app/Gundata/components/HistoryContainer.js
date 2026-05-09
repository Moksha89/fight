import {StyleSheet, View, ScrollView} from 'react-native';
import React, {useEffect, useState, useRef} from 'react';

import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';

import AppText from '../../../../components/AppText';

export default function HistoryContainer({
  activeChannel,
  autoMatchHistory,
  manualMatchHistory,
}) {
  const historyScrollViewRef = useRef(null);

  const [activeChannelMatchHistory, setActiveChannelMatchHistory] = useState(
    [],
  );

  const rows = 7;
  const teamColorMap = {
    1: '#BA2343', // Red
    2: '#0000FF', // Blue
    3: '#43A048', // Green
    4: '#808080', // Gray (if used)
  };

  function processMatchHistory(results = []) {
    const columns = [];
    let currentColor = null;
    let rowIndex = 0;

    results.forEach(match => {
      const color = teamColorMap[match.winTeam];
      if (!color) return;

      if (color !== currentColor) {
        currentColor = color;
        rowIndex = 0;
        columns.push(new Array(rows).fill(null));
      }

      columns[columns.length - 1][rowIndex] = color;
      rowIndex++;

      // If rowIndex reaches the limit, force next one to start a new column
      if (rowIndex === rows) {
        currentColor = null; // Reset so next will always push new column
      }
    });

    return columns.reverse();
  }

  useEffect(() => {
    if (activeChannel == 0) {
      const struct = processMatchHistory(autoMatchHistory);
      setActiveChannelMatchHistory(struct);
    } else {
      const struct = processMatchHistory(
        manualMatchHistory[activeChannel] || [],
      );
      setActiveChannelMatchHistory(struct);
    }
  }, [activeChannel, autoMatchHistory, manualMatchHistory]);

  return (
    <View style={styles.bettingSection}>
      <View style={styles.bettingResultsSection}>
        <View style={styles.bettinResultLeft}>
          <View style={styles.colorDetails}>
            <View style={styles.bettingColor} />
            <AppText>Meron</AppText>
          </View>
          <View style={styles.colorDetails}>
            <View style={[styles.bettingColor, {backgroundColor: '#43A048'}]} />
            <AppText>Draw</AppText>
          </View>
          <View style={styles.colorDetails}>
            <View style={[styles.bettingColor, {backgroundColor: '#0000FF'}]} />
            <AppText>Wala</AppText>
          </View>
          <View style={styles.colorDetails}>
            <View style={[styles.bettingColor, {backgroundColor: '#bfbfbf'}]} />
            <AppText>Cancle</AppText>
          </View>
        </View>
        <ScrollView
          ref={historyScrollViewRef}
          horizontal
          contentContainerStyle={styles.grid}
          showsHorizontalScrollIndicator={false}
          onLayout={() =>
            historyScrollViewRef.current?.scrollToEnd({animated: false})
          }
          onContentSizeChange={() =>
            historyScrollViewRef.current?.scrollToEnd({animated: true})
          }>
          {activeChannelMatchHistory?.map((column, colIndex) => (
            <View key={colIndex} style={styles.column}>
              {column.map((color, rowIndex) => {
                const isLastRow = rowIndex === rows - 1;
                const isLastColumn =
                  colIndex === activeChannelMatchHistory.length - 1;
                return (
                  <View
                    key={rowIndex}
                    style={[
                      styles.cell,
                      {
                        borderRightWidth: isLastColumn ? 0 : 1,
                        borderBottomWidth: isLastRow ? 0 : 1,
                      },
                    ]}>
                    {color && (
                      <View style={[styles.circle, {borderColor: color}]} />
                    )}
                  </View>
                );
              })}
            </View>
          ))}
        </ScrollView>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  bettingSection: {
    width: wp(100),
    // borderRadius: wp(3),
    overflow: 'hidden',
    position: 'relative',
    marginTop: hp(0.5),
  },
  bettingResultsSection: {
    width: wp(95),
    backgroundColor: '#ffffff',
    marginLeft: wp(2.5),
    marginTop: hp(1),
    paddingHorizontal: wp(3),
    paddingVertical: hp(3),
    flexDirection: 'row',
    borderTopLeftRadius: wp(4),
    borderTopRightRadius: wp(4),
  },
  bettinResultLeft: {
    width: wp(12),
    marginRight: wp(3),
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  colorDetails: {
    alignItems: 'center',
    justifyContent: 'flex-end',
    marginBottom: hp(2),
  },
  bettingColor: {
    width: wp(2),
    height: wp(2),
    borderRadius: '50%',
    backgroundColor: '#BA2343',
    marginBottom: hp(0.5),
  },
  column: {
    flexDirection: 'column',
  },
  cell: {
    width: hp(3),
    height: hp(3),
    borderColor: '#ccc',
    justifyContent: 'center',
    alignItems: 'center',
    borderRightWidth: 1,
    borderBottomWidth: 1,
  },
  circle: {
    width: 12,
    height: 12,
    borderRadius: 15,
    borderWidth: 1,
    backgroundColor: 'transparent',
  },
});
