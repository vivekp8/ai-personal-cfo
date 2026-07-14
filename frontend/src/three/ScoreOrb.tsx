import { Canvas, useFrame } from "@react-three/fiber";
import { Float } from "@react-three/drei";
import { useMemo, useRef } from "react";
import * as THREE from "three";

// 3D animated orb whose color/glow shifts red -> amber -> green with the score.

function scoreColor(score: number): THREE.Color {
  // 0 -> red, 50 -> amber, 100 -> green
  const t = Math.max(0, Math.min(100, score)) / 100;
  const red = new THREE.Color("#ef4444");
  const amber = new THREE.Color("#f59e0b");
  const green = new THREE.Color("#22c55e");
  if (t < 0.5) return red.clone().lerp(amber, t / 0.5);
  return amber.clone().lerp(green, (t - 0.5) / 0.5);
}

function Orb({ score }: { score: number }) {
  const mesh = useRef<THREE.Mesh>(null);
  const color = useMemo(() => scoreColor(score), [score]);

  useFrame((state) => {
    if (mesh.current) {
      mesh.current.rotation.y += 0.004;
      const pulse = 1 + Math.sin(state.clock.elapsedTime * 2) * 0.02;
      mesh.current.scale.setScalar(pulse);
    }
  });

  return (
    <Float speed={1.5} rotationIntensity={0.3} floatIntensity={0.8}>
      <mesh ref={mesh}>
        <icosahedronGeometry args={[1.4, 3]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={0.6}
          metalness={0.4}
          roughness={0.25}
          wireframe={false}
        />
      </mesh>
      <mesh scale={1.18}>
        <icosahedronGeometry args={[1.4, 1]} />
        <meshBasicMaterial color={color} wireframe transparent opacity={0.25} />
      </mesh>
    </Float>
  );
}

export default function ScoreOrb({ score }: { score: number }) {
  return (
    <Canvas camera={{ position: [0, 0, 4.2], fov: 50 }} dpr={[1, 1.5]}>
      <ambientLight intensity={0.6} />
      <pointLight position={[4, 4, 4]} intensity={1.4} />
      <Orb score={score} />
    </Canvas>
  );
}
