import { Canvas, useFrame } from "@react-three/fiber";
import { Billboard, Line, OrbitControls, Text } from "@react-three/drei";
import { useMemo, useRef } from "react";
import * as THREE from "three";
import { WorkflowNode } from "../api";

const STATUS_COLOR: Record<string, string> = {
  ok: "#2dd4bf",
  error: "#fb7185",
  pending: "#64748b",
  deferred: "#a78bfa",
};

function nodeColor(n: WorkflowNode): string {
  return STATUS_COLOR[n.status || "pending"] || "#64748b";
}

// Serpentine layout so long pipelines stay framed nicely in 3D.
function layout(count: number): [number, number, number][] {
  const perRow = 5;
  const positions: [number, number, number][] = [];
  for (let i = 0; i < count; i++) {
    const row = Math.floor(i / perRow);
    let col = i % perRow;
    if (row % 2 === 1) col = perRow - 1 - col; // reverse every other row
    const x = (col - (perRow - 1) / 2) * 2.6;
    const y = -(row * 2.4) + 2;
    const z = Math.sin(i * 0.6) * 0.8;
    positions.push([x, y, z]);
  }
  return positions;
}

function NodeMesh({
  node,
  position,
  selected,
  onSelect,
}: {
  node: WorkflowNode;
  position: [number, number, number];
  selected: boolean;
  onSelect: () => void;
}) {
  const ref = useRef<THREE.Mesh>(null);
  const c = nodeColor(node);
  const active = node.status === "ok" || node.status === "error";

  useFrame((s) => {
    if (!ref.current) return;
    if (selected || node.status === "error") {
      const p = 1 + Math.sin(s.clock.elapsedTime * 4) * 0.09;
      ref.current.scale.setScalar(p);
    } else {
      ref.current.scale.setScalar(1);
    }
    ref.current.rotation.y += 0.005;
  });

  return (
    <group position={position}>
      <mesh
        ref={ref}
        onClick={(e) => {
          e.stopPropagation();
          onSelect();
        }}
        onPointerOver={(e) => {
          e.stopPropagation();
          document.body.style.cursor = "pointer";
        }}
        onPointerOut={() => (document.body.style.cursor = "default")}
      >
        <icosahedronGeometry args={[0.6, 0]} />
        <meshStandardMaterial
          color={c}
          emissive={c}
          emissiveIntensity={active ? 0.7 : 0.25}
          metalness={0.3}
          roughness={0.35}
          flatShading
        />
      </mesh>
      {selected && (
        <mesh scale={1.4}>
          <icosahedronGeometry args={[0.6, 0]} />
          <meshBasicMaterial color="#ffffff" wireframe transparent opacity={0.35} />
        </mesh>
      )}
      <Billboard position={[0, 0.95, 0]}>
        <Text fontSize={0.26} color="#e2e8f0" anchorX="center" anchorY="middle">
          {node.label}
        </Text>
      </Billboard>
      {active && (
        <Billboard position={[0, -0.95, 0]}>
          <Text fontSize={0.2} color={c} anchorX="center" anchorY="middle">
            {node.status === "error" ? "error" : `${Math.round(node.duration_ms || 0)}ms`}
          </Text>
        </Billboard>
      )}
    </group>
  );
}

// A pulse of light travelling each edge to convey execution flow.
function FlowPulse({
  from,
  to,
  offset,
}: {
  from: [number, number, number];
  to: [number, number, number];
  offset: number;
}) {
  const ref = useRef<THREE.Mesh>(null);
  const a = useMemo(() => new THREE.Vector3(...from), [from]);
  const b = useMemo(() => new THREE.Vector3(...to), [to]);
  useFrame((s) => {
    if (!ref.current) return;
    const t = (s.clock.elapsedTime * 0.4 + offset) % 1;
    ref.current.position.lerpVectors(a, b, t);
  });
  return (
    <mesh ref={ref}>
      <sphereGeometry args={[0.09, 12, 12]} />
      <meshBasicMaterial color="#ffffff" />
    </mesh>
  );
}

function Scene({
  nodes,
  selected,
  onSelect,
}: {
  nodes: WorkflowNode[];
  selected: number | null;
  onSelect: (i: number) => void;
}) {
  const positions = useMemo(() => layout(nodes.length), [nodes.length]);
  return (
    <>
      <ambientLight intensity={0.6} />
      <pointLight position={[6, 6, 8]} intensity={1.1} />
      <pointLight position={[-6, -4, -2]} intensity={0.6} color="#a78bfa" />

      {positions.slice(0, -1).map((p, i) => {
        const edgeActive = nodes[i].status === "ok" && nodes[i + 1].status === "ok";
        return (
          <group key={`edge-${i}`}>
            <Line
              points={[p, positions[i + 1]]}
              color={edgeActive ? "#2dd4bf" : "#334155"}
              lineWidth={edgeActive ? 1.8 : 1}
              transparent
              opacity={edgeActive ? 0.7 : 0.3}
            />
            {edgeActive && (
              <FlowPulse from={p} to={positions[i + 1]} offset={i * 0.12} />
            )}
          </group>
        );
      })}

      {nodes.map((n, i) => (
        <NodeMesh
          key={n.id}
          node={n}
          position={positions[i]}
          selected={selected === i}
          onSelect={() => onSelect(i)}
        />
      ))}

      <OrbitControls enablePan={false} enableDamping dampingFactor={0.1} minDistance={6} maxDistance={26} />
    </>
  );
}

export default function WorkflowScene(props: {
  nodes: WorkflowNode[];
  selected: number | null;
  onSelect: (i: number) => void;
}) {
  return (
    <Canvas
      camera={{ position: [0, -2, 14], fov: 55 }}
      dpr={[1, 1.5]}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      style={{ background: "transparent" }}
    >
      <Scene {...props} />
    </Canvas>
  );
}
