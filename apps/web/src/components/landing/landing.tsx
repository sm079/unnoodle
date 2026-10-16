import { Fragment, type CSSProperties, type ReactNode } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { AtSignIcon, CopyIcon, FolderIcon, Layers2Icon, SlidersHorizontalIcon, Volume2Icon } from 'lucide-react';
import { BrandMark } from '@/components/brand-mark';
import { CreditAmount } from '@/components/credit-glyph';
import { BeforeAfter } from '@/components/landing/before-after';
import { LoopVideo } from '@/components/landing/loop-video';
import { Untangle } from '@/components/landing/untangle';
import { cn } from '@/lib/utils';

// Everything shown here came out of the app: the Demo project's generations, with the prompts that made them
const show = (name: string) => `/showcase/${name}`;

const primary =
  'flex h-12 items-center justify-center rounded-[14px] bg-linear-to-b from-[#ff6a45] via-[#ff5b3a] to-[#f24a2a] px-6 text-[0.9375rem] font-bold text-white shadow-[0_3px_0_var(--color-brand-edge),0_10px_24px_rgb(255_91_58/0.25)] transition-[translate,box-shadow,filter] duration-300 ease-spring hover:brightness-105 active:translate-y-[2px] active:shadow-[0_1px_0_var(--color-brand-edge)] active:duration-75';
const secondary =
  'flex h-12 items-center justify-center rounded-[14px] bg-white/[0.08] px-6 text-[0.9375rem] font-semibold text-white backdrop-blur-md transition-[background-color,scale] duration-200 ease-spring hover:bg-white/[0.14] active:scale-[0.97]';
const display = 'font-display leading-[0.95] font-bold tracking-[-0.01em] uppercase font-stretch-[86%]';

export function Landing() {
  return (
    <div className="min-h-dvh bg-background text-foreground">
      <Header />
      <main>
        <Hero />
        <Features />
        <Unnoodled />
        <Details />
        <Showcase />
        <Pricing />
        <Closing />
      </main>
      <Footer />
    </div>
  );
}

function Header() {
  return (
    <header className="fixed inset-x-0 top-0 z-30 pt-[env(safe-area-inset-top)]">
      <div className="mx-auto flex h-16 max-w-6xl items-center gap-3 px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2.5 rounded-xl" aria-label="unnoodle, home">
          <BrandMark />
          <span className="text-lg font-semibold tracking-tight">unnoodle</span>
        </Link>
        <nav className="ml-auto flex items-center gap-1.5">
          <Link
            href="/sign-in"
            className="flex h-9 items-center rounded-xl px-3 text-sm font-semibold text-white/80 transition-colors hover:text-white"
          >
            Sign in
          </Link>
          <Link
            href="/sign-up"
            className="flex h-9 items-center rounded-xl bg-brand px-3.5 text-sm font-bold text-white transition-[scale,filter] duration-200 ease-spring hover:brightness-110 active:scale-95"
          >
            Get started
          </Link>
        </nav>
      </div>
      {/* Frosted, so the page scrolling under it stays out of the way of the links */}
      <div aria-hidden className="absolute inset-0 -z-10 border-b border-white/[0.06] bg-background/75 backdrop-blur-xl" />
    </header>
  );
}

function Headline({ text, className }: { text: string; className?: string }) {
  return (
    <h1 className={cn(className, display, 'text-balance')}>
      {text.split(' ').map((word, index) => (
        <Fragment key={index}>
          {index > 0 && ' '}
          <span className="hero-word -mb-[0.1em] pb-[0.1em]" style={{ '--i': index } as CSSProperties}>
            {word}
          </span>
        </Fragment>
      ))}
    </h1>
  );
}

function Hero() {
  return (
    <section className="relative isolate flex min-h-[92svh] flex-col justify-end overflow-hidden lg:min-h-0 lg:justify-center lg:pt-32 lg:pb-24">
      {/* Phones: the video fills the screen behind the words */}
      <LoopVideo
        src={show('market-ride.mp4')}
        poster={show('market-ride.webp')}
        label="A musician rides a red bicycle through a night market in the rain"
        className="absolute inset-0 -z-10 lg:hidden"
      />
      <div aria-hidden className="absolute inset-0 -z-10 bg-linear-to-t from-background via-background/60 to-background/10 lg:hidden" />

      <div className="mx-auto grid w-full max-w-6xl items-center gap-10 px-4 pb-10 sm:px-6 lg:grid-cols-[1.1fr_1fr] lg:pb-0">
        <div className="animate-rise">
          <Headline text="Pictures and videos from one prompt" className="text-[clamp(2.6rem,1.6rem+5vw,5.25rem)]" />
          <p className="mt-5 max-w-md text-[1.0625rem] leading-relaxed text-[#c8c9cb]">
            Describe what you want, attach a photo or a clip if you have one, and press Generate. No nodes to wire and no settings to learn.
          </p>
          <div className="mt-7 flex flex-wrap gap-2.5">
            <Link href="/sign-up" className={primary}>
              Get started
            </Link>
            <Link href="/demo" className={secondary}>
              Look around
            </Link>
          </div>
          <p className="mt-4 text-sm text-[#8a8b8c]">Invite only for now.</p>
        </div>

        {/* Wider screens: the video in a frame, with two of the pictures that went into it beside it */}
        <div className="relative hidden h-[34rem] lg:block">
          <LoopVideo
            src={show('market-ride.mp4')}
            poster={show('market-ride.webp')}
            label="A musician rides a red bicycle through a night market in the rain"
            sound
            className="absolute top-0 left-1/2 aspect-[9/16] h-full -translate-x-1/2 rounded-[26px] shadow-[0_30px_80px_rgb(0_0_0/0.6)] ring-1 ring-white/10"
          />
          <Image
            src={show('bicycle.webp')}
            alt="A red vintage bicycle against a pale blue wall"
            width={624}
            height={832}
            sizes="12rem"
            className="absolute top-14 left-0 w-44 -rotate-6 rounded-2xl shadow-2xl ring-1 ring-white/10"
          />
          <Image
            src={show('raincoat.webp')}
            alt="A young woman in a yellow raincoat"
            width={720}
            height={1080}
            sizes="12rem"
            className="absolute right-0 bottom-10 w-40 rotate-6 rounded-2xl shadow-2xl ring-1 ring-white/10"
          />
        </div>
      </div>
    </section>
  );
}

function SectionTitle({ id, eyebrow, title, children }: { id: string; eyebrow: string; title: string; children?: ReactNode }) {
  return (
    <div className="reveal max-w-2xl">
      <p className="text-sm font-semibold text-brand">{eyebrow}</p>
      <h2 id={id} className={cn('mt-2 text-[clamp(2rem,1.4rem+3vw,3.5rem)] text-balance', display)}>
        {title}
      </h2>
      {children && <p className="mt-4 text-[1.0625rem] leading-relaxed text-[#a0a1a3]">{children}</p>}
    </div>
  );
}

/** A prompt as the composer shows it, with @photo1-style handles in the brand color. */
function Prompt({ text }: { text: string }) {
  return (
    <p className="rounded-xl bg-white/[0.05] px-3 py-2.5 text-[0.8125rem] leading-relaxed text-[#c8c9cb]">
      {text.split(/(@(?:photo|clip)\d+)/).map((part, index) =>
        index % 2 === 1 ? (
          <span key={index} className="rounded-md bg-brand/12 px-1 py-0.5 font-semibold whitespace-nowrap text-brand">
            {part}
          </span>
        ) : (
          part
        )
      )}
    </p>
  );
}

type Input = { src: string; handle: string; alt: string };

function Inputs({ items }: { items: Input[] }) {
  return (
    <ul className="flex gap-2" aria-label="Attached">
      {items.map(item => (
        <li key={item.handle} className="flex items-center gap-1.5 rounded-xl bg-white/[0.05] py-1 pr-2.5 pl-1">
          <Image src={item.src} alt={item.alt} width={64} height={64} className="size-7 rounded-lg object-cover" />
          <span className="text-xs font-semibold text-brand">{item.handle}</span>
        </li>
      ))}
    </ul>
  );
}

const raincoat: Input = { src: show('raincoat.webp'), handle: '@photo1', alt: 'The woman in the yellow raincoat' };

function Feature({
  title,
  line,
  media,
  prompt,
  inputs
}: {
  title: string;
  line: string;
  media: ReactNode;
  prompt: string;
  inputs?: Input[];
}) {
  return (
    <li className="flex w-[78vw] max-w-[22rem] shrink-0 snap-start flex-col gap-3 rounded-[22px] bg-panel p-2.5 pb-3.5 lg:w-auto lg:max-w-none">
      <div className="overflow-hidden rounded-[16px]">{media}</div>
      <div className="flex flex-1 flex-col gap-3 px-1.5">
        <div>
          <h3 className={cn('text-2xl', display)}>{title}</h3>
          <p className="mt-1 text-sm text-[#a0a1a3]">{line}</p>
        </div>
        {inputs && <Inputs items={inputs} />}
        <div className="mt-auto">
          <Prompt text={prompt} />
        </div>
      </div>
    </li>
  );
}

function Features() {
  return (
    <section className="mx-auto max-w-6xl px-4 pt-16 sm:px-6 lg:pt-24" aria-labelledby="features">
      <SectionTitle id="features" eyebrow="What it makes" title="Four things, one box">
        Pick a picture or a video. What you attach decides the rest.
      </SectionTitle>
      <ul className="-mx-4 mt-8 no-scrollbar flex snap-x snap-mandatory scroll-px-4 gap-3 overflow-x-auto px-4 pb-2 sm:-mx-6 sm:scroll-px-6 sm:px-6 lg:mx-0 lg:grid lg:grid-cols-4 lg:overflow-visible lg:px-0">
        <Feature
          title="Create a picture"
          line="Describe it in a sentence."
          media={
            <Image
              src={show('market.webp')}
              alt="A night market in Kathmandu in the rain, with lanterns and umbrellas"
              width={610}
              height={1080}
              sizes="(min-width: 1024px) 25vw, 78vw"
              className="aspect-[3/4] w-full object-cover"
            />
          }
          prompt="a busy night market street in Kathmandu in the rain, lanterns, people with umbrellas"
        />
        <Feature
          title="Edit a photo"
          line="Attach one and say what changes."
          media={
            <BeforeAfter
              before={{ src: show('raincoat.webp'), alt: 'Before: the woman in a yellow raincoat' }}
              after={{ src: show('jacket.webp'), alt: 'After: the same woman in a black leather jacket' }}
              width={720}
              height={1080}
              className="aspect-[3/4] w-full"
            />
          }
          inputs={[raincoat]}
          prompt="@photo1 wears a black leather jacket instead of the raincoat, same pose and background"
        />
        <Feature
          title="Combine photos"
          line="Up to three in one scene."
          media={
            <Image
              src={show('ride.webp')}
              alt="The woman in the raincoat rides the red bicycle with the teapot in its basket"
              width={720}
              height={1080}
              sizes="(min-width: 1024px) 25vw, 78vw"
              className="aspect-[3/4] w-full object-cover"
            />
          }
          inputs={[
            raincoat,
            { src: show('bicycle.webp'), handle: '@photo2', alt: 'The red bicycle' },
            { src: show('teapot.webp'), handle: '@photo3', alt: 'The teapot with a blue fish' }
          ]}
          prompt="@photo1 rides the bicycle from @photo2 down a quiet street, the teapot from @photo3 in the front basket"
        />
        <Feature
          title="Make a video"
          line="From words, photos or clips. With sound."
          media={
            <LoopVideo
              src={show('tea.mp4')}
              poster={show('tea.webp')}
              label="The woman pours tea from the fish teapot and says cheers"
              sound
              className="aspect-[3/4] w-full"
            />
          }
          inputs={[
            { src: show('jacket.webp'), handle: '@photo1', alt: 'The woman in the leather jacket' },
            { src: show('teapot.webp'), handle: '@photo2', alt: 'The teapot with a blue fish' }
          ]}
          prompt={'@photo1 pours tea from the teapot in @photo2 into a cup, then smiles and says "cheers" to the camera'}
        />
      </ul>
    </section>
  );
}

function Unnoodled() {
  return (
    <section className="mx-auto grid max-w-6xl items-center gap-10 px-4 pt-24 sm:px-6 lg:grid-cols-2 lg:pt-32" aria-labelledby="unnoodled">
      <div>
        <SectionTitle id="unnoodled" eyebrow="Why it exists" title="The wiring stays on our side">
          Open image and video models are good now, but using them usually means a canvas of nodes, model files and settings with names like
          CFG and denoise. unnoodle does that part on the server. It picks the model from what you ask for and what you attach, builds the
          steps for that one request, and runs them on a GPU.
        </SectionTitle>
        <ol className="reveal mt-8 grid gap-3 sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3">
          {[
            ['Describe', 'A sentence about what you want.'],
            ['Attach', 'Photos or clips to work from, if you have them.'],
            ['Generate', 'The price is on the button before you press it.']
          ].map(([step, text], index) => (
            <li key={step} className="rounded-2xl bg-panel p-4">
              <span className="text-xs font-semibold text-[#8a8b8c] tabular-nums">0{index + 1}</span>
              <p className="mt-1 font-semibold">{step}</p>
              <p className="mt-0.5 text-sm text-[#a0a1a3]">{text}</p>
            </li>
          ))}
        </ol>
      </div>
      <div className="reveal">
        <Untangle />
      </div>
    </section>
  );
}

function Details() {
  const items = [
    {
      icon: SlidersHorizontalIcon,
      title: 'Settings in words',
      text: 'Low, medium or high quality. A shape like portrait or wide. 5, 10 or 15 seconds.'
    },
    {
      icon: AtSignIcon,
      title: '@mentions',
      text: 'Each attachment gets a handle, @photo1 or @clip1, so the prompt can say which is which.'
    },
    { icon: CopyIcon, title: 'Same shape as a photo', text: 'Keep the shape of the photo or clip you attached instead of picking one.' },
    { icon: Layers2Icon, title: 'Up to four at once', text: 'Queue a few takes of one prompt in one tap, each a little different.' },
    { icon: FolderIcon, title: 'Projects', text: 'Keep generations in folders. Anything you made can go back in as an input.' },
    { icon: Volume2Icon, title: 'Video with sound', text: 'Every video comes with its own audio: rain, a guitar, a voice saying cheers.' }
  ];
  return (
    <section className="mx-auto max-w-6xl px-4 pt-24 sm:px-6 lg:pt-32" aria-labelledby="details">
      <SectionTitle id="details" eyebrow="The small things" title="Plain words, no knobs" />
      <ul className="mt-8 grid grid-cols-2 gap-2.5 sm:gap-3 lg:grid-cols-3">
        {items.map(({ icon: Icon, title, text }) => (
          <li key={title} className="reveal rounded-[20px] bg-panel p-4 sm:p-5">
            <span className="flex size-9 items-center justify-center rounded-xl bg-brand/12 text-brand">
              <Icon className="size-[1.125rem]" />
            </span>
            <h3 className="mt-3 font-semibold">{title}</h3>
            <p className="mt-1 text-sm leading-relaxed text-[#a0a1a3]">{text}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Showcase() {
  type Tile = { name: string; prompt: string; width: number; height: number; video?: boolean };
  const tiles: Tile[] = [
    { name: 'boat', prompt: 'a paper boat on a puddle, close-up', width: 720, height: 720 },
    {
      name: 'musician',
      prompt: 'a street musician plays an acoustic guitar under a lamp on a rainy night and sings softly, rain patters on the pavement',
      width: 672,
      height: 384,
      video: true
    },
    {
      name: 'teapot',
      prompt: 'a white ceramic teapot painted with a blue fish, product photo on a white table',
      width: 1024,
      height: 1024
    },
    {
      name: 'references',
      prompt:
        'the camera moves through the market street from @clip1; the musician from @clip2 rides the bicycle from @photo1 through the crowd, ringing its bell',
      width: 400,
      height: 720,
      video: true
    },
    { name: 'kitchen', prompt: '@photo1 holds the teapot from @photo2 in both hands, in a sunny kitchen', width: 832, height: 624 },
    { name: 'bicycle', prompt: 'a red vintage bicycle leaning on a pale blue wall, soft morning light, photo', width: 624, height: 832 },
    {
      name: 'jacket',
      prompt: '@photo1 wears a black leather jacket instead of the raincoat, same pose and background',
      width: 720,
      height: 1080
    }
  ];
  return (
    <section className="mx-auto max-w-6xl px-4 pt-24 sm:px-6 lg:pt-32" aria-labelledby="showcase">
      <SectionTitle id="showcase" eyebrow="Made with unnoodle" title="Straight out of the app">
        Every picture and video on this page came from the prompt shown with it.
      </SectionTitle>
      <ul className="mt-8 columns-2 gap-2.5 sm:gap-3 lg:columns-3">
        {tiles.map(tile => (
          <li key={tile.name} className="reveal group relative mb-2.5 break-inside-avoid overflow-hidden rounded-[18px] sm:mb-3">
            {tile.video ? (
              <LoopVideo src={show(`${tile.name}.mp4`)} poster={show(`${tile.name}.webp`)} label={tile.prompt} sound className="w-full" />
            ) : (
              <Image
                src={show(`${tile.name}.webp`)}
                alt={tile.prompt}
                width={tile.width}
                height={tile.height}
                sizes="(min-width: 1024px) 33vw, 50vw"
                className="w-full"
              />
            )}
            <div className="pointer-events-none absolute inset-x-0 top-0 bg-linear-to-b from-black/70 to-transparent p-3 pb-8">
              <p className="line-clamp-2 text-xs leading-snug text-white/90">{tile.prompt}</p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Pricing() {
  // The same prices as the API's table (apps/api/app/credits.py, PRICES)
  const prices = [
    { what: 'A picture', amount: 1, note: '2 at high quality' },
    { what: 'A video', amount: 10, note: 'Per 5 seconds at low quality; 20 at medium, 40 at high' },
    { what: 'Each clip attached', amount: 10, note: 'On top of the video it goes into' }
  ];
  return (
    <section className="mx-auto max-w-6xl px-4 pt-24 sm:px-6 lg:pt-32" aria-labelledby="pricing">
      <SectionTitle id="pricing" eyebrow="Credits" title="Priced up front">
        Every generation costs a fixed number of credits, shown on Generate before you press it. A failed one gives them back.
      </SectionTitle>
      <ul className="mt-8 grid gap-2.5 sm:grid-cols-3 sm:gap-3">
        {prices.map(price => (
          <li key={price.what} className="reveal rounded-[20px] bg-panel p-5">
            <p className="text-sm text-[#a0a1a3]">{price.what}</p>
            <CreditAmount value={price.amount} className="mt-2 text-4xl font-bold text-white [&_svg]:text-brand" />
            <p className="mt-2 text-sm text-[#8a8b8c]">{price.note}</p>
          </li>
        ))}
      </ul>
      <p className="reveal mt-4 text-sm text-[#a0a1a3]">
        Buying credits opens soon. For now they come with an invite code.{' '}
        <Link href="/sign-up" className="font-semibold text-white underline decoration-white/30 underline-offset-4 hover:decoration-white">
          Have a code? Make an account
        </Link>
      </p>
    </section>
  );
}

function Closing() {
  return (
    <section className="mx-auto max-w-6xl px-4 pt-24 pb-20 sm:px-6 lg:pt-32" aria-labelledby="closing">
      <div className="reveal relative isolate overflow-hidden rounded-[28px] bg-panel px-6 py-14 text-center sm:py-20">
        <div aria-hidden className="absolute inset-0 -z-10 bg-[radial-gradient(60%_80%_at_50%_120%,rgb(255_91_58/0.35),transparent)]" />
        <h2 id="closing" className={cn('text-[clamp(2.2rem,1.4rem+4vw,4.25rem)] text-balance', display)}>
          Describe it. Press Generate.
        </h2>
        <p className="mx-auto mt-4 max-w-sm text-[#a0a1a3]">Everything else is our problem.</p>
        <div className="mt-7 flex justify-center gap-2.5">
          <Link href="/sign-up" className={primary}>
            Get started
          </Link>
          <Link href="/demo" className={secondary}>
            Look around
          </Link>
        </div>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="border-t border-white/[0.06] pb-[env(safe-area-inset-bottom)]">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-3 px-4 py-8 text-sm text-[#8a8b8c] sm:px-6">
        <span className="flex items-center gap-2 text-white">
          <BrandMark className="size-6 rounded-[7px] [&_svg]:size-4" />
          unnoodle
        </span>
        <Link href="/sign-in" className="hover:text-white">
          Sign in
        </Link>
        <Link href="/sign-up" className="hover:text-white">
          Make an account
        </Link>
        <span className="ml-auto">© 2026 unnoodle</span>
      </div>
    </footer>
  );
}
