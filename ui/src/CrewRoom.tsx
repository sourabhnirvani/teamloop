import { useEffect, useRef } from "react";
import * as THREE from "three";
import { RoundedBoxGeometry } from "three/examples/jsm/geometries/RoundedBoxGeometry.js";
import type { Bot } from "./api";
import { botColor, type Move } from "./Avatar";

// The Crew Room: the six bots as little 3D mascots living in one room. Idle bots wander and do their
// own thing (S checks its compass, Web daydreams then dashes off, Scout hops, Inbox waddles, Writer
// scribbles). A working bot walks to its spot and glows, a hand-off is a glowing task orb thrown from
// one bot to the other, a bot that needs your OK turns to you with a "?", finished work gets a jump
// and confetti, a failure gets a droop. Hover a bot and it stops and looks at you; click to open it.

export type Handoff = { from: string; to: string; key: number };

type Props = {
  bots: Bot[];
  moves: Record<string, Move>;
  working: string[];
  asking: string[];
  handoff: Handoff | null;
  signs?: Record<string, string | null>; // the same signs the chats show: 👂 💭 🔎 🙋 ✨ ...
  onPick?: (botId: string) => void;
  height?: number | string;
};

type Eye = { pupil: THREE.Object3D; base: THREE.Vector3; range: number };

type Rig = {
  id: string;
  root: THREE.Group;
  body: THREE.Group;
  skin: THREE.MeshPhysicalMaterial;
  eyes: Eye[];
  eyeScale: THREE.Object3D[];
  hit: THREE.Mesh;
  shadow: THREE.Mesh;
  bubble: THREE.Sprite;
  extra: Record<string, THREE.Object3D>;
  pos: THREE.Vector2;
  vel: THREE.Vector2;
  target: THREE.Vector2;
  home: THREE.Vector2;
  heading: number;
  speed: number;
  nextWander: number;
  dashUntil: number;
  daydreamUntil: number;
  nextQuirk: number;
  quirkUntil: number;
  hop: number;
  jumpUntil: number;
  catchUntil: number;
  label: HTMLDivElement;
  lastMove: Move;
  signShown: string;
};

type Particle = { mesh: THREE.Mesh; vel: THREE.Vector3; life: number; max: number; spin: number };
type Orb = { mesh: THREE.Mesh; trail: THREE.Mesh[]; from: string; to: string; t: number };

const ROOM = 3.1;

function clay(color: THREE.ColorRepresentation) {
  return new THREE.MeshPhysicalMaterial({
    color, roughness: 0.38, metalness: 0, clearcoat: 0.6, clearcoatRoughness: 0.35,
    sheen: 0.6, sheenRoughness: 0.5, sheenColor: new THREE.Color("#ffffff"), emissive: new THREE.Color(color), emissiveIntensity: 0,
  });
}

function blobTexture(inner: string, outer: string) {
  const c = document.createElement("canvas");
  c.width = c.height = 128;
  const g = c.getContext("2d")!;
  const grad = g.createRadialGradient(64, 64, 4, 64, 64, 64);
  grad.addColorStop(0, inner);
  grad.addColorStop(1, outer);
  g.fillStyle = grad;
  g.fillRect(0, 0, 128, 128);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

// a speech-bubble sign with an emoji, drawn once per emoji
function signTexture(emoji: string) {
  const c = document.createElement("canvas");
  c.width = c.height = 128;
  const g = c.getContext("2d")!;
  g.fillStyle = "#151b33";
  g.strokeStyle = "rgba(170,185,255,.55)";
  g.lineWidth = 4;
  g.beginPath();
  g.roundRect(10, 8, 108, 92, 30);
  g.moveTo(44, 98);
  g.lineTo(52, 122);
  g.lineTo(70, 98);
  g.fill();
  g.stroke();
  g.font = "62px 'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', sans-serif";
  g.textAlign = "center";
  g.textBaseline = "middle";
  g.fillText(emoji, 64, 57);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

const INK = "#1d2150";

function addEyes(parent: THREE.Object3D, spots: [number, number, number][], r: number): { eyes: Eye[]; whites: THREE.Object3D[] } {
  const ink = new THREE.MeshStandardMaterial({ color: INK, roughness: 0.2, metalness: 0.1 });
  const shine = new THREE.MeshBasicMaterial({ color: "#ffffff" });
  const eyes: Eye[] = [];
  const whites: THREE.Object3D[] = [];
  for (const [x, y, z] of spots) {
    const eye = new THREE.Group();
    eye.position.set(x, y, z);
    const ball = new THREE.Mesh(new THREE.SphereGeometry(r, 20, 16), ink);
    ball.scale.set(0.86, 1.18, 0.5);
    eye.add(ball);
    const glints = new THREE.Group();
    const big = new THREE.Mesh(new THREE.SphereGeometry(r * 0.32, 10, 8), shine);
    big.position.set(r * 0.28, r * 0.42, 0);
    const small = new THREE.Mesh(new THREE.SphereGeometry(r * 0.14, 8, 6), shine);
    small.position.set(-r * 0.22, -r * 0.4, 0);
    glints.add(big, small);
    glints.position.set(0, 0, r * 0.42);
    eye.add(glints);
    parent.add(eye);
    eyes.push({ pupil: glints, base: glints.position.clone(), range: r * 0.3 });
    whites.push(eye);
  }
  return { eyes, whites };
}

// a smile and two blush dots; the mouth talks, grins or frowns in the loop
function addFace(parent: THREE.Object3D, mouth: [number, number, number], blush: [number, number, number][], size: number,
                 ink: THREE.ColorRepresentation = INK, glow = false): THREE.Object3D {
  const mat = glow ? new THREE.MeshStandardMaterial({ color: ink, emissive: ink, emissiveIntensity: 1.6 })
    : new THREE.MeshStandardMaterial({ color: ink, roughness: 0.3 });
  const smile = new THREE.Mesh(new THREE.TorusGeometry(size, size * 0.24, 8, 18, Math.PI), mat);
  smile.rotation.z = Math.PI; // the lower half of a ring: a smile
  smile.position.set(...mouth);
  parent.add(smile);
  const pink = new THREE.MeshBasicMaterial({ color: "#ff8fb3", transparent: true, opacity: 0.55, depthWrite: false });
  for (const [x, y, z] of blush) {
    const dot = new THREE.Mesh(new THREE.CircleGeometry(size * 0.9, 18), pink);
    dot.scale.set(1, 0.6, 1);
    dot.position.set(x, y, z);
    dot.rotation.y = x * 0.9; // follow the body's curve a little
    parent.add(dot);
  }
  return smile;
}

function heartShape(s: number) {
  const h = new THREE.Shape();
  h.moveTo(0, -0.6 * s);
  h.bezierCurveTo(-1.1 * s, 0.1 * s, -0.5 * s, 0.9 * s, 0, 0.35 * s);
  h.bezierCurveTo(0.5 * s, 0.9 * s, 1.1 * s, 0.1 * s, 0, -0.6 * s);
  return h;
}

// Builds one mascot. Shapes, colours and accessories are TeamLoop's own: a captain, a screen-cube,
// a globe-ball, a monocled bean, an envelope and a bespectacled pill.
function build(bot: Bot): Omit<Rig, "pos" | "vel" | "target" | "home" | "heading" | "speed" | "nextWander" | "dashUntil" |
  "daydreamUntil" | "nextQuirk" | "quirkUntil" | "hop" | "jumpUntil" | "catchUntil" | "label" | "lastMove" | "shadow" | "bubble" | "hit" | "signShown"> {
  const picked = bot.look?.colour && bot.look.colour !== "rainbow" ? bot.look.colour : null; // a built bot keeps its colour
  const color = new THREE.Color(picked ?? botColor(bot.id));
  const skin = clay(bot.id === "s" ? "#eef0ff" : color); // S is the logo's white blob
  const root = new THREE.Group();
  const body = new THREE.Group();
  root.add(body);
  const extra: Record<string, THREE.Object3D> = {};
  let eyes: Eye[] = [];
  let whites: THREE.Object3D[] = [];

  switch (bot.id) {
    case "s": { // the logo's friendly blob with its antenna star and an indigo collar
      const blob = new THREE.Mesh(new THREE.SphereGeometry(0.55, 40, 30), skin);
      blob.scale.set(1, 0.92, 0.95);
      blob.position.y = 0.53;
      body.add(blob);
      const stalk = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, 0.24, 8), clay("#c9d0ff"));
      stalk.position.y = 1.12;
      body.add(stalk);
      const star = new THREE.Mesh(new THREE.SphereGeometry(0.075, 18, 14),
        new THREE.MeshStandardMaterial({ color: "#ffd45c", emissive: "#ffb800", emissiveIntensity: 1.2 }));
      star.position.y = 1.26;
      body.add(star);
      extra.tip = star;
      const collar = new THREE.Mesh(new THREE.TorusGeometry(0.4, 0.05, 10, 40), clay("#5b6bff"));
      collar.rotation.x = Math.PI / 2;
      collar.position.y = 0.14;
      body.add(collar);
      ({ eyes, whites } = addEyes(body, [[-0.19, 0.62, 0.46], [0.19, 0.62, 0.46]], 0.115));
      extra.mouth = addFace(body, [0, 0.43, 0.5], [[-0.33, 0.47, 0.41], [0.33, 0.47, 0.41]], 0.06);
      break;
    }
    case "desk": {
      const cube = new THREE.Mesh(new RoundedBoxGeometry(0.92, 0.86, 0.78, 5, 0.2), skin);
      cube.position.y = 0.48;
      body.add(cube);
      const screen = new THREE.Mesh(new RoundedBoxGeometry(0.66, 0.46, 0.06, 3, 0.07),
        new THREE.MeshStandardMaterial({ color: "#0b1322", roughness: 0.15, metalness: 0.4 }));
      screen.position.set(0, 0.52, 0.39);
      body.add(screen);
      const glow = new THREE.MeshStandardMaterial({ color: "#7dfbd3", emissive: "#3df5c0", emissiveIntensity: 2 });
      const px = [-0.13, 0.13].map((x) => {
        const p = new THREE.Mesh(new RoundedBoxGeometry(0.1, 0.13, 0.02, 2, 0.03), glow);
        p.position.set(x, 0.54, 0.43);
        body.add(p);
        return p;
      });
      eyes = px.map((p) => ({ pupil: p, base: p.position.clone(), range: 0.07 }));
      whites = px;
      extra.mouth = addFace(body, [0, 0.41, 0.43], [[-0.24, 0.42, 0.425], [0.24, 0.42, 0.425]], 0.045, "#7dfbd3", true);
      const stalk = new THREE.Mesh(new THREE.CylinderGeometry(0.018, 0.018, 0.22, 8), clay("#b9c3dc"));
      stalk.position.y = 1.02;
      body.add(stalk);
      const tip = new THREE.Mesh(new THREE.SphereGeometry(0.06, 16, 12), glow);
      tip.position.y = 1.15;
      body.add(tip);
      extra.tip = tip;
      break;
    }
    case "web": {
      const ball = new THREE.Group();
      ball.position.y = 0.56;
      body.add(ball);
      ball.add(new THREE.Mesh(new THREE.SphereGeometry(0.56, 48, 36), skin));
      const lineMat = new THREE.MeshBasicMaterial({ color: "#ffffff", transparent: true, opacity: 0.32 });
      const m1 = new THREE.Mesh(new THREE.TorusGeometry(0.565, 0.012, 8, 72), lineMat);
      m1.rotation.y = Math.PI / 2;
      ball.add(m1);
      const m2 = new THREE.Mesh(new THREE.TorusGeometry(0.565, 0.012, 8, 72), lineMat);
      m2.rotation.x = Math.PI / 2;
      ball.add(m2);
      const m3 = new THREE.Mesh(new THREE.TorusGeometry(0.565, 0.012, 8, 72), lineMat);
      m3.rotation.y = Math.PI / 5;
      ball.add(m3);
      extra.ball = ball;
      ({ eyes, whites } = addEyes(ball, [[-0.17, 0.12, 0.49], [0.17, 0.12, 0.49]], 0.115));
      extra.mouth = addFace(ball, [0, -0.07, 0.53], [[-0.3, -0.02, 0.46], [0.3, -0.02, 0.46]], 0.055);
      const ring = new THREE.Mesh(new THREE.TorusGeometry(0.74, 0.026, 10, 72),
        new THREE.MeshStandardMaterial({ color: "#ffe0bd", emissive: "#ffb070", emissiveIntensity: 0.25, roughness: 0.4 }));
      ring.rotation.set(Math.PI / 2 - 0.62, 0, 0.22); // tilted toward you, so it reads as a ring
      ring.position.y = 0.56;
      body.add(ring);
      break;
    }
    case "scout": {
      const bean = new THREE.Mesh(new THREE.CapsuleGeometry(0.34, 0.42, 12, 32), skin);
      bean.position.y = 0.62;
      bean.rotation.z = 0.18;
      body.add(bean);
      ({ eyes, whites } = addEyes(body, [[-0.12, 0.78, 0.29], [0.15, 0.8, 0.27]], 0.1));
      extra.mouth = addFace(body, [0.03, 0.6, 0.33], [[-0.22, 0.66, 0.29], [0.3, 0.68, 0.24]], 0.05);
      const hat = new THREE.Group();
      hat.position.set(-0.1, 1.13, 0);
      hat.rotation.z = 0.18;
      const brim = new THREE.Mesh(new THREE.CylinderGeometry(0.46, 0.46, 0.03, 36), clay("#d9a94e"));
      const crown = new THREE.Mesh(new THREE.SphereGeometry(0.25, 28, 16, 0, Math.PI * 2, 0, Math.PI / 2), clay("#efc46d"));
      crown.scale.set(1, 0.9, 1);
      const band = new THREE.Mesh(new THREE.CylinderGeometry(0.255, 0.255, 0.06, 28), clay("#8a5a2b"));
      band.position.y = 0.04;
      hat.add(brim, crown, band);
      body.add(hat);
      const gold = new THREE.MeshStandardMaterial({ color: "#f6c453", metalness: 0.85, roughness: 0.2 });
      const monocle = new THREE.Mesh(new THREE.TorusGeometry(0.13, 0.022, 10, 36), gold);
      monocle.position.set(0.15, 0.8, 0.33);
      body.add(monocle);
      const handle = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, 0.2, 8), gold);
      handle.position.set(0.27, 0.66, 0.33);
      handle.rotation.z = 0.6;
      body.add(handle);
      extra.monocle = monocle;
      break;
    }
    case "inbox": {
      const env = new THREE.Mesh(new RoundedBoxGeometry(1.0, 0.72, 0.56, 5, 0.16), skin);
      env.position.y = 0.42;
      body.add(env);
      const flapShape = new THREE.Shape();
      flapShape.moveTo(-0.44, 0.3);
      flapShape.lineTo(0, -0.02);
      flapShape.lineTo(0.44, 0.3);
      const flap = new THREE.Mesh(new THREE.ShapeGeometry(flapShape),
        new THREE.MeshStandardMaterial({ color: "#ffffff", transparent: true, opacity: 0.55, side: THREE.DoubleSide }));
      flap.position.set(0, 0.44, 0.285);
      body.add(flap);
      const heart = new THREE.Mesh(new THREE.ExtrudeGeometry(heartShape(0.1), { depth: 0.03, bevelEnabled: false }),
        new THREE.MeshStandardMaterial({ color: "#e53965", emissive: "#ff4f7d", emissiveIntensity: 0.35 }));
      heart.position.set(0, 0.47, 0.29);
      body.add(heart);
      extra.heart = heart;
      ({ eyes, whites } = addEyes(body, [[-0.25, 0.3, 0.29], [0.25, 0.3, 0.29]], 0.095));
      extra.mouth = addFace(body, [0, 0.17, 0.29], [[-0.38, 0.2, 0.285], [0.38, 0.2, 0.285]], 0.045);
      break;
    }
    case "writer": {
      const pill = new THREE.Mesh(new THREE.CapsuleGeometry(0.34, 0.56, 12, 32), skin);
      pill.position.y = 0.66;
      body.add(pill);
      ({ eyes, whites } = addEyes(body, [[-0.13, 0.82, 0.3], [0.13, 0.82, 0.3]], 0.088));
      extra.mouth = addFace(body, [0, 0.62, 0.33], [[-0.24, 0.68, 0.29], [0.24, 0.68, 0.29]], 0.05);
      const rim = new THREE.MeshStandardMaterial({ color: "#1b1f2e", roughness: 0.4 });
      for (const x of [-0.13, 0.13]) {
        const lens = new THREE.Mesh(new THREE.TorusGeometry(0.115, 0.016, 10, 32), rim);
        lens.position.set(x, 0.82, 0.335);
        body.add(lens);
      }
      const bridge = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, 0.05, 6), rim);
      bridge.rotation.z = Math.PI / 2;
      bridge.position.set(0, 0.84, 0.34);
      body.add(bridge);
      const quill = new THREE.Group();
      quill.position.set(0.28, 1.05, -0.08);
      quill.rotation.z = -0.5;
      const feather = new THREE.Mesh(new THREE.SphereGeometry(0.16, 20, 14), clay("#cfe8ff"));
      feather.scale.set(0.5, 1.9, 0.18);
      feather.position.y = 0.18;
      quill.add(feather);
      body.add(quill);
      extra.quill = quill;
      break;
    }
    default: {
      const blob = new THREE.Mesh(new THREE.SphereGeometry(0.52, 32, 24), skin);
      blob.position.y = 0.52;
      body.add(blob);
      ({ eyes, whites } = addEyes(body, [[-0.17, 0.6, 0.44], [0.17, 0.6, 0.44]], 0.105));
      extra.mouth = addFace(body, [0, 0.42, 0.49], [[-0.3, 0.46, 0.41], [0.3, 0.46, 0.41]], 0.055);
    }
  }
  return { id: bot.id, root, body, skin, eyes, eyeScale: whites, extra };
}

export function CrewRoom({ bots, moves, working, asking, handoff, signs, onPick, height = 300 }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const live = useRef({ moves, working, asking, signs, onPick });
  live.current = { moves, working, asking, signs, onPick };
  const orbQueue = useRef<Handoff[]>([]);
  const ids = bots.map((b) => b.id).join(",");

  const openedAt = useRef(Date.now());
  useEffect(() => {
    if (handoff && handoff.key >= openedAt.current) orbQueue.current.push(handoff); // not old ones when the tab opens
  }, [handoff]);

  useEffect(() => {
    const el = host.current;
    if (!el || bots.length === 0) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    el.appendChild(renderer.domElement);
    const labels = document.createElement("div");
    labels.className = "room-labels";
    el.appendChild(labels);

    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog("#0a0e1c", 9, 17);
    const camera = new THREE.PerspectiveCamera(34, 1, 0.1, 60);

    scene.add(new THREE.HemisphereLight("#dfe8ff", "#251a3d", 1.05));
    const key = new THREE.DirectionalLight("#fff4e6", 2.4);
    key.position.set(3, 7, 5);
    scene.add(key);
    const rim = new THREE.DirectionalLight("#7c9cff", 1.6);
    rim.position.set(-5, 4, -5);
    scene.add(rim);
    const glow = new THREE.PointLight("#8b7bff", 6, 9, 2);
    glow.position.set(0, 2.6, -2.5);
    scene.add(glow);

    const floor = new THREE.Mesh(new THREE.CircleGeometry(ROOM + 1.6, 96),
      new THREE.MeshStandardMaterial({ map: blobTexture("#2a3466", "#0b0f1f"), roughness: 0.9 }));
    floor.rotation.x = -Math.PI / 2;
    scene.add(floor);
    for (const [r, o] of [[ROOM + 0.2, 0.35], [ROOM * 0.62, 0.18]] as const) {
      const ring = new THREE.Mesh(new THREE.RingGeometry(r - 0.012, r + 0.012, 128),
        new THREE.MeshBasicMaterial({ color: "#6d7fff", transparent: true, opacity: o }));
      ring.rotation.x = -Math.PI / 2;
      ring.position.y = 0.004;
      scene.add(ring);
    }
    const dustGeo = new THREE.BufferGeometry();
    const dustPts = new Float32Array(160 * 3);
    for (let i = 0; i < 160; i++) {
      dustPts[i * 3] = (Math.random() - 0.5) * 12;
      dustPts[i * 3 + 1] = Math.random() * 4;
      dustPts[i * 3 + 2] = (Math.random() - 0.5) * 8 - 1;
    }
    dustGeo.setAttribute("position", new THREE.BufferAttribute(dustPts, 3));
    const dust = new THREE.Points(dustGeo, new THREE.PointsMaterial({ color: "#a9b8ff", size: 0.035, transparent: true, opacity: 0.55 }));
    scene.add(dust);

    const shadowTex = blobTexture("rgba(0,0,0,0.55)", "rgba(0,0,0,0)");
    const signTex: Record<string, THREE.CanvasTexture> = {};
    const texFor = (emoji: string) => (signTex[emoji] ??= signTexture(emoji));
    const hitMat = new THREE.MeshBasicMaterial({ visible: false });

    const lead = bots.findIndex((b) => b.id === "s");
    const order = lead >= 0 ? [bots[lead], ...bots.filter((_, i) => i !== lead)] : bots;
    const rigs: Rig[] = order.map((bot, i) => {
      const part = build(bot);
      const ang = order.length === 1 ? 0 : -1.15 + (2.3 * i) / (order.length - 1);
      const home = i === 0 ? new THREE.Vector2(0, 1.2) : new THREE.Vector2(Math.sin(ang) * 2.4, -Math.cos(ang) * 1.1 + 0.2);
      const start = home.clone().multiplyScalar(0.6).add(new THREE.Vector2((Math.random() - 0.5) * 0.4, (Math.random() - 0.5) * 0.4));
      const shadow = new THREE.Mesh(new THREE.PlaneGeometry(1.4, 1.4),
        new THREE.MeshBasicMaterial({ map: shadowTex, transparent: true, depthWrite: false }));
      shadow.rotation.x = -Math.PI / 2;
      shadow.position.y = 0.01;
      part.root.add(shadow);
      const bubble = new THREE.Sprite(new THREE.SpriteMaterial({ map: texFor("💭"), transparent: true, opacity: 0, depthTest: false }));
      bubble.scale.set(0.46, 0.46, 0.46);
      bubble.position.set(0.42, 1.55, 0);
      part.root.add(bubble);
      const hit = new THREE.Mesh(new THREE.SphereGeometry(0.72, 12, 8), hitMat);
      hit.position.y = 0.6;
      part.root.add(hit);
      part.root.position.set(start.x, 0, start.y);
      scene.add(part.root);
      const label = document.createElement("div");
      label.className = "room-label";
      label.style.setProperty("--bot", botColor(bot.id));
      label.innerHTML = `<b>${bot.name}</b><i></i>`;
      labels.appendChild(label);
      return {
        ...part, shadow, bubble, hit, label, home, pos: start, vel: new THREE.Vector2(), target: start.clone(),
        heading: 0, speed: 0.55 + Math.random() * 0.25, nextWander: Math.random() * 3, dashUntil: 0,
        daydreamUntil: 0, nextQuirk: 2 + Math.random() * 6, quirkUntil: 0, hop: 0, jumpUntil: 0, catchUntil: 0, lastMove: "idle",
        signShown: "",
      };
    });
    const byId: Record<string, Rig> = Object.fromEntries(rigs.map((r) => [r.id, r]));
    const bounds = { x: 2.4, z: 1.15, cz: -0.25 }; // the walking area: an ellipse centred a little back
    let camDist = 6.4;
    function layoutHomes() {
      // two rows at similar depth: the back row, then the front row with S in the middle
      const rest = rigs.slice(1);
      const back = rest.slice(0, Math.ceil(rest.length / 2)), front = rest.slice(back.length);
      const row = (list: Rig[], z: number, spread: number) =>
        list.forEach((r, i) => r.home.set(list.length === 1 ? 0 : ((i / (list.length - 1)) - 0.5) * 2 * spread, z));
      row(back, -1.05, bounds.x * 0.78);
      const fr = [...front.slice(0, Math.floor(front.length / 2)), rigs[0], ...front.slice(Math.floor(front.length / 2))].filter(Boolean);
      row(fr, 0.55, bounds.x * 0.82);
    }

    // pooled particles: work sparks and confetti
    const particles: Particle[] = [];
    const sparkGeo = new THREE.BoxGeometry(0.05, 0.05, 0.05);
    const confettiGeo = new THREE.PlaneGeometry(0.07, 0.04);
    function emit(at: THREE.Vector3, color: THREE.ColorRepresentation, n: number, kind: "spark" | "confetti") {
      for (let i = 0; i < n; i++) {
        const mat = new THREE.MeshBasicMaterial({ color: kind === "confetti" ? new THREE.Color().setHSL(Math.random(), 0.8, 0.6) : color,
          transparent: true, side: THREE.DoubleSide });
        const mesh = new THREE.Mesh(kind === "confetti" ? confettiGeo : sparkGeo, mat);
        mesh.position.copy(at);
        const vel = kind === "confetti"
          ? new THREE.Vector3((Math.random() - 0.5) * 2.4, 2 + Math.random() * 1.8, (Math.random() - 0.5) * 2.4)
          : new THREE.Vector3((Math.random() - 0.5) * 0.4, 0.6 + Math.random() * 0.5, (Math.random() - 0.5) * 0.4);
        scene.add(mesh);
        particles.push({ mesh, vel, life: 0, max: kind === "confetti" ? 1.6 : 0.9, spin: (Math.random() - 0.5) * 10 });
      }
    }

    const orbs: Orb[] = [];
    const orbGeo = new THREE.SphereGeometry(0.11, 20, 14);
    const trailGeo = new THREE.SphereGeometry(0.05, 10, 8);
    function throwOrb(h: Handoff) {
      const a = byId[h.from], b = byId[h.to];
      if (!a || !b || a === b) return;
      const c = new THREE.Color(botColor(h.to));
      const mesh = new THREE.Mesh(orbGeo, new THREE.MeshStandardMaterial({ color: c, emissive: c, emissiveIntensity: 3.2 }));
      const trail = Array.from({ length: 8 }, (_, i) => {
        const t = new THREE.Mesh(trailGeo, new THREE.MeshBasicMaterial({ color: c, transparent: true, opacity: 0.5 - i * 0.05 }));
        scene.add(t);
        return t;
      });
      scene.add(mesh);
      orbs.push({ mesh, trail, from: h.from, to: h.to, t: 0 });
      a.jumpUntil = clock.elapsedTime + 0.9; // the same 0.9 s hop the cheer uses
    }

    const size = () => {
      const w = el.clientWidth, h = el.clientHeight;
      renderer.setSize(w, h, false);
      camera.aspect = w / Math.max(h, 1);
      camera.fov = 38;
      camera.updateProjectionMatrix();
      // the walking area follows the panel, but never so narrow that the bots pile up
      bounds.x = THREE.MathUtils.clamp(camera.aspect * 1.9, 2.3, 3.2);
      bounds.z = camera.aspect < 1 ? 1.5 : 1.15;
      // back the camera off until the whole floor (plus a bot's width each side) fits across
      const halfWidth = bounds.x + 0.9;
      const fit = halfWidth / (Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * camera.aspect) - 0.35;
      camDist = Math.max(camera.aspect < 1.1 ? 6.3 : 6.6, fit);
      const fog = scene.fog as THREE.Fog;
      fog.near = 9 * camDist / 6.6;
      fog.far = 17 * camDist / 6.6;
      layoutHomes();
    };
    const ro = new ResizeObserver(size);
    ro.observe(el);
    size();
    for (const r of rigs) { // start every bot near its own spot, so the first frame isn't a huddle
      r.pos.copy(r.home);
      r.target.copy(r.pos);
      r.root.position.set(r.pos.x, 0, r.pos.y);
    }

    const ray = new THREE.Raycaster();
    const ptr = new THREE.Vector2(-9, -9);
    let hovered: Rig | undefined;
    const onMove = (e: PointerEvent) => {
      const r = el.getBoundingClientRect();
      ptr.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    };
    const onLeave = () => ptr.set(-9, -9);
    const onClick = (e: MouseEvent) => {
      // pick what is under the finger right now (a tap on a phone or tablet has no hover before it)
      onMove(e as PointerEvent);
      ray.setFromCamera(ptr, camera);
      const hit = ray.intersectObjects(rigs.map((r) => r.hit), false)[0];
      const picked = hit ? rigs.find((r) => r.hit === hit.object) : hovered;
      if (picked) live.current.onPick?.(picked.id);
    };
    el.addEventListener("pointermove", onMove);
    el.addEventListener("pointerleave", onLeave);
    el.addEventListener("click", onClick);

    const clock = new THREE.Clock();
    const camPos = new THREE.Vector3();
    const tmp = new THREE.Vector3();
    const local = new THREE.Vector3();
    let frame = 0;

    const tick = () => {
      frame = requestAnimationFrame(tick);
      const dt = Math.min(clock.getDelta(), 0.05);
      const t = clock.elapsedTime;
      const amp = reduced ? 0.3 : 1;
      while (orbQueue.current.length) throwOrb(orbQueue.current.shift()!);

      // camera: a slow drift plus a little parallax from the pointer
      const px = ptr.x > -2 ? ptr.x : 0;
      camera.position.set(Math.sin(t * 0.1) * 0.3 * amp + px * 0.35, 2.7 * camDist / 6.6, camDist);
      camera.lookAt(0, 0.5, -0.35);
      camPos.copy(camera.position);

      ray.setFromCamera(ptr, camera);
      const hit = ray.intersectObjects(rigs.map((r) => r.hit), false)[0];
      hovered = hit ? rigs.find((r) => r.hit === hit.object) : undefined;
      el.style.cursor = hovered ? "pointer" : "default";

      for (const r of rigs) {
        const move = live.current.moves[r.id] ?? "idle";
        const busy = live.current.working.includes(r.id) || move === "think";
        const asks = live.current.asking.includes(r.id) || move === "ask";
        const isHover = hovered === r;
        if (move !== r.lastMove) {
          if (move === "cheer") {
            r.jumpUntil = t + 0.9;
            emit(tmp.set(r.pos.x, 1.3, r.pos.y), botColor(r.id), 26, "confetti");
          }
          r.lastMove = move;
        }

        // where to go
        if (busy) r.target.copy(r.home);
        else if (asks) r.target.set(THREE.MathUtils.clamp(r.pos.x, -2, 2), bounds.cz + bounds.z * 0.9); // to the front, still on the floor
        else if (t > r.nextWander && t > r.daydreamUntil) {
          const a = Math.random() * Math.PI * 2, d = Math.sqrt(Math.random());
          r.target.set(Math.cos(a) * d * bounds.x, bounds.cz + Math.sin(a) * d * bounds.z);
          r.nextWander = t + 3 + Math.random() * 5;
          if (r.id === "web" && Math.random() < 0.6) { r.daydreamUntil = t + 1.6; r.dashUntil = t + 2.4; }
        }
        const stopped = isHover || t < r.daydreamUntil;
        const to = r.target.clone().sub(r.pos);
        const dist = to.length();
        let sp = r.speed * (busy ? 1.6 : 1) * (t < r.dashUntil && t > r.daydreamUntil ? 3.2 : 1);
        if (dist < 0.5) sp *= dist / 0.5;
        const want = stopped || dist < 0.04 ? new THREE.Vector2() : to.normalize().multiplyScalar(sp);
        r.vel.lerp(want, Math.min(1, dt * 3.5));
        for (const o of rigs) {
          if (o === r) continue;
          const d = r.pos.clone().sub(o.pos);
          const l = d.length();
          if (l > 0 && l < 1.25) r.vel.add(d.multiplyScalar(((1.25 - l) / l) * dt * 14)); // personal space: no piles
        }
        r.pos.addScaledVector(r.vel, dt);
        const e = (r.pos.x / bounds.x) ** 2 + ((r.pos.y - bounds.cz) / bounds.z) ** 2;
        if (e > 1) { const k = 1 / Math.sqrt(e); r.pos.set(r.pos.x * k, bounds.cz + (r.pos.y - bounds.cz) * k); }
        const moving = r.vel.length() > 0.08;

        // which way to face: walking direction, or you when it needs you / you hover it
        // standing still they turn to you (so you see their faces); walking they face where they go
        // they keep their faces to you: walking, they turn at most ~55 degrees away from the camera
        let face = Math.atan2(camPos.x - r.pos.x, camPos.z - r.pos.y);
        if (moving && !isHover && !asks) {
          const walk = Math.atan2(r.vel.x, r.vel.y);
          const off = Math.atan2(Math.sin(walk - face), Math.cos(walk - face));
          face += THREE.MathUtils.clamp(off, -0.95, 0.95);
        }
        let dh = face - r.heading;
        dh = Math.atan2(Math.sin(dh), Math.cos(dh));
        r.heading += dh * Math.min(1, dt * 6);
        r.root.position.set(r.pos.x, 0, r.pos.y);
        r.root.rotation.y = r.heading;

        // gait and personality
        const step = t * (6 + r.speed * 6);
        let y = Math.sin(t * 1.7 + r.speed * 9) * 0.035 * amp;
        let tiltZ = 0, tiltX = 0, sy = 1;
        if (moving) {
          if (r.id === "scout") { y = Math.abs(Math.sin(step * 0.7)) * 0.32 * amp; }
          else if (r.id === "inbox") { tiltZ = Math.sin(step) * 0.16 * amp; y = Math.abs(Math.sin(step)) * 0.05; }
          else if (r.id === "web") { y = 0.06 + Math.sin(step * 0.5) * 0.04; }
          else if (r.id === "desk") { y = Math.abs(Math.sin(step * 1.4)) * 0.03; }
          else { y = Math.abs(Math.sin(step)) * 0.08 * amp; tiltZ = Math.sin(step) * 0.05; }
        }
        if (!moving && !busy && !asks && t > r.nextQuirk) { r.quirkUntil = t + 1.4; r.nextQuirk = t + 6 + Math.random() * 7; }
        const quirk = t < r.quirkUntil;
        if (quirk && r.id === "s") tiltX = 0.35; // checks the compass
        if (r.extra.needle) r.extra.needle.rotation.z = quirk ? Math.sin(t * 9) * 0.8 : Math.sin(t * 0.8) * 0.2;
        if (r.extra.quill) r.extra.quill.rotation.z = -0.5 + (quirk || busy ? Math.sin(t * 14) * 0.25 : 0);
        if (r.extra.monocle) r.extra.monocle.scale.setScalar(quirk || busy ? 1.15 + Math.sin(t * 6) * 0.08 : 1);
        if (r.extra.tip) (r.extra.tip as THREE.Mesh).scale.setScalar(busy ? 1.3 + Math.sin(t * 12) * 0.3 : 1);
        if (r.extra.ball && r.id === "web" && t < r.daydreamUntil) r.extra.ball.rotation.x = -0.25;
        else if (r.extra.ball) r.extra.ball.rotation.x *= 0.9;
        if (r.extra.heart) r.extra.heart.scale.setScalar(1 + Math.max(0, Math.sin(t * 4)) * 0.15);
        if (busy) { y += Math.sin(t * 9) * 0.03; if (Math.random() < dt * 9) emit(tmp.set(r.pos.x, 1.25, r.pos.y), botColor(r.id), 1, "spark"); }
        if (asks) tiltZ = Math.sin(t * 5) * 0.14 * amp;
        if (t < r.jumpUntil) { const k = (r.jumpUntil - t) / 0.9; y += Math.sin(k * Math.PI) * 0.55; r.body.rotation.y = (1 - k) * Math.PI * 2; } else r.body.rotation.y = 0;
        if (t < r.catchUntil) sy = 1 - Math.sin(((r.catchUntil - t) / 0.4) * Math.PI) * 0.18;
        if (move === "oops") { y = -0.05; tiltZ = 0.25; sy = 0.86; }
        if (move === "talk") sy *= 1 + Math.sin(t * 22) * 0.04;
        r.body.position.y = y;
        r.body.rotation.z = tiltZ;
        r.body.rotation.x = tiltX;
        r.body.scale.set(1 / Math.sqrt(sy), sy, 1 / Math.sqrt(sy));
        const glowBase = r.id === "s" ? 0.16 : 0; // S is white: a little inner light keeps it from looking grey
        r.skin.emissiveIntensity += ((busy ? 0.22 + Math.sin(t * 6) * 0.08 : isHover ? 0.12 : glowBase) - r.skin.emissiveIntensity) * Math.min(1, dt * 6);
        (r.shadow.material as THREE.MeshBasicMaterial).opacity = 0.9 - y * 1.1;
        const sign = live.current.signs?.[r.id] ?? (asks ? "🙋" : "");
        const bub = r.bubble.material as THREE.SpriteMaterial;
        if (sign && sign !== r.signShown) {
          bub.map = texFor(sign);
          r.signShown = sign;
          r.bubble.scale.setScalar(0.2); // pops in
        }
        bub.opacity += ((sign ? 1 : 0) - bub.opacity) * Math.min(1, dt * 8);
        r.bubble.scale.setScalar(THREE.MathUtils.lerp(r.bubble.scale.x, 0.46, Math.min(1, dt * 10)));
        r.bubble.position.y = 1.55 + Math.sin(t * 4) * 0.05;
        const mouth = r.extra.mouth;
        if (mouth) {
          const open = move === "talk" ? 1 + Math.abs(Math.sin(t * 16)) * 1.5 : move === "cheer" ? 1.7 : move === "ask" || move === "think" ? 0.55 : 1;
          mouth.scale.set(move === "cheer" ? 1.3 : move === "think" || move === "ask" ? 0.6 : 1, move === "oops" ? -0.9 : open, 1);
        }

        // eyes look at you, at the floor while working, or ahead; blink now and then
        const lookAt = isHover || asks ? camPos : busy ? tmp.set(r.pos.x, 0, r.pos.y + 1) : tmp.set(r.pos.x + r.vel.x * 3, 0.6, r.pos.y + r.vel.y * 3 + 2);
        for (const e of r.eyes) {
          local.copy(lookAt);
          e.pupil.parent!.worldToLocal(local);
          local.sub(e.base).normalize();
          const dayX = r.id === "web" && t < r.daydreamUntil ? 0.7 : 0;
          const dayY = r.id === "web" && t < r.daydreamUntil ? 0.7 : 0;
          e.pupil.position.set(e.base.x + (local.x + dayX) * e.range, e.base.y + (local.y + dayY) * e.range * 0.8, e.base.z);
        }
        const blink = Math.sin(t * 0.9 + r.speed * 20) > 0.985 || move === "oops" ? 0.15 : 1;
        r.eyeScale.forEach((w) => (w.scale.y = THREE.MathUtils.lerp(w.scale.y, blink, Math.min(1, dt * 20))));

        tmp.set(r.pos.x, 0, r.pos.y).project(camera);
        const w = el.clientWidth, h = el.clientHeight;
        r.label.style.transform = `translate(-50%, 0) translate(${(tmp.x * 0.5 + 0.5) * w}px, ${(-tmp.y * 0.5 + 0.5) * h + 4}px)`;
        r.label.className = `room-label${busy ? " busy" : ""}${asks ? " ask" : ""}${isHover ? " hover" : ""}`;
        (r.label.lastChild as HTMLElement).textContent = asks ? "needs your OK" : busy ? "working…" : isHover ? "say hi" : "";
      }

      // task orbs fly in an arc and the teammate catches them
      for (let i = orbs.length - 1; i >= 0; i--) {
        const o = orbs[i];
        const a = byId[o.from], b = byId[o.to];
        o.t += dt / 1.0;
        const k = Math.min(o.t, 1);
        const from = new THREE.Vector3(a.pos.x, 1.1, a.pos.y), to = new THREE.Vector3(b.pos.x, 1.0, b.pos.y);
        const mid = from.clone().lerp(to, 0.5).add(new THREE.Vector3(0, 1.4, 0));
        const at = (u: number) => new THREE.Vector3().copy(from).multiplyScalar((1 - u) ** 2)
          .add(mid.clone().multiplyScalar(2 * (1 - u) * u)).add(to.clone().multiplyScalar(u * u));
        o.mesh.position.copy(at(k));
        o.trail.forEach((m, j) => m.position.copy(at(Math.max(0, k - (j + 1) * 0.035))));
        if (o.t >= 1) {
          b.catchUntil = t + 0.4;
          emit(to, botColor(o.to), 10, "spark");
          scene.remove(o.mesh, ...o.trail);
          (o.mesh.material as THREE.Material).dispose();
          o.trail.forEach((m) => (m.material as THREE.Material).dispose());
          orbs.splice(i, 1);
        }
      }

      for (let i = particles.length - 1; i >= 0; i--) {
        const p = particles[i];
        p.life += dt;
        p.vel.y -= (p.max > 1 ? 4.5 : -0.3) * dt;
        p.mesh.position.addScaledVector(p.vel, dt);
        p.mesh.rotation.x += p.spin * dt;
        p.mesh.rotation.y += p.spin * dt * 0.7;
        (p.mesh.material as THREE.MeshBasicMaterial).opacity = 1 - p.life / p.max;
        if (p.life >= p.max || p.mesh.position.y < 0) {
          scene.remove(p.mesh);
          (p.mesh.material as THREE.Material).dispose();
          particles.splice(i, 1);
        }
      }
      dust.rotation.y = t * 0.02;
      renderer.render(scene, camera);
    };
    tick();

    return () => {
      cancelAnimationFrame(frame);
      ro.disconnect();
      el.removeEventListener("pointermove", onMove);
      el.removeEventListener("pointerleave", onLeave);
      el.removeEventListener("click", onClick);
      scene.traverse((obj) => {
        const m = obj as THREE.Mesh;
        m.geometry?.dispose?.();
        const mat = m.material as THREE.Material | THREE.Material[] | undefined;
        if (Array.isArray(mat)) mat.forEach((x) => x.dispose());
        else mat?.dispose?.();
      });
      shadowTex.dispose();
      Object.values(signTex).forEach((tx) => tx.dispose());
      renderer.dispose();
      el.innerHTML = "";
    };
    // The room is rebuilt only when the crew changes; moves and states arrive through `live`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ids]);

  return <div className="room" ref={host} style={{ height }} aria-label="The Crew Room: the bots at work" />;
}
