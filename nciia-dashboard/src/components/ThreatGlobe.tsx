import { useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Stars } from '@react-three/drei';
import * as THREE from 'three';

// Simple rotating globe
function Globe() {
  const globeRef = useRef<THREE.Mesh>(null);
  
  useFrame(() => {
    if (globeRef.current) {
      globeRef.current.rotation.y += 0.003;
    }
  });
  
  return (
    <group>
      {/* Main globe */}
      <mesh ref={globeRef}>
        <sphereGeometry args={[1, 64, 64]} />
        <meshStandardMaterial
          color="#0a1628"
          metalness={0.3}
          roughness={0.7}
        />
      </mesh>
      
      {/* Wireframe overlay */}
      <mesh>
        <sphereGeometry args={[1.01, 24, 24]} />
        <meshBasicMaterial
          color="#00ffff"
          wireframe
          transparent
          opacity={0.15}
        />
      </mesh>
      
      {/* Glow */}
      <mesh scale={[1.1, 1.1, 1.1]}>
        <sphereGeometry args={[1, 32, 32]} />
        <meshBasicMaterial
          color="#00ffff"
          transparent
          opacity={0.05}
          side={THREE.BackSide}
        />
      </mesh>
      
      {/* Threat points */}
      <ThreatPoint position={[0.8, 0.4, 0.4]} color="#ff4466" />
      <ThreatPoint position={[-0.6, 0.6, 0.5]} color="#ff8800" />
      <ThreatPoint position={[0.3, -0.8, 0.5]} color="#ffaa00" />
      <ThreatPoint position={[-0.4, 0.2, 0.9]} color="#ff4466" />
      <ThreatPoint position={[0.7, -0.3, -0.6]} color="#00ff88" />
    </group>
  );
}

function ThreatPoint({ position, color }: { position: [number, number, number]; color: string }) {
  const ref = useRef<THREE.Mesh>(null);
  
  useFrame((state) => {
    if (ref.current) {
      const scale = 1 + Math.sin(state.clock.elapsedTime * 3) * 0.3;
      ref.current.scale.set(scale, scale, scale);
    }
  });
  
  return (
    <mesh ref={ref} position={position}>
      <sphereGeometry args={[0.04, 16, 16]} />
      <meshBasicMaterial color={color} />
    </mesh>
  );
}

interface ThreatGlobeProps {
  height?: string;
}

export default function ThreatGlobe({ height = '400px' }: ThreatGlobeProps) {
  return (
    <div style={{ width: '100%', height, background: '#050510' }}>
      <Canvas camera={{ position: [0, 0, 2.5], fov: 50 }}>
        <ambientLight intensity={0.3} />
        <pointLight position={[10, 10, 10]} intensity={0.5} />
        <pointLight position={[-10, -10, -10]} intensity={0.3} color="#00ffff" />
        
        <Stars radius={50} depth={50} count={1000} factor={3} fade speed={1} />
        <Globe />
        
        <OrbitControls
          enableZoom={false}
          enablePan={false}
          autoRotate
          autoRotateSpeed={0.3}
        />
      </Canvas>
    </div>
  );
}
