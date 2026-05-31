import React from "react";
import { View, Text, Pressable, StyleSheet } from "react-native";

export default function RecordingCard({ recording, onPress }) {
  const start = new Date(recording.start_time);
  const end = new Date(recording.end_time);
  const mins = Math.floor((end - start) / 60000);
  const secs = Math.floor(((end - start) % 60000) / 1000);
  const dur = mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;

  return (
    <Pressable onPress={onPress} style={({ pressed }) => [s.card, pressed && s.pressed]}>
      <View style={s.bar} />
      <View style={s.body}>
        <View style={s.row}>
          <View style={s.cam}>
            <Text style={s.camIcon}>📹</Text>
            <Text style={s.camName}>{recording.camera_name}</Text>
          </View>
          <View style={s.badge}><Text style={s.badgeText}>{dur}</Text></View>
        </View>
        <Text style={s.time}>
          {start.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
          {" • "}
          {start.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false })}
        </Text>
      </View>
      <View style={s.btn}><Text style={s.play}>▶</Text></View>
    </Pressable>
  );
}

const s = StyleSheet.create({
  card: { flexDirection: "row", alignItems: "center", backgroundColor: "#13131a", borderRadius: 14, marginHorizontal: 16, marginBottom: 12, overflow: "hidden", borderWidth: 1, borderColor: "#1e1e2e" },
  pressed: { opacity: 0.7, transform: [{ scale: 0.98 }] },
  bar: { width: 4, alignSelf: "stretch", backgroundColor: "#6c63ff" },
  body: { flex: 1, paddingVertical: 16, paddingHorizontal: 14 },
  row: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 8 },
  cam: { flexDirection: "row", alignItems: "center" },
  camIcon: { fontSize: 16, marginRight: 8 },
  camName: { color: "#fff", fontSize: 16, fontWeight: "600" },
  badge: { backgroundColor: "#6c63ff20", paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 },
  badgeText: { color: "#6c63ff", fontSize: 12, fontWeight: "700" },
  time: { color: "#8888aa", fontSize: 13 },
  btn: { width: 40, height: 40, borderRadius: 20, backgroundColor: "#6c63ff15", justifyContent: "center", alignItems: "center", marginRight: 14 },
  play: { color: "#6c63ff", fontSize: 14 },
});
