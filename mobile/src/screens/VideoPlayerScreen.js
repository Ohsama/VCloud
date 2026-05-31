import React, { useState, useEffect, useRef } from "react";
import { View, Text, StyleSheet, Pressable, ActivityIndicator, Dimensions } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Video, ResizeMode } from "expo-av";
import * as FileSystem from "expo-file-system/legacy";

const W = Dimensions.get("window").width;

export default function VideoPlayerScreen({ route, navigation }) {
  const { isLive, camera_name, date, chunks, url } = route.params;
  const videoRef = useRef(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [uri, setUri] = useState(null);

  useEffect(() => {
    if (isLive) { setUri(url); }
    else { buildPlaylist(); }
  }, []);

  const buildPlaylist = async () => {
    try {
      const ts = (chunks || []).filter((c) => c.s3_video_url?.endsWith(".ts"));
      if (!ts.length) throw new Error("No .ts segments found for this day.");
      let m3u = "#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:60\n#EXT-X-MEDIA-SEQUENCE:0\n#EXT-X-PLAYLIST-TYPE:VOD\n";
      ts.forEach((c) => { m3u += `#EXTINF:60.0,\n${c.s3_video_url}\n`; });
      m3u += "#EXT-X-ENDLIST\n";
      const path = `${FileSystem.documentDirectory}pl_${Date.now()}.m3u8`;
      await FileSystem.writeAsStringAsync(path, m3u, { encoding: "utf8" });
      setUri(path);
    } catch (e) {
      setError(e.message);
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={s.container} edges={["top"]}>
      <View style={s.header}>
        <Pressable onPress={() => navigation.goBack()} style={s.back}>
          <Text style={s.backIcon}>←</Text>
        </Pressable>
        <View style={s.info}>
          <Text style={s.title} numberOfLines={1}>{isLive ? `LIVE: ${camera_name}` : camera_name}</Text>
          <Text style={s.sub}>{isLive ? "Real-time feed" : date}</Text>
        </View>
      </View>

      <View style={s.player}>
        {loading && (
          <View style={s.overlay}>
            <ActivityIndicator size="large" color="#6c63ff" />
            <Text style={s.buf}>Buffering...</Text>
          </View>
        )}
        {error
          ? <View style={s.errBox}><Text style={s.errIcon}>⚠️</Text><Text style={s.errMsg}>{error}</Text></View>
          : uri
            ? <Video ref={videoRef} source={{ uri }} style={s.video} useNativeControls resizeMode={ResizeMode.CONTAIN} shouldPlay
                onPlaybackStatusUpdate={(st) => { if (st.isLoaded && loading) setLoading(false); if (st.error) setError(`Playback error: ${st.error}`); }}
                onError={(e) => { setError(`Video error: ${e}`); setLoading(false); }}
              />
            : null
        }
      </View>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0a0a0f" },
  header: { flexDirection: "row", alignItems: "center", padding: 16 },
  back: { width: 40, height: 40, borderRadius: 12, backgroundColor: "#13131a", justifyContent: "center", alignItems: "center", borderWidth: 1, borderColor: "#1e1e2e" },
  backIcon: { color: "#fff", fontSize: 20 },
  info: { marginLeft: 14, flex: 1 },
  title: { color: "#fff", fontSize: 18, fontWeight: "700" },
  sub: { color: "#8888aa", fontSize: 13, marginTop: 2 },
  player: { width: W, height: W * (9 / 16), backgroundColor: "#000", justifyContent: "center", alignItems: "center" },
  video: { width: "100%", height: "100%" },
  overlay: { ...StyleSheet.absoluteFillObject, justifyContent: "center", alignItems: "center", backgroundColor: "#000c", zIndex: 10 },
  buf: { color: "#8888aa", marginTop: 10, fontSize: 13 },
  errBox: { alignItems: "center", padding: 30 },
  errIcon: { fontSize: 40, marginBottom: 12 },
  errMsg: { color: "#ff6666", fontSize: 13, textAlign: "center", lineHeight: 18 },
});
