interface MasteryDotsProps {
  level: number;
}

export function MasteryDots({ level }: MasteryDotsProps) {
  return (
    <div className="flex items-center gap-2" aria-label={`Mastery level ${level} out of 5`}>
      {Array.from({ length: 5 }, (_, index) => {
        const filled = index < level;
        return (
          <span
            key={index}
            className={`h-3 w-3 rounded-full border transition-all duration-300 ${
              filled ? "scale-105 border-moss bg-moss" : "border-black/15 bg-white/60"
            }`}
          />
        );
      })}
    </div>
  );
}
