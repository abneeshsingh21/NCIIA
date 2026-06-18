interface ThreatMeterProps {
  score: number;
}

export default function ThreatMeter({ score }: ThreatMeterProps) {
  const getLevel = (score: number) => {
    if (score >= 80) return 'critical';
    if (score >= 60) return 'high';
    if (score >= 40) return 'medium';
    return 'low';
  };

  const level = getLevel(score);

  return (
    <div className="threat-meter">
      <div className="meter-bar">
        <div 
          className={`meter-fill ${level}`} 
          style={{ width: `${score}%` }}
        />
      </div>
      <span className="meter-value">{score}</span>
    </div>
  );
}
