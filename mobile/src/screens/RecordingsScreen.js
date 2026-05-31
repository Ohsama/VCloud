import React, { useState, useEffect, useCallback } from "react";
import { View, Text, FlatList, StyleSheet, ActivityIndicator, RefreshControl, Pressable } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { supabase } from "../lib/supabase";

const SHOP_ID = "00000000-0000-0000-0000-000000000001";
const CAMERA_NAME = "cam-01";
const MINIO_BASE = process.env.EXPO_PUBLIC_MINIO_BASE_URL
  ? `${process.env.EXPO_PUBLIC_MINIO_BASE_URL}/vsaas-storage`
  : "http://192.168.1.54:9000/vsaas-storage";

export default function RecordingsScreen({ navigation }) {
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  const fetch = useCallback(async () => {
    try {
      setError(null);
      const { data, error: e } = await supabase
        .from("camera_recordings")
        .select("*")
        .eq("shop_id", SHOP_ID)
        .eq("camera_name", CAMERA_NAME)
        .order("start_time", { ascending: false });
      if (e) throw e;

      const map = {};
      (data || []).forEach((rec) => {
        const d = new Date(rec.start_time).toLocaleDateString("en-US", {
          weekday: "long", month: "short", day: "numeric", year: "numeric",
        });
        if (!map[d]) map[d] = [];
        map[d].push(rec);
      });

      setGroups(Object.keys(map).map((date) => ({
        id: date, date,
        chunks: map[date].sort((a, b) => new Date(a.start_time) - new Date(b.start_time)),
        count: map[date].length,
      })));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  return (
    <SafeAreaView style={s.container} edges={["top"]}>
      <View style={s.header}>
        <Text style={s.icon}>☁️</Text>
        <View>
          <Text style={s.title}>VCloud</Text>
          <Text style={s.sub}>Cloud Surveillance</Text>
        </View>
      </View>

      <Pressable style={({ pressed }) => [s.live, pressed && s.pressed]}
        onPress={() => navigation.navigate("VideoPlayer", {
          isLive: true, camera_name: CAMERA_NAME,
          url: `${MINIO_BASE}/${SHOP_ID}/${CAMERA_NAME}/live/index.m3u8`,
        })}>
        <View style={s.dot} />
        <Text style={s.liveText}>WATCH LIVE FEED</Text>
      </Pressable>

      {error && <View style={s.err}><Text style={s.errText}>Error: {error}</Text></View>}

      {loading
        ? <View style={s.center}><ActivityIndicator size="large" color="#6c63ff" /></View>
        : <FlatList
            data={groups}
            keyExtractor={(i) => i.id}
            contentContainerStyle={s.list}
            refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); fetch(); }} tintColor="#6c63ff" colors={["#6c63ff"]} />}
            ListEmptyComponent={<View style={s.empty}><Text style={s.emptyIcon}>📡</Text><Text style={s.emptyText}>No archives yet</Text></View>}
            renderItem={({ item }) => (
              <Pressable style={({ pressed }) => [s.card, pressed && s.pressed]}
                onPress={() => navigation.navigate("VideoPlayer", { isLive: false, camera_name: CAMERA_NAME, date: item.date, chunks: item.chunks })}>
                <Text style={s.cardIcon}>📅</Text>
                <View style={s.cardBody}>
                  <Text style={s.cardTitle}>{item.date}</Text>
                  <Text style={s.cardSub}>{CAMERA_NAME} · {item.count} segments</Text>
                </View>
                <Text style={s.play}>▶</Text>
              </Pressable>
            )}
          />
      }
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0a0a0f" },
  center: { flex: 1, justifyContent: "center", alignItems: "center" },
  header: { flexDirection: "row", alignItems: "center", paddingHorizontal: 20, paddingTop: 12, paddingBottom: 20 },
  icon: { fontSize: 32, marginRight: 12 },
  title: { color: "#fff", fontSize: 28, fontWeight: "800", letterSpacing: 1 },
  sub: { color: "#8888aa", fontSize: 13 },
  live: { flexDirection: "row", alignItems: "center", justifyContent: "center", backgroundColor: "#1e1e2e", marginHorizontal: 16, marginBottom: 20, paddingVertical: 14, borderRadius: 12, borderWidth: 1, borderColor: "#ff444440" },
  pressed: { opacity: 0.7 },
  dot: { width: 10, height: 10, borderRadius: 5, backgroundColor: "#ff4444", marginRight: 10 },
  liveText: { color: "#ff4444", fontWeight: "700", fontSize: 14, letterSpacing: 1 },
  err: { backgroundColor: "#ff444420", marginHorizontal: 16, marginBottom: 12, padding: 12, borderRadius: 10 },
  errText: { color: "#ff6666", fontSize: 13 },
  list: { paddingBottom: 24, paddingHorizontal: 16 },
  card: { flexDirection: "row", alignItems: "center", backgroundColor: "#13131a", borderRadius: 14, padding: 16, marginBottom: 12, borderWidth: 1, borderColor: "#1e1e2e", borderLeftWidth: 4, borderLeftColor: "#6c63ff" },
  cardIcon: { fontSize: 24, marginRight: 14 },
  cardBody: { flex: 1 },
  cardTitle: { color: "#fff", fontSize: 16, fontWeight: "700", marginBottom: 4 },
  cardSub: { color: "#8888aa", fontSize: 13 },
  play: { color: "#6c63ff", fontSize: 20 },
  empty: { alignItems: "center", padding: 40 },
  emptyIcon: { fontSize: 48, marginBottom: 16 },
  emptyText: { color: "#fff", fontSize: 20, fontWeight: "700" },
});
