import { Component, Suspense, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { OrbitControls, RoundedBox } from '@react-three/drei'
import { AdditiveBlending, Color, DataTexture, DoubleSide, Group, InstancedMesh, MathUtils, Mesh, Object3D, RGBAFormat } from 'three'
import './scene.css'

type SceneProps = { variant?: 'hero' | 'compact'; progress?: number; activeNode?: number }

function useReducedMotion() {
  const [reduced, setReduced] = useState(() => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches)
  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)')
    const update = () => setReduced(query.matches)
    query.addEventListener('change', update)
    return () => query.removeEventListener('change', update)
  }, [])
  return reduced
}

export function SceneFallback() {
  return (
    <div className="intelligence-fallback" role="img" aria-label="ledgar.ai intelligence core, connecting finance documents, transactions, and compliance">
      <div className="fallback-orbit fallback-orbit-one" />
      <div className="fallback-orbit fallback-orbit-two" />
      <div className="fallback-orbit fallback-orbit-three" />
      <div className="fallback-core"><span /><span /><span /></div>
      <i className="fallback-satellite satellite-one" />
      <i className="fallback-satellite satellite-two" />
    </div>
  )
}

class SceneBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  render() { return this.state.failed ? <SceneFallback /> : this.props.children }
}

function Glow() {
  const texture = useMemo(() => {
    const size = 64
    const data = new Uint8Array(size * size * 4)
    for (let y = 0; y < size; y++) {
      for (let x = 0; x < size; x++) {
        const distance = Math.hypot((x - size / 2) / (size / 2), (y - size / 2) / (size / 2))
        const offset = (y * size + x) * 4
        data[offset] = 19
        data[offset + 1] = 236
        data[offset + 2] = 223
        data[offset + 3] = Math.round(Math.pow(Math.max(0, 1 - distance), 3.7) * 130)
      }
    }
    return new DataTexture(data, size, size, RGBAFormat)
  }, [])
  useEffect(() => { texture.needsUpdate = true; return () => texture.dispose() }, [texture])
  return <sprite scale={[5.3, 5.3, 1]}><spriteMaterial map={texture} transparent blending={AdditiveBlending} depthWrite={false} /></sprite>
}

function RingTicks({ radius }: { radius: number }) {
  const major = useRef<InstancedMesh>(null)
  const minor = useRef<InstancedMesh>(null)
  useLayoutEffect(() => {
    const dummy = new Object3D()
    let majorIndex = 0
    let minorIndex = 0
    for (let tick = 0; tick < 48; tick++) {
      const angle = tick / 48 * Math.PI * 2
      dummy.position.set(Math.cos(angle) * (radius + .1), Math.sin(angle) * (radius + .1), 0)
      dummy.rotation.set(0, 0, angle - Math.PI / 2)
      dummy.updateMatrix()
      if (tick % 4 === 0) major.current?.setMatrixAt(majorIndex++, dummy.matrix)
      else minor.current?.setMatrixAt(minorIndex++, dummy.matrix)
    }
    if (major.current) major.current.instanceMatrix.needsUpdate = true
    if (minor.current) minor.current.instanceMatrix.needsUpdate = true
  }, [radius])
  return <>
    <instancedMesh ref={major} args={[undefined, undefined, 12]}><boxGeometry args={[.011, .085, .012]} /><meshBasicMaterial color="#9db5c5" transparent opacity={.8} /></instancedMesh>
    <instancedMesh ref={minor} args={[undefined, undefined, 36]}><boxGeometry args={[.011, .034, .012]} /><meshBasicMaterial color="#3d687b" transparent opacity={.55} /></instancedMesh>
  </>
}

function OrbitalRing({ radius, rotation, index, highlighted }: { radius: number; rotation: [number, number, number]; index: number; highlighted: boolean }) {
  const group = useRef<Group>(null)
  const [hover, setHover] = useState(false)
  const brightness = hover || highlighted
  return (
    <group ref={group} rotation={rotation} onPointerOver={(event) => { event.stopPropagation(); setHover(true) }} onPointerOut={() => setHover(false)}>
      <mesh>
        <torusGeometry args={[radius, .034, 8, 160]} />
        <meshStandardMaterial color={brightness ? '#aad6dc' : '#5a778a'} metalness={.86} roughness={.24} />
      </mesh>
      <mesh position={[0, 0, .029]}>
        <torusGeometry args={[radius - .053, .006, 4, 160]} />
        <meshBasicMaterial color="#70dfdf" transparent opacity={brightness ? .88 : .32} />
      </mesh>
      <mesh position={[0, 0, -.029]}>
        <torusGeometry args={[radius + .053, .006, 4, 160]} />
        <meshBasicMaterial color="#b0d9e2" transparent opacity={.2} />
      </mesh>
      {[0, 1, 2].map((segment) => (
        <mesh key={segment} rotation={[0, 0, segment * 2.094 + index * .49]} position={[0, 0, .037]}>
          <torusGeometry args={[radius, .012, 5, 48, .69]} />
          <meshBasicMaterial color={brightness ? '#a6fff7' : '#24d8d4'} />
        </mesh>
      ))}
      <RingTicks radius={radius} />
      {[.6, 2.7, 4.8].map((angle, i) => (
        <group key={angle} position={[Math.cos(angle + index) * radius, Math.sin(angle + index) * radius, .06]}>
          <mesh><sphereGeometry args={[i === index % 3 ? .065 : .036, 12, 8]} /><meshBasicMaterial color={i === index % 3 ? '#c5fffa' : '#32c6c7'} /></mesh>
          {i === index % 3 && <mesh><sphereGeometry args={[.115, 12, 8]} /><meshBasicMaterial color="#34dfd6" transparent opacity={.16} depthWrite={false} /></mesh>}
        </group>
      ))}
    </group>
  )
}

function Core({ reduced }: { reduced: boolean }) {
  const crystal = useRef<Group>(null)
  const halo = useRef<Mesh>(null)
  useFrame(({ clock }, delta) => {
    if (!reduced && crystal.current) {
      crystal.current.rotation.y += delta * .12
      crystal.current.rotation.z = Math.sin(clock.elapsedTime * .15) * .1
    }
    if (halo.current) halo.current.scale.setScalar(reduced ? 1 : 1 + Math.sin(clock.elapsedTime * .8) * .018)
  })
  return (
    <group>
      <Glow />
      <pointLight color="#2cecdf" intensity={16} distance={6} decay={2} />
      <mesh ref={halo}>
        <sphereGeometry args={[1.03, 48, 32]} />
        <meshBasicMaterial color="#30dcd5" transparent opacity={.035} depthWrite={false} />
      </mesh>
      <group ref={crystal} rotation={[.25, .3, -.12]}>
        <mesh>
          <icosahedronGeometry args={[.83, 2]} />
          <meshStandardMaterial color="#054b53" metalness={.72} roughness={.22} emissive="#007c7b" emissiveIntensity={.45} />
        </mesh>
        <mesh>
          <icosahedronGeometry args={[.842, 2]} />
          <meshBasicMaterial color="#70fff0" wireframe transparent opacity={.36} />
        </mesh>
        <mesh>
          <icosahedronGeometry args={[.978, 1]} />
          <meshBasicMaterial color="#39dacf" wireframe transparent opacity={.15} depthWrite={false} />
        </mesh>
        <mesh rotation={[.25, .1, 0]}>
          <octahedronGeometry args={[.5, 0]} />
          <meshStandardMaterial color="#affff1" emissive="#2fffe3" emissiveIntensity={1.7} roughness={.18} metalness={.15} />
        </mesh>
        <mesh><octahedronGeometry args={[.59, 0]} /><meshBasicMaterial color="#76ffe7" wireframe transparent opacity={.8} /></mesh>
      </group>
      <mesh rotation={[Math.PI / 2, .2, 0]}>
        <torusGeometry args={[1.18, .007, 4, 112]} />
        <meshBasicMaterial color="#6ae6db" transparent opacity={.55} />
      </mesh>
      <mesh rotation={[.17, .38, .27]}>
        <torusGeometry args={[1.38, .004, 4, 112]} />
        <meshBasicMaterial color="#2c8f9b" transparent opacity={.5} />
      </mesh>
      {Array.from({ length: 16 }, (_, index) => {
        const angle = index / 16 * Math.PI * 2
        return <mesh key={index} position={[Math.cos(angle) * 1.18, 0, Math.sin(angle) * 1.18]}><sphereGeometry args={[index % 4 === 0 ? .025 : .014, 8, 6]} /><meshBasicMaterial color="#8bfff0" /></mesh>
      })}
    </group>
  )
}

function DocumentPanel({ position, rotation, index, reduced }: { position: [number, number, number]; rotation: [number, number, number]; index: number; reduced: boolean }) {
  const panel = useRef<Group>(null)
  const [hover, setHover] = useState(false)
  useFrame(({ clock }) => {
    if (panel.current && !reduced) panel.current.position.y = position[1] + Math.sin(clock.elapsedTime * .45 + index * 2) * .07
  })
  return (
    <group ref={panel} position={position} rotation={rotation} scale={hover ? 1.06 : 1} onPointerOver={(event) => { event.stopPropagation(); setHover(true) }} onPointerOut={() => setHover(false)}>
      <RoundedBox args={[.93, .66, .035]} radius={.035} smoothness={2}>
        <meshStandardMaterial color={hover ? '#153d4c' : '#0a2637'} metalness={.35} roughness={.4} />
      </RoundedBox>
      <mesh position={[0, 0, .019]}>
        <planeGeometry args={[.88, .61]} />
        <meshBasicMaterial color="#123848" transparent opacity={.8} side={DoubleSide} />
      </mesh>
      <mesh position={[-.337, .218, .027]}><planeGeometry args={[.075, .075]} /><meshBasicMaterial color="#40ded5" /></mesh>
      <mesh position={[-.105, .227, .027]}><planeGeometry args={[.29, .018]} /><meshBasicMaterial color="#a0c4cf" /></mesh>
      <mesh position={[-.155, .18, .027]}><planeGeometry args={[.19, .01]} /><meshBasicMaterial color="#3a6a7c" /></mesh>
      <mesh position={[0, .105, .027]}><planeGeometry args={[.72, .006]} /><meshBasicMaterial color="#285368" /></mesh>
      {[.035, -.035, -.105].map((y, row) => (
        <group key={y}>
          <mesh position={[-.19, y, .027]}><planeGeometry args={[.34 - row * .035, .014]} /><meshBasicMaterial color="#67909e" /></mesh>
          <mesh position={[.262, y, .027]}><planeGeometry args={[.14, .014]} /><meshBasicMaterial color={row === index % 3 ? '#71d9cf' : '#497586'} /></mesh>
        </group>
      ))}
      <mesh position={[-.23, -.237, .028]}><planeGeometry args={[.26, .047]} /><meshBasicMaterial color="#1aa79f" /></mesh>
      <mesh position={[.289, -.237, .028]}><circleGeometry args={[.026, 12]} /><meshBasicMaterial color="#75f0cc" /></mesh>
      <mesh position={[0, -.328, .022]}><planeGeometry args={[.74, .007]} /><meshBasicMaterial color="#39b4b5" transparent opacity={.55} /></mesh>
    </group>
  )
}

function Particles({ reduced }: { reduced: boolean }) {
  const points = useRef<Group>(null)
  const data = useMemo(() => {
    const positions = new Float32Array(180 * 3)
    let seed = 37
    const random = () => { seed = (seed * 16807) % 2147483647; return (seed - 1) / 2147483646 }
    for (let i = 0; i < 180; i++) {
      const angle = random() * Math.PI * 2
      const z = random() * 2 - 1
      const radius = 1.3 + random() * 2
      positions[i * 3] = Math.sqrt(1 - z * z) * Math.cos(angle) * radius
      positions[i * 3 + 1] = z * radius
      positions[i * 3 + 2] = Math.sqrt(1 - z * z) * Math.sin(angle) * radius
    }
    return positions
  }, [])
  useFrame((_, delta) => { if (points.current && !reduced) points.current.rotation.y += delta * .025 })
  return <group ref={points}><points><bufferGeometry><bufferAttribute attach="attributes-position" args={[data, 3]} /></bufferGeometry><pointsMaterial size={.015} color="#6edcdb" transparent opacity={.42} sizeAttenuation depthWrite={false} /></points></group>
}

function Engine({ progress = 0, activeNode = -1, reduced, variant }: SceneProps & { reduced: boolean }) {
  const engine = useRef<Group>(null)
  const rings = useRef<Group>(null)
  const { pointer, camera } = useThree()
  const scroll = reduced ? 0 : MathUtils.clamp(progress, 0, 1)
  useFrame(({ clock }, delta) => {
    const smoothing = Math.min(delta * 2.5, 1)
    if (engine.current) {
      engine.current.rotation.x = MathUtils.lerp(engine.current.rotation.x, -.08 - (reduced ? 0 : pointer.y * .08) + scroll * .25, smoothing)
      engine.current.rotation.y = MathUtils.lerp(engine.current.rotation.y, -.18 + (reduced ? 0 : pointer.x * .12) + scroll * .5, smoothing)
      engine.current.position.y = MathUtils.lerp(engine.current.position.y, -scroll * .2, smoothing)
    }
    if (rings.current) {
      if (!reduced) rings.current.rotation.y = Math.sin(clock.elapsedTime * .1) * .12
      rings.current.scale.setScalar(1 + scroll * .3)
    }
    const targetZ = Math.max(.7, (variant === 'compact' ? 8.5 : 8.4) - scroll * 7.7)
    if (!reduced) {
      camera.position.z = MathUtils.lerp(camera.position.z, targetZ, smoothing)
      if (scroll > .05) {
        camera.position.x = MathUtils.lerp(camera.position.x, 0, smoothing)
        camera.position.y = MathUtils.lerp(camera.position.y, .15 - scroll * .2, smoothing)
        camera.lookAt(0, -scroll * .2, 0)
      }
    }
  })
  return (
    <>
      <ambientLight intensity={.85} color="#a5cfde" />
      <directionalLight position={[3, 5, 4]} intensity={3.2} color="#e3f5ff" />
      <directionalLight position={[-5, -2, 1]} intensity={2} color="#326682" />
      <group ref={engine} rotation={[-.08, -.18, 0]}>
        <Particles reduced={reduced} />
        <group ref={rings}>
          <OrbitalRing radius={2.48} rotation={[.55, -.46, -.45]} index={0} highlighted={activeNode === 0} />
          <OrbitalRing radius={2.13} rotation={[1.25, .62, .28]} index={1} highlighted={activeNode === 1} />
          <OrbitalRing radius={1.83} rotation={[.23, 1.1, -.34]} index={2} highlighted={activeNode === 2} />
        </group>
        <Core reduced={reduced} />
        <DocumentPanel position={[-2.16, .92, .5]} rotation={[-.12, -.42, -.08]} index={0} reduced={reduced} />
        <DocumentPanel position={[2.02, -.75, .65]} rotation={[.12, .35, .07]} index={1} reduced={reduced} />
        <DocumentPanel position={[1.3, 1.83, -.55]} rotation={[-.2, .24, -.05]} index={2} reduced={reduced} />
      </group>
      <OrbitControls enabled={scroll <= .05} enableZoom={false} enablePan={false} enableDamping={!reduced && scroll <= .05} dampingFactor={.08} rotateSpeed={.4} minPolarAngle={Math.PI * .32} maxPolarAngle={Math.PI * .65} />
    </>
  )
}

export default function IntelligenceScene({ variant = 'hero', progress = 0, activeNode = -1 }: SceneProps) {
  const reduced = useReducedMotion()
  const [contextLost, setContextLost] = useState(false)
  const container = useRef<HTMLDivElement>(null)
  const [active, setActive] = useState(true)
  useEffect(() => {
    const element = container.current
    if (!element) return
    let visible = true
    const update = () => setActive(visible && !document.hidden)
    const observer = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; update() }, { rootMargin: '100px' })
    observer.observe(element)
    document.addEventListener('visibilitychange', update)
    return () => { observer.disconnect(); document.removeEventListener('visibilitychange', update) }
  }, [])
  return (
    <div ref={container} className={`intelligence-scene intelligence-scene-${variant}`}>
      {contextLost ? <SceneFallback /> : (
        <SceneBoundary>
          <Suspense fallback={<SceneFallback />}>
            <Canvas
              dpr={[1, 1.5]}
              frameloop={!active ? 'never' : reduced ? 'demand' : 'always'}
              camera={{ position: [0, .15, 8.4], fov: 43, near: .1, far: 35 }}
              gl={{ alpha: true, antialias: true, powerPreference: 'high-performance' }}
              onCreated={({ gl }) => {
                gl.setClearColor(new Color('#061522'), 0)
                gl.domElement.addEventListener('webglcontextlost', (event) => { event.preventDefault(); setContextLost(true) }, { once: true })
              }}
              aria-hidden="true"
            >
              <Engine variant={variant} progress={progress} activeNode={activeNode} reduced={reduced} />
            </Canvas>
          </Suspense>
        </SceneBoundary>
      )}
      <span className="intelligence-scene-description">Interactive ledgar.ai intelligence engine. Drag to explore the connected document and transaction network.</span>
    </div>
  )
}
