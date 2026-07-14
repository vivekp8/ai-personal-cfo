import { Canvas, useFrame } from "@react-three/fiber";
import { Float, Icosahedron, Torus, Points, PointMaterial } from "@react-three/drei";
import { useMemo, useRef } from "react";
import * as THREE from "three";

// A slowly rotating low-poly abstract object + a modest particle field.
// Performance guardrail: low-poly geometry, ~400 particles only.

function ParticleField() {
  const ref = useRef<THREE.Points>(null);
  const positions = useMemo(() => {
    const count = 400;
    const arr = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      arr[i * 3] = (Math.random() - 0.5) * 18;
      arr[i * 3 + 1] = (Math.random() - 0.5) * 12;
      arr[i * 3 + 2] = (Math.random() - 0.5) * 10;
    }
    return arr;
  }, []);

  useFrame((_, delta) => {
    if (ref.current) ref.current.rotation.y += delta * 0.02;
  });

  return (
    <Points ref={ref} positions={positions} stride={3}>
      <PointMaterial
        transparent
        color="#2dd4bf"
        size={0.06}
        sizeAttenuation
        depthWrite={false}
        opacity={0.55}
      />
    </Points>
  );
}

function CoinCluster() {
  const group = useRef<THREE.Group>(null);
  useFrame((_, delta) => {
    if (group.current) group.current.rotation.y += delta * 0.25;
  });
  return (
    <group ref={group}>
      <Float speed={1.4} rotationIntensity={0.6} floatIntensity={1.2}>
        <Icosahedron args={[1.5, 0]}>
          <meshStandardMaterial
            color="#a78bfa"
            metalness={0.6}
            roughness={0.2}
            emissive="#5b21b6"
            emissiveIntensity={0.4}
            flatShading
          />
        </Icosahedron>
      </Float>
      <Float speed={1} rotationIntensity={0.4} floatIntensity={1}>
        <Torus args={[2.7, 0.12, 16, 60]} rotation={[Math.PI / 2.4, 0, 0]}>
          <meshStandardMaterial
            color="#2dd4bf"
            metalness={0.5}
            roughness={0.3}
            emissive="#0f766e"
            emissiveIntensity={0.5}
          />
        </Torus>
      </Float>
    </group>
  );
}

export default function HeroScene() {
  return (
    <Canvas
      camera={{ position: [0, 0, 7], fov: 50 }}
      dpr={[1, 1.5]}
      gl={{ antialias: true, powerPreference: "high-performance" }}
    >
      <ambientLight intensity={0.5} />
      <pointLight position={[6, 6, 6]} intensity={1.2} color="#a78bfa" />
      <pointLight position={[-6, -3, 2]} intensity={0.8} color="#2dd4bf" />
      <CoinCluster />
      <ParticleField />
    </Canvas>
  );
}
