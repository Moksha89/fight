import React, {useEffect, useRef, useState} from 'react';
import {View, Text, TouchableOpacity, Animated, StyleSheet} from 'react-native';

export default function DinoGame() {
  const jumpValue = useRef(new Animated.Value(0)).current;
  const [isJumping, setIsJumping] = useState(false);
  const [score, setScore] = useState(0);
  const [obstacleLeft, setObstacleLeft] = useState(300);
  const [gameOver, setGameOver] = useState(false);
  const obstacleAnim = useRef();

  const jump = () => {
    if (isJumping || gameOver) return;
    setIsJumping(true);
    Animated.sequence([
      Animated.timing(jumpValue, {
        toValue: -100,
        duration: 300,
        useNativeDriver: true,
      }),
      Animated.timing(jumpValue, {
        toValue: 0,
        duration: 300,
        useNativeDriver: true,
      }),
    ]).start(() => setIsJumping(false));
  };

  useEffect(() => {
    obstacleAnim.current = setInterval(() => {
      setObstacleLeft(prev => {
        if (gameOver) return prev;
        if (prev <= 0) {
          setScore(score => score + 1);
          return 300;
        }
        return prev - 10;
      });
    }, 50);
    return () => clearInterval(obstacleAnim.current);
  }, [gameOver]);

  useEffect(() => {
    if (obstacleLeft < 40 && !isJumping && !gameOver) {
      setGameOver(true);
    }
  }, [obstacleLeft, isJumping, gameOver]);

  const resetGame = () => {
    setScore(0);
    setObstacleLeft(300);
    setGameOver(false);
  };

  return (
    <View style={styles.gameContainer}>
      <Text style={styles.score}>Score: {score}</Text>
      <View style={styles.gameArea}>
        <Animated.View
          style={[styles.dino, {transform: [{translateY: jumpValue}]}]}
        />
        <View style={[styles.obstacle, {left: obstacleLeft}]} />
      </View>

      <TouchableOpacity
        style={[styles.actionButton, gameOver ? {backgroundColor: '#000'} : {}]}
        onPress={gameOver ? resetGame : jump}>
        <Text style={[styles.buttonText]}>{gameOver ? 'Restart' : 'Jump'}</Text>
      </TouchableOpacity>

      <Text style={[styles.gameOverText, {opacity: gameOver ? 1 : 0}]}>
        💥 Game Over! Final Score: {score}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  gameContainer: {
    alignItems: 'center',
    marginTop: 10,
  },
  score: {
    fontSize: 16,
    fontWeight: 'bold',
    marginBottom: 10,
    color: '#000',
  },
  gameArea: {
    width: 300,
    height: 150,
    backgroundColor: '#f4f4f4',
    overflow: 'hidden',
    position: 'relative',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#ddd',
  },
  dino: {
    width: 30,
    height: 30,
    backgroundColor: '#d4a843',
    position: 'absolute',
    bottom: 0,
    left: 20,
    borderRadius: 4,
    borderRadius: 1000,
  },
  obstacle: {
    width: 10,
    height: 40,
    backgroundColor: '#000',
    position: 'absolute',
    bottom: 0,
    borderRadius: 10,
  },
  actionButton: {
    backgroundColor: '#ff6b00',
    paddingVertical: 12,
    paddingHorizontal: 30,
    borderRadius: 30,
    marginTop: 30,
    elevation: 2,
  },
  buttonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  gameOverText: {
    fontSize: 16,
    marginTop: 15,
    color: '#e74c3c',
    fontWeight: 'bold',
  },
});
