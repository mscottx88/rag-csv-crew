/**
 * CircuitBoard
 * Fixed-position PCB-style wireframe background.
 * 480×480 tile — signal traces routed with 45° elbows between component
 * clusters. No repetitive straight grid lines or bold power buses.
 * Adds: DIP-8 package, mounting holes, silk-screen designators, test points,
 * fiducial marks, decoupling cap array, and additional trace fill.
 * Purely decorative — pointer events disabled.
 */

import React from 'react';
import './CircuitBoard.css';

/** Solder pad positions (component pins + routing waypoints). */
const PADS: readonly [number, number][] = [
  // IC1 — SOIC-8
  [52,68],[52,76],[52,84],[52,92],
  [80,68],[80,76],[80,84],[80,92],
  // IC2 — QFP left/right pins
  [196,180],[196,192],[196,208],[196,220],
  [264,180],[264,192],[264,208],[264,220],
  // IC2 — QFP top/bottom pins
  [210,168],[222,168],[236,168],[248,168],
  [210,236],[222,236],[236,236],[248,236],
  // IC3 — DIP-8 left/right pins
  [130,355],[130,365],[130,375],[130,385],
  [170,355],[170,365],[170,375],[170,385],
  // Crystal leads
  [368,80],[418,80],
  // Connector J1
  [308,391],[320,391],[332,391],[344,391],[356,391],
  // Decoupling caps below IC2
  [204,248],[216,248],[228,248],[240,248],
  // Routing waypoints / test points
  [104,76],[124,56],[192,56],[300,186],
  [80,280],[316,302],[420,320],[100,420],
  [380,300],[240,420],
];

/** Via positions (ring + centre dot). */
const VIAS: readonly [number, number][] = [
  [160,192],[290,100],[380,148],[80,320],
  [240,60],[420,260],[60,360],[104,210],[240,420],
];

/** Single 480×480 PCB tile. */
function PcbTile(): React.ReactElement {
  const tg = 'rgba(57,255,20,0.16)';   // green signal trace
  const tc = 'rgba(0,220,240,0.11)';   // cyan inner-layer trace
  const p  = 'rgba(57,255,20,0.30)';   // solder pad fill
  const pr = 'rgba(57,255,20,0.22)';   // component outline
  const sk = 'rgba(57,255,20,0.28)';   // silk-screen text / marks
  const sw = 1;

  return (
    <g>
      {/* ══ Green signal traces — routed with 45° bends ══ */}

      {/* Route A: IC1 right-pin escape → 45° NE → IC2 top entry */}
      <line x1="80"  y1="76"  x2="104" y2="76"  stroke={tg} strokeWidth={sw} />
      <line x1="104" y1="76"  x2="124" y2="56"  stroke={tg} strokeWidth={sw} />
      <line x1="124" y1="56"  x2="192" y2="56"  stroke={tg} strokeWidth={sw} />
      <line x1="192" y1="56"  x2="214" y2="78"  stroke={tg} strokeWidth={sw} />
      <line x1="214" y1="78"  x2="214" y2="168" stroke={tg} strokeWidth={sw} />

      {/* Route B: IC1 left escape → 45° SW → left edge */}
      <line x1="52"  y1="76"  x2="32"  y2="76"  stroke={tg} strokeWidth={sw} />
      <line x1="32"  y1="76"  x2="12"  y2="96"  stroke={tg} strokeWidth={sw} />
      <line x1="12"  y1="96"  x2="0"   y2="96"  stroke={tg} strokeWidth={sw} />

      {/* Route C: IC2 left → 45° SW chain → lower-left area */}
      <line x1="196" y1="192" x2="160" y2="192" stroke={tg} strokeWidth={sw} />
      <line x1="160" y1="192" x2="140" y2="212" stroke={tg} strokeWidth={sw} />
      <line x1="140" y1="212" x2="104" y2="212" stroke={tg} strokeWidth={sw} />
      <line x1="104" y1="212" x2="80"  y2="236" stroke={tg} strokeWidth={sw} />
      <line x1="80"  y1="236" x2="80"  y2="280" stroke={tg} strokeWidth={sw} />

      {/* Route D: IC2 right → 45° NE → far-right area */}
      <line x1="264" y1="186" x2="300" y2="186" stroke={tg} strokeWidth={sw} />
      <line x1="300" y1="186" x2="322" y2="164" stroke={tg} strokeWidth={sw} />
      <line x1="322" y1="164" x2="376" y2="164" stroke={tg} strokeWidth={sw} />
      <line x1="376" y1="164" x2="398" y2="142" stroke={tg} strokeWidth={sw} />
      <line x1="398" y1="142" x2="460" y2="142" stroke={tg} strokeWidth={sw} />

      {/* Route E: Crystal right → top-right corner */}
      <line x1="418" y1="80"  x2="452" y2="80"  stroke={tg} strokeWidth={sw} />
      <line x1="452" y1="80"  x2="470" y2="62"  stroke={tg} strokeWidth={sw} />
      <line x1="470" y1="62"  x2="480" y2="62"  stroke={tg} strokeWidth={sw} />

      {/* Route F: Crystal left → 45° SW → IC2 top pin */}
      <line x1="368" y1="80"  x2="340" y2="80"  stroke={tg} strokeWidth={sw} />
      <line x1="340" y1="80"  x2="318" y2="102" stroke={tg} strokeWidth={sw} />
      <line x1="318" y1="102" x2="288" y2="102" stroke={tg} strokeWidth={sw} />
      <line x1="288" y1="102" x2="266" y2="124" stroke={tg} strokeWidth={sw} />
      <line x1="266" y1="124" x2="234" y2="124" stroke={tg} strokeWidth={sw} />
      <line x1="234" y1="124" x2="222" y2="136" stroke={tg} strokeWidth={sw} />
      <line x1="222" y1="136" x2="222" y2="168" stroke={tg} strokeWidth={sw} />

      {/* Route G: IC2 bottom → 45° SE chain → connector pin */}
      <line x1="222" y1="236" x2="222" y2="258" stroke={tg} strokeWidth={sw} />
      <line x1="222" y1="258" x2="244" y2="280" stroke={tg} strokeWidth={sw} />
      <line x1="244" y1="280" x2="284" y2="280" stroke={tg} strokeWidth={sw} />
      <line x1="284" y1="280" x2="302" y2="298" stroke={tg} strokeWidth={sw} />
      <line x1="302" y1="298" x2="316" y2="298" stroke={tg} strokeWidth={sw} />
      <line x1="316" y1="298" x2="316" y2="378" stroke={tg} strokeWidth={sw} />

      {/* Route H: lower-left meander → bottom edge */}
      <line x1="80"  y1="320" x2="60"  y2="340" stroke={tg} strokeWidth={sw} />
      <line x1="60"  y1="340" x2="60"  y2="378" stroke={tg} strokeWidth={sw} />
      <line x1="60"  y1="378" x2="40"  y2="398" stroke={tg} strokeWidth={sw} />
      <line x1="40"  y1="398" x2="0"   y2="398" stroke={tg} strokeWidth={sw} />

      {/* Route I: top-left corner stub */}
      <line x1="0"   y1="38"  x2="40"  y2="38"  stroke={tg} strokeWidth={sw} />
      <line x1="40"  y1="38"  x2="52"  y2="50"  stroke={tg} strokeWidth={sw} />

      {/* Route J: right-side vertical + elbow */}
      <line x1="460" y1="142" x2="460" y2="200" stroke={tg} strokeWidth={sw} />
      <line x1="460" y1="200" x2="480" y2="220" stroke={tg} strokeWidth={sw} />

      {/* Route K: bottom sections + right-side wrap */}
      <line x1="100" y1="380" x2="100" y2="420" stroke={tg} strokeWidth={sw} />
      <line x1="100" y1="420" x2="80"  y2="440" stroke={tg} strokeWidth={sw} />
      <line x1="80"  y1="440" x2="0"   y2="440" stroke={tg} strokeWidth={sw} />
      <line x1="160" y1="380" x2="160" y2="416" stroke={tg} strokeWidth={sw} />
      <line x1="160" y1="416" x2="182" y2="438" stroke={tg} strokeWidth={sw} />
      <line x1="182" y1="438" x2="260" y2="438" stroke={tg} strokeWidth={sw} />
      <line x1="420" y1="260" x2="440" y2="278" stroke={tg} strokeWidth={sw} />
      <line x1="440" y1="278" x2="440" y2="358" stroke={tg} strokeWidth={sw} />
      <line x1="440" y1="358" x2="420" y2="378" stroke={tg} strokeWidth={sw} />
      <line x1="420" y1="378" x2="378" y2="378" stroke={tg} strokeWidth={sw} />

      {/* Route L: DIP left pins → existing via at (80, 320) */}
      <line x1="130" y1="355" x2="116" y2="355" stroke={tg} strokeWidth={sw} />
      <line x1="116" y1="355" x2="96"  y2="375" stroke={tg} strokeWidth={sw} />
      <line x1="96"  y1="375" x2="80"  y2="375" stroke={tg} strokeWidth={sw} />
      <line x1="80"  y1="375" x2="80"  y2="320" stroke={tg} strokeWidth={sw} />

      {/* Route M: DIP right pins → diagonal stub toward IC2 area */}
      <line x1="170" y1="365" x2="208" y2="365" stroke={tg} strokeWidth={sw} />
      <line x1="208" y1="365" x2="226" y2="347" stroke={tg} strokeWidth={sw} />
      <line x1="226" y1="347" x2="258" y2="347" stroke={tg} strokeWidth={sw} />

      {/* Route N: test point TP1 → right-side fill */}
      <line x1="380" y1="300" x2="400" y2="300" stroke={tg} strokeWidth={sw} />
      <line x1="400" y1="300" x2="420" y2="280" stroke={tg} strokeWidth={sw} />
      <line x1="420" y1="280" x2="460" y2="280" stroke={tg} strokeWidth={sw} />

      {/* Route P: bottom connection to connector left side */}
      <line x1="260" y1="438" x2="294" y2="438" stroke={tg} strokeWidth={sw} />
      <line x1="294" y1="438" x2="294" y2="402" stroke={tg} strokeWidth={sw} />

      {/* ══ Cyan inner-layer traces ══ */}

      {/* Cyan 1: left side diagonal chain */}
      <line x1="0"   y1="220" x2="40"  y2="220" stroke={tc} strokeWidth={sw} />
      <line x1="40"  y1="220" x2="62"  y2="198" stroke={tc} strokeWidth={sw} />
      <line x1="62"  y1="198" x2="102" y2="198" stroke={tc} strokeWidth={sw} />
      <line x1="102" y1="198" x2="122" y2="178" stroke={tc} strokeWidth={sw} />
      <line x1="122" y1="178" x2="162" y2="178" stroke={tc} strokeWidth={sw} />

      {/* Cyan 2: IC2 right lower → far-right bottom arc */}
      <line x1="264" y1="208" x2="302" y2="208" stroke={tc} strokeWidth={sw} />
      <line x1="302" y1="208" x2="322" y2="228" stroke={tc} strokeWidth={sw} />
      <line x1="322" y1="228" x2="380" y2="228" stroke={tc} strokeWidth={sw} />
      <line x1="380" y1="228" x2="402" y2="250" stroke={tc} strokeWidth={sw} />
      <line x1="402" y1="250" x2="402" y2="318" stroke={tc} strokeWidth={sw} />
      <line x1="402" y1="318" x2="422" y2="318" stroke={tc} strokeWidth={sw} />

      {/* Cyan 3: top-centre diagonal run */}
      <line x1="198" y1="0"   x2="242" y2="0"   stroke={tc} strokeWidth={sw} />
      <line x1="242" y1="0"   x2="264" y2="22"  stroke={tc} strokeWidth={sw} />
      <line x1="264" y1="22"  x2="300" y2="22"  stroke={tc} strokeWidth={sw} />
      <line x1="300" y1="22"  x2="340" y2="62"  stroke={tc} strokeWidth={sw} />
      <line x1="340" y1="62"  x2="368" y2="62"  stroke={tc} strokeWidth={sw} />

      {/* Cyan 4: mid-left to IC2 area */}
      <line x1="0"   y1="298" x2="80"  y2="298" stroke={tc} strokeWidth={sw} />
      <line x1="80"  y1="298" x2="100" y2="278" stroke={tc} strokeWidth={sw} />
      <line x1="100" y1="278" x2="162" y2="278" stroke={tc} strokeWidth={sw} />
      <line x1="162" y1="278" x2="180" y2="260" stroke={tc} strokeWidth={sw} />
      <line x1="180" y1="260" x2="196" y2="260" stroke={tc} strokeWidth={sw} />

      {/* Cyan 5: connector to right edge */}
      <line x1="356" y1="378" x2="362" y2="358" stroke={tc} strokeWidth={sw} />
      <line x1="362" y1="358" x2="422" y2="358" stroke={tc} strokeWidth={sw} />
      <line x1="422" y1="358" x2="442" y2="338" stroke={tc} strokeWidth={sw} />
      <line x1="442" y1="338" x2="480" y2="338" stroke={tc} strokeWidth={sw} />

      {/* Cyan 6: lower-right fill */}
      <line x1="380" y1="460" x2="420" y2="420" stroke={tc} strokeWidth={sw} />
      <line x1="420" y1="420" x2="460" y2="420" stroke={tc} strokeWidth={sw} />
      <line x1="460" y1="420" x2="480" y2="420" stroke={tc} strokeWidth={sw} />

      {/* Cyan 7: DIP area inner layer */}
      <line x1="130" y1="385" x2="110" y2="385" stroke={tc} strokeWidth={sw} />
      <line x1="110" y1="385" x2="90"  y2="405" stroke={tc} strokeWidth={sw} />
      <line x1="90"  y1="405" x2="0"   y2="405" stroke={tc} strokeWidth={sw} />
      <line x1="170" y1="385" x2="196" y2="385" stroke={tc} strokeWidth={sw} />
      <line x1="196" y1="385" x2="210" y2="399" stroke={tc} strokeWidth={sw} />
      <line x1="210" y1="399" x2="240" y2="399" stroke={tc} strokeWidth={sw} />

      {/* ══ Solder pads ══ */}
      {PADS.map(([cx, cy]) => (
        <circle key={`pad-${cx}-${cy}`} cx={cx} cy={cy} r="2.5" fill={p} />
      ))}

      {/* ══ Through-hole vias ══ */}
      {VIAS.map(([cx, cy]) => (
        <g key={`via-${cx}-${cy}`}>
          <circle cx={cx} cy={cy} r="5"  fill="none" stroke={pr} strokeWidth="1" />
          <circle cx={cx} cy={cy} r="2"  fill={p} />
        </g>
      ))}

      {/* ══ Mounting holes — one at each tile corner ══ */}
      {([
        [20,20],[460,20],[20,460],[460,460],
      ] as const).map(([cx, cy]) => (
        <g key={`mh-${cx}-${cy}`}>
          <circle cx={cx} cy={cy} r="9"   fill="none" stroke={pr} strokeWidth="0.75" />
          <circle cx={cx} cy={cy} r="5.5" fill="none" stroke={pr} strokeWidth="0.5"  />
          <circle cx={cx} cy={cy} r="2"   fill={p} />
        </g>
      ))}

      {/* ══ Fiducial marks (pick-and-place alignment) ══ */}
      {([
        [80,460],[440,460],[440,20],
      ] as const).map(([cx, cy]) => (
        <g key={`fid-${cx}-${cy}`}>
          <circle cx={cx} cy={cy} r="5"   fill="none" stroke={pr} strokeWidth="0.5"  />
          <circle cx={cx} cy={cy} r="1.5" fill={p} />
        </g>
      ))}

      {/* ══ Test points ══ */}
      <circle cx="380" cy="300" r="4.5" fill="none" stroke={pr} strokeWidth="0.75" />
      <circle cx="380" cy="300" r="2"   fill={p} />
      <text x="387" y="298" fontFamily="Courier New,monospace" fontSize="4.5" fill={sk}>TP1</text>

      <circle cx="240" cy="420" r="4.5" fill="none" stroke={pr} strokeWidth="0.75" />
      <text x="247" y="418" fontFamily="Courier New,monospace" fontSize="4.5" fill={sk}>TP2</text>

      {/* ══ IC1 — SOIC-8 (body 52–80, 60–104) ══ */}
      <rect x="52" y="60" width="28" height="44" rx="2"
            fill="none" stroke={pr} strokeWidth="1" />
      {([68,76,84,92] as const).map((y) => (
        <g key={`s8-${y}`}>
          <line x1="52" y1={y} x2="46" y2={y} stroke={pr} strokeWidth="0.75" />
          <line x1="80" y1={y} x2="86" y2={y} stroke={pr} strokeWidth="0.75" />
        </g>
      ))}
      <circle cx="55" cy="63" r="1.5" fill={pr} />
      <text x="57" y="57" fontFamily="Courier New,monospace" fontSize="5" fill={sk}>U1</text>

      {/* ══ IC2 — QFP (body 196–264, 168–236) ══ */}
      <rect x="196" y="168" width="68" height="68" rx="2"
            fill="none" stroke={pr} strokeWidth="1" />
      {([180,192,208,220] as const).map((y) => (
        <g key={`qfp-v-${y}`}>
          <line x1="196" y1={y} x2="190" y2={y} stroke={pr} strokeWidth="0.75" />
          <line x1="264" y1={y} x2="270" y2={y} stroke={pr} strokeWidth="0.75" />
        </g>
      ))}
      {([210,222,236,248] as const).map((x) => (
        <g key={`qfp-h-${x}`}>
          <line x1={x} y1="168" x2={x} y2="162" stroke={pr} strokeWidth="0.75" />
          <line x1={x} y1="236" x2={x} y2="242" stroke={pr} strokeWidth="0.75" />
        </g>
      ))}
      <path d="M212,168 a4,4 0 0,0 8,0" fill="none" stroke={pr} strokeWidth="0.75" />
      <text x="200" y="163" fontFamily="Courier New,monospace" fontSize="5" fill={sk}>U2</text>

      {/* ══ IC3 — DIP-8 (body 128–172, 344–394) ══ */}
      <rect x="128" y="344" width="44" height="50" rx="2"
            fill="none" stroke={pr} strokeWidth="1" />
      {/* Centre line (IC body division) */}
      <line x1="150" y1="344" x2="150" y2="394" stroke={pr} strokeWidth="0.4" />
      {/* Pin-1 notch */}
      <path d="M145,344 a5,5 0 0,1 10,0" fill="none" stroke={pr} strokeWidth="0.75" />
      {/* Through-hole pins */}
      {([355,365,375,385] as const).map((y) => (
        <g key={`dip-${y}`}>
          <circle cx={130} cy={y} r="3.5" fill="none" stroke={pr} strokeWidth="0.75" />
          <circle cx={130} cy={y} r="1.5" fill={p} />
          <circle cx={170} cy={y} r="3.5" fill="none" stroke={pr} strokeWidth="0.75" />
          <circle cx={170} cy={y} r="1.5" fill={p} />
        </g>
      ))}
      <text x="134" y="340" fontFamily="Courier New,monospace" fontSize="5" fill={sk}>U3</text>

      {/* ══ Crystal X1 (cx=393, cy=80) ══ */}
      <ellipse cx="393" cy="80" rx="20" ry="12"
               fill="none" stroke={pr} strokeWidth="0.75" />
      <line x1="373" y1="80" x2="355" y2="80" stroke={pr} strokeWidth="0.75" />
      <line x1="413" y1="80" x2="430" y2="80" stroke={pr} strokeWidth="0.75" />
      {/* Load caps */}
      <rect x="340" y="77" width="9" height="7" rx="0.5" fill="none" stroke={pr} strokeWidth="0.75" />
      <rect x="431" y="77" width="9" height="7" rx="0.5" fill="none" stroke={pr} strokeWidth="0.75" />
      <text x="378" y="73" fontFamily="Courier New,monospace" fontSize="5" fill={sk}>X1</text>

      {/* ══ Connector J1 — 5-pin (296–368, 378–402) ══ */}
      <rect x="296" y="378" width="72" height="24" rx="1"
            fill="none" stroke={pr} strokeWidth="0.75" />
      {([308,320,332,344,356] as const).map((x) => (
        <circle key={`cn-${x}`} cx={x} cy="390" r="3"
                fill="none" stroke={pr} strokeWidth="0.75" />
      ))}
      <text x="300" y="374" fontFamily="Courier New,monospace" fontSize="5" fill={sk}>J1</text>

      {/* ══ Inductor L1 — coil on IC2-right route ══ */}
      <path d="M338,186 q5,-9 10,0 q5,-9 10,0 q5,-9 10,0 q5,-9 10,0"
            fill="none" stroke={pr} strokeWidth="0.75" />
      <text x="338" y="198" fontFamily="Courier New,monospace" fontSize="5" fill={sk}>L1</text>

      {/* ══ Resistors ══ */}
      <rect x="90"  y="73" width="20" height="6" rx="1.5"
            fill="none" stroke={pr} strokeWidth="0.75" />
      <text x="93" y="69" fontFamily="Courier New,monospace" fontSize="4.5" fill={sk}>R1</text>

      <rect x="156" y="36" width="6" height="20" rx="1.5"
            fill="none" stroke={pr} strokeWidth="0.75" />
      <text x="159" y="32" fontFamily="Courier New,monospace" fontSize="4.5" fill={sk}>R2</text>

      <rect x="254" y="277" width="6" height="20" rx="1.5"
            fill="none" stroke={pr} strokeWidth="0.75" />
      <text x="258" y="273" fontFamily="Courier New,monospace" fontSize="4.5" fill={sk}>R3</text>

      {/* ══ SMD Capacitors ══ */}
      {/* C1/C2: decoupling on IC1 bottom */}
      <rect x="44"  y="108" width="5" height="6" rx="0.5" fill="none" stroke={pr} strokeWidth="0.75" />
      <rect x="44"  y="117" width="5" height="6" rx="0.5" fill="none" stroke={pr} strokeWidth="0.75" />
      {/* C3: near IC2 right-side route */}
      <rect x="294" y="183" width="5" height="6" rx="0.5" fill="none" stroke={pr} strokeWidth="0.75" />
      <rect x="294" y="193" width="5" height="6" rx="0.5" fill="none" stroke={pr} strokeWidth="0.75" />
      {/* C4: on cyan-4 route */}
      <rect x="130" y="275" width="5" height="6" rx="0.5" fill="none" stroke={pr} strokeWidth="0.75" />
      <rect x="140" y="275" width="5" height="6" rx="0.5" fill="none" stroke={pr} strokeWidth="0.75" />

      {/* ══ Decoupling cap array — 4 caps below IC2 ══ */}
      {([204, 216, 228, 240] as const).map((x) => (
        <g key={`dc-${x}`}>
          {/* Short stub from IC2 bottom pin */}
          <line x1={x} y1="242" x2={x} y2="244" stroke={tg} strokeWidth="0.6" />
          <rect x={x-3} y={244} width={5} height={6} rx="0.5" fill="none" stroke={pr} strokeWidth="0.75" />
          <rect x={x-3} y={253} width={5} height={6} rx="0.5" fill="none" stroke={pr} strokeWidth="0.75" />
        </g>
      ))}
      <text x="200" y="268" fontFamily="Courier New,monospace" fontSize="4.5" fill={sk}>C5–C8</text>
    </g>
  );
}

export const CircuitBoard: React.FC = () => (
  <div className="circuit-board-bg" aria-hidden="true">
    <svg
      className="circuit-board-svg"
      xmlns="http://www.w3.org/2000/svg"
      width="100%"
      height="100%"
    >
      <defs>
        <pattern
          id="pcb-tile"
          x="0"
          y="0"
          width="480"
          height="480"
          patternUnits="userSpaceOnUse"
        >
          <PcbTile />
        </pattern>
      </defs>
      {/* Blurred glow layer */}
      <rect width="100%" height="100%" fill="url(#pcb-tile)"
            className="circuit-board-glow-layer" />
      {/* Sharp detail layer */}
      <rect width="100%" height="100%" fill="url(#pcb-tile)" />
    </svg>
  </div>
);
