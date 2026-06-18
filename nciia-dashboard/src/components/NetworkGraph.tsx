import { useRef, useEffect, useState, useCallback } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

// Mock Data Generation for Visual Power
const genRandomTree = (N = 300) => {
  return {
    nodes: [...Array(N).keys()].map(i => ({ 
      id: i,
      val: Math.random() * 5,
      color: i === 0 ? '#ef4444' : (i < 5 ? '#f59e0b' : '#3b82f6'),
      name: i === 0 ? 'Threat Actor' : (i < 5 ? 'C2 Node' : 'Compromised Device')
    })),
    links: [...Array(N).keys()]
      .filter(id => id)
      .map(id => ({
        source: id,
        target: Math.round(Math.random() * (id - 1))
      }))
  };
};

export default function NetworkGraph() {
  const fgRef = useRef<any>();
  const boxRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
  const [data] = useState(genRandomTree(50));

  useEffect(() => {
    // Resize observer for responsive graph
    if (!boxRef.current) return;
    
    const ro = new ResizeObserver(entries => {
      if (entries[0]) {
        const { width, height } = entries[0].contentRect;
        setDimensions({ width, height });
      }
    });
    
    ro.observe(boxRef.current);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    // Initial zoom logic
    setTimeout(() => {
        if (fgRef.current) {
            fgRef.current.d3Force('charge').strength(-100);
            fgRef.current.zoomToFit(400); 
        }
    }, 500);
  }, []);

  // Custom node rendering for glow effect
  const paintNode = useCallback((node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const r = 4;
    
    // Glow effect
    ctx.shadowColor = node.color;
    ctx.shadowBlur = 15;
    ctx.beginPath();
    ctx.arc(node.x, node.y, r, 0, 2 * Math.PI, false);
    ctx.fillStyle = node.color;
    ctx.fill();
    
    // Reset shadow for text
    ctx.shadowBlur = 0;
    
    // Text label on hover or for key nodes
    if (globalScale > 1.5 || node.id < 5) {
        const label = node.name;
        const fontSize = 12 / globalScale;
        ctx.font = `${fontSize}px "JetBrains Mono", Sans-Serif`;
        ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(label, node.x, node.y + r + fontSize);
    }
  }, []);

  return (
    <div ref={boxRef} style={{ width: '100%', height: '100%', background: '#050510', position: 'relative' }}>
        <div style={{ position: 'absolute', top: 10, left: 10, padding: '10px', pointerEvents: 'none', zIndex: 10 }}>
            <h3 style={{ margin: 0, color: '#fff', fontSize: '14px', textShadow: '0 0 10px rgba(0, 212, 255, 0.5)' }}>
                DEEP LINK ANALYSIS
            </h3>
            <div style={{ display: 'flex', gap: '12px', marginTop: '4px' }}>
                <span style={{ fontSize: '10px', color: '#888', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#ef4444', boxShadow: '0 0 5px #ef4444' }}></span> 
                    ACTOR
                </span>
                <span style={{ fontSize: '10px', color: '#888', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#f59e0b', boxShadow: '0 0 5px #f59e0b' }}></span> 
                    INFRA
                </span>
                 <span style={{ fontSize: '10px', color: '#888', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#3b82f6', boxShadow: '0 0 5px #3b82f6' }}></span> 
                    DEVICE
                </span>
            </div>
        </div>
        
        {dimensions.width > 0 && (
            <ForceGraph2D
                ref={fgRef}
                width={dimensions.width}
                height={dimensions.height}
                graphData={data}
                backgroundColor="#050510"
                nodeCanvasObject={paintNode}
                linkColor={() => "rgba(0, 212, 255, 0.15)"}
                linkWidth={1}
                cooldownTicks={100}
                onEngineStop={() => fgRef.current?.zoomToFit(400)}
            />
        )}
    </div>
  );
}
