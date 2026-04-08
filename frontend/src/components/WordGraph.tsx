import type { WordWithMastery } from "../types";

interface WordGraphProps {
  words: WordWithMastery[];
  onSelect: (word: WordWithMastery) => void;
}

const masteryClasses: Record<number, string> = {
  0: "bg-slate-200 text-slate-700",
  1: "bg-amber-200 text-amber-900",
  2: "bg-amber-400 text-amber-950",
  3: "bg-teal-200 text-teal-900",
  4: "bg-teal-500 text-white",
  5: "bg-emerald-500 text-white",
};

const statusClasses: Record<string, string> = {
  active: "",
  suspended: "opacity-45 line-through",
  archived: "opacity-30 line-through grayscale",
};

export function WordGraph({ words, onSelect }: WordGraphProps) {
  const grouped = words.reduce<Record<string, WordWithMastery[]>>((accumulator, word) => {
    const key = word.category || "uncategorised";
    accumulator[key] ??= [];
    accumulator[key].push(word);
    return accumulator;
  }, {});

  return (
    <div className="space-y-6">
      {Object.entries(grouped).map(([category, items]) => (
        <section key={category} className="glass-panel rounded-[28px] p-5 shadow-soft">
          <div className="mb-4 flex items-center justify-between gap-4">
            <h3 className="font-display text-2xl capitalize text-ink">{category}</h3>
            <span className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">
              {items.length} words
            </span>
          </div>
          <div className="chip-scrollbar flex flex-wrap gap-2 overflow-x-auto">
            {items.map((word) => (
              <button
                key={word.id}
                type="button"
                onClick={() => onSelect(word)}
                className={`rounded-full px-3 py-2 text-sm font-semibold transition hover:-translate-y-0.5 ${
                  masteryClasses[word.mastery_level] ?? masteryClasses[0]
                } ${statusClasses[word.status] ?? ""}`}
              >
                {word.thai}
              </button>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
