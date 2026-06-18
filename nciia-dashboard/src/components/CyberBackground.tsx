import { useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import * as THREE from 'three';

function FloatingParticles() {
  const particlesRef = useRef<THREE.Points>(null);
  
  const { positions, colors } = useMemo(() => {
    const count = 500;
    const positions = new Float32Array(count * 3);
    const colors = new Float32Array(count * 3);
    
    for (let i = 0; i < count; i++) {
      positions[i * 3] = (Math.random() - 0.5) * 20;
      positions[i * 3 + 1] = (Math.random() - 0.5) * 20;
      positions[i * 3 + 2] = (Math.random() - 0.5) * 20;
      
      // Cyan to purple gradient
      const t = Math.random();
      colors[i * 3] = 0.0 + t * 0.5;      // R
      colors[i * 3 + 1] = 1.0 - t * 0.5;  // G
      colors[i * 3 + 2] = 1.0;             // B
    }
    
    return { positions, colors };
  }, []);
  
  useFrame((state) => {
    if (particlesRef.current) {
      particlesRef.current.rotation.y += 0.0003;
      particlesRef.current.rotation.x = Math.sin(state.clock.elapsedTime * 0.1) * 0.1;
    }
  });
  
  return (
    <points ref={particlesRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          count={500}
          array={positions}
          itemSize={3}
        />
        <bufferAttribute
          attach="attributes-color"
          count={500}
          array={colors}
          itemSize={3}
        />
      </bufferGeometry>
      <pointsMaterial
        size={0.05}
        vertexColors
        transparent
        opacity={0.4}
        sizeAttenuation
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
}

function GlowingOrb({ position, color, size }: { position: [number, number, number]; color: string; size: number }) {
  const meshRef = useRef<THREE.Mesh>(null);
  
  useFrame((state) => {
    if (meshRef.current) {
      meshRef.current.position.y = position[1] + Math.sin(state.clock.elapsedTime + position[0]) * 0.3;
      const scale = size + Math.sin(state.clock.elapsedTime * 2) * 0.1;
      meshRef.current.scale.set(scale, scale, scale);
    }
  });
  
  return (
    <mesh ref={meshRef} position={position}>
      <sphereGeometry args={[1, 32, 32]} />
      <meshBasicMaterial color={color} transparent opacity={0.3} />
      <pointLight color={color} intensity={2} distance={5} />
    </mesh>
  );
}

function DataStream() {
  const progressRef = useRef(0);
  
  const points = useMemo(() => {
    const curve = new THREE.CatmullRomCurve3([
      new THREE.Vector3(-5, 2, -3),
      new THREE.Vector3(-2, -1, 0),
      new THREE.Vector3(2, 1, 1),
      new THREE.Vector3(5, -2, -2),
    ]);
    return curve.getPoints(100);
  }, []);
  
  useFrame(() => {
    progressRef.current = (progressRef.current + 0.005) % 1;
  });
  
  return (
    <line>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          count={points.length}
          array={new Float32Array(points.flatMap(p => [p.x, p.y, p.z]))}
          itemSize={3}
        />
      </bufferGeometry>
      <lineBasicMaterial color="#00ffff" transparent opacity={0.3} />
    </line>
  );
}

export default function CyberBackground() {
  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      width: '100vw',
      height: '100vh',
      zIndex: -1,
      background: 'linear-gradient(135deg, #0a0a1a 0%, #0d1b2a 50%, #1a0a2e 100%)'
    }}>
      <Canvas camera={{ position: [0, 0, 8], fov: 60 }}>
        <fog attach="fog" args={['#0a0a1a', 5, 20]} />
        <ambientLight intensity={0.1} />
        
        <FloatingParticles />
        
        {/* Floating orbs */}
        <GlowingOrb position={[-4, 2, -5]} color="#00ffff" size={0.5} />
        <GlowingOrb position={[4, -1, -3]} color="#ff00ff" size={0.3} />
        <GlowingOrb position={[-2, -3, -4]} color="#00ff88" size={0.4} />
        <GlowingOrb position={[3, 3, -6]} color="#ff6600" size={0.35} />
        
        <DataStream />
      </Canvas>
    </div>
  );
}
