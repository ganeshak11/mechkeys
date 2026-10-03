use std::collections::HashMap;
use std::fs::File;
use std::io::{BufRead, BufReader, Read, Write};
use std::os::unix::net::{UnixListener, UnixStream};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, RwLock};
use std::thread;

use evdev::{Device, EventType, KeyCode};
use rodio::buffer::SamplesBuffer;
use rodio::mixer::Mixer;
use rodio::{Decoder, DeviceSinkBuilder, Source};
use serde::Deserialize;

const SOCKET_PATH: &str = "/tmp/mechkeys.sock";

#[derive(Clone)]
pub struct SoundSample {
    pub channels: rodio::ChannelCount,
    pub sample_rate: rodio::SampleRate,
    pub samples: Arc<Vec<f32>>,
}

#[derive(Deserialize)]
struct PackConfig {
    #[serde(default)]
    defaults: Vec<String>,
    #[serde(default)]
    mappings: HashMap<String, String>,
}

pub struct SoundPack {
    pub name: String,
    pub mappings: HashMap<u16, Arc<SoundSample>>,
    pub defaults: Vec<Arc<SoundSample>>,
}

impl SoundPack {
    pub fn load(pack_path: &Path) -> Result<Self, Box<dyn std::error::Error + Send + Sync>> {
        let config_path = pack_path.join("config.json");
        let config_file = File::open(&config_path)?;
        let config: PackConfig = serde_json::from_reader(BufReader::new(config_file))?;

        let mut file_cache: HashMap<String, Arc<SoundSample>> = HashMap::new();
        let name = pack_path
            .file_name()
            .and_then(|n| n.to_str())
            .unwrap_or("unknown")
            .to_string();

        let mut load_file = |filename: &str| -> Option<Arc<SoundSample>> {
            if let Some(sample) = file_cache.get(filename) {
                return Some(sample.clone());
            }

            let file_path = pack_path.join(filename);
            let file = File::open(&file_path).ok()?;
            let mut reader = BufReader::new(file);
            let mut bytes = Vec::new();
            reader.read_to_end(&mut bytes).ok()?;

            let cursor = std::io::Cursor::new(bytes);
            let decoder = Decoder::try_from(cursor).ok()?;
            let channels = decoder.channels();
            let sample_rate = decoder.sample_rate();
            let samples: Vec<f32> = decoder.collect();

            let sample = Arc::new(SoundSample {
                channels,
                sample_rate,
                samples: Arc::new(samples),
            });

            file_cache.insert(filename.to_string(), sample.clone());
            Some(sample)
        };

        let mut mappings = HashMap::new();
        for (code_str, filename) in config.mappings {
            if let Ok(code) = code_str.parse::<u16>() {
                if let Some(sample) = load_file(&filename) {
                    mappings.insert(code, sample);
                }
            }
        }

        let mut defaults = Vec::new();
        for filename in config.defaults {
            if let Some(sample) = load_file(&filename) {
                defaults.push(sample);
            }
        }

        if defaults.is_empty() && !mappings.is_empty() {
            if let Some(first) = mappings.values().next() {
                defaults.push(first.clone());
            }
        }

        Ok(Self {
            name,
            mappings,
            defaults,
        })
    }

    pub fn get_sample(&self, code: u16) -> Option<Arc<SoundSample>> {
        if let Some(sample) = self.mappings.get(&code) {
            return Some(sample.clone());
        }
        if !self.defaults.is_empty() {
            let idx = (code as usize) % self.defaults.len();
            return Some(self.defaults[idx].clone());
        }
        None
    }
}

pub struct AppState {
    pub soundpacks_dir: PathBuf,
    pub current_pack: Option<Arc<SoundPack>>,
    pub is_muted: AtomicBool,
}

fn play_click(sample: &SoundSample, mixer: &Mixer) {
    let buffer = SamplesBuffer::new(
        sample.channels,
        sample.sample_rate,
        (*sample.samples).clone(),
    );
    mixer.add(buffer);
}

fn find_keyboard_paths() -> Vec<PathBuf> {
    let mut keyboards = Vec::new();
    for (path, device) in evdev::enumerate() {
        let is_kbd = device.supported_keys().map_or(false, |keys| {
            keys.contains(KeyCode::KEY_SPACE) && keys.contains(KeyCode::KEY_A)
        });
        if is_kbd {
            keyboards.push(path);
        }
    }
    keyboards
}

fn start_keyboard_listener(path: PathBuf, state: Arc<RwLock<AppState>>, mixer: Mixer) {
    thread::spawn(move || {
        let mut device = match Device::open(&path) {
            Ok(d) => d,
            Err(e) => {
                eprintln!("⚠️ Failed to open keyboard device {:?}: {}", path, e);
                return;
            }
        };

        println!("⚡ Listening to keyboard {:?} at {:?}", device.name(), path);

        loop {
            match device.fetch_events() {
                Ok(events) => {
                    for event in events {
                        if event.event_type() == EventType::KEY && event.value() == 1 {
                            // Key Press Down
                            let code = event.code();
                            let state_guard = state.read().unwrap();
                            if !state_guard.is_muted.load(Ordering::Relaxed) {
                                if let Some(ref pack) = state_guard.current_pack {
                                    if let Some(sample) = pack.get_sample(code) {
                                        play_click(&sample, &mixer);
                                    }
                                }
                            }
                        }
                    }
                }
                Err(e) => {
                    eprintln!("Keyboard {:?} disconnected: {}", path, e);
                    break;
                }
            }
        }
    });
}

fn start_ipc_server(state: Arc<RwLock<AppState>>) {
    let _ = std::fs::remove_file(SOCKET_PATH);
    let listener = UnixListener::bind(SOCKET_PATH).expect("Failed to bind Unix socket");
    println!("🔌 IPC Socket active at {}", SOCKET_PATH);

    thread::spawn(move || {
        for stream in listener.incoming() {
            if let Ok(mut stream) = stream {
                let mut reader = BufReader::new(stream.try_clone().unwrap());
                let mut line = String::new();
                if reader.read_line(&mut line).is_ok() {
                    let cmd = line.trim();
                    let parts: Vec<&str> = cmd.split_whitespace().collect();
                    let mut response = String::new();

                    match parts.get(0).copied() {
                        Some("SET") => {
                            if let Some(pack_name) = parts.get(1) {
                                if *pack_name == "off" || *pack_name == "OFF" {
                                    let state_guard = state.read().unwrap();
                                    state_guard.is_muted.store(true, Ordering::Relaxed);
                                    response = "Muted (Sound OFF)\n".to_string();
                                } else {
                                    let dir = state.read().unwrap().soundpacks_dir.clone();
                                    let pack_path = dir.join(pack_name);
                                    match SoundPack::load(&pack_path) {
                                        Ok(pack) => {
                                            let mut state_guard = state.write().unwrap();
                                            state_guard.current_pack = Some(Arc::new(pack));
                                            state_guard.is_muted.store(false, Ordering::Relaxed);
                                            response = format!("Switched to: {}\n", pack_name);
                                            println!("Switched to profile: {}", pack_name);
                                        }
                                        Err(e) => {
                                            response = format!("Error loading pack: {}\n", e);
                                        }
                                    }
                                }
                            }
                        }
                        Some("TOGGLE") => {
                            let state_guard = state.read().unwrap();
                            let current = state_guard.is_muted.load(Ordering::Relaxed);
                            state_guard.is_muted.store(!current, Ordering::Relaxed);
                            response = format!("Muted: {}\n", !current);
                        }
                        Some("STATUS") => {
                            let state_guard = state.read().unwrap();
                            let muted = state_guard.is_muted.load(Ordering::Relaxed);
                            let name = state_guard
                                .current_pack
                                .as_ref()
                                .map(|p| p.name.as_str())
                                .unwrap_or("none");
                            response = format!("Active: {} (Muted: {})\n", name, muted);
                        }
                        Some("LIST") => {
                            let dir = state.read().unwrap().soundpacks_dir.clone();
                            if let Ok(entries) = std::fs::read_dir(dir) {
                                for entry in entries.flatten() {
                                    if entry.path().is_dir()
                                        && entry.path().join("config.json").exists()
                                    {
                                        if let Some(name) = entry.file_name().to_str() {
                                            response.push_str(name);
                                            response.push('\n');
                                        }
                                    }
                                }
                            }
                        }
                        _ => {
                            response =
                                "Unknown command. Valid: SET <name>, TOGGLE, STATUS, LIST\n"
                                    .to_string();
                        }
                    }

                    let _ = stream.write_all(response.as_bytes());
                }
            }
        }
    });
}

fn send_ipc_cmd(cmd: &str) -> Result<String, Box<dyn std::error::Error>> {
    let mut stream = UnixStream::connect(SOCKET_PATH)?;
    stream.write_all(format!("{}\n", cmd).as_bytes())?;
    let mut reader = BufReader::new(stream);
    let mut response = String::new();
    reader.read_to_string(&mut response)?;
    Ok(response)
}

fn open_kde_menu() {
    // Try launching our custom sleek glassmorphic PyQt6 dropdown first
    let home = std::env::var("HOME").unwrap_or_else(|_| "/home/ganeshak11".to_string());
    let custom_gui_path = format!("{}/.local/bin/mechkeys-menu", home);

    if std::path::Path::new(&custom_gui_path).exists() {
        let status = std::process::Command::new(&custom_gui_path).status();
        if status.map(|s| s.success()).unwrap_or(false) {
            return;
        }
    }

    // Fallback to native kdialog if custom GUI is unavailable
    let list_output = match send_ipc_cmd("LIST") {
        Ok(res) => res,
        Err(_) => {
            eprintln!("Mechkeys daemon is not running! Start with `mechkeys daemon` first.");
            return;
        }
    };

    let mut profiles: Vec<&str> = list_output.lines().filter(|l| !l.is_empty()).collect();
    profiles.sort();

    let mut args = vec![
        "--title".to_string(),
        "⌨️ MechKeys Switcher".to_string(),
        "--menu".to_string(),
        "Select Mechanical Switch Profile:".to_string(),
    ];

    for p in &profiles {
        let label = match *p {
            "cherry_mx_brown_abs" => "🟤 Cherry MX Brown (Tactile Thock)",
            "cherry_mx_red_abs" => "🔴 Cherry MX Red (Linear Muted)",
            "kailh_box_white" => "⚪ Kailh Box White (Clicky Blue)",
            "glorious_panda" => "🐼 Glorious Panda (Deep Thock)",
            "unicomp_classic" => "📜 IBM Model M (Buckling Spring / Vintage)",
            "nk_cream" => "🍦 NovelKeys Cream (Creamy Smooth)",
            "tealios_v2" => "💎 Tealios V2 (Ultra Smooth)",
            other => other,
        };
        args.push(p.to_string());
        args.push(label.to_string());
    }

    args.push("off".to_string());
    args.push("🔇 Turn OFF (Mute / Silent)".to_string());

    let output = std::process::Command::new("kdialog")
        .args(&args)
        .output();

    if let Ok(out) = output {
        let selected = String::from_utf8_lossy(&out.stdout).trim().to_string();
        if !selected.is_empty() {
            let res = send_ipc_cmd(&format!("SET {}", selected)).unwrap_or_default();
            println!("{}", res.trim());
            let _ = std::process::Command::new("notify-send")
                .args([
                    "⌨️ MechKeys",
                    &format!("Switched to: {}", selected),
                    "-t",
                    "1500",
                    "-a",
                    "MechKeys",
                ])
                .spawn();
        }
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = std::env::args().collect();
    let subcommand = args.get(1).map(|s| s.as_str()).unwrap_or("daemon");

    match subcommand {
        "menu" => {
            open_kde_menu();
            return Ok(());
        }
        "set" => {
            if let Some(name) = args.get(2) {
                let res = send_ipc_cmd(&format!("SET {}", name))?;
                print!("{}", res);
            } else {
                eprintln!("Usage: mechkeys set <profile_name|off>");
            }
            return Ok(());
        }
        "toggle" => {
            let res = send_ipc_cmd("TOGGLE")?;
            print!("{}", res);
            return Ok(());
        }
        "status" => {
            let res = send_ipc_cmd("STATUS")?;
            print!("{}", res);
            return Ok(());
        }
        "list" => {
            let res = send_ipc_cmd("LIST")?;
            print!("{}", res);
            return Ok(());
        }
        "daemon" | _ => {}
    }

    println!("🚀 Starting MechKeys Ultra-Low-Latency Audio Daemon...");

    let exe_dir = std::env::current_exe()?
        .parent()
        .unwrap()
        .to_path_buf();
    let mut soundpacks_dir = exe_dir.join("soundpacks");
    if !soundpacks_dir.exists() {
        soundpacks_dir = PathBuf::from("/home/ganeshak11/dev/Projects/mechkeys/soundpacks");
    }

    println!("📁 Soundpacks path: {:?}", soundpacks_dir);

    let default_profile = "cherry_mx_brown_abs";
    println!("📦 Pre-loading profile: {} into RAM...", default_profile);
    let initial_pack = match SoundPack::load(&soundpacks_dir.join(default_profile)) {
        Ok(pack) => {
            println!(
                "✅ Profile '{}' loaded: {} scancodes mapped in RAM",
                default_profile,
                pack.mappings.len()
            );
            Some(Arc::new(pack))
        }
        Err(e) => {
            eprintln!("⚠️ Failed to load default profile: {}", e);
            None
        }
    };

    let state = Arc::new(RwLock::new(AppState {
        soundpacks_dir,
        current_pack: initial_pack,
        is_muted: AtomicBool::new(false),
    }));

    // Start Audio Engine
    let sink_handle = DeviceSinkBuilder::open_default_sink()
        .expect("Failed to initialize physical audio output device");
    let mixer = sink_handle.mixer().clone();

    // Start IPC Socket
    start_ipc_server(state.clone());

    // Find and listen to all hardware keyboards
    let keyboards = find_keyboard_paths();
    if keyboards.is_empty() {
        eprintln!("❌ No keyboards found in /dev/input/! Are you in the 'input' group?");
    } else {
        for kbd_path in keyboards {
            start_keyboard_listener(kbd_path, state.clone(), mixer.clone());
        }
    }

    println!("\n✨ MechKeys is LIVE! Type on your keyboard to hear the mechanical switches!");
    println!("💡 Tip: Run `mechkeys menu` in another terminal or bind it to a shortcut to switch switches!\n");

    loop {
        thread::sleep(std::time::Duration::from_secs(3600));
    }
}
