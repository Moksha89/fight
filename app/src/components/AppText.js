import {Text} from 'react-native';

export default function AppText({children, style, ...props}) {
  return (
    <Text style={[style]} {...props}>
      {children}
    </Text>
  );
}
