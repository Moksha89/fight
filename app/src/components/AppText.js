import {Text} from 'react-native';

export default function AppText({children, style, ...props}) {
  return (
    <Text style={[{color: '#F5F1E8'}, style]} {...props}>
      {children}
    </Text>
  );
}
