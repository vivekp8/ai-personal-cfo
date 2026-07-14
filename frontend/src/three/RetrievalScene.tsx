import { Canvas, useFrame } from "@react-three/fiber";
import { Billboard, Line, OrbitControls, Text } from "@react-three/drei";
import { useMemo, useRef } from "react";
import * as THREE from "three";
import { RagChunk } from "../api";

const KNOWLEDGE = "#22d3ee";
const MEMORY = "#a78bfa";
const QUERY = "#f472b6";

function color(collection: string): string {
  return collection === "user_memory" ? MEMORY : KNOWLEDGE;
}

function QueryNode({ position }: { position: [number, number, number] }) {
  const ref = useRef<THREE.Mesh>(null);
  useFrame((s) => {
    if (ref.current) {
      ref.current.rotation.y += 0.01;
      const p = 1 + Math.sin(s.clock.elapsedTime * 2) * 0.06;
      ref.current.scale.setScalar(p);
    }
  });
  return (
    <group position={position}>
      <mesh ref={ref}>
        <icosahedronGeometry args={[0.42, 1]} />
        <meshStandardMaterial
          color={QUERY}
          emissive={QUERY}
          emissiveIntensity={0.7}
          metalness={0.3}
          roughness={0.3}
        />
      </mesh>
      <Billboard position={[0, 0.7, 0]}>
        <Text fontSize={0.28} color="#ffffff" anchorX="center" anchorY="middle">
          Query
        </Text>
      </Billboard>
    </group>
  );
}

function ChunkNode({
  chunk,
  selected,
  onSelect,
}: {
  chunk: RagChunk;
  selected: boolean;
  onSelect: () => void;
}) {
  const ref = useRef<THREE.Mesh>(null);
  const pos = (chunk.point ?? [0, 0, 0]) as [number, number, number];
  const radius = 0.16 + chunk.similarity * 0.34;
  const c = color(chunk.collection);

  useFrame((s) => {
    if (ref.current && selected) {
      ref.current.rotation.y += 0.02;
      const p = 1 + Math.sin(s.clock.elapsedTime * 4) * 0.08;
      ref.current.scale.setScalar(p);
    }
  });

  return (
    <group position={pos}>
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
        <sphereGeometry args={[radius, 24, 24]} />
        <meshStandardMaterial
          color={c}
          emissive={c}
          emissiveIntensity={selected ? 1.1 : 0.5}
          metalness={0.2}
          roughness={0.35}
        />
      </mesh>
      {selected && (
        <mesh scale={1.35}>
          <sphereGeometry args={[radius, 16, 16]} />
          <meshBasicMaterial color="#ffffff" wireframe transparent opacity={0.4} />
        </mesh>
      )}
      <Billboard position={[0, radius + 0.28, 0]}>
        <Text fontSize={0.24} color="#e2e8f0" anchorX="center" anchorY="middle">
          {`#${chunk.rank} · ${Math.round(chunk.similarity * 100)}%`}
        </Text>
      </Billboard>
    </group>
  );
}

function Scene({
  queryPoint,
  chunks,
  selected,
  onSelect,
}: {
  queryPoint: [number, number, number];
  chunks: RagChunk[];
  selected: number | null;
  onSelect: (i: number) => void;
}) {
  const lines = useMemo(
    () =>
      chunks.map((c) => ({
        points: [queryPoint, (c.point ?? [0, 0, 0]) as [number, number, number]],
        color: color(c.collection),
        opacity: 0.15 + c.similarity * 0.6,
        width: 0.5 + c.similarity * 2,
      })),
    [chunks, queryPoint]
  );

  return (
    <>
      <ambientLight intensity={0.6} />
      <pointLight position={[6, 6, 6]} intensity={1.1} />
      <pointLight position={[-6, -4, -2]} intensity={0.6} color={MEMORY} />

      {lines.map((l, i) => (
        <Line
          key={i}
          points={l.points}
          color={l.color}
          lineWidth={l.width}
          transparent
          opacity={l.opacity}
        />
      ))}

      <QueryNode position={queryPoint} />
      {chunks.map((c, i) => (
        <ChunkNode
          key={i}
          chunk={c}
          selected={selected === i}
          onSelect={() => onSelect(i)}
        />
      ))}

      <OrbitControls enablePan={false} enableDamping dampingFactor={0.1} minDistance={4} maxDistance={20} />
    </>
  );
}

export default function RetrievalScene(props: {
  queryPoint: [number, number, number];
  chunks: RagChunk[];
  selected: number | null;
  onSelect: (i: number) => void;
}) {
  return (
    <Canvas
      camera={{ position: [0, 2, 11], fov: 55 }}
      dpr={[1, 1.5]}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      style={{ background: "transparent" }}
    >
      <Scene {...props} />
    </Canvas>
  );
}
