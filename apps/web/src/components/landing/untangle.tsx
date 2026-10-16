'use client';

import { m, type Variants } from 'motion/react';
import { CreditGlyph } from '@/components/credit-glyph';

// What a request is made of on the left; each line runs from one of them to Generate on the right. The tangled and
// straight paths use the same commands, so one morphs into the other.
const inputs = ['Prompt', 'Photo', 'Clip', 'Quality', 'Shape'];
const rowY = (i: number) => 28 + i * 44;
const endX = 300;
const endY = rowY(2);

const tangles = [
  [
    [150, -40],
    [40, 220],
    [200, 160],
    [260, 30]
  ],
  [
    [230, 210],
    [60, 10],
    [170, 40],
    [140, 230]
  ],
  [
    [120, 230],
    [250, -10],
    [80, 30],
    [210, 200]
  ],
  [
    [60, -30],
    [260, 60],
    [180, 230],
    [120, 10]
  ],
  [
    [250, 30],
    [40, 120],
    [220, -20],
    [90, 220]
  ]
];

function path(i: number, straight: boolean) {
  const x0 = 72;
  const y0 = rowY(i);
  const [a, b, c, d] = tangles[i];
  if (!straight)
    return `M${x0} ${y0}C${a[0]} ${a[1]} ${b[0]} ${b[1]} 180 ${(y0 + endY) / 2}C${c[0]} ${c[1]} ${d[0]} ${d[1]} ${endX} ${endY}`;
  // Straight: control points on the line itself, easing in toward Generate
  const midY = (y0 + endY) / 2;
  return `M${x0} ${y0}C110 ${y0} 140 ${y0} 180 ${midY}C220 ${endY} 250 ${endY} ${endX} ${endY}`;
}

const line: Variants = {
  tangled: (i: number) => ({ d: path(i, false), stroke: 'var(--color-chip)' }),
  straight: (i: number) => ({
    d: path(i, true),
    stroke: 'var(--color-brand)',
    transition: { type: 'spring', bounce: 0.3, visualDuration: 0.9, delay: 0.25 + i * 0.08 }
  })
};

/** Settings wired every which way, which straighten into one Generate button when the picture scrolls into view. */
export function Untangle() {
  return (
    <m.div
      initial="tangled"
      whileInView="straight"
      viewport={{ once: true, amount: 0.6 }}
      className="relative overflow-hidden rounded-[22px] border border-white/[0.06] bg-panel p-4"
    >
      <svg viewBox="0 0 400 230" className="w-full" aria-hidden>
        {inputs.map((name, i) => (
          <m.path
            key={name}
            custom={i}
            variants={line}
            fill="none"
            strokeWidth="3"
            strokeLinecap="round"
            style={{ mixBlendMode: 'screen' }}
          />
        ))}
        {inputs.map((name, i) => (
          <g key={name}>
            <rect x="4" y={rowY(i) - 13} width="68" height="26" rx="8" fill="var(--color-panel-raised)" />
            <text x="38" y={rowY(i) + 4.5} textAnchor="middle" fontSize="12" fontWeight="600" fill="#c8c9cb">
              {name}
            </text>
          </g>
        ))}
      </svg>
      <m.div
        variants={{ tangled: { scale: 0.92, opacity: 0.5 }, straight: { scale: 1, opacity: 1, transition: { delay: 0.9 } } }}
        className="absolute top-1/2 right-4 flex h-12 w-[24%] min-w-24 -translate-y-1/2 flex-col items-center justify-center rounded-[14px] bg-linear-to-b from-[#ff6a45] via-[#ff5b3a] to-[#f24a2a] text-white shadow-[0_3px_0_var(--color-brand-edge)]"
      >
        <span className="font-display text-[0.8125rem] leading-none font-bold tracking-wide uppercase font-stretch-[86%]">Generate</span>
        <span className="mt-0.5 flex items-center gap-0.5 text-xs font-bold">
          <CreditGlyph />1
        </span>
      </m.div>
    </m.div>
  );
}
