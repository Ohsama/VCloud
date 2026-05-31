import "react-native-url-polyfill/auto";
import React from "react";
import { StatusBar } from "expo-status-bar";
import { NavigationContainer, DarkTheme as NavDarkTheme } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import RecordingsScreen from "./src/screens/RecordingsScreen";
import VideoPlayerScreen from "./src/screens/VideoPlayerScreen";

const Stack = createNativeStackNavigator();

const DarkTheme = {
  ...NavDarkTheme,
  colors: {
    ...NavDarkTheme.colors,
    primary: "#6c63ff",
    background: "#0a0a0f",
    card: "#13131a",
    text: "#ffffff",
    border: "#1e1e2e",
  },
};

export default function App() {
  return (
    <NavigationContainer theme={DarkTheme}>
      <StatusBar style="light" />
      <Stack.Navigator screenOptions={{ headerShown: false, contentStyle: { backgroundColor: "#0a0a0f" }, animation: "slide_from_right" }}>
        <Stack.Screen name="Recordings" component={RecordingsScreen} />
        <Stack.Screen name="VideoPlayer" component={VideoPlayerScreen} />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
